from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, expr
from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType, IntegerType,  ArrayType
from lib.logger import Log4j
import logging

if __name__ == "__main__":
    spark = SparkSession\
        .builder\
        .appName("file streaming")\
        .master("local[3]")\
        .config("spark.streaming.stopGraceFullyOnShutdown", "true")\
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.0.0")\
        .getOrCreate()
    
    logger = Log4j(spark)

    schema = StructType([
        StructField("InvoiceNumber", StringType()),
        StructField("CreatedTime", LongType()),
        StructField("StoreID", StringType()),
        StructField("PosID", StringType()),
        StructField("CashierID", StringType()),
        StructField("CustomerType", StringType()),
        StructField("CustomerCardNo", StringType()),
        StructField("TotalAmount", DoubleType()),
        StructField("NumberOfItems", IntegerType()),
        StructField("PaymentMethod", StringType()),
        StructField("CGST", DoubleType()),
        StructField("SGST", DoubleType()),
        StructField("CESS", DoubleType()),
        StructField("DeliveryType", StringType()),
        StructField("DeliveryAddress", StructType([
            StructField("AddressLine", StringType()),
            StructField("City", StringType()),
            StructField("State", StringType()),
            StructField("PinCode", StringType()),
            StructField("ContactNumber", StringType())
        ])),
        StructField("InvoiceLineItems", ArrayType(StructType([
            StructField("ItemCode", StringType()),
            StructField("ItemDescription", StringType()),
            StructField("ItemPrice", DoubleType()),
            StructField("ItemQty", IntegerType()),
            StructField("TotalValue", DoubleType())
        ]))),
    ])
    kafka_df = spark.readStream\
        .format("kafka")\
        .option("kafka.bootstrap.servers", "localhost:9092")\
        .option("subscribe", "invoices")\
        .option("startingOffsets", "earliest")\
        .load()
    
   # kafka_df.printSchema()
    value_df = kafka_df.select(from_json(col("value").cast("string"), schema).alias("value"))
    #value_df.printSchema()
    explode_df = value_df.selectExpr("value.InvoiceNumber", "value.CreatedTime", "value.StoreID",
                                     "value.PosID", "value.CustomerType", "value.CustomerCardNo", "value.DeliveryType",
                                     "value.DeliveryAddress.City",
                                     "value.DeliveryAddress.State", "value.DeliveryAddress.PinCode",
                                     "explode(value.InvoiceLineItems) as LineItem"
                                    
                )
    #flatted_Df
    flatted_df = explode_df\
        .withColumn("ItemCode", expr("LineItem.ItemCode")) \
        .withColumn("ItemDescription", expr("LineItem.ItemDescription")) \
        .withColumn("ItemPrice", expr("LineItem.ItemPrice")) \
        .withColumn("ItemQty", expr("LineItem.ItemQty")) \
        .withColumn("TotalValue", expr("LineItem.TotalValue")) \
        .drop("LineItem")
    
    #start straming process
    invoice_writer_query = flatted_df.writeStream\
        .format("json")\
        .queryName("Flatter Invoice Writwr")\
        .outputMode("append")\
        .option("path", "output")\
        .option("checkpointLocation", "chk-pint-dir")\
        .trigger(processingTime="1 minute")\
        .start()
    
    
    invoice_writer_query.awaitTermination()
    
