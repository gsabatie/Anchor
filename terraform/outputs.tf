output "backend_url" {
  value = google_cloud_run_v2_service.backend.uri
}

output "artifact_registry" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.anchor.repository_id}"
}
