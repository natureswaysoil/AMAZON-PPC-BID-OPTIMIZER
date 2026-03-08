"""
Keyword Harvester - Discovers new keywords from search term reports
"""
import logging, os, sys
from datetime import datetime, timezone, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)

MIN_CLICKS_WITH_ORDERS = 3
MIN_CLICKS_NO_ORDERS = 15
MAX_ACOS_TO_ADD = 0.60
STARTING_BID = 0.75
MAX_KEYWORDS_PER_RUN = 50

def run_keyword_harvester():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("=" * 60)
    logger.info("🌱 Starting Keyword Harvester")
    logger.info(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info("=" * 60)
    try:
        from shared.token_manager import token_manager
        from shared.amazon_client import AmazonAdsClient
        from google.cloud import bigquery

        token_manager.get_access_token()
        client = AmazonAdsClient()
        bq = bigquery.Client(project=os.getenv('GOOGLE_CLOUD_PROJECT', 'amazon-ppc-474902'))
        dataset = os.getenv('BIGQUERY_DATASET', 'amazon_ppc')

        logger.info("📋 Step 1: Loading existing keywords...")
        existing = _get_existing_keywords(bq, dataset)
        logger.info(f"   Loaded {len(existing)} existing keyword+campaign combos")

        logger.info("📊 Step 2: Loading search terms from BigQuery...")
        search_terms = _get_search_terms_from_bq(bq, dataset)
        logger.info(f"   Found {len(search_terms)} search terms")

        if not search_terms:
            logger.warning("⚠️ No search terms in BigQuery yet - run ads-data-sync first")
            return

        logger.info("🔍 Step 3: Filtering candidates...")
        candidates = _filter_candidates(search_terms, existing)[:MAX_KEYWORDS_PER_RUN]
        logger.info(f"   {len(candidates)} candidates qualify")

        if not candidates:
            logger.info("✅ No new keywords to add this run")
            return

        logger.info("➕ Step 4: Adding keywords to campaigns...")
        added, failed = _add_keywords(client, candidates)

        _log_to_bigquery(bq, dataset, candidates)

        logger.info("=" * 60)
        logger.info(f"🌱 Complete | Analyzed:{len(search_terms)} Candidates:{len(candidates)} Added:{added} Failed:{failed}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Keyword harvester failed: {e}", exc_info=True)
        sys.exit(1)

def _get_search_terms_from_bq(bq, dataset) -> list:
    """Read search terms from BigQuery search_term_reports table"""
    try:
        rows = bq.query(f"""
            SELECT
                search_term as searchTerm,
                CAST(campaign_id AS STRING) as campaignId,
                CAST(ad_group_id AS STRING) as adGroupId,
                SUM(clicks) as clicks,
                SUM(conversions) as purchases14d,
                SUM(conversion_value) as sales14d,
                SUM(cost) as cost,
                '' as matchType,
                0.75 as keywordBid
            FROM `{bq.project}.{dataset}.search_term_reports`
            WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
            GROUP BY search_term, campaign_id, ad_group_id
            HAVING SUM(clicks) >= 1
            ORDER BY SUM(clicks) DESC
            LIMIT 5000
        """).result()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to load search terms from BQ: {e}")
        return []

def _get_existing_keywords(bq, dataset):
    try:
        rows = bq.query(f"""
            SELECT LOWER(keyword_text) as kw, CAST(campaign_id AS STRING) as cid
            FROM `{bq.project}.{dataset}.keywords` WHERE state = 'ENABLED'
        """).result()
        return {(r.kw, r.cid) for r in rows}
    except Exception as e:
        logger.warning(f"Could not load existing keywords: {e}")
        return set()

def _get_search_term_report(client):
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=30)
    report_config = {
        "name": "Search Term Harvesting Report",
        "startDate": start_date.strftime('%Y-%m-%d'),
        "endDate": end_date.strftime('%Y-%m-%d'),
        "configuration": {
            "adProduct": "SPONSORED_PRODUCTS",
            "groupBy": ["searchTerm"],
            "columns": ["campaignId","campaignName","adGroupId","adGroupName",
                        "keywordId","keywordBid","matchType","searchTerm",
                        "impressions","clicks","cost","purchases14d","sales14d","acosClicks14d"],
            "reportTypeId": "spSearchTerm",
            "timeUnit": "SUMMARY",
            "format": "GZIP_JSON"
        }
    }
    try:
        data = client.request_and_download_report_v3(report_config, max_wait=300)
        return data if data else []
    except Exception as e:
        logger.error(f"Search term report failed: {e}")
        return []

