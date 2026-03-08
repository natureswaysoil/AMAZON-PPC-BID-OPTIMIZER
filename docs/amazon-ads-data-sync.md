# Amazon Ads Data Sync Job - Usage Guide

## Overview

The Amazon Ads Data Sync job synchronizes advertising performance data from Amazon Ads API v3 to BigQuery tables for analysis and bid optimization.

## Features

✅ **API v3 Compliance**: Uses the latest `/reporting/reports` endpoint  
✅ **Async Report Polling**: Waits for reports to generate (up to 5 minutes)  
✅ **GZIP Decompression**: Handles compressed JSON line format  
✅ **Region-Aware**: Configurable endpoints for NA/EU/FE regions  
✅ **Comprehensive Data**: Syncs keywords, campaigns, and product metrics  

## Data Synced

### 1. Keywords Performance (30-day summary)
- **Table**: `sp_keywords`
- **Data**: Keyword-level performance with 30-day attribution windows
- **Columns**: keyword_id, keyword_text, keyword_bid, match_type, impressions, clicks, cost, purchases, sales, etc.
- **Use Case**: Identify high-performing keywords for bid optimization

### 2. Campaign Performance (14-day daily)
- **Table**: `sp_campaign_performance`  
- **Data**: Daily campaign metrics for trend analysis
- **Columns**: campaign_id, campaign_name, date, impressions, clicks, cost, purchases, sales, acos, roas
- **Use Case**: Monitor campaign performance trends over time

### 3. Advertised Product Metrics (30-day summary)
- **Table**: `sp_advertised_product_metrics`
- **Data**: ASIN-level data for AOV calculation
- **Columns**: campaign_id, asin, sku, impressions, clicks, cost, purchases, sales, units_sold
- **Use Case**: Calculate Average Order Value (AOV) for bid ceiling optimization

## Configuration

### Environment Variables

```bash
# Required
PROJECT_ID=your-gcp-project-id
BIGQUERY_DATASET=amazon_ppc

# Optional - Region configuration
AMAZON_ADS_REGION=NA  # Options: NA (default), EU, FE

# Secret Manager secret names (defaults shown)
AMAZON_CLIENT_ID_SECRET=amazon_client_id
AMAZON_CLIENT_SECRET_SECRET=amazon_client_secret
AMAZON_REFRESH_TOKEN_SECRET=amazon_refresh_token
AMAZON_PROFILE_ID_SECRET=amazon_profile_id
```

### Region Endpoints

| Region | Endpoint | Use For |
|--------|----------|---------|
| NA | `https://advertising-api.amazon.com` | North America (US, CA, MX) |
| EU | `https://advertising-api-eu.amazon.com` | Europe (UK, DE, FR, IT, ES) |
| FE | `https://advertising-api-fe.amazon.com` | Far East (JP, AU, IN) |

## Setup

### 1. Create BigQuery Tables

```bash
# Replace placeholders with your values
sed 's/{project_id}/your-project-id/g; s/{dataset}/amazon_ppc/g' \
  scripts/create_sync_tables.sql | \
  bq query --use_legacy_sql=false
```

This creates:
- `sp_keywords` - Partitioned by sync_date, clustered by campaign_id, keyword_id
- `sp_campaign_performance` - Partitioned by date, clustered by campaign_id
- `sp_advertised_product_metrics` - Partitioned by sync_date, clustered by campaign_id, asin

### 2. Deploy Cloud Run Job

```bash
# Build and push Docker image
docker build -t gcr.io/YOUR_PROJECT/amazon-ppc-backend:latest \
  -f backend/Dockerfile ./backend
docker push gcr.io/YOUR_PROJECT/amazon-ppc-backend:latest

# Deploy Cloud Run Job
gcloud run jobs deploy amazon-ads-sync \
  --image=gcr.io/YOUR_PROJECT/amazon-ppc-backend:latest \
  --region=us-central1 \
  --set-env-vars=JOB_TYPE=ads_sync \
  --set-env-vars=AMAZON_ADS_REGION=NA \
  --memory=2Gi \
  --cpu=2 \
  --max-retries=2 \
  --task-timeout=30m
```

### 3. Run the Job

```bash
# Execute manually
gcloud run jobs execute amazon-ads-sync \
  --region=us-central1 \
  --project=YOUR_PROJECT

# Schedule with Cloud Scheduler (daily at 6 AM)
gcloud scheduler jobs create http amazon-ads-sync-daily \
  --location=us-central1 \
  --schedule="0 6 * * *" \
  --time-zone="America/New_York" \
  --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/YOUR_PROJECT/jobs/amazon-ads-sync:run" \
  --http-method=POST \
  --oauth-service-account-email=YOUR_SERVICE_ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com
```

## Monitoring

### Check Logs

```bash
# View recent logs
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=amazon-ads-sync" \
  --limit=100 \
  --format=json \
  --project=YOUR_PROJECT

# Filter for errors
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=amazon-ads-sync AND severity>=ERROR" \
  --limit=50 \
  --format=json
```

### Expected Log Output

