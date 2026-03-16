terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "anchor-erp-therapy-tfstate"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# ---------- Data sources ----------

data "google_project" "current" {
  project_id = var.project_id
}

# ---------- API enablement ----------

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "firestore.googleapis.com",
    "aiplatform.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
    "compute.googleapis.com",
  ])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# ---------- Artifact Registry ----------

resource "google_artifact_registry_repository" "anchor" {
  location      = var.region
  repository_id = "anchor"
  format        = "DOCKER"

  depends_on = [google_project_service.apis["artifactregistry.googleapis.com"]]
}

# ---------- Secret Manager ----------

resource "google_secret_manager_secret" "google_genai_api_key" {
  secret_id = "google-genai-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret" "ws_auth_token" {
  secret_id = "ws-auth-token"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret" "basic_auth_htpasswd" {
  secret_id = "basic-auth-htpasswd"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

# ---------- Firestore ----------

resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis["firestore.googleapis.com"]]
}

resource "google_firebaserules_ruleset" "firestore" {
  provider = google-beta

  source {
    files {
      name = "firestore.rules"
      content = <<-EOT
        rules_version = '2';
        service cloud.firestore {
          match /databases/{database}/documents {
            match /{document=**} {
              allow read, write: if false;
            }
          }
        }
      EOT
    }
  }
}

resource "google_firebaserules_release" "firestore" {
  provider     = google-beta
  name         = "cloud.firestore/database/${google_firestore_database.default.name}"
  ruleset_name = google_firebaserules_ruleset.firestore.name
}

# ---------- Cloud Run — Backend ----------

resource "google_cloud_run_v2_service" "backend" {
  name     = "anchor-backend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.backend.email
    timeout         = "3600s"

    scaling {
      min_instance_count = 0
      max_instance_count = var.max_instances
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/anchor/backend:latest"

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      startup_probe {
        http_get {
          path = "/api/health"
          port = 8000
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        failure_threshold     = 3
      }

      # --- Plain env vars ---
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_REGION"
        value = var.region
      }
      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
      env {
        name  = "IMAGEN_MODEL"
        value = var.imagen_model
      }
      env {
        name  = "VERTEX_LOCATION"
        value = var.region
      }
      env {
        name  = "FIRESTORE_COLLECTION"
        value = var.firestore_collection
      }
      env {
        name  = "GEMINI_TEXT_MODEL"
        value = var.gemini_text_model
      }
      env {
        name  = "GEMINI_PRO_MODEL"
        value = var.gemini_pro_model
      }
      env {
        name  = "FRONTEND_URL"
        value = google_cloud_run_v2_service.frontend.uri
      }

      # --- Secret env vars ---
      env {
        name = "GOOGLE_GENAI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.google_genai_api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "WS_AUTH_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.ws_auth_token.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_artifact_registry_repository.anchor,
  ]
}

# ---------- Cloud Run — Frontend ----------

resource "google_cloud_run_v2_service" "frontend" {
  name     = "anchor-frontend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/anchor/frontend:latest"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      startup_probe {
        http_get {
          path = "/healthz"
          port = 8080
        }
        initial_delay_seconds = 2
        period_seconds        = 5
        failure_threshold     = 3
      }

      env {
        name = "BASIC_AUTH_HTPASSWD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.basic_auth_htpasswd.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_artifact_registry_repository.anchor,
  ]
}

# ---------- Cloud Build trigger ----------

resource "google_cloudbuild_trigger" "main_push" {
  name     = "anchor-deploy-main"
  location = var.region

  github {
    owner = var.github_owner
    name  = var.github_repo

    push {
      branch = "^main$"
    }
  }

  filename = "cloudbuild.yaml"

  substitutions = {
    _REGION = var.region
  }

  depends_on = [google_project_service.apis["cloudbuild.googleapis.com"]]
}
