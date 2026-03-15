variable "project_id" {
  description = "Google Cloud project ID"
  type        = string
}

variable "region" {
  description = "Google Cloud region"
  type        = string
  default     = "europe-west1"
}

variable "gemini_model" {
  description = "Gemini model ID for live audio"
  type        = string
  default     = "gemini-2.5-flash-native-audio-latest"
}

variable "imagen_model" {
  description = "Vertex AI Imagen model ID"
  type        = string
  default     = "imagegeneration@006"
}

variable "firestore_collection" {
  description = "Firestore collection name for sessions"
  type        = string
  default     = "sessions"
}

variable "max_instances" {
  description = "Maximum Cloud Run instances"
  type        = number
  default     = 5
}

variable "frontend_url" {
  description = "Frontend URL (Firebase Hosting) for CORS"
  type        = string
  default     = ""
}

variable "github_owner" {
  description = "GitHub repository owner"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
}
