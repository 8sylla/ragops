# GKE Autopilot cluster and an Artifact Registry repository for the API image.

terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "apis" {
  for_each           = toset(["container.googleapis.com", "artifactregistry.googleapis.com"])
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "images" {
  repository_id = "ragops"
  location      = var.region
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

resource "google_container_cluster" "autopilot" {
  name                = "ragops"
  location            = var.region
  enable_autopilot    = true
  deletion_protection = false
  depends_on          = [google_project_service.apis]
}
