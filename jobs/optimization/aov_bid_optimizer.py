# jobs/optimization/aov_bid_optimizer.py
"""
AOV-Based Bid Optimizer with Amazon Suggested Bid Blending

Features:
- AOV-aware dynamic bid ceilings
- Performance tier classification (A-E)
- Dayparting (time-based multipliers)
- Amazon suggested bid blending
- Max change per run safety limits
- Comprehensive audit logging
"""
from google.cloud import bigquery
from datetime import datetime
import logging
from typing import Dict, List, Optional
import pytz
import sys
import os
from pathlib import Path

# Add parent directories to path for local AND Cloud Run
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))
sys.path.insert(0, '/app')

try:
    from backend.shared.amazon_client import amazon_client
    from backend.shared.token_manager import token_manager
    from backend.core.config import (
        AOV_TIERS, PERFORMANCE_MULTIPLIERS, MATCH_TYPE_MULTIPLIERS,
        get_time_multiplier, MAX_BID_AS_PERCENT_OF_AOV, TARGET_ACOS_DEFAULT, settings
    )
    from backend.aov_fetcher import aov_fetcher
except ImportError:
    # Fallback for local run
    from shared.amazon_client import amazon_client
    from shared.token_manager import token_manager
    from core.config import (
        AOV_TIERS, PERFORMANCE_MULTIPLIERS, MATCH_TYPE_MULTIPLIERS,
        get_time_multiplier, MAX_BID_AS_PERCENT_OF_AOV, TARGET_ACOS_DEFAULT, settings
    )
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from aov_fetcher import aov_fetcher

logger = logging.getLogger(__name__)

