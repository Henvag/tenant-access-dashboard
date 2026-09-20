output "web_service_url" {
  description = "Public URL of the web service (after first deploy)."
  value       = try(render_web_service.app.url, null)
}

output "postgres_id" {
  value = render_postgres.db.id
}

output "web_service_id" {
  value = render_web_service.app.id
}
