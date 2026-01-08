# Amazon Ads Data Sync - Usage Guide

## Overview

This implementation adds Amazon Ads API v3 reporting capabilities to sync campaign and keyword performance data to BigQuery.

## Features

- ✅ Amazon Ads API v3 reporting endpoints
- ✅ Campaign metadata sync
- ✅ Keyword metadata sync  
- ✅ Campaign performance data sync (reports API)
- ✅ Keyword performance data sync (reports API)
- ✅ AOV metrics calculation
- ✅ BigQuery table creation scripts
- ✅ Proper error handling and logging

## File Changes

### 1. `backend/shared/amazon_client.py`
Added new Amazon Ads API v3 reporting methods:

- `create_report()` - Create reports using v3 API
- `get_report_status()` - Check report generation status
- `download_report()` - Download and parse completed reports
- `get_campaigns_report()` - Helper for campaign performance
- `get_keywords_report()` - Helper for keyword performance
- `get_search_terms_report()` - Helper for search terms

Old v2 methods renamed to `*_v2` for backward compatibility.

### 2. `backend/jobs/data_sync/amazon_ads_sync.py`
New data sync job with methods:

- `sync_campaigns()` - Sync campaign metadata via direct API
- `sync_keywords()` - Sync keyword metadata via direct API
- `sync_campaign_performance()` - Sync performance via reports API v3
- `sync_keyword_performance()` - Sync performance via reports API v3
- `sync_advertised_products()` - Calculate AOV metrics
- `run_full_sync()` - Execute complete sync workflow

### 3. `backend/main.py`
Updated to support `data_sync` job type routing.

### 4. `scripts/create_sync_tables.py`
Python script to programmatically create BigQuery tables.

### 5. `scripts/create_sync_tables.sql`
SQL definitions for all required BigQuery tables.

## BigQuery Tables Created

### `sp_campaigns`
Campaign metadata (WRITE_TRUNCATE on each sync)
- campaign_id, campaign_name, campaign_status, campaign_type, daily_budget, start_date, end_date, updated_at

### `sp_keywords`
Keyword metadata (WRITE_TRUNCATE on each sync)
- keyword_id, campaign_id, ad_group_id, keyword_text, match_type, bid, state, updated_at

### `sp_campaign_performance`
Campaign performance metrics (WRITE_APPEND, partitioned by date)
- date, campaign_id, impressions, clicks, cost, sales, purchases, updated_at

### `keyword_performance`
Keyword performance metrics (WRITE_APPEND, partitioned by date)
- date, keyword_id, campaign_id, ad_group_id, impressions, clicks, cost, conversion_value, conversions, updated_at

### `sp_advertised_product_metrics`
Calculated AOV and revenue metrics (CREATE OR REPLACE)
- campaign_id, date, aov, orders, revenue, updated_at

## Usage

### Step 1: Create BigQuery Tables

```bash
# Using Python script
python scripts/create_sync_tables.py YOUR_PROJECT_ID amazon_ppc

# Or using SQL (replace placeholders first)
# Edit create_sync_tables.sql and replace {project_id} and {dataset}
# Then run via bq command or BigQuery console
```

### Step 2: Run Data Sync Job

```bash
# Set environment variables
export JOB_TYPE=data_sync
export GOOGLE_CLOUD_PROJECT=your-project-id
export BIGQUERY_DATASET=amazon_ppc

# Run the job
python backend/main.py
```

### Step 3: Verify Data

```bash
# Check tables were created
bq ls amazon_ppc

# Check row counts
bq query --use_legacy_sql=false "
SELECT 
  (SELECT COUNT(*) FROM \`your-project.amazon_ppc.sp_campaigns\`) as campaigns,
  (SELECT COUNT(*) FROM \`your-project.amazon_ppc.sp_keywords\`) as keywords,
  (SELECT COUNT(*) FROM \`your-project.amazon_ppc.sp_campaign_performance\`) as perf
"
```

## Environment Variables

Required:
- `JOB_TYPE` - Set to `data_sync` for sync job
- `GOOGLE_CLOUD_PROJECT` - GCP project ID
- `BIGQUERY_DATASET` - BigQuery dataset name (default: `amazon_ppc`)