```
=============================================================
🔄 Starting Amazon Ads Data Sync (API v3)
Project: your-project-id
Dataset: amazon_ppc
Region: NA
Endpoint: https://advertising-api.amazon.com
=============================================================

📊 Step 1: Syncing keywords performance...
Requesting keywords report: 2026-01-01 to 2026-01-08
✅ Report requested: amzn1.advertisingreports.v1.m1.XXXX
⏳ Report status: IN_PROGRESS, waiting...
✅ Report ready, downloading...
✅ Downloaded 1,247 rows
Loading 1,247 rows to sp_keywords...
✅ Loaded 1,247 rows to sp_keywords
✅ Synced 1,247 keyword records

📊 Step 2: Syncing campaign performance...
...
✅ Synced 196 campaign records

📊 Step 3: Syncing advertised product metrics...
...
✅ Synced 523 product records

=============================================================
✅ Amazon Ads Data Sync Complete
=============================================================
```

## Troubleshooting

### Error: 403 Forbidden

**Cause**: Using wrong API endpoint or expired credentials

**Solution**:
1. Verify AMAZON_ADS_REGION matches your account region
2. Check that secrets are up-to-date in Secret Manager
3. Ensure refresh token is valid (not expired)

### Error: 400 Bad Request

**Cause**: Invalid report configuration format

**Solution**:
1. Check logs for the exact error message
2. Verify date ranges are valid (not in future)
3. Ensure columns match the reportTypeId specification

**Common issues**:
- Missing required columns for reportTypeId
- Wrong adProduct for your account type (e.g., trying SPONSORED_BRANDS without permission)
- Invalid timeUnit for the selected reportTypeId

### Error: Report Timeout

**Cause**: Report took longer than 5 minutes to generate

**Solution**:
1. Reduce date range (fewer days)
2. Increase max_wait parameter in code
3. Check Amazon Ads API status

### Error: No Data Returned

**Cause**: No ad activity in the date range

**Solution**:
- This is normal if campaigns are new or paused
- Check that campaigns are actively running
- Verify date range matches when ads were active

## Query Examples

### Top Keywords by Performance

```sql
SELECT 
  keyword_text,
  match_type,
  campaign_name,
  impressions,
  clicks,
  ROUND(cost, 2) as cost,
  purchases,
  ROUND(sales, 2) as sales,
  ROUND(acos, 3) as acos,
  ROUND(ctr, 3) as ctr,
  ROUND(cvr, 3) as cvr
FROM `your-project.amazon_ppc.sp_keywords`
WHERE sync_date = CURRENT_DATE()
  AND clicks > 10
ORDER BY sales DESC
LIMIT 20;
```

### Campaign Trend Analysis

```sql
SELECT 
  date,
  campaign_name,
  impressions,
  clicks,
  ROUND(cost, 2) as cost,
  purchases,
  ROUND(sales, 2) as sales,
  ROUND(acos, 3) as acos
FROM `your-project.amazon_ppc.sp_campaign_performance`
WHERE campaign_id = 123456789
  AND date >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)
ORDER BY date DESC;
```

### Product AOV Calculation

```sql
SELECT 
  asin,
  sku,
  SUM(purchases) as total_purchases,
  SUM(sales) as total_sales,
  SUM(units_sold) as total_units,
  ROUND(SAFE_DIVIDE(SUM(sales), SUM(purchases)), 2) as aov
FROM `your-project.amazon_ppc.sp_advertised_product_metrics`
WHERE sync_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
  AND purchases > 0
GROUP BY asin, sku
HAVING total_purchases >= 5
ORDER BY aov DESC;
```

## API v3 Report Format Reference

The sync job uses Amazon Ads API v3 format:

```python
{
  "name": "Report Name",
  "startDate": "2026-01-01",
  "endDate": "2026-01-08",
  "configuration": {
    "adProduct": "SPONSORED_PRODUCTS",
    "groupBy": ["keyword"],  # or ["campaign"], ["advertiser"]
    "columns": [
      "campaignId",
      "impressions",
      "clicks",
      # ... more columns
    ],
    "reportTypeId": "spTargetingKeyword",  # or "spCampaigns", "spAdvertisedProduct"
    "timeUnit": "SUMMARY",  # or "DAILY"
    "format": "GZIP_JSON"
  }
}
```

### Available Report Types

| reportTypeId | groupBy | timeUnit | Use Case |
|--------------|---------|----------|----------|
| spTargetingKeyword | keyword | SUMMARY, DAILY | Keyword performance |
| spCampaigns | campaign | SUMMARY, DAILY | Campaign metrics |
| spAdvertisedProduct | advertiser | SUMMARY, DAILY | Product/ASIN metrics |

See [Amazon Ads API Documentation](https://advertising.amazon.com/API/docs/en-us/reporting/v3/overview) for full details.

## Next Steps

After data is synced:
1. ✅ Use `sp_keywords` data for bid optimization
2. ✅ Calculate AOV from `sp_advertised_product_metrics`
3. ✅ Monitor trends in `sp_campaign_performance`
4. ✅ Run the bid optimizer job to apply AOV-based bid adjustments
