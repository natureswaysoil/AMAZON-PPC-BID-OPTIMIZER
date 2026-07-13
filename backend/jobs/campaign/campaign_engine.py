"""Campaign Engine - Product to Campaign Builder"""

from __future__ import annotations
import csv
import io
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

BASE_DIR = Path(__file__).parent
PRODUCTS_CSV_URL = os.getenv(
    "PRODUCTS_CSV_URL",
    "https://docs.google.com/spreadsheets/d/1dtUYrSy18_D2updwCpVa5wXfgf0hzAXaiQTQqMQnrSc/export?format=csv",
)

# ====================== HELPERS ======================
def normalize(text: str) -> str:
    """Normalize text for keyword matching"""
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def slugify(text: str) -> str:
    """Convert text to URL-safe slug"""
    text = normalize(text).replace(" ", "_")
    return re.sub(r"_+", "_", text).strip("_")[:60] or "product"

def split_keywords(value: str) -> List[str]:
    """Split comma/newline separated keywords"""
    if not value: return []
    parts = re.split(r"[\n,;|]+", str(value))
    out: List[str] = []
    seen = set()
    for part in parts:
        kw = normalize(part)
        if kw and kw not in seen:
            seen.add(kw)
            out.append(kw)
    return out

def first(row: Dict[str, Any], *names: str, default: str = "") -> str:
    """Get first non-empty value from row by multiple possible column names"""
    lower_map = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        value = row.get(name) or lower_map.get(name.lower())
        if value not in (None, ""):
            return str(value).strip()
    return default

def money(value: Any, default: float = 0.0) -> float:
    """Parse money value"""
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except Exception:
        return default

def is_real_product_row(row: Dict[str, Any]) -> bool:
    """Filter out header rows and incomplete products"""
    product_id = first(row, "Product_ID", "Product ID", default="")
    sku = first(row, "SKU", default="")
    asin = first(row, "ASIN", default="")
    title = first(row, "Title", "Product_Name", "Product Name", default="")
    lower_values = {product_id.lower(), sku.lower(), asin.lower(), title.lower()}
    if {"product_id", "sku", "asin", "title"} & lower_values:
        return False
    if not any([product_id, sku, asin, title]) or not any([sku, asin]):
        return False
    return True

