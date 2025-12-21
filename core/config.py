cat > core/config.py << 'EOF'
import os
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class AOVTier:
    name: str
    min_aov: float
    max_aov: float
    base_ceiling_exact: float

# AOV-based bid ceilings
AOV_TIERS = {
    'L': AOVTier('Low', 18, 29, 1.05),      # $18-29 products
    'M': AOVTier('Mid', 30, 45, 1.45),      # $30-45 products
    'H': AOVTier('High', 46, 70, 1.95),     # $46-70 products
    'X': AOVTier('Premium', 70, 999, 2.50)  # $70+ products
}

# Performance tier multipliers
PERFORMANCE_MULTIPLIERS = {
    'A': 1.00,   # Winners
    'B': 0.85,   # Solid
    'C': 0.65,   # Testing
    'D': 0.40,   # Bleeding
    'E': 0.15    # Kill zone
}

# Match type multipliers
MATCH_TYPE_MULTIPLIERS = {
    'EXACT': 1.00,
    'PHRASE': 0.75,
    'BROAD': 0.50,
    'AUTO': 0.45
}

# Prime time configuration (2-hour windows during peak)
PRIME_HOURS = [
    (16, 18),  # 4-6 PM
    (18, 20),  # 6-8 PM  
    (20, 22),  # 8-10 PM
]

# Time-based multipliers
def get_time_multiplier(hour: int, performance_tier: str) -> float:
    """Get bid multiplier based on time and performance"""
    # Check if in prime time
    in_prime = any(start <= hour < end for start, end in PRIME_HOURS)
    
    if not in_prime:
        return 0.90  # Reduce bids outside prime time
    
    # During prime time
    if 16 <= hour < 18:
        return 1.00
    elif 18 <= hour < 22:
        # Only boost Tier A during peak evening
        return 1.10 if performance_tier == 'A' else 1.00
    else:
        return 1.00

# Safety limits
MAX_BID_AS_PERCENT_OF_AOV = 0.07  # Never bid more than 7% of AOV
MIN_CONVERSIONS_FOR_PROMOTION = 2
TARGET_ACOS_DEFAULT = 0.30

class Settings:
    PROJECT_ID: str = os.getenv('PROJECT_ID', os.getenv('GOOGLE_CLOUD_PROJECT', 'amazon-ppc-474902'))
    BIGQUERY_DATASET: str = os.getenv('BIGQUERY_DATASET', 'amazon_ppc')
    REGION: str = 'us-central1'
    
    # Secret names
    AMAZON_ADS_SECRET: str = 'NEW_AMAZON_CLIENT_ID'
    AMAZON_SP_SECRET: str = 'amazon-sp-default'

settings = Settings()
EOF
