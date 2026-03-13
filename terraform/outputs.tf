output "backend_url" {
  description = "Cloud Run backend HTTPS URL"
  value       = google_cloud_run_v2_service.backend.uri
}

output "backend_ws_url" {
  description = "WebSocket URL for frontend connection"
  value       = "wss://${replace(google_cloud_run_v2_service.backend.uri, "https://", "")}/ws/session"
}

output "artifact_registry" {
  description = "Docker image registry path"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.anchor.repository_id}"
}

output "service_account_email" {
  description = "Backend service account email"
  value       = google_service_account.backend.email
}

output "secret_ids" {
  description = "Secret Manager secret IDs (add values manually)"
  value = {
    genai_api_key = google_secret_manager_secret.google_genai_api_key.secret_id
    ws_auth_token = google_secret_manager_secret.ws_auth_token.secret_id
  }
}

output "post_apply_instructions" {
  description = "Manual steps after terraform apply"
  value       = <<-EOT

    ┌─────────────────────────────────────────────────────┐
    │              Post-apply manual steps                 │
    ├─────────────────────────────────────────────────────┤
    │                                                     │
    │  1. Add secret values:                              │
    │     echo -n "YOUR_KEY" | gcloud secrets versions    │
    │       add google-genai-api-key --data-file=-        │
    │     echo -n "YOUR_TOKEN" | gcloud secrets versions  │
    │       add ws-auth-token --data-file=-               │
    │                                                     │
    │  2. Connect GitHub repo in Cloud Build console      │
    │     (first time only)                               │
    │                                                     │
    │  3. Build & push initial backend image:             │
    │     gcloud builds submit --tag                      │
    │       ${var.region}-docker.pkg.dev/${var.project_id}/anchor/backend │
    │                                                     │
    └─────────────────────────────────────────────────────┘
  EOT
}
