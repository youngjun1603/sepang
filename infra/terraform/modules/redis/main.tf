# ElastiCache Redis — 세션/캐시/Celery 브로커
variable "vpc_id" {}; variable "private_subnet_ids" {}; variable "env" {}

resource "aws_elasticache_subnet_group" "main" {
  name       = "sepang-redis-${var.env}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "redis" {
  name   = "sepang-redis-${var.env}"
  vpc_id = var.vpc_id
  ingress { from_port = 6379; to_port = 6379; protocol = "tcp"; cidr_blocks = ["10.0.0.0/16"] }
  egress  { from_port = 0;    to_port = 0;    protocol = "-1";  cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id       = "sepang-redis-${var.env}"
  description                = "세팡 Redis 클러스터"
  node_type                  = var.env == "production" ? "cache.r7g.large" : "cache.t4g.small"
  num_cache_clusters         = var.env == "production" ? 2 : 1
  automatic_failover_enabled = var.env == "production"
  multi_az_enabled           = var.env == "production"
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.redis_password
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.redis.id]
}

variable "redis_password" { sensitive = true }
output "redis_url" {
  value     = "rediss://:${var.redis_password}@${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0"
  sensitive = true
}
