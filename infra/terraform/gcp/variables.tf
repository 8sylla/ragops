variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "europe-west9" # Paris
}

output "cluster" {
  value = google_container_cluster.autopilot.name
}

output "image_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}
