# cloudbuild.yaml
steps:
  # Build backend Docker image
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'gcr.io/$PROJECT_ID/amazon-ppc-backend:$COMMIT_SHA'
      - '-f'
      - 'backend/Dockerfile'
      - './backend'
  
  # Push backend image
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'gcr.io/$PROJECT_ID/amazon-ppc-backend:$COMMIT_SHA'
  
  # Build frontend Docker image
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'gcr.io/$PROJECT_ID/amazon-ppc-frontend:$COMMIT_SHA'
      - '-f'
      - 'frontend/Dockerfile'
      - './frontend'
  
  # Push frontend image
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'gcr.io/$PROJECT_ID/amazon-ppc-frontend:$COMMIT_SHA'
  
  # Deploy backend jobs
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'jobs'
      - 'update'
      - 'ads-data-sync'
      - '--image=gcr.io/$PROJECT_ID/amazon-ppc-backend:$COMMIT_SHA'
      - '--region=us-central1'
  
  # Deploy frontend service
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'amazon-ppc-dashboard'
      - '--image=gcr.io/$PROJECT_ID/amazon-ppc-frontend:$COMMIT_SHA'
      - '--region=us-central1'
      - '--platform=managed'
      - '--allow-unauthenticated'

timeout: 1200s