def clean_product_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove header rows and incomplete products"""
    return [row for row in rows if is_real_product_row(row)]

def load_products_from_sheet(url: str = PRODUCTS_CSV_URL) -> List[Dict[str, str]]:
    """Load products from Google Sheet CSV export"""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    reader = csv.DictReader(io.StringIO(response.text))
    rows = [{str(k).strip(): (v or "").strip() for k, v in row.items()} for row in reader]
    return clean_product_rows(rows)

def product_name(row: Dict[str, Any]) -> str:
    """Extract product name from row"""
    return first(row, "Product_Name", "Product Name", "Title", "SKU", "ASIN", default="Product")

def keyword_groups(row: Dict[str, Any]) -> Dict[str, List[str]]:
    """Extract keyword groups from product row"""
    return {
        "EXACT_Core": split_keywords(first(row, "Keywords", "Core_Keywords", "Core Keywords")),
        "PHRASE_Research": split_keywords(first(row, "Research_Keywords", "Research Keywords", "Problem_Keywords", "Problem Keywords")),
        "EXACT_Long_Tail": split_keywords(first(row, "Long_Tail_Keywords", "Long Tail Keywords")),
        "COMPETITOR": split_keywords(first(row, "Competitor_Keywords", "Competitor Keywords")),
        "negative_phrase": split_keywords(first(row, "Negative_Phrase", "Negative Phrase")),
        "negative_exact": split_keywords(first(row, "Negative_Exact", "Negative Exact")),
        "ingredient": split_keywords(first(row, "Ingredient_Keywords", "Ingredient Keywords")),
        "problem": split_keywords(first(row, "Problem_Keywords", "Problem Keywords")),
    }

def merge_unique(*groups: List[str]) -> List[str]:
    """Merge multiple keyword lists removing duplicates"""
    out: List[str] = []
    seen = set()
    for group in groups:
        for item in group:
            if item and item not in seen:
                seen.add(item)
                out.append(item)
    return out

# ====================== CAMPAIGN ENGINE ======================
class CampaignEngine:
    """Build optimized campaign plans from product data"""
    
    def __init__(self, target_acos: float = 0.35, product_margin: float = 0.40,
                 max_bid: float = 3.50, min_bid: float = 0.30):
        self.target_acos = target_acos
        self.product_margin = product_margin
        self.max_bid = max_bid
        self.min_bid = min_bid

    def generate_long_tail_keywords(self, product: Dict[str, str], num_variations: int = 12) -> List[str]:
        """Generate long-tail keyword variations from product title"""
        title = product.get("title", "") or product.get("Product_Name", "") or product.get("Title", "") or product_name(product)
        words = title.lower().split()
        seed = words[0] if words else "product"
        patterns = [
            f"{seed} for raised beds",
            f"best {seed} for vegetables",
            f"organic living {seed}",
            f"{seed} with beneficial microbes",
        ]
        return list(dict.fromkeys(patterns))[:num_variations]

    def build_broad_match_campaign(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Build a broad-match discovery campaign"""
        short_name = slugify(product_name(product))[:40]
        keywords = self.generate_long_tail_keywords(product)
        return {
            "campaign_type": "BROAD_Discovery",
            "campaign_name": f"BROAD_Discovery_{short_name}",
            "match_type": "broad",
            "purpose": "Discovery + volume ramp",
            "daily_budget": 20.0,
            "default_bid": 0.75,
            "min_bid": self.min_bid,
            "max_bid": self.max_bid,
            "keywords": [{"keywordText": kw, "matchType": "broad"} for kw in keywords],
            "negative_keywords": [],
            "bidding_strategy": "dynamicBidsUpAndDown",
            "keyword_count": len(keywords)
        }

    def harvest_search_terms_to_exact_phrase(self, search_terms_df: Optional[pd.DataFrame], 
                                              min_orders: int = 1, max_acos: float = 0.50) -> List[Dict[str, Any]]:
        """Convert winning search terms to exact/phrase keywords"""
        if search_terms_df is None or len(search_terms_df) == 0:
            return []

        df = search_terms_df.copy()
        col_map = {
            "Customer Search Term": "search_term",
            "Search Term": "search_term",
            "search_term": "search_term",
            "7 Day Total Orders (#)": "orders",
            "Orders": "orders",
            "orders": "orders",
            "Total Advertising Cost of Sales (ACOS)": "acos",
            "ACOS": "acos",
            "acos": "acos",
            "Clicks": "clicks",
            "clicks": "clicks",
        }
        for old, new in col_map.items():
            if old in df.columns:
                df = df.rename(columns={old: new})

        if "orders" not in df.columns:
            df["orders"] = 0
        if "acos" not in df.columns:
            df["acos"] = 999
        if "clicks" not in df.columns:
            df["clicks"] = 0
        if "search_term" not in df.columns:
            return []

        df["orders"] = pd.to_numeric(df["orders"], errors="coerce").fillna(0)
        df["clicks"] = pd.to_numeric(df["clicks"], errors="coerce").fillna(0)
        df["acos"] = df["acos"].apply(lambda v: money(v, 999))
        df.loc[df["acos"] > 1, "acos"] = df.loc[df["acos"] > 1, "acos"] / 100.0

        winners = df[(df["orders"] >= min_orders) & (df["acos"] <= max_acos) & (df["clicks"] >= 3)].copy()

        harvested: List[Dict[str, Any]] = []
        for _, row in winners.iterrows():
            term = str(row.get("search_term") or "").strip()
            if not term:
                continue
            match_type = "exact" if len(term.split()) > 5 else "phrase"
            harvested.append({
                "keywordText": term,
                "matchType": match_type,
                "bid": round(1.2 * 1.15, 2),
                "reason": f"{int(row.get('orders',0))} orders @ ACOS {float(row.get('acos',0)):.1%}"
            })
        return harvested[:60]

    def decide_bid(self, row: Dict[str, Any], current_bid: float) -> Dict[str, Any]:
        """Decide bid adjustment based on performance"""
        spend = money(row.get("spend") or row.get("cost"), 0)
        orders = int(row.get("orders", 0) or row.get("purchases7d", 0))
        acos = money(row.get("acos"), 999)
        if acos > 1:
            acos = acos / 100.0
        clicks = int(row.get("clicks", 0))
        conv_rate = (orders / clicks) if clicks > 0 else 0.0

        if spend > 120 and orders < 2:
            new_bid = round(max(current_bid * 0.60, self.min_bid), 2)
            return {"action": "decrease", "new_bid": new_bid, "reason": "CASH PROTECTION - high spend, low orders"}

        if orders >= 3 and acos <= self.target_acos * 0.90:
            multiplier = 1.32 if conv_rate >= 0.13 else 1.24
            new_bid = round(min(current_bid * multiplier, self.max_bid), 2)
        elif orders >= 2 and acos <= self.target_acos * 0.95:
            new_bid = round(min(current_bid * 1.22, self.max_bid), 2)
        elif orders >= 1 and acos <= self.target_acos * 1.08:
            new_bid = round(min(current_bid * 1.15, self.max_bid), 2)
        elif acos > self.target_acos * 1.45 or (clicks > 15 and orders == 0):
            new_bid = round(max(current_bid * 0.75, self.min_bid), 2)
        else:
            new_bid = current_bid

        action = "increase" if new_bid > current_bid else "decrease" if new_bid < current_bid else "hold"
        return {"action": action, "new_bid": new_bid, "reason": f"Orders:{orders} ACOS:{acos:.1%} CR:{conv_rate:.1%}"}


