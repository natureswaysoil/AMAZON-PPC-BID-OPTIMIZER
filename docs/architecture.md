  Cloud Scheduler (Triggers)               │
└──────────────┬──────────────────────────────────────────────┘
               │
    ┌──────────┴──────────┬──────────────┬─────────────────┐
    │                     │              │                 │ System Architecture Overview

```
┌─────────────────────────────────────────
┌───▼────┐         ┌──────▼─────┐  ┌────▼─────┐    ┌─────▼─────┐
│ Data   │         │ PPC Opt    │  │ Alert    │    │ Listing   │
│ Sync   │         │ Engine     │  │ Engine   │    │ Monitor   │
│ Jobs   │         │            │  │          │    │           │
└───┬────┘         └──────┬─────┘  └────┬─────┘    └─────┬─────┘
    │                     │              │                 │
    └─────────────────────┴──────────────┴─────────────────┘
                          │
                    ┌─────▼──────┐
                    │  BigQuery  │
                    │  Data      │
                    │  Warehouse │
                    └─────┬──────┘
                          │
                    ┌─────▼──────┐
                    │  Next.js   │
                    │  Dashboard │
                    └────────────┘
```

## 📁 Project Structure

```
amazon-ppc-optimizer/
├── backend/
│   ├── jobs/
│   │   ├── data_sync/
│   │   │   ├── ads_data_sync.py
│   │   │   ├── orders_sync.py
│   │   │   ├── inventory_sync.py
│   │   │   └── product_sync.py
│   │   ├── optimization/
│   │   │   ├── bid_optimizer.py
│   │   │   ├── budget_pacer.py
│   │   │   ├── keyword_harvester.py
│   │   │   └── placement_optimizer.py
│   │   ├── intelligence/
│   │   │   ├── margin_calculator.py
│   │   │   ├── aov_tracker.py
│   │   │   └── time_optimizer.py
│   │   └── alerts/
│   │       ├── alert_engine.py
│   │       └── notification_sender.py
│   ├── core/
│   │   ├── amazon_api/
│   │   │   ├── ads_api.py
│   │   │   └── sp_api.py
│   │   ├── config.py
│   │   ├── secrets.py
│   │   └── bigquery_client.py
│   ├── models/
│   │   ├── schemas.py
│   │   └── rules.py
│   └── utils/
│       ├── logger.py
│       └── helpers.py
├── frontend/
│   ├── app/
│   │   ├── dashboard/
│   │   ├── campaigns/
│   │   ├── products/
│   │   └── settings/
│   ├── components/
│   └── lib/
├── infrastructure/
│   ├── terraform/
│   │   ├── main.tf
│   │   ├── cloud_run.tf
│   │   ├── cloud_scheduler.tf
│   │   └── bigquery.tf
│   └── cloudbuild.yaml
├── sql/
│   ├── schema/
│   │   ├── ads_data.sql
│   │   ├── product_data.sql
│   │   └── optimization_logs.sql
│   └── queries/
│       ├── performance_summary.sql
│       └── margin_analysis.sql
└── requirements.txt
```

## 🔧 Phase 1: Core Foundation (Week 1-2)

### 1.1 Secret Management & Config

```python
# backend/core/secrets.py
from google.cloud import secretmanager
from functools import lru_cache
import json

class SecretManager:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.client = secretmanager.SecretManagerServiceClient()
    
    @lru_cache(maxsize=128)
    def get_secret(self, secret_id: str, version: str = "latest") -> str:
        """Retrieve secret from Google Secret Manager"""
        name = f"projects/{self.project_id}/secrets/{secret_id}/versions/{version}"
        response = self.client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    
    def get_amazon_ads_credentials(self, account_name: str = "default"):
        """Get Amazon Ads API credentials"""
        secret_data = self.get_secret(f"amazon-ads-{account_name}")
        return json.loads(secret_data)
    
    def get_amazon_sp_credentials(self, account_name: str = "default"):
        """Get Amazon SP-API credentials"""
        secret_data = self.get_secret(f"amazon-sp-{account_name}")
        return json.loads(secret_data)

# backend/core/config.py
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_ID: str = os.getenv("GOOGLE_CLOUD_PROJECT")
    BIGQUERY_DATASET: str = "amazon_data"
    REGION: str = "us-central1"
    
    # Optimization Defaults
    MIN_BID: float = 0.30
    MAX_BID: float = 5.00
    TARGET_ACOS_DEFAULT: float = 0.25
    
    # Time-based multipliers
    PEAK_HOURS: list = [8, 9, 10, 11, 17, 18, 19, 20]
    PEAK_BID_MULTIPLIER: float = 1.3
    OFF_HOURS_MULTIPLIER: float = 0.5
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 1.2 Amazon API Clients

```python
# backend/core/amazon_api/ads_api.py
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time