class AOVBidOptimizer:
    """Enhanced bid optimizer with suggested bid blending"""
    
    def __init__(self):
        self.bq_client = bigquery.Client(project=settings.PROJECT_ID)
        self.amazon_client = amazon_client
        
        # Get current hour in configured timezone
        tz = pytz.timezone(settings.TIMEZONE)
        self.current_hour = datetime.now(tz).hour
        
        logger.info(f"Optimizer initialized (timezone={settings.TIMEZONE}, hour={self.current_hour})")
    
    def get_aov_tier(self, aov: float) -> str:
        """Determine AOV tier for a product"""
        if aov is None:
            return 'L'
        
        for tier_code, tier in AOV_TIERS.items():
            if tier.min_aov <= aov <= tier.max_aov:
                return tier_code
        
        return 'L'  # Default to Low
    
    def get_performance_tier(self, keyword_data: dict) -> str:
        """Classify keyword performance into tiers A-E"""
        acos = float(keyword_data.get('acos') or 1.0)
        cvr = float(keyword_data.get('cvr') or 0)
        conversions = int(keyword_data.get('conversions_30d') or 0)
        clicks = int(keyword_data.get('clicks_30d') or 0)
        
        # Tier A: Winners
        if conversions >= 5 and acos <= 0.25 and cvr >= 0.12:
            return 'A'
        
        # Tier B: Solid performers
        if conversions >= 3 and acos <= 0.35 and cvr >= 0.08:
            return 'B'
        
        # Tier C: Testing phase
        if conversions >= 1 and acos <= 0.45:
            return 'C'
        
        # Tier D: Bleeding money
        if acos > 0.45 or (conversions == 0 and clicks > 20):
            return 'D'
        
        # Tier E: Kill zone
        if conversions == 0 and clicks > 50:
            return 'E'
        
        return 'C'  # Default
    
    def calculate_aov_based_bid(
        self,
        keyword_data: dict,
        current_hour: int
    ) -> Dict:
        """
        Calculate optimal bid using AOV-aware dynamic ceiling
        
        Returns dict with:
        - aov_bid: The AOV-based calculated bid
        - ceiling: Maximum allowed bid
        - aov_tier: Tier code (L/M/H/X)
        - performance_tier: Tier code (A/B/C/D/E)
        """
        aov = float(keyword_data.get('aov') or 30)
        match_type = keyword_data.get('match_type', 'EXACT')
        current_bid = float(keyword_data.get('current_bid') or 0.50)
        
        # Get tier and ceiling
        aov_tier_code = self.get_aov_tier(aov)
        aov_tier = AOV_TIERS[aov_tier_code]
        base_ceiling = aov_tier.base_ceiling_exact
        
        performance_tier = self.get_performance_tier(keyword_data)
        
        # Calculate dynamic ceiling
        ceiling = (
            base_ceiling
            * PERFORMANCE_MULTIPLIERS[performance_tier]
            * MATCH_TYPE_MULTIPLIERS.get(match_type, 0.75)
            * get_time_multiplier(current_hour, performance_tier)
        )
        
        # Apply AOV safety ceiling (never bid more than 7% of AOV)
        aov_safety_ceiling = aov * MAX_BID_AS_PERCENT_OF_AOV
        ceiling = min(ceiling, aov_safety_ceiling)
        
        # Calculate bid adjustment based on performance
        acos = float(keyword_data.get('acos') or 0)
        target_acos = float(keyword_data.get('target_acos') or TARGET_ACOS_DEFAULT)
        
        if acos == 0 or acos < target_acos * 0.7:
            # Performing well - increase bid
            new_bid = min(current_bid * 1.15, ceiling)
        elif acos < target_acos:
            # Good performance - slight increase
            new_bid = min(current_bid * 1.05, ceiling)
        elif acos < target_acos * 1.3:
            # Near target - maintain
            new_bid = current_bid
        else:
            # Above target - decrease
            decrease_factor = min(0.85, target_acos / acos if acos > 0 else 0.85)
            new_bid = current_bid * decrease_factor
        
        # Apply ceiling and floor
        new_bid = max(settings.MIN_BID, min(new_bid, ceiling))
        
        # Only change if difference is significant (>5%)
        if current_bid > 0 and abs(new_bid - current_bid) / current_bid < 0.05:
            new_bid = current_bid
        
        return {
            'aov_bid': round(new_bid, 2),
            'ceiling': round(ceiling, 2),
            'aov_tier': aov_tier_code,
            'performance_tier': performance_tier,
            'aov_safety_ceiling': round(aov_safety_ceiling, 2)
        }
    
    def blend_bids(
        self,
        aov_bid: float,
        suggested_bid: Optional[float],
        current_bid: float,
        ceiling: float
    ) -> Dict:
        """
        Blend AOV-based bid with Amazon's suggested bid
        
        Args:
            aov_bid: Your AOV-based calculation
            suggested_bid: Amazon's suggestion (can be None)
            current_bid: Current bid amount
            ceiling: Maximum allowed bid from AOV calculation
        
        Returns:
            Dict with final_bid and reasoning
        """
        # If no suggestion available, use AOV bid
        if suggested_bid is None or suggested_bid <= 0:
            return {
                'final_bid': aov_bid,
                'blend_method': 'aov_only',
                'reasoning': 'No suggested bid available'
            }
        
        # Blend: 70% suggested, 30% AOV-based
        blend_weight = settings.SUGGEST_BLEND
        
        # Validate blend weight is between 0 and 1
        if not (0 <= blend_weight <= 1):
            logger.warning(f"Invalid SUGGEST_BLEND value: {blend_weight}, using default 0.70")
            blend_weight = 0.70  # Default fallback to match settings default
        
        blended = (suggested_bid * blend_weight) + (aov_bid * (1 - blend_weight))
        
        # Apply ceiling from AOV calculation
        blended = min(blended, ceiling)
        
        # Apply global min/max
        blended = max(settings.MIN_BID, min(blended, settings.MAX_BID))
        
        # Apply max change per run limits
        if current_bid > 0:
            max_increase = current_bid * (1 + settings.MAX_UP_PCT_PER_RUN)
            max_decrease = current_bid * (1 - settings.MAX_DOWN_PCT_PER_RUN)
            
            if blended > max_increase:
                blended = max_increase
                reasoning = f'Capped at +{settings.MAX_UP_PCT_PER_RUN*100:.0f}% max increase'
            elif blended < max_decrease:
                blended = max_decrease
                reasoning = f'Capped at -{settings.MAX_DOWN_PCT_PER_RUN*100:.0f}% max decrease'
            else:
                reasoning = f'Blended: {blend_weight*100:.0f}% suggested + {(1-blend_weight)*100:.0f}% AOV'
        else:
            reasoning = 'Initial bid setting'
        
        return {
            'final_bid': round(blended, 2),
            'blend_method': 'blended',
            'suggested_bid': round(suggested_bid, 2),
            'aov_bid': round(aov_bid, 2),
            'reasoning': reasoning
        }
    
    def get_keywords_to_optimize(self) -> List[Dict]:
        """
        Fetch keywords from BigQuery with performance metrics
        
        Returns list of keyword dicts with:
        - keyword_id, keyword_text, current_bid, match_type
        - campaign_id, ad_group_id
        - clicks_30d, conversions_30d, cost_30d, sales_30d
        - cvr, acos
        """
        query = f"""
        WITH keyword_perf AS (
          SELECT 
            k.keyword_id,
            k.keyword_text,
            k.bid as current_bid,
            k.match_type,
            k.campaign_id,
            k.ad_group_id,
            k.state,
            SUM(kp.clicks) as clicks_30d,
            SUM(kp.conversions) as conversions_30d,
            SUM(kp.cost) as cost_30d,
            SUM(kp.conversion_value) as sales_30d,
            SAFE_DIVIDE(
              CAST(SUM(kp.conversions) AS FLOAT64),
              CAST(SUM(kp.clicks) AS FLOAT64)
            ) as cvr,
            SAFE_DIVIDE(
              SUM(kp.cost),
              NULLIF(SUM(kp.conversion_value), 0)
            ) as acos
          FROM `{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.keywords` k
          LEFT JOIN `{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.keyword_performance` kp 
            ON k.keyword_id = kp.keyword_id
            AND kp.date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
          WHERE k.state = 'ENABLED'
          GROUP BY 
            k.keyword_id, k.keyword_text, k.bid, k.match_type,
            k.campaign_id, k.ad_group_id, k.state
        )
        SELECT 
          keyword_id,
          keyword_text,
          current_bid,
          match_type,
          campaign_id,
          ad_group_id,
          COALESCE(clicks_30d, 0) as clicks_30d,
          COALESCE(conversions_30d, 0) as conversions_30d,
          COALESCE(cost_30d, 0.0) as cost_30d,
          COALESCE(sales_30d, 0.0) as sales_30d,
          COALESCE(cvr, 0.0) as cvr,
          COALESCE(acos, 0.0) as acos
        FROM keyword_perf
        WHERE clicks_30d >= 1  -- Minimum data requirement
        ORDER BY cost_30d DESC
        """
        
        try:
            logger.info("Fetching keywords from BigQuery...")
            results = self.bq_client.query(query).result()
            keywords = [dict(row) for row in results]
            logger.info(f"✅ Retrieved {len(keywords)} keywords for optimization")
            return keywords
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch keywords: {e}")
            return []
    
    def optimize_all_keywords(self, dry_run: bool = False) -> List[Dict]:
        """
        Main optimization workflow
        
        1. Fetch keywords from BigQuery
        2. Fetch real-time AOV data
        3. Get Amazon's suggested bids
        4. Calculate AOV-based bids
        5. Blend bids
        6. Apply to Amazon (unless dry_run)
        7. Log to BigQuery audit table
        """
        logger.info("=" * 60)
        logger.info("🚀 Starting Bid Optimization Run")
        logger.info(f"Dry Run: {dry_run}")
        logger.info(f"Current Hour: {self.current_hour} ({settings.TIMEZONE})")
        logger.info("=" * 60)
        
        # Step 1: Fetch keywords
        keywords = self.get_keywords_to_optimize()
        
        if not keywords:
            logger.warning("⚠️ No keywords to optimize")
            return []
        
        # Step 2: Fetch AOV data
        logger.info("\n📊 Step 2: Fetching real-time AOV data...")
        try:
            aov_fetcher.fetch_all()
        except Exception as e:
            logger.error(f"Failed to fetch AOV data: {e}")
            logger.info("Continuing with default AOV values...")
        
        # Step 3: Get suggested bids from Amazon
        logger.info("\n💡 Step 3: Fetching Amazon suggested bids...")
        keyword_list = [
            {'keyword_id': kw['keyword_id'], 'ad_group_id': kw['ad_group_id']}
            for kw in keywords
        ]
        
        suggested_bids = {}
        try:
            suggested_bids = self.amazon_client.get_keyword_bid_recommendations_batch(keyword_list)
            logger.info(f"✅ Retrieved {len(suggested_bids)} suggested bids")
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch suggested bids: {e}")
            logger.info("Continuing with AOV-only calculations...")
        
        # Step 4-5: Calculate and blend bids
        logger.info("\n🧮 Step 4-5: Calculating optimal bids...")
        
        optimizations = []
        
        for kw in keywords:
            try:
                # Get AOV for this keyword's campaign
                campaign_id = kw['campaign_id']
                aov_data = aov_fetcher.get_aov(str(campaign_id))
                
                kw['aov'] = aov_data.aov
                kw['aov_confidence'] = aov_data.confidence
                kw['target_acos'] = TARGET_ACOS_DEFAULT
                
                # Calculate AOV-based bid
                aov_calc = self.calculate_aov_based_bid(kw, self.current_hour)
                
                # Get suggested bid if available
                suggested = suggested_bids.get(kw['keyword_id'])
                suggested_bid = suggested['suggested_bid'] if suggested else None
                
                # Blend bids
                blend_result = self.blend_bids(
                    aov_bid=aov_calc['aov_bid'],
                    suggested_bid=suggested_bid,
                    current_bid=kw['current_bid'],
                    ceiling=aov_calc['ceiling']
                )
                
                final_bid = blend_result['final_bid']
                
                # Only include if bid changed
                if abs(final_bid - kw['current_bid']) >= 0.01:
                    optimizations.append({
                        'keyword_id': kw['keyword_id'],
                        'keyword_text': kw['keyword_text'],
                        'campaign_id': campaign_id,
                        'ad_group_id': kw['ad_group_id'],
                        'current_bid': kw['current_bid'],
                        'final_bid': final_bid,
                        'aov': aov_data.aov,
                        'aov_confidence': aov_data.confidence,
                        'aov_tier': aov_calc['aov_tier'],
                        'performance_tier': aov_calc['performance_tier'],
                        'ceiling': aov_calc['ceiling'],
                        'suggested_bid': blend_result.get('suggested_bid'),
                        'aov_bid': blend_result['aov_bid'],
                        'blend_method': blend_result['blend_method'],
                        'reasoning': blend_result['reasoning'],
                        'timestamp': datetime.utcnow().isoformat(),
                        'hour_of_day': self.current_hour
                    })
                    
            except Exception as e:
                logger.error(f"Failed to optimize keyword {kw.get('keyword_id')}: {e}")
                continue
        
        logger.info(f"\n✅ Calculated {len(optimizations)} bid changes")
        
        # Step 6: Apply changes to Amazon
        if optimizations and not dry_run:
            logger.info("\n🔄 Step 6: Applying bid changes to Amazon...")
            self._apply_bid_changes(optimizations)
        else:
            logger.info(f"\n⏭️  Step 6: Skipped (dry_run={dry_run})")
        
        # Step 7: Log to BigQuery audit table
        if optimizations:
            logger.info("\n📝 Step 7: Logging to BigQuery audit table...")
            self._log_optimizations(optimizations)
        
        # Print summary
        self._print_summary(optimizations)
        
        return optimizations
    
    def _apply_bid_changes(self, optimizations: List[Dict]):
        """Apply bid changes to Amazon in batches"""
        batch_size = 100
        success_count = 0
        
        for i in range(0, len(optimizations), batch_size):
            batch = optimizations[i:i + batch_size]
            
            try:
                updates = [
                    {
                        'keyword_id': opt['keyword_id'],
                        'new_bid': opt['final_bid']
                    }
                    for opt in batch
                ]
                
                self.amazon_client.update_keyword_bids_batch(updates)
                success_count += len(batch)
                logger.info(f"✅ Updated batch {i//batch_size + 1} ({len(batch)} keywords)")
                
            except Exception as e:
                logger.error(f"❌ Failed to update batch {i//batch_size + 1}: {e}")
                continue
        
        logger.info(f"✅ Successfully updated {success_count}/{len(optimizations)} bids")
    
    def _log_optimizations(self, optimizations: List[Dict]):
        """Log optimization decisions to BigQuery audit table"""
        table_id = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.bid_optimization_log"
        
        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND",
            schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
        )
        
        try:
            job = self.bq_client.load_table_from_json(
                optimizations, table_id, job_config=job_config
            )
            job.result()
            logger.info(f"✅ Logged {len(optimizations)} optimizations to BigQuery")
            
        except Exception as e:
            logger.error(f"❌ Failed to log optimizations: {e}")
    
    def _print_summary(self, optimizations: List[Dict]):
        """Print optimization summary"""
        if not optimizations:
            logger.info("\n" + "=" * 60)
            logger.info("⚠️  No bid changes needed")
            logger.info("=" * 60)
            return
        
        # Summarize by tier
        by_aov_tier = {}
        by_perf_tier = {}
        by_blend_method = {}
        
        total_increase = 0
        total_decrease = 0
        
        for opt in optimizations:
            # AOV tier
            aov_tier = opt['aov_tier']
            by_aov_tier[aov_tier] = by_aov_tier.get(aov_tier, 0) + 1
            
            # Performance tier
            perf_tier = opt['performance_tier']
            by_perf_tier[perf_tier] = by_perf_tier.get(perf_tier, 0) + 1
            
            # Blend method
            method = opt['blend_method']
            by_blend_method[method] = by_blend_method.get(method, 0) + 1
            
            # Count increases/decreases
            if opt['final_bid'] > opt['current_bid']:
                total_increase += 1
            else:
                total_decrease += 1
        
        logger.info("\n" + "=" * 60)
        logger.info("📊 OPTIMIZATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Changes: {len(optimizations)}")
        logger.info(f"  ↗️  Increases: {total_increase}")
        logger.info(f"  ↘️  Decreases: {total_decrease}")
        logger.info("")
        logger.info("By AOV Tier:")
        for tier in sorted(by_aov_tier.keys()):
            logger.info(f"  Tier {tier}: {by_aov_tier[tier]} keywords")
        logger.info("")
        logger.info("By Performance Tier:")
        for tier in sorted(by_perf_tier.keys()):
            logger.info(f"  Tier {tier}: {by_perf_tier[tier]} keywords")
        logger.info("")
        logger.info("By Blend Method:")
        for method, count in by_blend_method.items():
            logger.info(f"  {method}: {count} keywords")
        logger.info("=" * 60)


def run_aov_optimizer():
    """Entry point for Cloud Run job"""
    import sys
    
    dry_run = os.getenv('DRY_RUN', 'false').lower() == 'true'
    
    try:
        optimizer = AOVBidOptimizer()
        optimizations = optimizer.optimize_all_keywords(dry_run=dry_run)
        
        logger.info(f"\n✅ Optimization complete: {len(optimizations)} bids updated")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"\n❌ Optimization failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_aov_optimizer()
