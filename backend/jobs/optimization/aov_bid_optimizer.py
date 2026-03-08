
from google.cloud import bigquery
import sys
import os
from datetime import datetime, timedelta
import pytz # Requires: pip install pytz
import logging

sys.path.insert(0, '/app')

# Assuming these exist in your backend/core/config.py
from backend.core.config import (
    AOV_TIERS, PERFORMANCE_MULTIPLIERS, MATCH_TYPE_MULTIPLIERS,
    get_time_multiplier, MAX_BID_AS_PERCENT_OF_AOV, settings
)
from backend.aov_fetcher import aov_fetcher

logger = logging.getLogger(__name__)

class AOVBidOptimizer:
    def __init__(self):
        self.bq_client = bigquery.Client(project=settings.PROJECT_ID)
        # Set account timezone (Default to America/Los_Angeles for Amazon NA)
        self.account_timezone = pytz.timezone('America/Los_Angeles') 
    
    def get_aov_tier(self, aov: float) -> str:
        """Determine AOV tier for a product"""
        if aov is None:
            return 'L'
        for tier_code, tier in AOV_TIERS.items():
            if tier.min_aov <= aov <= tier.max_aov:
                return tier_code
        return 'L'
    
    def get_performance_tier(self, keyword_data: dict) -> str:
        """Classify keyword performance into tiers A-E"""
        acos = float(keyword_data.get('acos') or 1.0)
        cvr = float(keyword_data.get('cvr') or 0)
        conversions = int(keyword_data.get('conversions_30d') or 0)
        clicks = int(keyword_data.get('clicks_30d') or 0)
        
        if conversions >= 5 and acos <= 0.25 and cvr >= 0.12:
            return 'A'
        if conversions >= 3 and acos <= 0.35 and cvr >= 0.08:
            return 'B'
        if conversions >= 1 and acos <= 0.45:
            return 'C'
        if acos > 0.45 or (conversions == 0 and clicks > 20):
            return 'D'
        if conversions == 0 and clicks > 50:
            return 'E'
        return 'C'
    
    def calculate_optimal_bid(self, keyword_data: dict, current_hour: int) -> dict:
        """Calculate optimal bid using AOV-aware dynamic ceiling"""
        aov = float(keyword_data.get('aov') or 30)
        match_type = keyword_data.get('match_type', 'EXACT')
        current_bid = float(keyword_data.get('current_bid') or 0.50)
        
        # Performance Metrics
        clicks = int(keyword_data.get('clicks_30d') or 0)
        conversions = int(keyword_data.get('conversions_30d') or 0)
        
        aov_tier_code = self.get_aov_tier(aov)
        aov_tier = AOV_TIERS[aov_tier_code]
        base_ceiling = aov_tier.base_ceiling_exact
        
        performance_tier = self.get_performance_tier(keyword_data)
        
        # Calculate Max Allowable Bid (Ceiling)
        ceiling = (
            base_ceiling
            * PERFORMANCE_MULTIPLIERS[performance_tier]
            * MATCH_TYPE_MULTIPLIERS.get(match_type, 0.75)
            * get_time_multiplier(current_hour, performance_tier)
        )
        
        # Absolute safety cap based on product price
        aov_safety_ceiling = aov * MAX_BID_AS_PERCENT_OF_AOV
        ceiling = min(ceiling, aov_safety_ceiling)
        
        acos = float(keyword_data.get('acos') or 0)
        target_acos = float(keyword_data.get('target_acos') or 0.30)
        
        # --- LOGIC CORRECTION START ---
        
        new_bid = current_bid

        # Scenario 1: BLEEDER (High Clicks, No Sales)
        # Fix: Stop increasing bids on keywords that spend but don't sell.
        if conversions == 0 and clicks > 15:
             # Cut bid aggressively
             new_bid = current_bid * 0.75
        
        # Scenario 2: GHOST (Low Clicks, No Sales)
        # Fix: Give it a chance, but respect the ceiling.
        elif conversions == 0 and clicks <= 15:
             new_bid = min(current_bid * 1.10, ceiling)
             
        # Scenario 3: HIGH PERFORMANCE (Good ACoS)
        elif conversions > 0 and acos < target_acos * 0.8:
            new_bid = min(current_bid * 1.15, ceiling)
            
        # Scenario 4: ON TARGET
        elif conversions > 0 and acos <= target_acos:
            new_bid = min(current_bid * 1.05, ceiling)
            
        # Scenario 5: SLIGHTLY UNPROFITABLE (Tolerance buffer)
        elif acos <= target_acos * 1.2:
            new_bid = current_bid
            
        # Scenario 6: UNPROFITABLE
        else:
            # Calculate decrease needed to break even, capped at 20% reduction
            if acos > 0:
                decrease_factor = max(0.80, target_acos / acos)
                new_bid = current_bid * decrease_factor
            else:
                new_bid = current_bid * 0.9

        # Final Bounds Check
        new_bid = min(new_bid, ceiling)
        new_bid = max(0.20, new_bid) # Hard Floor of $0.20
        
        # Stability Check: Don't update if change is less than 5%
        if current_bid > 0 and abs(new_bid - current_bid) / current_bid < 0.05:
            new_bid = current_bid
            
        # --- LOGIC CORRECTION END ---
        
        reasoning = (
            f"AOV: ${aov:.2f} (Tier {aov_tier_code}) | "
            f"Perf: Tier {performance_tier} | "
            f"Match: {match_type} | "
            f"Hour: {current_hour} | "
            f"Clicks: {clicks} / Conv: {conversions} | "
            f"ACOS: {acos:.1%} vs Target: {target_acos:.1%} | "
            f"Ceiling: ${ceiling:.2f}"
        )
        
        return {
            'new_bid': round(new_bid, 2),
            'ceiling': round(ceiling, 2),
            'aov_tier': aov_tier_code,
            'performance_tier': performance_tier,
            'reasoning': reasoning,
            'aov': aov,
            'safety_ceiling': round(aov_safety_ceiling, 2)
        }
    
    def optimize_all_keywords(self, dry_run: bool = False) -> list:
        """Get all keywords and calculate optimal bids"""
        
        # Fetch real-time AOV data once at the start
        logger.info("Fetching real-time AOV data...")
        aov_fetcher.fetch_all()
        
        # Fix: Use Account Timezone for Dayparting (not UTC/Server time)
        now_in_account_tz = datetime.now(self.account_timezone)
        current_hour = now_in_account_tz.hour
        
        # Fix: Adjusted SQL window to account for 3-day attribution lag
        # We look at data from Day -33 to Day -3
        query = """
        WITH keyword_performance AS (
          SELECT 
            k.keyword_id,
            k.keyword_text,
            k.bid as current_bid,
            k.match_type,
            k.campaign_id,
            SUM(kp.clicks) as clicks_30d,
            SUM(kp.conversions) as conversions_30d,
            SUM(kp.cost) as cost_30d,
            SUM(kp.conversion_value) as sales_30d,
            SAFE_DIVIDE(CAST(SUM(kp.conversions) AS FLOAT64), CAST(SUM(kp.clicks) AS FLOAT64)) as cvr,
            SAFE_DIVIDE(SUM(kp.cost), NULLIF(SUM(kp.conversion_value), 0)) as acos
          FROM `{project}.{dataset}.keywords` k
          LEFT JOIN `{project}.{dataset}.keyword_performance` kp 
            ON k.keyword_id = kp.keyword_id
            AND kp.date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 33 DAY) AND DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
          WHERE k.state = 'ENABLED'
          GROUP BY 
            k.keyword_id, k.keyword_text, k.bid, k.match_type, k.campaign_id
        )
        SELECT 
          keyword_id,
          keyword_text,
          current_bid,
          match_type,
          campaign_id,
          COALESCE(clicks_30d, 0) as clicks_30d,
          COALESCE(conversions_30d, 0) as conversions_30d,
          COALESCE(cost_30d, 0.0) as cost_30d,
          COALESCE(sales_30d, 0.0) as sales_30d,
          COALESCE(cvr, 0.0) as cvr,
          COALESCE(acos, 0.0) as acos
        FROM keyword_performance
        WHERE clicks_30d >= 1
        """.format(project=settings.PROJECT_ID, dataset=settings.BIGQUERY_DATASET)
        
        try:
            results = self.bq_client.query(query).result()
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
        
        optimizations = []
        
        for row in results:
            keyword_data = dict(row)
            
            # Get real-time AOV from fetcher using campaign_id
            campaign_id = keyword_data.get('campaign_id')
            aov_data = aov_fetcher.get_aov(campaign_id)
            
            # Inject AOV into keyword data
            keyword_data['aov'] = aov_data.aov
            keyword_data['aov_confidence'] = aov_data.confidence
            keyword_data['target_acos'] = 0.30
            
            try:
                optimization = self.calculate_optimal_bid(keyword_data, current_hour)
                
                # Only append if bid actually changed
                if optimization['new_bid'] != keyword_data['current_bid']:
                    optimizations.append({
                        'keyword_id': keyword_data['keyword_id'],
                        'keyword_text': keyword_data['keyword_text'],
                        'campaign_id': campaign_id,
                        'current_bid': keyword_data['current_bid'],
                        'aov_confidence': aov_data.confidence,
                        **optimization,
                        'timestamp': datetime.utcnow().isoformat(),
                        'is_dry_run': dry_run
                    })
            except Exception as e:
                logger.error(f"Failed to optimize keyword {keyword_data.get('keyword_id')}: {e}")
                continue
        
        logger.info(f"Found {len(optimizations)} keywords to optimize")
        
        if optimizations:
            self._log_optimizations(optimizations, dry_run)
        
        return optimizations
    
    def _log_optimizations(self, optimizations: list, dry_run: bool):
        """Log optimization decisions to BigQuery"""
        
        if dry_run:
            logger.info("DRY RUN: Skipping write to BigQuery.")
            return

        table_id = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.bid_optimizations"
        
        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND",
            schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
        )
        
        try:
            job = self.bq_client.load_table_from_json(
                optimizations, table_id, job_config=job_config
            )
            job.result()
            logger.info(f"Logged {len(optimizations)} optimizations to BigQuery")
        except Exception as e:
            logger.error(f"Failed to log optimizations: {e}")

def run_aov_optimizer():
    """Entry point for Cloud Run job"""
    logging.basicConfig(level=logging.INFO)
    logger.info("🚀 Starting AOV-based bid optimizer...")
    
    optimizer = AOVBidOptimizer()
    # Set dry_run=False to actually write to DB, True to test
    optimizations = optimizer.optimize_all_keywords(dry_run=False)
    
    logger.info(f"Optimization complete: {len(optimizations)} bids calculated")
    
    if optimizations:
        tier_summary = {}
        for opt in optimizations:
            tier = opt['aov_tier']
            tier_summary[tier] = tier_summary.get(tier, 0) + 1
        
        print("\n📊 Optimization Summary by AOV Tier:")
        for tier, count in sorted(tier_summary.items()):
            print(f"  Tier {tier}: {count} keywords")
        
        print(f"\n✅ Total optimizations: {len(optimizations)}")
    else:
        print("\n⚠️ No keywords needed optimization")

if __name__ == "__main__":
    run_aov_optimizer()