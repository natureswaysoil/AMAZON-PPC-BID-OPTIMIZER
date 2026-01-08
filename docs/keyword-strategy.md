# backend/jobs/optimization/keyword_harvester.py
from google.cloud import bigquery
from backend.core.amazon_api.ads_api import AmazonAdsAPI
from backend.core.secrets import SecretManager
from backend.core.config import settings
from datetime import datetime
import logging
import re
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

class KeywordHarvester:
    """
    Automatically harvest high-performing search terms and add as keywords
    Also identifies negative keywords to prevent waste
    """
    
    def __init__(self):
        self.secret_manager = SecretManager(settings.PROJECT_ID)
        self.bq_client = bigquery.Client(project=settings.PROJECT_ID)
        
        ads_creds = self.secret_manager.get_amazon_ads_credentials()
        self.ads_api = AmazonAdsAPI(ads_creds)
        
        # Junk keyword patterns for lawn & garden
        self.negative_patterns = [
            r'\bhow to\b',
            r'\bwhy\b',
            r'\bwhat is\b',
            r'\bdiy\b',
            r'\bhomemade\b',
            r'\bfree\b',
            r'\bcheap\b',
            r'\bused\b',
            r'\brepair\b',
            r'\bfix\b',
            r'\breviews?\b',
            r'\bimages?\b',
            r'\bpictures?\b',
            r'\bphotos?\b',
        ]
    
    def get_search_terms_to_harvest(self) -> List[Dict]:
        """Find high-performing search terms not yet added as keywords"""
        query = """
        WITH search_term_performance AS (
          SELECT 
            st.search_term,
            st.campaign_id,
            st.ad_group_id,
            k.keyword_text as matched_keyword,
            k.match_type,
            
            -- Performance metrics (30 days)
            SUM(st.clicks) as clicks,
            SUM(st.orders) as orders,
            SUM(st.cost) as cost,
            SUM(st.sales) as sales,
            SAFE_DIVIDE(SUM(st.sales), SUM(st.cost)) as roas,
            SAFE_DIVIDE(SUM(st.cost), SUM(st.sales)) as acos,
            SAFE_DIVIDE(SUM(st.orders), SUM(st.clicks)) as cvr
            
          FROM `{project}.{dataset}.search_terms` st
          LEFT JOIN `{project}.{dataset}.keywords` k 
            ON st.keyword_id = k.keyword_id
          WHERE 
            st.date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
            AND st.search_term IS NOT NULL
          GROUP BY 
            st.search_term, st.campaign_id, st.ad_group_id,
            k.keyword_text, k.match_type
        ),
        existing_keywords AS (
          SELECT DISTINCT LOWER(keyword_text) as keyword_text
          FROM `{project}.{dataset}.keywords`
        )
        SELECT 
          sp.*,
          CASE 
            WHEN ek.keyword_text IS NULL THEN TRUE 
            ELSE FALSE 
          END as is_new_keyword
        FROM search_term_performance sp
        LEFT JOIN existing_keywords ek 
          ON LOWER(sp.search_term) = ek.keyword_text
        WHERE 
          sp.clicks >= 5
          AND sp.orders >= 1
          AND sp.acos <= 0.40  -- Reasonable ACOS threshold
        ORDER BY sp.roas DESC
        """.format(project=settings.PROJECT_ID, dataset=settings.BIGQUERY_DATASET)
        
        results = self.bq_client.query(query).result()
        return [dict(row) for row in results]
    
    def classify_search_term(self, search_term: str) -> Tuple[str, float]:
        """
        Classify search term intent and return confidence score
        Returns: (intent_type, confidence)
        
        Intent types:
        - buyer: High purchase intent
        - researcher: Information seeking
        - junk: Irrelevant traffic
        """
        search_term_lower = search_term.lower()
        
        # Check for junk patterns
        for pattern in self.negative_patterns:
            if re.search(pattern, search_term_lower):
                return ('junk', 0.9)
        
        # Buyer intent signals
        buyer_signals = [
            'buy', 'purchase', 'order', 'best', 'top rated',
            'for sale', 'price', 'deal', 'discount', 'amazon'
        ]
        
        # Research intent signals
        research_signals = [
            'how', 'why', 'what', 'review', 'vs', 'versus',
            'compare', 'difference', 'guide', 'tutorial'
        ]
        
        buyer_score = sum(1 for signal in buyer_signals if signal in search_term_lower)
        research_score = sum(1 for signal in research_signals if signal in search_term_lower)
        
        if buyer_score > research_score:
            confidence = min(0.8, 0.5 + (buyer_score * 0.1))
            return ('buyer', confidence)
        elif research_score > 0:
            confidence = min(0.8, 0.5 + (research_score * 0.1))
            return ('researcher', confidence)
        else:
            return ('buyer', 0.6)  # Default to buyer with medium confidence
    
    def get_negative_keywords_to_add(self) -> List[Dict]:
        """Find search terms that should be added as negatives"""
        query = """
        SELECT 
          search_term,
          campaign_id,
          ad_group_id,
          SUM(clicks) as clicks,
          SUM(cost) as cost,
          SUM(sales) as sales,
          SUM(orders) as orders,
          SAFE_DIVIDE(SUM(cost), SUM(sales)) as acos
        FROM `{project}.{dataset}.search_terms`
        WHERE 
          date >= DATE_SUB(CURRENT_DATE(), INTERVAL 60 DAY)
          AND search_term IS NOT NULL
        GROUP BY search_term, campaign_id, ad_group_id
        HAVING 
          clicks >= 10
          AND orders = 0  -- No conversions
          AND cost > 5    -- Spent at least $5
        ORDER BY cost DESC
        """.format(project=settings.PROJECT_ID, dataset=settings.BIGQUERY_DATASET)
        
        results = self.bq_client.query(query).result()
        
        negative_keywords = []
        for row in results:
            intent, confidence = self.classify_search_term(row['search_term'])
            
            if intent in ['junk', 'researcher'] or confidence > 0.7:
                negative_keywords.append({
                    'search_term': row['search_term'],
                    'campaign_id': row['campaign_id'],
                    'ad_group_id': row['ad_group_id'],
                    'wasted_spend': row['cost'],
                    'clicks': row['clicks'],
                    'reason': f"Intent: {intent} (confidence: {confidence:.0%})"
                })
        
        return negative_keywords
    
    def harvest_keywords(self, min_orders: int = 2, max_acos: float = 0.35, 
                         dry_run: bool = False) -> Dict:
        """
        Main harvesting function
        Returns summary of actions taken
        """
        logger.info("Starting keyword harvesting")
        
        search_terms = self.get_search_terms_to_harvest()
        negative_terms = self.get_negative_keywords_to_add()
        
        added_keywords = []
        added_negatives = []
        skipped = []
        
        # Process positive keywords
        for st in search_terms:
            if not st['is_new_keyword']:
                continue
            
            # Additional filters
            if st['orders'] < min_orders or st['acos'] > max_acos:
                skipped.append(st)
                continue
            
            # Classify intent
            intent, confidence = self.classify_search_term(st['search_term'])
            
            if intent == 'buyer' and confidence > 0.6:
                # Determine match type based on keyword length and specificity
                word_count = len(st['search_term'].split())
                if word_count >= 4:
                    match_type = 'EXACT'
                elif word_count == 3:
                    match_type = 'PHRASE'
                else:
                    match_type = 'BROAD'
                
                # Calculate initial bid based on performance
                suggested_bid = self._calculate_harvest_bid(st)
                
                keyword_data = {
                    'search_term': st['search_term'],
                    'campaign_id': st['campaign_id'],
                    'ad_group_id': st['ad_group_id'],
                    'match_type': match_type,
                    'suggested_bid': suggested_bid,
                    'performance': {
                        'clicks': st['clicks'],
                        'orders': st['orders'],
                        'acos': st['acos'],
                        'roas': st['roas']
                    },
                    'intent': intent,
                    'confidence': confidence
                }
                
                added_keywords.append(keyword_data)
                
                if not dry_run:
                    try:
                        self._add_keyword_via_api(keyword_data)
                        logger.info(f"Added keyword: {st['search_term']} ({match_type}) @ ${suggested_bid}")
                    except Exception as e:
                        logger.error(f"Failed to add keyword {st['search_term']}: {e}")
        
        # Process negative keywords
        for nt in negative_terms:
            added_negatives.append(nt)
            
            if not dry_run:
                try:
                    self._add_negative_keyword_via_api(nt)
                    logger.info(f"Added negative keyword: {nt['search_term']} (saved ${nt['wasted_spend']:.2f})")
                except Exception as e:
                    logger.error(f"Failed to add negative {nt['search_term']}: {e}")
        
        # Log results
        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'keywords_added': len(added_keywords),
            'negatives_added': len(added_negatives),
            'skipped': len(skipped),
            'potential_savings': sum(n['wasted_spend'] for n in added_negatives),
            'details': {
                'added_keywords': added_keywords,
                'added_negatives': added_negatives
            }
        }
        
        self._log_harvest_results(summary)
        
        logger.info(f"Harvesting complete: +{len(added_keywords)} keywords, +{len(added_negatives)} negatives")
        return summary
    
    def _calculate_harvest_bid(self, search_term_data: Dict) -> float:
        """Calculate initial bid for harvested keyword"""
        # Base bid on historical CPC but be conservative
        if search_term_data['clicks'] > 0:
            avg_cpc = search_term_data['cost'] / search_term_data['clicks']
            # Start at 80% of historical CPC
            suggested_bid = avg_cpc * 0.8
        else:
            suggested_bid = 0.75  # Default starting bid
        
        # Adjust based on performance
        if search_term_data['acos'] < 0.20:
            suggested_bid *= 1.2  # Great performer, bid higher
        elif search_term_data['acos'] > 0.30:
            suggested_bid *= 0.8  # Marginal performer, bid lower
        
        # Apply bounds
        suggested_bid = max(settings.MIN_BID, min(2.00, suggested_bid))
        
        return round(suggested_bid, 2)
    
    def _add_keyword_via_api(self, keyword_data: Dict):
        """Add keyword via Amazon Ads API"""
        # Implementation depends on your API setup
        # This is a placeholder for the actual API call
        pass
    
    def _add_negative_keyword_via_api(self, negative_data: Dict):
        """Add negative keyword via Amazon Ads API"""
        # Implementation depends on your API setup
        pass
    
    def _log_harvest_results(self, summary: Dict):
        """Log harvesting results to BigQuery"""
        table_id = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.keyword_harvest_log"
        
        rows = [{
            'harvest_id': f"harvest_{int(datetime.now().timestamp())}",
            'timestamp': summary['timestamp'],
            'keywords_added': summary['keywords_added'],
            'negatives_added': summary['negatives_added'],
            'potential_savings': summary['potential_savings'],
            'details': summary['details']
        }]
        
        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND",
            schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
        )
        
        job = self.bq_client.load_table_from_json(rows, table_id, job_config=job_config)
        job.result()

def run_keyword_harvest():
    harvester = KeywordHarvester()
    harvester.harvest_keywords(dry_run=False)

if __name__ == "__main__":
    run_keyword_harvest()
