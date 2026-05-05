# ============================================================
# 세팡 AWS 인프라 — Terraform 루트 모듈
# ============================================================
terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
  backend "s3" {
    bucket         = "sepang-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "ap-northeast-2"
    encrypt        = true
    dynamodb_table = "sepang-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
  default_tags { tags = local.common_tags }
}

locals {
  common_tags = {
    Project     = "Sepang"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# ── 모듈 호출 ─────────────────────────────────────────────────
module "vpc"   { source = "./modules/vpc";   env = var.environment }
module "rds"   { source = "./modules/rds";   vpc_id = module.vpc.vpc_id; private_subnet_ids = module.vpc.private_subnet_ids; env = var.environment }
module "redis" { source = "./modules/redis"; vpc_id = module.vpc.vpc_id; private_subnet_ids = module.vpc.private_subnet_ids; env = var.environment }
module "s3"    { source = "./modules/s3";    env = var.environment }
module "ecs"   {
  source             = "./modules/ecs"
  vpc_id             = module.vpc.vpc_id
  public_subnet_ids  = module.vpc.public_subnet_ids
  private_subnet_ids = module.vpc.private_subnet_ids
  database_url       = module.rds.database_url
  redis_url          = module.redis.redis_url
  s3_bucket          = module.s3.bucket_name
  env                = var.environment
}
