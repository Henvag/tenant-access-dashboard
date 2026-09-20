# Infra as code

Three layers, on purpose — not three ways to do the same thing blindly:

| Layer | File(s) | What it is |
| --- | --- | --- |
| **Render Blueprint** | `/render.yaml` | What the **live** Render demo uses today. One file → web + Postgres. |
| **Fly app config** | `/fly.toml` | Container-platform deploy config. Image build + HTTP service + health check. Deploy with `fly deploy`. |
| **Terraform (Render)** | `infra/render/` | Same shape as the Blueprint, expressed as state-managed resources — if you prefer `terraform apply` over “New → Blueprint”. |

I did **not** put Fly under Terraform. Fly’s older official provider is unmaintained; for this app `fly.toml` + `flyctl` is the honest, supported path. The dual-host story is still there: Blueprint/TF on Render, containers on Fly, same Docker image.

## Secrets

OAuth client secrets and `DATABASE_URL` never belong in git or in committed `.tfvars`. Pass them via env / `terraform.tfvars` (gitignored) / your secret store. Terraform state will hold sensitive values — use remote state with encryption if you apply this for real.

## Apply `infra/render` (optional)

Creates a **new** Render Postgres (free) + web service (**starter** — the Terraform provider’s web plans start there; the live Blueprint demo stays on free). Don’t apply on top of the existing demo unless you want a second environment or you `terraform import` first.

```powershell
cd infra/render
# From https://dashboard.render.com → Account Settings / API
$env:RENDER_API_KEY = "..."
$env:RENDER_OWNER_ID = "..."   # user or team id

copy terraform.tfvars.example terraform.tfvars
# edit: repo_url, oauth client ids/secrets

terraform init
terraform plan
# terraform apply   # only when you mean it
```
