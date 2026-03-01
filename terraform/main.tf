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

# Artifact Registry
resource "google_artifact_registry_repository" "anchor" {
  location      = var.region
  repository_id = "anchor"
  format        = "DOCKER"
}

# Cloud Run — Backend
resource "google_cloud_run_v2_service" "backend" {
  name     = "anchor-backend"
  location = var.region

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/anchor/backend:latest"
      ports {
        container_port = 8000
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_REGION"
        value = var.region
      }
    }
  }
}

# Allow unauthenticated access to Cloud Run
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Firestore database
resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
}
