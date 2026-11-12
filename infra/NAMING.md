# Naming conventions

Naming follows the scheme from Avangards, [My Quest To Finding the Perfect AWS Resource Naming Scheme](https://blog.avangards.io/my-quest-to-finding-the-perfect-aws-resource-naming-scheme),
an AWS adaptation of the Azure Cloud Adoption Framework pattern:

```
<resource-type>-<workload>-<environment>-<region>-<instance>
```

Refer to the article for the resource-type and region abbreviations.

Project-specific notes:
- `workload` is `var.project` in [variables.tf](variables.tf).
- S3 bucket names must be globally unique, so append the AWS account ID.
- Lowercase letters, numbers and hyphens only. S3 bucket names are 3 to 63 characters
  ([S3 naming rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html)).
- Shared tags (`project`, `managed_by`) are set once in `default_tags` in [main.tf](main.tf).
