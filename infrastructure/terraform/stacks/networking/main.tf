terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "local" {
    path = "../../state/networking.tfstate"
  }
}

data "terraform_remote_state" "foundational" {
  backend = "local"
  config = {
    path = "../../state/foundational.tfstate"
  }
}

provider "aws" {
  region = data.terraform_remote_state.foundational.outputs.aws_region
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC."
  default     = "10.30.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public subnet CIDRs (at least 2)."
  default     = ["10.30.0.0/24", "10.30.1.0/24"]
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "Private subnet CIDRs for EKS worker nodes (at least 2)."
  default     = ["10.30.10.0/24", "10.30.11.0/24"]
}

locals {
  tags = merge(
    data.terraform_remote_state.foundational.outputs.common_tags,
    { Stack = "networking" }
  )
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(
    local.tags,
    { Name = "${data.terraform_remote_state.foundational.outputs.name_prefix}-vpc" }
  )
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = merge(
    local.tags,
    { Name = "${data.terraform_remote_state.foundational.outputs.name_prefix}-igw" }
  )
}

resource "aws_subnet" "public" {
  count = length(var.public_subnet_cidrs)

  vpc_id                  = aws_vpc.this.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = merge(
    local.tags,
    {
      Name                                                                                        = "${data.terraform_remote_state.foundational.outputs.name_prefix}-public-${count.index + 1}"
      "kubernetes.io/role/elb"                                                                    = "1"
      "kubernetes.io/cluster/${data.terraform_remote_state.foundational.outputs.name_prefix}-eks" = "shared"
    }
  )
}

resource "aws_subnet" "private" {
  count = length(var.private_subnet_cidrs)

  vpc_id            = aws_vpc.this.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = merge(
    local.tags,
    {
      Name                                                                                        = "${data.terraform_remote_state.foundational.outputs.name_prefix}-private-${count.index + 1}"
      "kubernetes.io/role/internal-elb"                                                           = "1"
      "kubernetes.io/cluster/${data.terraform_remote_state.foundational.outputs.name_prefix}-eks" = "shared"
    }
  )
}

resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = merge(local.tags, { Name = "${data.terraform_remote_state.foundational.outputs.name_prefix}-nat-eip" })
}

resource "aws_nat_gateway" "this" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id

  depends_on = [aws_internet_gateway.this]
  tags       = merge(local.tags, { Name = "${data.terraform_remote_state.foundational.outputs.name_prefix}-nat" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = merge(local.tags, { Name = "${data.terraform_remote_state.foundational.outputs.name_prefix}-public-rt" })
}

resource "aws_route_table_association" "public" {
  count = length(aws_subnet.public)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this.id
  }

  tags = merge(local.tags, { Name = "${data.terraform_remote_state.foundational.outputs.name_prefix}-private-rt" })
}

resource "aws_route_table_association" "private" {
  count = length(aws_subnet.private)

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

output "vpc_id" {
  value       = aws_vpc.this.id
  description = "VPC ID for compute stack."
}

output "private_subnet_ids" {
  value       = aws_subnet.private[*].id
  description = "Private subnet IDs for EKS cluster and node groups."
}

output "public_subnet_ids" {
  value       = aws_subnet.public[*].id
  description = "Public subnet IDs."
}