def _filter_candidates(search_terms, existing):
    candidates = []
    for row in search_terms:
        term = str(row.get('searchTerm', '') or '').strip().lower()
        campaign_id = str(row.get('campaignId', ''))
        ad_group_id = str(row.get('adGroupId', ''))
        clicks = int(row.get('clicks', 0) or 0)
        purchases = int(row.get('purchases14d', 0) or 0)
        spend = float(row.get('cost', 0) or 0)
        sales = float(row.get('sales14d', 0) or 0)
        match_type = str(row.get('matchType', 'BROAD')).upper()
        keyword_bid = float(row.get('keywordBid', STARTING_BID) or STARTING_BID)

        if not term or not campaign_id or not ad_group_id:
            continue
        if (term, campaign_id) in existing:
            continue
        if len(term.split()) < 2 and clicks < 20:
            continue
        if match_type == 'EXACT':
            continue

        acos = (spend / sales) if sales > 0 else 999
        qualifies = False
        reason = ""

        if purchases > 0 and clicks >= MIN_CLICKS_WITH_ORDERS and acos <= MAX_ACOS_TO_ADD:
            qualifies = True
            reason = f"orders={purchases}, clicks={clicks}, acos={acos:.0%}"
        elif purchases == 0 and clicks >= MIN_CLICKS_NO_ORDERS:
            qualifies = True
            reason = f"high-traffic clicks={clicks}"

        if qualifies:
            bid = max(round(min(keyword_bid * 0.8, 1.50), 2), 0.30)
            candidates.append({
                'search_term': term, 'campaign_id': campaign_id,
                'campaign_name': row.get('campaignName', ''),
                'ad_group_id': ad_group_id, 'ad_group_name': row.get('adGroupName', ''),
                'clicks': clicks, 'purchases': purchases, 'spend': spend,
                'sales': sales, 'acos': acos if acos < 999 else None,
                'starting_bid': bid, 'reason': reason,
            })

    candidates.sort(key=lambda x: (x['purchases'], x['clicks']), reverse=True)
    return candidates

def _add_keywords(client, candidates):
    added = failed = 0
    by_adgroup = {}
    for c in candidates:
        by_adgroup.setdefault(c['ad_group_id'], []).append(c)

    for ad_group_id, group in by_adgroup.items():
        payload = [{"campaignId": int(c['campaign_id']), "adGroupId": int(ad_group_id),
                    "keywordText": c['search_term'], "matchType": "EXACT",
                    "bid": c['starting_bid'], "state": "ENABLED"} for c in group]
        try:
            response = client._make_request('POST', '/sp/keywords', json=payload)
            if isinstance(response, list):
                for r in response:
                    if r.get('code') == 'SUCCESS' or r.get('keywordId'):
                        added += 1
                        logger.info(f"   ✅ Added: '{r.get('keywordText','')}' @ ${group[0]['starting_bid']}")
                    else:
                        failed += 1
                        logger.warning(f"   ⚠️ Failed: {r.get('description', r)}")
            else:
                added += len(payload)
        except Exception as e:
            logger.error(f"   ❌ adGroup {ad_group_id}: {e}")
            failed += len(group)
    return added, failed

def _log_to_bigquery(bq, dataset, candidates):
    from google.cloud import bigquery as bq_lib
    table_id = f"{bq.project}.{dataset}.keyword_harvest_log"
    now = datetime.utcnow().isoformat()
    rows = [{**c, 'harvested_at': now, 'status': 'added'} for c in candidates]
    try:
        job = bq.load_table_from_json(rows, table_id,
            job_config=bq_lib.LoadJobConfig(write_disposition="WRITE_APPEND", autodetect=True))
        job.result()
        logger.info(f"📝 Logged {len(rows)} entries to keyword_harvest_log")
    except Exception as e:
        logger.warning(f"BQ log failed: {e}")

if __name__ == "__main__":
    run_keyword_harvester()
