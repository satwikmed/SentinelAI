# Minimal Terraform for SentinelAI cloud secrets / config.
# Demonstrates IaC for the LLM provider configuration surface.
# Apply after creating a Fly.io app (or adapt for your cloud).

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

variable "app_name" {
  type        = string
  description = "Fly.io app name for the SentinelAI API"
  default     = "sentinelai-gateway"
}

variable "openai_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "anthropic_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "google_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

# Writes a deployable secrets env file (gitignored in practice via fly secrets).
resource "local_sensitive_file" "provider_secrets" {
  filename = "${path.module}/generated/provider_secrets.env"
  content  = <<-EOT
    OPENAI_API_KEY=${var.openai_api_key}
    ANTHROPIC_API_KEY=${var.anthropic_api_key}
    GOOGLE_API_KEY=${var.google_api_key}
  EOT
}

# Documents the intended Fly secret sync step for operators.
resource "null_resource" "fly_secrets_instructions" {
  triggers = {
    app = var.app_name
    hash = sha256(local_sensitive_file.provider_secrets.content)
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "Terraform generated provider secrets for ${var.app_name}."
      echo "Sync to Fly with:"
      echo "  fly secrets set -a ${var.app_name} \$(grep -v '^$' ${path.module}/generated/provider_secrets.env | xargs)"
    EOT
  }
}

output "secrets_file" {
  value = local_sensitive_file.provider_secrets.filename
}

output "fly_app_name" {
  value = var.app_name
}
