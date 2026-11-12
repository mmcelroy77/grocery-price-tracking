# Infrastructure

Terraform for the project's AWS resources. Names and tags follow [NAMING.md](NAMING.md).

| Path | What |
|---|---|
| `main.tf`, `variables.tf`, `outputs.tf` | The project's resources (data bucket). State lives in S3. |
| `bootstrap/` | One-time setup: state bucket and the release IAM user. Local state. |
| `../.github/workflows/release.yml` | Manual pipeline: plan, and optionally apply, behind an approval. |

## One-time setup

Run these from the repository root; `-chdir` avoids changing directories.

1. Sign in locally (`aws sts get-caller-identity` should work), then create the state bucket and the release IAM user:
   ```
   terraform -chdir=infra/bootstrap init
   terraform -chdir=infra/bootstrap apply
   ```
   Keep `infra/bootstrap/terraform.tfstate`; it is gitignored.
2. State is already in the S3 bucket. On a fresh clone, `terraform -chdir=infra init` connects to it.
3. Create an access key for the release user (not through Terraform, so the secret stays out of state):
   ```
   aws iam create-access-key --user-name grocery-price-tracking-github-release
   ```
   Copy `AccessKeyId` and `SecretAccessKey` straight into step 4; they are not shown again.
4. In GitHub, **Settings > Environments**, create `production`, add yourself as a required reviewer, and add
   two **environment secrets**: `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. Environment secrets are only
   released to a job after the reviewer approves.

Rotate the key now and then: create a new one, update the secrets, then
`aws iam delete-access-key --user-name grocery-price-tracking-github-release --access-key-id <old id>`.

## Day to day

Run **Release** from the GitHub Actions tab (**Run workflow**) and approve the `production` deployment.
The plan appears in the job summary. The run only plans unless **apply** is ticked.

The release user is scoped to this project's buckets. When `infra/` starts managing other kinds of resources,
add the permissions to `bootstrap/main.tf` and apply `bootstrap` locally first.
