# backend/shared/__init__.py
"""
Shared utilities for Amazon PPC Optimizer

Provides centralized authentication and API client for all jobs
"""
from shared.token_manager import token_manager, TokenManager
from shared.amazon_client import amazon_client, AmazonAdsClient

__all__ = [
    'token_manager',
    'TokenManager',
    'amazon_client',
    'AmazonAdsClient',
]
