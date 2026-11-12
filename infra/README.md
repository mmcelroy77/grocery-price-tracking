# Infrastructure

Terraform for the project's AWS resources. Names and tags follow [NAMING.md](NAMING.md).

| Path | What |
|---|---|
| `main.tf`, `variables.tf`, `outputs.tf` | The project's resources (data bucket). State lives in S3. |
| `bootstrap/` | One-time setup: state bucket, GitHub OIDC provider, pipeline IAM roles. Local state. |
| `../.github/workflows/release.yml` | Manual pipeline: plan, and optionally apply, behind an approval. |

## One-time setup

1. Sign in locally (`aws sts get-caller-identity` should work), then create the pipeline prerequisites:
   ```
   cd infra/bootstrap
   terraform init && terraform apply
   ```
   Keep `infra/bootstrap/terraform.tfstate`; it is gitignored.
2. Move the existing local state into the new S3 backend:
   ```
   cd ..
   terraform init -migrate-state    # answer yes
   terraform plan                   # should show no changes
   ```
3. In GitHub, **Settings > Secrets and variables > Actions > Variables**, add:
   - `AWS_RELEASE_ROLE_ARN`: the `release_role_arn` output from `bootstrap`
4. In GitHub, **Settings > Environments**, create `production` and add yourself as a required reviewer.
   The role only trusts jobs that run in this environment.

## Day to day

Run **Release** from the GitHub Actions tab (**Run workflow**) and approve the `production` deployment.
The plan appears in the job summary. The run only plans unless **apply** is ticked.

The release role is scoped to this project's buckets. When `infra/` starts managing other kinds of resources,
add the permissions to `bootstrap/main.tf` and apply `bootstrap` locally first.
