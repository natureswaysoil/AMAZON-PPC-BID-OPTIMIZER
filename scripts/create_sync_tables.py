# scripts/create_sync_tables.py
"""
Create all BigQuery tables needed for Amazon Ads data sync
"""
from google.cloud import bigquery
import sys

def create_tables(project_id: str, dataset: str = 'amazon_ppc'):
    """Create all sync tables"""
    client = bigquery.Client(project=project_id)
    
    tables = {
        'sp_campaigns': [
            bigquery.SchemaField("campaign_id", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("campaign_name", "STRING"),
            bigquery.SchemaField("campaign_status", "STRING"),
            bigquery.SchemaField("campaign_type", "STRING"),
            bigquery.SchemaField("daily_budget", "FLOAT"),
            bigquery.SchemaField("start_date", "DATE"),
            bigquery.SchemaField("end_date", "DATE"),
            bigquery.SchemaField("updated_at", "TIMESTAMP"),
        ],
        'sp_keywords': [
            bigquery.SchemaField("keyword_id", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("campaign_id", "INTEGER"),
            bigquery.SchemaField("ad_group_id", "INTEGER"),
            bigquery.SchemaField("keyword_text", "STRING"),
            bigquery.SchemaField("match_type", "STRING"),
            bigquery.SchemaField("bid", "FLOAT"),
            bigquery.SchemaField("state", "STRING"),
            bigquery.SchemaField("updated_at", "TIMESTAMP"),
        ],
        'sp_campaign_performance': [
            bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("campaign_id", "INTEGER"),
            bigquery.SchemaField("impressions", "INTEGER"),
            bigquery.SchemaField("clicks", "INTEGER"),
            bigquery.SchemaField("cost", "FLOAT"),
            bigquery.SchemaField("sales", "FLOAT"),
            bigquery.SchemaField("purchases", "INTEGER"),
            bigquery.SchemaField("updated_at", "TIMESTAMP"),
        ],
        'keyword_performance': [
            bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("keyword_id", "INTEGER"),
            bigquery.SchemaField("campaign_id", "INTEGER"),
            bigquery.SchemaField("ad_group_id", "INTEGER"),
            bigquery.SchemaField("impressions", "INTEGER"),
            bigquery.SchemaField("clicks", "INTEGER"),
            bigquery.SchemaField("cost", "FLOAT"),
            bigquery.SchemaField("conversion_value", "FLOAT"),
            bigquery.SchemaField("conversions", "INTEGER"),
            bigquery.SchemaField("updated_at", "TIMESTAMP"),
        ],
        'sp_advertised_product_metrics': [
            bigquery.SchemaField("campaign_id", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("aov", "FLOAT"),
            bigquery.SchemaField("orders", "INTEGER"),
            bigquery.SchemaField("revenue", "FLOAT"),
            bigquery.SchemaField("updated_at", "TIMESTAMP"),
        ],
    }
    
    for table_name, schema in tables.items():
        table_id = f"{project_id}.{dataset}.{table_name}"
        
        table = bigquery.Table(table_id, schema=schema)
        
        # Add partitioning for date-based tables
        if any(field.name == 'date' and field.mode == 'REQUIRED' for field in schema):
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="date"
            )
            
            # Add clustering
            if table_name == 'sp_campaign_performance':
                table.clustering_fields = ['campaign_id']
            elif table_name == 'keyword_performance':
                table.clustering_fields = ['keyword_id', 'campaign_id']
            elif table_name == 'sp_advertised_product_metrics':
                table.clustering_fields = ['campaign_id']
        
        table = client.create_table(table, exists_ok=True)
        print(f"✅ Created table {table_id}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python create_sync_tables.py PROJECT_ID [DATASET]")
        sys.exit(1)
    
    project = sys.argv[1]
    dataset = sys.argv[2] if len(sys.argv) > 2 else 'amazon_ppc'
    
    create_tables(project, dataset)
    print("\n✅ All tables created successfully!")
