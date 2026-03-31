terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "local" {
    path = "../../state/foundational.tfstate"
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type        = string
  description = "AWS region for all foundational resources."
  default     = "us-west-1"
}

variable "project_name" {
  type        = string
  description = "Project name prefix for resource naming."
  default     = "governance"
}

variable "environment" {
  type        = string
  description = "Environment name (dev/staging/prod)."
  default     = "dev"
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Stack       = "foundational"
  }
}

resource "aws_iam_role" "eks_cluster_role" {
  name = "${local.name_prefix}-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "cluster_policy" {
  role       = aws_iam_role.eks_cluster_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_iam_role" "eks_node_role" {
  name = "${local.name_prefix}-eks-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "worker_node_policy" {
  role       = aws_iam_role.eks_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "cni_policy" {
  role       = aws_iam_role.eks_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "ecr_read_only_policy" {
  role       = aws_iam_role.eks_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

output "aws_region" {
  value       = var.aws_region
  description = "Region shared by downstream stacks."
}

output "project_name" {
  value       = var.project_name
  description = "Project name shared by downstream stacks."
}

output "environment" {
  value       = var.environment
  description = "Environment name shared by downstream stacks."
}

output "name_prefix" {
  value       = local.name_prefix
  description = "Resolved resource naming prefix."
}

output "common_tags" {
  value       = local.common_tags
  description = "Common tags for downstream stacks."
}

output "eks_cluster_role_arn" {
  value       = aws_iam_role.eks_cluster_role.arn
  description = "IAM role ARN used by EKS control plane."
}

output "eks_node_role_arn" {
  value       = aws_iam_role.eks_node_role.arn
  description = "IAM role ARN used by worker nodes."
}

