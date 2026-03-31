# Terraform Stacks: EKS Cluster

This folder uses a stack architecture with clear separation:

- `stacks/foundational` - IAM roles, shared naming/tags/region outputs
- `stacks/networking` - VPC, subnets, routes, NAT, IGW
- `stacks/compute` - EKS control plane + managed node group

State is local by default under `state/*.tfstate` for quick start.

## Prerequisites

- Terraform `>= 1.5`
- AWS credentials configured (`aws configure` or env vars)
- Permissions to create IAM, VPC, EKS, EC2, and related resources

## Folder structure

- `stacks/foundational/main.tf`
- `stacks/networking/main.tf`
- `stacks/compute/main.tf`
- `state/` (local tfstate files)

## Apply order

You must apply stacks in this order because of remote-state dependencies:

1. foundational
2. networking
3. compute

## Commands to run

From repo root:

```bash
cd infrastructure/terraform/stacks/foundational
terraform init
terraform plan -out tfplan
terraform apply tfplan
```

```bash
cd ../networking
terraform init
terraform plan -out tfplan
terraform apply tfplan
```

```bash
cd ../compute
terraform init
terraform plan -out tfplan
terraform apply tfplan
```

## Destroy order

Destroy in reverse order:

```bash
cd infrastructure/terraform/stacks/compute && terraform destroy
cd ../networking && terraform destroy
cd ../foundational && terraform destroy
```

### Destroy only the foundational stack

Use this when you applied **foundational** only and want to remove those IAM roles before changing region or re-applying:

```bash
cd infrastructure/terraform/stacks/foundational
terraform init
terraform destroy
```

If you already applied **networking** or **compute**, tear those down **first** (see destroy order above), then destroy foundational.

### One-shot: destroy foundational, then apply all stacks (us-west-1)

Default region is **`us-west-1`** (`stacks/foundational/main.tf`). With AWS credentials configured (`aws sts get-caller-identity` works), from the **repository root**:

```bash
cd infrastructure/terraform/stacks/foundational
terraform init -input=false
terraform destroy -auto-approve -input=false
terraform apply -auto-approve -input=false

cd ../networking
terraform init -input=false
terraform apply -auto-approve -input=false

cd ../compute
terraform init -input=false
terraform apply -auto-approve -input=false
```

## Useful post-apply commands

Set kubeconfig:

```bash
aws eks update-kubeconfig --region us-west-1 --name governance-dev-eks
kubectl get nodes
```

## Notes

- This is a practical starter stack, not production-hardened.
- For production: remote backend (S3 + DynamoDB lock), private endpoint patterns, tighter security groups, KMS, logging retention, and policy guardrails.

