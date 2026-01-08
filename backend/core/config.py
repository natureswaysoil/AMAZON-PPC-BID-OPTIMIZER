import os
from dataclasses import dataclass
from pydantic_settings import BaseSettings

@dataclass
class AOVTier:
    name: str
    min_aov: float
    max_aov: float # Consider this an exclusive upper bound for lookup clarity
    base_ceiling_exact: float

# AOV-based bid ceilings
# Making max_aov an exclusive upper bound for clearer range definition
AOV_TIERS = {
    'L': AOVTier('Low', 18.0, 30.0, 1.05),    # $18-29.99 products (max_aov is exclusive)
    'M': AOVTier('Mid', 30.0, 46.0, 1.45),    # $30-45.99 products
    'H': AOVTier('High', 46.0, 70.0, 1.95),   # $46-69.99 products
    'X': AOVTier('Premium', 70.0, 999.0, 2.50) # $70+ products
}

# Performance tier multipliers
PERFORMANCE_MULTIPLIERS = {
    'A': 1.00,  # Winners
    'B': 0.85,  # Solid
    'C': 0.65,  # Testing
    'D': 0.40,  # Bleeding
    'E': 0.15   # Kill zone
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
    (16, 18),  # 4-6 PM (hour 16 and 17)
    (18, 20),  # 6-8 PM (hour 18 and 19)
    (20, 22),  # 8-10 PM (hour 20 and 21)
]

def get_time_multiplier(hour: int, performance_tier: str,
                        off_hours_mult: float = 0.90,
                        prime_a_mult: float = 1.10,
                        prime_other_mult: float = 1.00) -> float:
    """Get bid multiplier based on time and performance.
    Applies prime_a_mult/prime_other_mult to all defined PRIME_HOURS.
    """
    is_prime_hour = False
    for start, end in PRIME_HOURS:
        if start <= hour < end: # hour is >= start and < end
            is_prime_hour = True
            break # Found a prime window, no need to check further

    if is_prime_hour:
        return prime_a_mult if performance_tier == 'A' else prime_other_mult
    else:
        return off_hours_mult

# Safety limits
MAX_BID_AS_PERCENT_OF_AOV = 0.07  # Never bid more than 7% of AOV
MIN_CONVERSIONS_FOR_PROMOTION = 2
TARGET_ACOS_DEFAULT = 0.30

class Settings(BaseSettings):
    """Application settings using pydantic-settings"""
    PROJECT_ID: str = ""
    BIGQUERY_DATASET: str = "amazon_ppc"
    REGION: str = "us-central1"
    TIMEZONE: str = "America/New_York"
    
    # Bid rails
    MIN_BID: float = 0.35
    MAX_BID: float = 7.00
    
    # Suggested bid blending
    SUGGEST_BLEND: float = 0.70
    MAX_UP_PCT_PER_RUN: float = 0.20
    MAX_DOWN_PCT_PER_RUN: float = 0.25
    
    # Safety gates
    PAUSE_CLICKS_MIN: int = 15
    PAUSE_SPEND_MIN: float = 18.0
    LOSE_CLICKS_MIN: int = 10
    LOSE_SPEND_MIN: float = 10.0
    
    # Secret names
    AMAZON_CLIENT_ID_SECRET: str = "amazon_client_id"
    AMAZON_CLIENT_SECRET_SECRET: str = "amazon_client_secret"
    AMAZON_REFRESH_TOKEN_SECRET: str = "amazon_refresh_token"
    AMAZON_PROFILE_ID_SECRET: str = "amazon_profile_id"
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # If PROJECT_ID not set, try GOOGLE_CLOUD_PROJECT
        if not self.PROJECT_ID:
            self.PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT', '')

settings = Settings()
