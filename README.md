# Amazon PPC Bid Optimizer

Automated bid optimization system for Amazon PPC campaigns using AOV-based dynamic ceilings and performance tiers.

## Features

- 🎯 AOV-aware bid optimization
- 📊 Performance tier classification (A-E)
- ⏰ Time-based bid adjustments
- 🔍 Match type multipliers
- 📈 BigQuery analytics integration
- 🔐 Google Cloud Secret Manager integration

## Architecture

- **Backend**: Python + Google Cloud Run Jobs
- **Frontend**: Next.js dashboard
- **Database**: BigQuery
- **Infrastructure**: Google Cloud Platform

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

