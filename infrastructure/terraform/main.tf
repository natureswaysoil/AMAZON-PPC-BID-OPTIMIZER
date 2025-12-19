# infrastructure/terraform/main.tf
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# BigQuery Dataset
resource "google_bigquery_dataset" "amazon_data" {
  dataset_id                  = "amazon_data"
  friendly_name               = "Amazon PPC Data"
  description                 = "Data warehouse for Amazon advertising and sales data"
  location                    = "US"
  default_table_expiration_ms = null

  labels = {
    environment = var.environment
    app         = "amazon-ppc-optimizer"
  }
}

# Cloud Run Jobs
resource "google_cloud_run_v2_job" "ads_sync" {
  name     = "ads-data-sync"
  location = var.region

  template {
    template {
      containers {
        image = "gcr.io/${var.project_id}/amazon-ppc-backend:latest"
        
        env {
          name  = "JOB_TYPE"
          value = "ads_sync"
        }
        
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        
        resources {
          limits = {
            cpu    = "2"
            memory = "2Gi"
          }
        }
      }
      
      timeout = "1800s"
    }
  }
}

resource "google_cloud_run_v2_job" "orders_sync" {
  name     = "orders-sync"
  location = var.region

  template {
    template {
      containers {
        image = "gcr.io/${var.project_id}/amazon-ppc-backend:latest"
        
        env {
          name  = "JOB_TYPE"
          value = "orders_sync"
        }
        
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
      }
      
      timeout = "1800s"
    }
  }
}

resource "google_cloud_run_v2_job" "bid_optimizer" {
  name     = "bid-optimizer"
  location = var.region

  template {
    template {
      containers {
        image = "gcr.io/${var.project_id}/amazon-ppc-backend:latest"
        
        env {
          name  = "JOB_TYPE"
          value = "bid_optimizer"
        }
        
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
      }
      
      timeout = "3600s"
    }
  }
}

resource "google_cloud_run_v2_job" "keyword_harvester" {
  name     = "keyword-harvester"
  location = var.region

  template {
    template {
      containers {
        image = "gcr.io/${var.project_id}/amazon-ppc-backend:latest"
        
        env {
          name  = "JOB_TYPE"
          value = "keyword_harvest"
        }
        
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
      }
      
      timeout = "1800s"
    }
  }
}

resource "google_cloud_run_v2_job" "alert_engine" {
  name     = "alert-engine"
  location = var.region

  template {
    template {
      containers {
        image = "gcr.io/${var.project_id}/amazon-ppc-backend:latest"
        
        env {
          name  = "JOB_TYPE"
          value = "alerts"
        }
        
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
      }
      
      timeout = "900s"
    }
  }
}

# Cloud Scheduler Jobs
resource "google_cloud_scheduler_job" "ads_sync_schedule" {
  name             = "ads-sync-schedule"
  description      = "Sync Amazon Ads data every 6 hours"
  schedule         = "0 */6 * * *"
  time_zone        = "America/New_York"
  attempt_deadline = "1800s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/ads-data-sync:run"
    
    oauth_token {
      service_account_email = google_service_account.cloud_run_invoker.email
    }
  }
}

resource "google_cloud_scheduler_job" "orders_sync_schedule" {
  name             = "orders-sync-schedule"
  description      = "Sync orders daily"
  schedule         = "0 2 * * *"
  time_zone        = "America/New_York"
  attempt_deadline = "1800s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/orders-sync:run"
    
    oauth_token {
      service_account_email = google_service_account.cloud_run_invoker.email
    }
  }
}

resource "google_cloud_scheduler_job" "bid_optimizer_schedule" {
  name             = "bid-optimizer-schedule"
  description      = "Run bid optimization every 4 hours"
  schedule         = "0 */4 * * *"
  time_zone        = "America/New_York"
  attempt_deadline = "3600s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/bid-optimizer:run"
    
    oauth_token {
      service_account_email = google_service_account.cloud_run_invoker.email
    }
  }
}

resource "google_cloud_scheduler_job" "keyword_harvest_schedule" {
  name             = "keyword-harvest-schedule"
  description      = "Harvest keywords weekly"
  schedule         = "0 3 * * 1"  # Monday 3am
  time_zone        = "America/New_York"
  attempt_deadline = "1800s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/keyword-harvester:run"
    
    oauth_token {
      service_account_email = google_service_account.cloud_run_invoker.email
    }
  }
}

resource "google_cloud_scheduler_job" "alerts_schedule" {
  name             = "alerts-schedule"
  description      = "Check for alerts every hour"
  schedule         = "0 * * * *"
  time_zone        = "America/New_York"
  attempt_deadline = "900s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/alert-engine:run"
    
    oauth_token {
      service_account_email = google_service_account.cloud_run_invoker.email
    }
  }
}

# Service Account for Cloud Scheduler
resource "google_service_account" "cloud_run_invoker" {
  account_id   = "cloud-run-invoker"
  display_name = "Cloud Run Job Invoker"
}

resource "google_cloud_run_v2_job_iam_member" "invoker" {
  for_each = toset([
    google_cloud_run_v2_job.ads_sync.name,
    google_cloud_run_v2_job.orders_sync.name,
    google_cloud_run_v2_job.bid_optimizer.name,
    google_cloud_run_v2_job.keyword_harvester.name,
    google_cloud_run_v2_job.alert_engine.name,
  ])

  name     = each.value
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.cloud_run_invoker.email}"
}

# Frontend Cloud Run Service
resource "google_cloud_run_v2_service" "dashboard" {
  name     = "amazon-ppc-dashboard"
  location = var.region

  template {
    containers {
      image = "gcr.io/${var.project_id}/amazon-ppc-frontend:latest"
      
      ports {
        container_port = 3000
      }
      
      env {
        name  = "NEXT_PUBLIC_API_URL"
        value = "https://api-${var.region}.run.app"
      }
      
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
    
    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# Allow unauthenticated access to dashboard
resource "google_cloud_run_v2_service_iam_member" "dashboard_public" {
  name     = google_cloud_run_v2_service.dashboard.name
  location = google_cloud_run_v2_service.dashboard.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
