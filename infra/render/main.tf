# Mirrors /render.yaml as closely as the Render Terraform provider allows.
#
# Note: Blueprint still supports plan = free for the live demo. The provider's
# web_service plan enum is starter+ — so this module uses starter. Postgres can
# stay on free. Don't apply on top of the existing Blueprint demo unless you
# intend a second environment (or terraform import).

resource "render_postgres" "db" {
  name    = "${var.name_prefix}-db"
  plan    = "free"
  region  = var.region
  version = "16"
}

resource "render_web_service" "app" {
  name   = "${var.name_prefix}-dashboard"
  plan   = "starter"
  region = var.region

  runtime_source = {
    docker = {
      repo_url        = var.repo_url
      branch          = var.branch
      auto_deploy     = true
      dockerfile_path = "./Dockerfile"
    }
  }

  health_check_path = "/health"

  env_vars = {
    ENVIRONMENT = { value = "production" }
    DATABASE_URL = {
      value = render_postgres.db.connection_info.internal_connection_string
    }
    SESSION_SECRET = {
      generate_value = true
    }
    GOOGLE_CLIENT_ID = {
      value = var.google_client_id
    }
    GOOGLE_CLIENT_SECRET = {
      value = var.google_client_secret
    }
    ENTRA_CLIENT_ID = {
      value = var.entra_client_id
    }
    ENTRA_CLIENT_SECRET = {
      value = var.entra_client_secret
    }
    ENTRA_TENANT_ID = {
      value = var.entra_tenant_id
    }
  }
}