class AmazonAdsAPI:
    def __init__(self, credentials: Dict):
        self.client_id = credentials['client_id']
        self.client_secret = credentials['client_secret']
        self.refresh_token = credentials['refresh_token']
        self.profile_id = credentials['profile_id']
        self.region = credentials.get('region', 'NA')
        
        self.base_url = "https://advertising-api.amazon.com"
        self.access_token = None
        self.token_expiry = None
    
    def _get_access_token(self) -> str:
        """Get or refresh access token"""
        if self.access_token and self.token_expiry > datetime.now():
            return self.access_token
        
        url = "https://api.amazon.com/auth/o2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        response = requests.post(url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data['access_token']
        self.token_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'] - 300)
        
        return self.access_token
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make authenticated request to Ads API"""
        headers = {
            "Amazon-Advertising-API-ClientId": self.client_id,
            "Authorization": f"Bearer {self._get_access_token()}",
            "Amazon-Advertising-API-Scope": str(self.profile_id),
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{endpoint}"
        response = requests.request(method, url, headers=headers, **kwargs)
        
        # Handle rate limiting
        if response.status_code == 429:
            time.sleep(1)
            return self._make_request(method, endpoint, **kwargs)
        
        response.raise_for_status()
        return response.json() if response.content else {}
    
    def get_campaigns(self, state_filter: Optional[str] = None) -> List[Dict]:
        """Get all campaigns"""
        params = {}
        if state_filter:
            params['stateFilter'] = state_filter
        
        return self._make_request('GET', '/v2/sp/campaigns', params=params)
    
    def get_keywords(self, campaign_id: Optional[int] = None) -> List[Dict]:
        """Get keywords, optionally filtered by campaign"""
        endpoint = '/v2/sp/keywords'
        if campaign_id:
            endpoint += f'?campaignIdFilter={campaign_id}'
        
        return self._make_request('GET', endpoint)
    
    def update_keyword_bid(self, keyword_id: int, new_bid: float) -> Dict:
        """Update keyword bid"""
        data = [{
            "keywordId": keyword_id,
            "bid": round(new_bid, 2)
        }]
        
        return self._make_request('PUT', '/v2/sp/keywords', json=data)
    
    def get_campaign_performance(self, start_date: str, end_date: str, 
                                  metrics: List[str] = None) -> Dict:
        """Get campaign performance report"""
        if metrics is None:
            metrics = [
                'campaignId', 'campaignName', 'impressions', 'clicks', 
                'cost', 'sales', 'orders', 'attributedConversions14d'
            ]
        
        report_data = {
            "reportDate": start_date,
            "metrics": ",".join(metrics),
            "segment": "query"
        }
        
        # Request report
        response = self._make_request('POST', '/v2/sp/campaigns/report', json=report_data)
        report_id = response['reportId']
        
        # Poll for report completion
        return self._download_report(report_id)
    
    def get_search_term_report(self, start_date: str, end_date: str) -> List[Dict]:
        """Get search term report"""
        report_data = {
            "reportDate": start_date,
            "metrics": "campaignName,adGroupName,keywordText,query,impressions,clicks,cost,sales"
        }
        
        response = self._make_request('POST', '/v2/sp/keywords/report', json=report_data)
        return self._download_report(response['reportId'])
    
    def _download_report(self, report_id: str, max_retries: int = 30) -> Dict:
        """Download completed report"""
        for _ in range(max_retries):
            status_response = self._make_request('GET', f'/v2/reports/{report_id}')
            
            if status_response['status'] == 'SUCCESS':
                report_url = status_response['location']
                report_data = requests.get(report_url)
                return report_data.json()
            elif status_response['status'] == 'FAILURE':
                raise Exception(f"Report generation failed: {status_response}")
            
            time.sleep(10)
        
        raise TimeoutError("Report generation timed out")

# backend/core/amazon_api/sp_api.py
from sp_api.base import Marketplaces
from sp_api.api import Orders, Products, Reports, CatalogItems
from typing import Dict, List

class AmazonSPAPI:
    def __init__(self, credentials: Dict):
        self.credentials = {
            'refresh_token': credentials['refresh_token'],
            'lwa_app_id': credentials['lwa_app_id'],
            'lwa_client_secret': credentials['lwa_client_secret'],
            'aws_access_key': credentials['aws_access_key'],
            'aws_secret_key': credentials['aws_secret_key'],
            'role_arn': credentials['role_arn']
        }
        self.marketplace = Marketplaces.US
    
    def get_orders(self, created_after: str, created_before: str = None) -> List[Dict]:
        """Get orders within date range"""
        orders_api = Orders(credentials=self.credentials, marketplace=self.marketplace)
        
        params = {'CreatedAfter': created_after}
        if created_before:
            params['CreatedBefore'] = created_before
        
        response = orders_api.get_orders(**params)
        return response.payload.get('Orders', [])
    
    def get_order_items(self, order_id: str) -> List[Dict]:
        """Get items for a specific order"""
        orders_api = Orders(credentials=self.credentials, marketplace=self.marketplace)
        response = orders_api.get_order_items(order_id)
        return response.payload.get('OrderItems', [])
    
    def get_product_pricing(self, asin: str) -> Dict:
        """Get pricing for ASIN"""
        products_api = Products(credentials=self.credentials, marketplace=self.marketplace)
        response = products_api.get_competitive_pricing_for_asin(asin)
        return response.payload
    
    def get_catalog_item(self, asin: str) -> Dict:
        """Get catalog item details"""
        catalog_api = CatalogItems(credentials=self.credentials, marketplace=self.marketplace)
        response = catalog_api.get_catalog_item(asin)
        return response.payload
```

### 1.3 BigQuery Schema

```sql
-- sql/schema/ads_data.sql

-- Campaigns table
CREATE TABLE IF NOT EXISTS `amazon_data.campaigns` (
  campaign_id INT64,
  profile_id INT64,
  campaign_name STRING,
  campaign_type STRING,
  targeting_type STRING,
  state STRING,
  daily_budget FLOAT64,
  start_date DATE,
  end_date DATE,
  bidding_strategy STRING,
  updated_at TIMESTAMP,
  PRIMARY KEY (campaign_id) NOT ENFORCED
);

-- Keywords table
CREATE TABLE IF NOT EXISTS `amazon_data.keywords` (
  keyword_id INT64,
  campaign_id INT64,
  ad_group_id INT64,
  keyword_text STRING,
  match_type STRING,
  bid FLOAT64,
  state STRING,
  updated_at TIMESTAMP,
  PRIMARY KEY (keyword_id) NOT ENFORCED
);

-- Daily performance table (partitioned by date)
CREATE TABLE IF NOT EXISTS `amazon_data.daily_performance` (
  date DATE,
  campaign_id INT64,
  ad_group_id INT64,
  keyword_id INT64,
  impressions INT64,
  clicks INT64,
  cost FLOAT64,
  sales FLOAT64,
  orders INT64,
  conversions INT64,
  acos FLOAT64,
  roas FLOAT64,
  updated_at TIMESTAMP
)
PARTITION BY date
CLUSTER BY campaign_id, keyword_id;

-- Hourly performance (for time-based optimization)
CREATE TABLE IF NOT EXISTS `amazon_data.hourly_performance` (
  timestamp TIMESTAMP,
  campaign_id INT64,
  keyword_id INT64,
  hour INT64,
  day_of_week INT64,
  impressions INT64,
  clicks INT64,
  cost FLOAT64,
  sales FLOAT64,
  orders INT64,
  updated_at TIMESTAMP
)
PARTITION BY DATE(timestamp)
CLUSTER BY campaign_id, hour;

-- Search terms table
CREATE TABLE IF NOT EXISTS `amazon_data.search_terms` (
  date DATE,
  campaign_id INT64,
  ad_group_id INT64,
  keyword_id INT64,
  search_term STRING,
  impressions INT64,
  clicks INT64,
  cost FLOAT64,
  sales FLOAT64,
  orders INT64,
  updated_at TIMESTAMP
)
PARTITION BY date;

-- sql/schema/product_data.sql

-- Products/ASINs table
CREATE TABLE IF NOT EXISTS `amazon_data.products` (
  asin STRING,
  sku STRING,
  title STRING,
  brand STRING,
  category STRING,
  price FLOAT64,
  cost_of_goods FLOAT64,
  weight_lb FLOAT64,
  updated_at TIMESTAMP,
  PRIMARY KEY (asin) NOT ENFORCED
);

-- Orders table
CREATE TABLE IF NOT EXISTS `amazon_data.orders` (
  order_id STRING,
  purchase_date TIMESTAMP,
  asin STRING,
  sku STRING,
  quantity INT64,
  item_price FLOAT64,
  item_tax FLOAT64,
  shipping_price FLOAT64,
  gift_wrap_price FLOAT64,
  order_status STRING,
  fulfillment_channel STRING,
  updated_at TIMESTAMP,
  PRIMARY KEY (order_id, asin) NOT ENFORCED
)
PARTITION BY DATE(purchase_date);

-- AOV tracking table
CREATE TABLE IF NOT EXISTS `amazon_data.asin_aov` (
  asin STRING,
  date DATE,
  orders INT64,
  revenue FLOAT64,
  aov FLOAT64,
  aov_7d FLOAT64,
  aov_30d FLOAT64,
  updated_at TIMESTAMP,
  PRIMARY KEY (asin, date) NOT ENFORCED
)
PARTITION BY date;

-- Margin calculation table
CREATE TABLE IF NOT EXISTS `amazon_data.asin_margins` (
  asin STRING,
  date DATE,
  revenue FLOAT64,
  cogs FLOAT64,
  amazon_fees FLOAT64,
  shipping_cost FLOAT64,
  ad_spend FLOAT64,
  contribution_margin FLOAT64,
  margin_pct FLOAT64,
  breakeven_acos FLOAT64,
  updated_at TIMESTAMP,
  PRIMARY KEY (asin, date) NOT ENFORCED
)
PARTITION BY date;

-- Inventory table
CREATE TABLE IF NOT EXISTS `amazon_data.inventory` (
  asin STRING,
  sku STRING,
  fulfillment_center STRING,
  available_quantity INT64,
  inbound_quantity INT64,
  reserved_quantity INT64,
  unfulfillable_quantity INT64,
  days_of_cover FLOAT64,
  snapshot_date DATE,
  updated_at TIMESTAMP
)
PARTITION BY snapshot_date;

-- sql/schema/optimization_logs.sql

-- Bid changes log
CREATE TABLE IF NOT EXISTS `amazon_data.bid_changes` (
  change_id STRING,
  timestamp TIMESTAMP,
  keyword_id INT64,
  old_bid FLOAT64,
  new_bid FLOAT64,
  reason STRING,
  rule_triggered STRING,
  performance_metrics JSON,
  PRIMARY KEY (change_id) NOT ENFORCED
)
PARTITION BY DATE(timestamp);

-- Alerts log
CREATE TABLE IF NOT EXISTS `amazon_data.alerts` (
  alert_id STRING,
  timestamp TIMESTAMP,
  alert_type STRING,
  severity STRING,
  entity_type STRING,
  entity_id STRING,
  message STRING,
  data JSON,
  status STRING,
  PRIMARY KEY (alert_id) NOT ENFORCED
)
PARTITION BY DATE(timestamp);
```

## 🚀 Phase 2: Data Sync Jobs (Week 2-3)

```python
# backend/jobs/data_sync/ads_data_sync.py
from google.cloud import bigquery
from backend.core.amazon_api.ads_api import AmazonAdsAPI
from backend.core.secrets import SecretManager
from backend.core.config import settings
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class AdsDataSync:
    def __init__(self):
        self.secret_manager = SecretManager(settings.PROJECT_ID)
        self.bq_client = bigquery.Client(project=settings.PROJECT_ID)
        
        # Initialize Amazon Ads API
        ads_creds = self.secret_manager.get_amazon_ads_credentials()
        self.ads_api = AmazonAdsAPI(ads_creds)
    
    def sync_campaigns(self):
        """Sync campaign data to BigQuery"""
        logger.info("Starting campaign sync")
        
        campaigns = self.ads_api.get_campaigns()
        
        if not campaigns:
            logger.warning("No campaigns found")
            return
        
        # Transform data
        rows = []
        for camp in campaigns:
            rows.append({
                'campaign_id': camp['campaignId'],
                'profile_id': camp['profileId'],
                'campaign_name': camp['name'],
                'campaign_type': camp.get('campaignType'),
                'targeting_type': camp.get('targetingType'),
                'state': camp['state'],
                'daily_budget': camp.get('dailyBudget'),
                'start_date': camp.get('startDate'),
                'end_date': camp.get('endDate'),
                'bidding_strategy': camp.get('biddingStrategy'),
                'updated_at': datetime.utcnow().isoformat()
            })
        
        # Load to BigQuery
        table_id = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.campaigns"
        
        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_TRUNCATE",
            schema=[
                bigquery.SchemaField("campaign_id", "INTEGER"),
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
            ]
        )
        
        job = self.bq_client.load_table_from_json(rows, table_id, job_config=job_config)
        job.result()
        
        logger.info(f"Synced {len(rows)} campaigns")
    
    def sync_keywords(self):
        """Sync keyword data to BigQuery"""
        logger.info("Starting keyword sync")
        
        keywords = self.ads_api.get_keywords()
        
        rows = []
        for kw in keywords:
            rows.append({
                'keyword_id': kw['keywordId'],
                'campaign_id': kw['campaignId'],
                'ad_group_id': kw['adGroupId'],
                'keyword_text': kw['keywordText'],
                'match_type': kw['matchType'],
                'bid': kw.get('bid'),
                'state': kw['state'],
                'updated_at': datetime.utcnow().isoformat()
            })
        
        table_id = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.keywords"
        
        job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
        job = self.bq_client.load_table_from_json(rows, table_id, job_config=job_config)
        job.result()
        
        logger.info(f"Synced {len(rows)} keywords")
    
    def sync_performance(self, days_back: int = 7):
        """Sync performance data"""
        logger.info(f"Starting performance sync for last {days_back} days")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        performance_data = self.ads_api.get_campaign_performance(
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        # Transform and load to BigQuery
        rows = []
        for record in performance_data:
            rows.append({
                'date': record.get('date'),
                'campaign_id': record.get('campaignId'),
                'ad_group_id': record.get('adGroupId'),
                'keyword_id': record.get('keywordId'),
                'impressions': record.get('impressions', 0),
                'clicks': record.get('clicks', 0),
                'cost': record.get('cost', 0.0),
                'sales': record.get('sales', 0.0),
                'orders': record.get('orders', 0),
                'conversions': record.get('attributedConversions14d', 0),
                'acos': record.get('cost', 0) / record.get('sales', 1) if record.get('sales', 0) > 0 else 0,
                'roas': record.get('sales', 0) / record.get('cost', 1) if record.get('cost', 0) > 0 else 0,
                'updated_at': datetime.utcnow().isoformat()
            })
        
        table_id = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.daily_performance"
        
        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND",
            schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
        )
        
        job = self.bq_client.load_table_from_json(rows, table_id, job_config=job_config)
        job.result()
        
        logger.info(f"Synced {len(rows)} performance records")
    
    def sync_search_terms(self, days_back: int = 30):
        """Sync search term report for keyword harvesting"""
        logger.info("Starting search term sync")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        search_terms = self.ads_api.get_search_term_report(
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        rows = []
        for st in search_terms:
            rows.append({
                'date': st.get('date'),
                'campaign_id': st.get('campaignId'),
                'ad_group_id': st.get('adGroupId'),
                'keyword_id': st.get('keywordId'),
                'search_term': st.get('query'),
                'impressions': st.get('impressions', 0),
                'clicks': st.get('clicks', 0),
                'cost': st.get('cost', 0.0),
                'sales': st.get('sales', 0.0),
                'orders': st.get('orders', 0),
                'updated_at': datetime.utcnow().isoformat()
            })
        
        table_id = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.search_terms"
        
        job_config = bigquery.LoadJobConfig(write_disposition="WRITE_APPEND")
        job = self.bq_client.load_table_from_json(rows, table_id, job_config=job_config)
        job.result()
        
        logger.info(f"Synced {len(rows)} search term records")

def run_ads_sync():
    """Cloud Run job entry point"""
    sync = AdsDataSync()
    
    sync.sync_campaigns()
    sync.sync_keywords()
    sync.sync_performance(days_back=7)
    sync.sync_search_terms(days_back=30)
    
    logger.info("Ads data sync completed")

if __name__ == "__main__":
    run_ads_sync()
```

```python
# backend/jobs/data_sync/orders_sync.py
from backend.core.amazon_api.sp_api import AmazonSPAPI
from backend.core.secrets import SecretManager
from backend.core.config import settings
from google.cloud import bigquery
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class OrdersSync:
    def __init__(self):
        self.secret_manager = SecretManager(settings.PROJECT_ID)
        self.bq_client = bigquery.Client(project=settings.PROJECT_ID)
        
        sp_creds = self.secret_manager.get_amazon_sp_credentials()
        self.sp_api = AmazonSPAPI(sp_creds)
    
    def sync_orders(self, days_back: int = 7):
        """Sync order data for AOV calculation"""
        logger.info(f"Syncing orders from last {days_back} days")
        
        start_date = (datetime.now() - timedelta(days=days_back)).isoformat()
        orders = self.sp_api.get_orders(created_after=start_date)
        
        rows = []
        for order in orders:
            order_id = order['AmazonOrderId']
            
            # Get order items
            items = self.sp_api.get_order_items(order_id)
            
            for item in items:
                rows.append({
                    'order_id': order_id,
                    'purchase_date': order['PurchaseDate'],
                    'asin': item['ASIN'],
                    'sku': item.get('SellerSKU'),
                    'quantity': item['QuantityOrdered'],
                    'item_price': float(item['ItemPrice']['Amount']),
                    'item_tax': float(item.get('ItemTax', {}).get('Amount', 0)),
                    'shipping_price': float(item.get('ShippingPrice', {}).get('Amount', 0)),
                    'gift_wrap_price': float(item.get('GiftWrapPrice', {}).get('Amount', 0)),
                    'order_status': order['OrderStatus'],
                    'fulfillment_channel': order.get('FulfillmentChannel'),
                    'updated_at': datetime.utcnow().isoformat()
                })
        
        if rows:
            table_id = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.orders"
            
            job_config = bigquery.LoadJobConfig(
                write_disposition="WRITE_APPEND",
                schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
            )
            
            job = self.bq_client.load_table_from_json(rows, table_id, job_config=job_config)
            job.result()
            
            logger.info(f"Synced {len(rows)} order items")
    
    def calculate_aov(self):
        """Calculate AOV metrics per ASIN"""
        logger.info("Calculating AOV metrics")
        
        query = """
        INSERT INTO `{project}.{dataset}.asin_aov` 
        (asin, date, orders, revenue, aov, aov_7d, aov_30d, updated_at)
        
        WITH daily_stats AS (
          SELECT 
            asin,
            DATE(purchase_date) as date,
            COUNT(DISTINCT order_id) as orders,
            SUM(item_price) as revenue
          FROM `{project}.{dataset}.orders`
          WHERE order_status NOT IN ('Cancelled', 'Pending')
          GROUP BY asin, date
        ),
        rolling_stats AS (
          SELECT 
            asin,
            date,
            orders,
            revenue,
            revenue / NULLIF(orders, 0) as aov,
            AVG(revenue / NULLIF(orders, 0)) OVER (
              PARTITION BY asin 
              ORDER BY date 
              ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ) as aov_7d,
            AVG(revenue / NULLIF(orders, 0)) OVER (
              PARTITION BY asin 
              ORDER BY date 
              ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
            ) as aov_30d
          FROM daily_stats
        )
        SELECT 
          asin,
          date,
          orders,
          revenue,
          aov,
          aov_7d,
          aov_30d,
          CURRENT_TIMESTAMP() as updated_at
        FROM rolling_stats
        WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
        """.format(project=settings.PROJECT_ID, dataset=settings.BIGQUERY_DATASET)
        
        job = self.bq_client.query(query)
        job.result()
        
        logger.info("AOV calculation completed")

def run_orders_sync():
    sync = OrdersSync()
    sync.sync_orders(days_back=7)
    sync.calculate_aov()
    logger.info("Orders sync completed")

if __name__ == "__main__":
    run_orders_sync()
```

## ⚙️ Phase 3: Optimization Engine (Week 3-5)

```python
# backend/jobs/optimization/bid_optimizer.py
from google.cloud import bigquery
from backend.core.amazon_api.ads_api import AmazonAdsAPI
from backend.core.secrets import SecretManager
from backend.core.config import settings
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class BidOptimizer:
    def __init__(self):
        self.secret_manager = SecretManager(settings.PROJECT_ID)
        self.bq_client = bigquery.Client(project=settings.PROJECT_ID)
        
        ads_creds = self.secret_manager.get_amazon_ads_credentials()
        self.ads_api = AmazonAdsAPI(ads_creds)
    
    def get_keywords_to_optimize(self) -> List[Dict]:
        """Get keywords that need bid optimization"""
        query = """
        WITH keyword_performance AS (
          SELECT 
            k.keyword_id,
            k.campaign_id,
            k.keyword_text,
            k.bid as current_bid,
            k.match_type,
            p.asin,
            
            -- 7-day performance
            SUM(p.clicks) as clicks_7d,
            SUM(p.cost) as cost_7d,
            SUM(p.sales) as sales_7d,
            SUM(p.orders) as orders_7d,
            
            -- Conversion rate
            SAFE_DIVIDE(SUM(p.orders), SUM(p.clicks)) as cvr,
            
            -- Current ACOS
            SAFE_DIVIDE(SUM(p.cost), SUM(p.sales)) as current_acos,
            
            -- AOV
            m.aov_7d,
            m.breakeven_acos,
            
            -- Time-based performance
            AVG(CASE WHEN EXTRACT(HOUR FROM p.timestamp) IN UNNEST(@peak_hours) 
                THEN p.clicks ELSE 0 END) as peak_clicks,
            AVG(CASE WHEN EXTRACT(HOUR FROM p.timestamp) NOT IN UNNEST(@peak_hours) 
                THEN p.clicks ELSE 0 END) as offpeak_clicks
            
          FROM `{project}.{dataset}.keywords` k
          JOIN `{project}.{dataset}.daily_performance` p 
            ON k.keyword_id = p.keyword_id
          LEFT JOIN `{project}.{dataset}.asin_margins` m 
            ON p.asin = m.asin
          WHERE 
            k.state = 'ENABLED'
            AND p.date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
          GROUP BY 
            k.keyword_id, k.campaign_id, k.keyword_text, 
            k.bid, k.match_type, p.asin, m.aov_7d, m.breakeven_acos
        )
        SELECT *
        FROM keyword_performance
        WHERE clicks_7d >= 10  -- Minimum data requirement
        """.format(project=settings.PROJECT_ID, dataset=settings.BIGQUERY_DATASET)
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("peak_hours", "INT64", settings.PEAK_HOURS)
            ]
        )
        
        results = self.bq_client.query(query, job_config=job_config).result()
        return [dict(row) for row in results]
    
    def calculate_optimal_bid(self, keyword: Dict) -> float:
        """Calculate optimal bid based on performance and margins"""
        current_bid = keyword['current_bid']
        current_acos = keyword['current_acos']
        breakeven_acos = keyword['breakeven_acos']
        cvr = keyword['cvr']
        aov = keyword['aov_7d']
        
        if not all([current_acos, breakeven_acos, cvr, aov]):
            return current_bid
        
        # Target ACOS (80% of breakeven for safety margin)
        target_acos = breakeven_acos * 0.8
        
        # Calculate max CPC
        # Max CPC = AOV × Target ACOS × CVR
        max_cpc = aov * target_acos * cvr
        
        # Determine bid adjustment based on current ACOS
        if current_acos < target_acos * 0.7:
            # Performing well below target - increase bid
            new_bid = min(current_bid * 1.15, max_cpc)
        elif current_acos < target_acos:
            # Performing well - slight increase
            new_bid = min(current_bid * 1.05, max_cpc)
        elif current_acos < breakeven_acos:
            # Profitable but close to target - maintain
            new_bid = current_bid
        else:
            # Above breakeven - decrease
            decrease_factor = min(0.85, target_acos / current_acos)
            new_bid = current_bid * decrease_factor
        
        # Apply bounds
        new_bid = max(settings.MIN_BID, min(settings.MAX_BID, new_bid))
        
        # Only change if difference is significant (>5%)
        if abs(new_bid - current_bid) / current_bid < 0.05:
            return current_bid
        
        return round(new_bid, 2)
    
    def apply_time_based_multiplier(self, base_bid: float, hour: int) -> float:
        """Apply time-of-day multiplier to bid"""
        if hour in settings.PEAK_HOURS:
            return round(base_bid * settings.PEAK_BID_MULTIPLIER, 2)
        else:
            return round(base_bid * settings.OFF_HOURS_MULTIPLIER, 2)
    
    def optimize_bids(self, dry_run: bool = False):
        """Main optimization loop"""
        logger.info("Starting bid optimization")
        
        keywords = self.get_keywords_to_optimize()
        logger.info(f"Found {len(keywords)} keywords to optimize")
        
        bid_changes = []
        
        for kw in keywords:
            optimal_bid = self.calculate_optimal_bid(kw)
            
            if optimal_bid != kw['current_bid']:
                change = {
                    'change_id': f"{kw['keyword_id']}_{int(datetime.now().timestamp())}",
                    'timestamp': datetime.utcnow().isoformat(),
                    'keyword_id': kw['keyword_id'],
                    'keyword_text': kw['keyword_text'],
                    'old_bid': kw['current_bid'],
                    'new_bid': optimal_bid,
                    'reason': self._get_change_reason(kw, optimal_bid),
                    'rule_triggered': 'margin_based_optimization',
                    'performance_metrics': {
                        'current_acos': kw['current_acos'],
                        'breakeven_acos': kw['breakeven_acos'],
                        'cvr': kw['cvr'],
                        'clicks_7d': kw['clicks_7d']
                    }
                }
                
                bid_changes.append(change)
                
                if not dry_run:
                    try:
                        self.ads_api.update_keyword_bid(kw['keyword_id'], optimal_bid)
                        logger.info(f"Updated bid for {kw['keyword_text']}: ${kw['current_bid']} → ${optimal_bid}")
                    except Exception as e:
                        logger.error(f"Failed to update bid for {kw['keyword_id']}: {e}")
        
        # Log changes to BigQuery
        if bid_changes:
            self._log_bid_changes(bid_changes)
        
        logger.info(f"Optimization complete. Changed {len(bid_changes)} bids")
        return bid_changes
    
    def _get_change_reason(self, kw: Dict, new_bid: float) -> str:
        """Generate human-readable reason for bid change"""
        if new_bid > kw['current_bid']:
            if kw['current_acos'] < kw['breakeven_acos'] * 0.7:
                return f"High profitability (ACOS {kw['current_acos']:.1%} vs target {kw['breakeven_acos']*0.8:.1%})"
            else:
                return "Performance trending positive"
        else:
            if kw['current_acos'] > kw['breakeven_acos']:
                return f"Above breakeven ACOS ({kw['current_acos']:.1%} vs {kw['breakeven_acos']:.1%})"
            else:
                return "Optimizing toward target ACOS"
    
    def _log_bid_changes(self, changes: List[Dict]):
        """Log bid changes to BigQuery"""
        table_id = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.bid_changes"
        
        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND",
            schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
        )
        
        job = self.bq_client.load_table_from_json(changes, table_id, job_config=job_config)
        job.result()

def run_bid_optimization():
    optimizer = BidOptimizer()
    optimizer.optimize_bids(dry_run=False)

if __name__ == "__main__":
    run_bid_optimization()
```

I'll continue with more components. Would you like me to proceed with:
1. Keyword harvester
2. Alert engine  
3. Frontend dashboard
4. Deployment configuration

Or would you prefer I focus on a specific component first?
