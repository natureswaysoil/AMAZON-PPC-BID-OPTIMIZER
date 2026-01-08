import os
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

def get_time_multiplier(hour: int, performance_tier: str,
                        off_hours_mult: float = 0.90,
                        prime_a_mult: float = 1.10,
                        prime_other_mult: float = 1.00) -> float:
    """Get bid multiplier based on time and performance."""
    in_prime = any(start <= hour < end for start, end in PRIME_HOURS)

    if not in_prime:
        return off_hours_mult

    # During prime time
    if 18 <= hour < 22:
        return prime_a_mult if performance_tier == 'A' else prime_other_mult

    return 1.00

# Safety limits
MAX_BID_AS_PERCENT_OF_AOV = 0.07  # Never bid more than 7% of AOV
MIN_CONVERSIONS_FOR_PROMOTION = 2
TARGET_ACOS_DEFAULT = 0.30

class Settings:
    PROJECT_ID: str = os.getenv('PROJECT_ID', os.getenv('GOOGLE_CLOUD_PROJECT', 'amazon-ppc-474902'))
    BIGQUERY_DATASET: str = os.getenv('BIGQUERY_DATASET', 'amazon_ppc')
    REGION: str = os.getenv('REGION', 'us-central1')

    # Timezone (so prime hours are correct)
    TIMEZONE: str = os.getenv("TIMEZONE", "America/New_York")

    # Bid rails
    MIN_BID: float = float(os.getenv("MIN_BID", "0.35"))
    MAX_BID: float = float(os.getenv("MAX_BID", "7.00"))

    # Suggested bid blending
    SUGGEST_BLEND: float = float(os.getenv("SUGGEST_BLEND", "0.70"))
    MAX_UP_PCT_PER_RUN: float = float(os.getenv("MAX_UP_PCT_PER_RUN", "0.20"))
    MAX_DOWN_PCT_PER_RUN: float = float(os.getenv("MAX_DOWN_PCT_PER_RUN", "0.25"))

    # Safety gates
    PAUSE_CLICKS_MIN: int = int(os.getenv("PAUSE_CLICKS_MIN", "15"))
    PAUSE_SPEND_MIN: float = float(os.getenv("PAUSE_SPEND_MIN", "18.0"))
    LOSE_CLICKS_MIN: int = int(os.getenv("LOSE_CLICKS_MIN", "10"))
    LOSE_SPEND_MIN: float = float(os.getenv("LOSE_SPEND_MIN", "10.0"))

    # Secret names (make sure these match Secret Manager)
    AMAZON_CLIENT_ID_SECRET: str = os.getenv("AMAZON_CLIENT_ID_SECRET", "amazon_client_id")
    AMAZON_CLIENT_SECRET_SECRET: str = os.getenv("AMAZON_CLIENT_SECRET_SECRET", "amazon_client_secret")
    AMAZON_REFRESH_TOKEN_SECRET: str = os.getenv("AMAZON_REFRESH_TOKEN_SECRET", "amazon_refresh_token")
    AMAZON_PROFILE_ID_SECRET: str = os.getenv("AMAZON_PROFILE_ID_SECRET", "amazon_profile_id")

settings = Settings()
