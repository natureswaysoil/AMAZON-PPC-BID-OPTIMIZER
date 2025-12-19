# scripts/init_bigquery_tables.py
"""
Initialize BigQuery tables with proper schemas
"""
from google.cloud import bigquery
import sys

def create_tables(project_id: str):
    client = bigquery.Client(project=project_id)
    dataset_id = f"{project_id}.amazon_data"
    
    tables = {
        'campaigns': [
            bigquery.SchemaField("campaign_id", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("profile_id", "INTEGER"),
            bigquery.SchemaField("campaign_name", "STRING"),
            bigquery.SchemaField("campaign_type", "STRING"),
            bigquery.SchemaField("targeting_type", "STRING"),
            bigquery.SchemaField("state", "STRING"),
            bigquery.SchemaField("daily_budget", "FLOAT"),
            bigquery.SchemaField("start_date", "DATE"),
            bigquery.SchemaField("end_date", "DATE"),
            bigquery.SchemaField("bidding_strategy", "STRING"),
            bigquery.SchemaField("updated_at", "TIMESTAMP"),
        ],
        'keywords': [
            bigquery.SchemaField("keyword_id", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("campaign_id", "INTEGER"),
            bigquery.SchemaField("ad_group_id", "INTEGER"),
            bigquery.SchemaField("keyword_text", "STRING"),
            bigquery.SchemaField("match_type", "STRING"),
            bigquery.SchemaField("bid", "FLOAT"),
            bigquery.SchemaField("state", "STRING"),
            bigquery.SchemaField("updated_at", "TIMESTAMP"),
        ],
        'daily_performance': [
            bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("campaign_id", "INTEGER"),
            bigquery.SchemaField("ad_group_id", "INTEGER"),
            bigquery.SchemaField("keyword_id", "INTEGER"),
            bigquery.SchemaField("asin", "STRING"),
            bigquery.SchemaField("impressions", "INTEGER"),
            bigquery.SchemaField("clicks", "INTEGER"),
            bigquery.SchemaField("cost", "FLOAT"),
            bigquery.SchemaField("sales", "FLOAT"),
            bigquery.SchemaField("orders", "INTEGER"),
            bigquery.SchemaField("conversions", "INTEGER"),
            bigquery.SchemaField("acos", "FLOAT"),
            bigquery.SchemaField("roas", "FLOAT"),
            bigquery.SchemaField("updated_at", "TIMESTAMP"),
        ],
    }
    
    for table_name, schema in tables.items():
        table_id = f"{dataset_id}.{table_name}"
        
        table = bigquery.Table(table_id, schema=schema)
        
        # Add partitioning for date-based tables
        if 'date' in [field.name for field in schema]:
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="date"
            )
        
        table = client.create_table(table, exists_ok=True)
        print(f"✅ Created table {table_id}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python init_bigquery_tables.py PROJECT_ID")
        sys.exit(1)
    
    create_tables(sys.argv[1])
