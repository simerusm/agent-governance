terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "local" {
    path = "../../state/compute.tfstate"
  }
}

data "terraform_remote_state" "foundational" {
  backend = "local"
  config = {
    path = "../../state/foundational.tfstate"
  }
}

data "terraform_remote_state" "networking" {
  backend = "local"
  config = {
    path = "../../state/networking.tfstate"
  }
}

provider "aws" {
  region = data.terraform_remote_state.foundational.outputs.aws_region
}

variable "kubernetes_version" {
  type        = string
  description = "Kubernetes control plane version."
  default     = "1.30"
}

variable "node_instance_types" {
  type        = list(string)
  description = "EC2 instance types for managed node group."
  default     = ["t3.small"]
}

variable "desired_size" {
  type        = number
  description = "Desired node count."
  default     = 2
}

variable "min_size" {
  type        = number
  description = "Minimum node count."
  default     = 1
}

variable "max_size" {
  type        = number
  description = "Maximum node count."
  default     = 4
}

locals {
  cluster_name = "${data.terraform_remote_state.foundational.outputs.name_prefix}-eks"
  tags = merge(
    data.terraform_remote_state.foundational.outputs.common_tags,
    { Stack = "compute" }
  )
}

resource "aws_eks_cluster" "this" {
  name     = local.cluster_name
  role_arn = data.terraform_remote_state.foundational.outputs.eks_cluster_role_arn
  version  = var.kubernetes_version

  vpc_config {
    subnet_ids              = data.terraform_remote_state.networking.outputs.private_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = true
  }

  tags = merge(local.tags, { Name = local.cluster_name })
}

resource "aws_eks_node_group" "default" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${local.cluster_name}-default"
  node_role_arn   = data.terraform_remote_state.foundational.outputs.eks_node_role_arn
  subnet_ids      = data.terraform_remote_state.networking.outputs.private_subnet_ids

  instance_types = var.node_instance_types

  scaling_config {
    desired_size = var.desired_size
    min_size     = var.min_size
    max_size     = var.max_size
  }

  tags = merge(local.tags, { Name = "${local.cluster_name}-default-ng" })
}

output "cluster_name" {
  value       = aws_eks_cluster.this.name
  description = "EKS cluster name."
}

output "cluster_endpoint" {
  value       = aws_eks_cluster.this.endpoint
  description = "EKS API endpoint."
}

output "cluster_ca_data" {
  value       = aws_eks_cluster.this.certificate_authority[0].data
  description = "Base64 CA bundle for kubeconfig."
}

output "node_group_name" {
  value       = aws_eks_node_group.default.node_group_name
  description = "Managed node group name."
}