def build_campaign_plan(row: Dict[str, Any], 
                       search_terms_df: Optional[pd.DataFrame] = None,
                       target_acos: float = 0.35) -> Dict[str, Any]:
    """Build complete campaign plan from product row"""
    engine = CampaignEngine(target_acos=target_acos, product_margin=0.40)

    groups = keyword_groups(row)
    name = product_name(row)
    slug = slugify(name)
    asin = first(row, "ASIN")
    sku = first(row, "SKU")

    groups["EXACT_Core"] = merge_unique(groups["EXACT_Core"], groups["ingredient"])
    groups["PHRASE_Research"] = merge_unique(groups["PHRASE_Research"], groups["problem"], groups["ingredient"])

    campaigns: List[Dict[str, Any]] = []

    # Build standard campaigns
    campaign_types = {
        "EXACT_Core": {"keywords": groups["EXACT_Core"], "daily_budget": 30.0, "default_bid": 0.85},
        "PHRASE_Research": {"keywords": groups["PHRASE_Research"], "daily_budget": 20.0, "default_bid": 0.55},
        "EXACT_Long_Tail": {"keywords": groups["EXACT_Long_Tail"], "daily_budget": 15.0, "default_bid": 0.45},
        "COMPETITOR": {"keywords": groups["COMPETITOR"], "daily_budget": 15.0, "default_bid": 0.65},
    }

    for campaign_type, config in campaign_types.items():
        keywords = config.get("keywords", [])
        daily_budget = money(first(row, "Daily_Budget", "Daily Budget"), float(config.get("daily_budget", 5.0)))
        default_bid = money(first(row, "Default_Bid", "Default Bid"), float(config.get("default_bid", 0.55)))

        campaigns.append({
            "campaign_type": campaign_type,
            "campaign_name": f"SP_{campaign_type}_{slug}",
            "match_type": "exact" if "EXACT" in campaign_type else "phrase",
            "purpose": f"{campaign_type} campaigns",
            "daily_budget": daily_budget,
            "default_bid": default_bid,
            "min_bid": money(first(row, "Min_Bid", "Min Bid"), 0.25),
            "max_bid": money(first(row, "Max_Bid", "Max Bid"), 3.50),
            "keywords": [{"keywordText": kw, "matchType": "exact" if "EXACT" in campaign_type else "phrase"} for kw in keywords],
            "keyword_count": len(keywords),
            "negative_keywords": [],
            "bidding_strategy": "dynamicBidsUpAndDown"
        })

    # Add broad discovery campaign
    broad_camp = engine.build_broad_match_campaign(row)
    campaigns.append(broad_camp)
    
    # Harvest winning search terms
    harvested = engine.harvest_search_terms_to_exact_phrase(search_terms_df) if search_terms_df is not None else []

    return {
        "product_name": name,
        "product_slug": slug,
        "asin": asin,
        "sku": sku,
        "target_acos": target_acos,
        "campaigns": campaigns,
        "harvested_keywords": harvested,
        "total_keywords": sum(c.get("keyword_count", 0) for c in campaigns) + len(harvested),
    }