Amazon credentials (via Secret Manager):
- `AMAZON_CLIENT_ID_SECRET`
- `AMAZON_CLIENT_SECRET_SECRET`
- `AMAZON_REFRESH_TOKEN_SECRET`
- `AMAZON_PROFILE_ID_SECRET`

## Expected Log Output

```
============================================================
🚀 Starting Job: data_sync
Project: amazon-ppc-bid-optimizer
Dataset: amazon_ppc
Time: 2026-01-08 22:45:00 
============================================================

📊 Syncing campaigns from Amazon Ads API...
✅ Synced 12 campaigns to BigQuery

🔑 Syncing keywords from Amazon Ads API...
✅ Synced 347 keywords to BigQuery

📈 Syncing campaign performance (last 14 days)...
Creating campaigns report from 2025-12-26 to 2026-01-08...
✅ Report created: rpt_12345
Polling for report rpt_12345 completion...
Report status: IN_PROGRESS, waiting 10s...
✅ Report ready. Downloading from https://...
✅ Downloaded 168 report rows
✅ Synced 168 campaign performance rows

🎯 Syncing keyword performance (last 14 days)...
Creating keywords report from 2025-12-26 to 2026-01-08...
✅ Report created: rpt_67890
✅ Downloaded 4,858 report rows
✅ Synced 4,858 keyword performance rows

📦 Calculating advertised product metrics (last 30 days)...
✅ Calculated advertised product metrics

============================================================
✅ Amazon Ads Data Sync Complete!
============================================================
```

## Error Handling

The implementation handles:
- ✅ 403 Forbidden - Uses correct v3 endpoints instead of deprecated v2
- ✅ 400 Bad Request - Proper v3 request format
- ✅ 401 Unauthorized - Token refresh logic
- ✅ 429 Rate Limiting - Automatic retry with backoff
- ✅ Report failures - Proper error messages
- ✅ Empty data sets - Graceful handling with warnings

## Differences from v2 API

| Aspect | v2 API (Old) | v3 API (New) |
|--------|--------------|--------------|
| Endpoint | `/reports` | `/reporting/reports` |
| Request Format | Simple params | Structured config object |
| Date Format | YYYYMMDD | YYYY-MM-DD |
| Response Format | Direct JSON | GZIP_JSON |
| Status Endpoint | `/v2/reports/{id}` | `/reporting/reports/{id}` |

## Testing

Run validation script:
```bash
python scripts/validate_implementation.py
```

This checks:
- ✅ Python syntax for all files
- ✅ Required methods exist
- ✅ Proper imports
- ✅ Routing logic in main.py
- ✅ Table definitions
- ✅ Directory structure

## Integration with Bid Optimizer

The bid optimizer (`JOB_TYPE=aov_optimizer`) can now read from these tables:
- `sp_keywords` - Keyword metadata
- `keyword_performance` - Performance metrics
- `sp_advertised_product_metrics` - AOV calculations

Run sync before optimizer:
```bash
# 1. Sync data
export JOB_TYPE=data_sync
python backend/main.py

# 2. Run optimizer
export JOB_TYPE=aov_optimizer
export DRY_RUN=true
python backend/main.py
```

## Troubleshooting

### Issue: 403 Forbidden on /reports
**Solution**: This implementation uses `/reporting/reports` (v3) instead

### Issue: 400 Bad Request
**Solution**: v3 uses structured config object, not simple params

### Issue: No data in tables
**Check**: 
1. Amazon credentials are correct
2. Profile ID has required permissions
3. Campaigns/keywords exist in account
4. Date range is valid

### Issue: Report timeout
**Solution**: Increase `max_wait_seconds` in `download_report()` calls

## Next Steps

1. ✅ Implementation complete
2. ✅ Validation script created
3. Schedule regular sync (e.g., Cloud Scheduler + Cloud Run)
4. Monitor sync job logs
5. Adjust date ranges (`days_back`) as needed
6. Add monitoring/alerting for sync failures
