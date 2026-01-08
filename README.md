# Amazon PPC Bid Optimizer

Automated bid optimization system for Amazon PPC campaigns using AOV-based dynamic ceilings and performance tiers.

## Features

- 🎯 AOV-aware bid optimization
- 📊 Performance tier classification (A-E)
- ⏰ Time-based bid adjustments
- 🔍 Match type multipliers
- 📈 BigQuery analytics integration
- 🔐 Google Cloud Secret Manager integration
- 🔄 Centralized Amazon API authentication with auto-refresh

## Architecture

- **Backend**: Python + Google Cloud Run Jobs
- **Frontend**: Next.js dashboard
- **Database**: BigQuery
- **Infrastructure**: Google Cloud Platform

## Authentication System

This project uses a unified authentication system for all Amazon API interactions:

- **Token Manager** (`backend/shared/token_manager.py`): Handles OAuth token refresh, caching, and validation
- **Amazon Client** (`backend/shared/amazon_client.py`): Unified API client with retry logic, rate limiting, and error handling

All jobs automatically use these shared modules - no need to handle authentication manually.

### Using the Amazon Client

```python
from shared.amazon_client import amazon_client

# Get keywords - authentication handled automatically
keywords = amazon_client.get_keywords(state_filter='enabled')

# Update bid
amazon_client.update_keyword_bid(keyword_id=12345, new_bid=1.50)

# Batch update bids
updates = [
    {'keyword_id': 123, 'new_bid': 1.50},
    {'keyword_id': 456, 'new_bid': 2.00}
]
amazon_client.update_keyword_bids_batch(updates)
```

The client automatically:
- ✅ Refreshes expired tokens
- ✅ Retries on 401 Unauthorized errors
- ✅ Handles rate limiting (429 responses)
- ✅ Provides detailed logging for debugging

## Setup

See [docs/setup-guide.md](docs/setup-guide.md) for detailed setup instructions.

## Configuration

Copy `.env.example` to `.env` and configure your settings:

```bash
cp .env.example .env
```

Edit `.env` with your project-specific values.

## Documentation

- [Architecture](docs/architecture.md)
- [Setup Guide](docs/setup-guide.md)
- [Optimization Strategy](docs/optimization-settings.md)
- [Deployment](docs/deployment.md)
- [Keyword Strategy](docs/keyword-strategy.md)
- [Alerts](docs/alerts.md)
- [Dashboard](docs/dashboard.md)
- [Dashboard Components](docs/dashboard-components.md)

## Project Structure

```
backend/
├── __init__.py
├── main.py                    # Main entry point
├── aov_fetcher.py            # AOV data fetcher
├── core/
│   ├── __init__.py
│   ├── config.py             # Configuration settings
│   ├── secrets.py            # Secret Manager integration
│   └── bigquery_client.py    # BigQuery wrapper
├── shared/                    # NEW: Shared authentication modules
│   ├── __init__.py
│   ├── token_manager.py      # OAuth token management
│   └── amazon_client.py      # Amazon Ads API client
└── jobs/
    ├── __init__.py
    └── optimization/
        ├── __init__.py
        └── aov_bid_optimizer.py  # Main optimization logic
```

## Running Locally

```bash
# Set environment variables
export PROJECT_ID=your-project-id
export GOOGLE_CLOUD_PROJECT=your-project-id

# Run the optimizer
python backend/main.py
```

## License

Proprietary

