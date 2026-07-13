"""FastAPI server for campaign management and data endpoints"""

import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional, List
import logging
import os

from core.config import settings
from jobs.campaign.campaign_creator import CampaignCreator
from jobs.campaign.campaign_engine import load_products_from_sheet, build_campaign_plan, first
from shared.amazon_client import AmazonAdsClient

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Amazon PPC Optimizer API",
    description="Campaign creation, management, and bid optimization",
    version="1.0.0"
)

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== CAMPAIGN ROUTES ====================

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "amazon-ppc-optimizer"}


@app.get("/api/campaign-products")
async def get_campaign_products(limit: int = 20):
    """Get available products for campaign creation"""
    try:
        products = load_products_from_sheet()
        preview = []
        
        for p in products[:limit]:
            plan = build_campaign_plan(p)
            preview.append({
                "sku": first(p, "SKU"),
                "asin": first(p, "ASIN"),
                "product_name": plan["product_name"],
                "total_keywords": plan["total_keywords"],
                "campaign_count": len(plan["campaigns"]),
                "estimated_daily_budget": sum(c.get("daily_budget", 0) for c in plan["campaigns"]),
            })
        
        return {
            "count": len(preview),
            "products": preview
        }
    except Exception as e:
        logger.error(f"Error fetching campaign products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/campaign-preview")
async def preview_campaign(payload: Dict[str, Any] = Body(...)):
    """Preview campaign plan for a product"""
    try:
        sku = payload.get("sku")
        if not sku:
            raise HTTPException(status_code=400, detail="SKU is required")
        
        # Load products and find matching product
        products = load_products_from_sheet()
        product = None
        for p in products:
            if first(p, "SKU") == sku:
                product = p
                break
        
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {sku} not found")
        
        # Build campaign plan
        plan = build_campaign_plan(product)
        
        return {
            "product_name": plan["product_name"],
            "product_sku": sku,
            "asin": first(product, "ASIN"),
            "campaigns": plan["campaigns"],
            "harvested_keywords": plan["harvested_keywords"],
            "total_keywords": plan["total_keywords"],
            "target_acos": plan["target_acos"],
            "estimated_daily_budget": sum(c.get("daily_budget", 0) for c in plan["campaigns"]),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/campaign-create")
async def create_campaign(payload: Dict[str, Any] = Body(...)):
    """Create campaign(s) for a product"""
    try:
        sku = payload.get("sku")
        if not sku:
            raise HTTPException(status_code=400, detail="SKU is required")
        
        daily_budget = payload.get("daily_budget")
        starting_bid = payload.get("starting_bid")
        dry_run = payload.get("dry_run", True)
        
        # Initialize campaign creator
        amazon_client = AmazonAdsClient()
        creator = CampaignCreator(amazon_client)
        
        # Launch campaign
        result = creator.launch_campaign_from_product(
            product_sku=sku,
            daily_budget=daily_budget,
            starting_bid=starting_bid,
            dry_run=dry_run
        )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== STARTUP ====================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )
