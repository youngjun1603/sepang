# RDS PostgreSQL + PostGIS
variable "vpc_id" {}; variable "private_subnet_ids" {}; variable "env" {}

resource "aws_db_subnet_group" "main" {
  name       = "sepang-db-${var.env}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "rds" {
  name   = "sepang-rds-${var.env}"
  vpc_id = var.vpc_id
  ingress {
    from_port   = 5432; to_port = 5432; protocol = "tcp"
    cidr_blocks = ["10.0.0.0/16"]   # VPC 내부만
  }
  egress { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_db_parameter_group" "postgis" {
  name   = "sepang-postgis-${var.env}"
  family = "postgres16"
  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }
}

resource "aws_db_instance" "main" {
  identifier              = "sepang-db-${var.env}"
  engine                  = "postgres"
  engine_version          = "16.3"
  instance_class          = var.env == "production" ? "db.r7g.large" : "db.t4g.small"
  allocated_storage       = 100
  max_allocated_storage   = 1000          # 자동 스케일
  storage_encrypted       = true
  storage_type            = "gp3"
  iops                    = var.env == "production" ? 3000 : null

  db_name                 = "sepang"
  username                = "sepang"
  password                = var.db_password
  port                    = 5432

  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  parameter_group_name    = aws_db_parameter_group.postgis.name

  multi_az                = var.env == "production"
  backup_retention_period = 30
  backup_window           = "02:00-03:00"
  maintenance_window      = "Mon:03:00-Mon:04:00"
  deletion_protection     = var.env == "production"
  skip_final_snapshot     = var.env != "production"
  final_snapshot_identifier = var.env == "production" ? "sepang-final-snapshot" : null

  performance_insights_enabled = true

  tags = { Name = "sepang-db-${var.env}" }
}

variable "db_password" { sensitive = true }
output "database_url" {
  value     = "postgresql+asyncpg://${aws_db_instance.main.username}:${var.db_password}@${aws_db_instance.main.endpoint}/sepang"
  sensitive = true
}
