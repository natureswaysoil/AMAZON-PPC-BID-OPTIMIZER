#!/bin/bash
# scripts/setup.sh

set -e

PROJECT_ID=$1
REGION=${2:-us-central1}

if [ -z "$PROJECT_ID" ]; then
  echo "Usage: ./setup.sh PROJECT_ID [REGION]"
  exit 1
fi

echo "Setting up Amazon PPC Optimizer for project: $PROJECT_ID"

# Enable required APIs
echo "Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  bigquery.googleapis.com \
  secretmanager.googleapis.com \
  --project=$PROJECT_ID

# Create BigQuery dataset
echo "Creating BigQuery dataset..."
bq mk --dataset \
  --location=US \
  --description="Amazon PPC Data Warehouse" \
  $PROJECT_ID:amazon_data

# Create secrets
echo "Creating secret placeholders..."
echo "Please update these with your actual credentials:"

echo '{"client_id":"","client_secret":"","refresh_token":"","profile_id":""}' | \
  gcloud secrets create NEW_AMAZON_CLIENT_ID \
    --data-file=- \
    --project=$PROJECT_ID

echo '{"client_secret":""}' | \
  gcloud secrets create NEW_AMAZON_CLIENT_SECRET \
    --data-file=- \
    --project=$PROJECT_ID

echo '{"refresh_token":""}' | \
  gcloud secrets create NEW_AMAZON_REFRESH_TOKEN \
    --data-file=- \
    --project=$PROJECT_ID

# Deploy infrastructure with Terraform
echo "Deploying infrastructure..."
cd infrastructure/terraform
terraform init
terraform plan -var="project_id=$PROJECT_ID" -var="region=$REGION"
terraform apply -var="project_id=$PROJECT_ID" -var="region=$REGION" -auto-approve

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Update secrets in Google Secret Manager with your Amazon credentials"
echo "2. Run: gcloud builds submit --config cloudbuild.yaml"
echo "3. Access dashboard at: https://amazon-ppc-dashboard-[hash]-$REGION.run.app"
