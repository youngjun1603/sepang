# ECS Fargate — FastAPI API + Celery Workers
variable "vpc_id" {}
variable "public_subnet_ids"  {}
variable "private_subnet_ids" {}
variable "database_url"       { sensitive = true }
variable "redis_url"          { sensitive = true }
variable "s3_bucket"          {}
variable "env"                {}
variable "acm_certificate_arn" { default = "" }

resource "aws_ecs_cluster" "main" {
  name = "sepang-${var.env}"
  configuration {
    execute_command_configuration {
      logging = "OVERRIDE"
      log_configuration { cloud_watch_log_group_name = "/ecs/sepang/${var.env}" }
    }
  }
  setting { name = "containerInsights"; value = "enabled" }
}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/sepang/${var.env}"
  retention_in_days = 30
}

# IAM — ECS Execution Role (ECR 이미지 풀 + CloudWatch 로그)
resource "aws_iam_role" "ecs_execution" {
  name = "sepang-ecs-execution-${var.env}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_ssm" {
  name = "ssm-secrets"
  role = aws_iam_role.ecs_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameters", "ssm:GetParameter"]
      Resource = "arn:aws:ssm:ap-northeast-2:*:parameter/sepang/${var.env}/*"
    }]
  })
}

# IAM — ECS Task Role (S3 접근)
resource "aws_iam_role" "ecs_task" {
  name = "sepang-ecs-task-${var.env}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "ecs_task_s3" {
  name = "s3-access"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject","s3:PutObject","s3:DeleteObject","s3:GeneratePresignedUrl"]
      Resource = "arn:aws:s3:::${var.s3_bucket}/*"
    }]
  })
}

# Application Load Balancer
resource "aws_security_group" "alb" {
  name   = "sepang-alb-${var.env}"
  vpc_id = var.vpc_id
  ingress { from_port = 80;  to_port = 80;  protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  ingress { from_port = 443; to_port = 443; protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  egress  { from_port = 0;   to_port = 0;   protocol = "-1";  cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_lb" "main" {
  name               = "sepang-alb-${var.env}"
  load_balancer_type = "application"
  subnets            = var.public_subnet_ids
  security_groups    = [aws_security_group.alb.id]
  enable_http2       = true
  access_logs {
    bucket  = "sepang-alb-logs-${var.env}"
    enabled = var.env == "production"
  }
}

resource "aws_lb_target_group" "api" {
  name        = "sepang-api-${var.env}"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
  health_check {
    path                = "/api/v1/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 15
    matcher             = "200"
  }
  deregistration_delay = 30
}

# Blue/Green 배포용 Green TG
resource "aws_lb_target_group" "api_green" {
  name        = "sepang-api-green-${var.env}"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
  health_check {
    path    = "/api/v1/health"
    matcher = "200"
  }
  deregistration_delay = 30
}

# HTTP → HTTPS 리다이렉트
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# HTTPS 리스너 (인증서는 ACM에서 관리)
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
  lifecycle { ignore_changes = [default_action] }  # CodeDeploy가 관리
}

# ECS 전용 Security Group (ALB에서만 수신)
resource "aws_security_group" "ecs_tasks" {
  name   = "sepang-ecs-tasks-${var.env}"
  vpc_id = var.vpc_id
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
  tags = { Name = "sepang-ecs-tasks-${var.env}" }
}

# ECS Task Definition — FastAPI
resource "aws_ecs_task_definition" "api" {
  family                   = "sepang-api-${var.env}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.env == "production" ? 2048 : 512
  memory                   = var.env == "production" ? 4096 : 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "api"
    image     = "ghcr.io/your-org/sepang-api:latest"
    essential = true
    portMappings = [{ containerPort = 8000; protocol = "tcp" }]
    environment = [
      { name = "ENVIRONMENT"; value = var.env },
      { name = "S3_BUCKET";   value = var.s3_bucket },
    ]
    secrets = [
      { name = "DATABASE_URL"; valueFrom = aws_ssm_parameter.db_url.arn },
      { name = "REDIS_URL";    valueFrom = aws_ssm_parameter.redis_url.arn },
      { name = "JWT_SECRET";   valueFrom = aws_ssm_parameter.jwt_secret.arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
        "awslogs-region"        = "ap-northeast-2"
        "awslogs-stream-prefix" = "api"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval    = 15; timeout = 5; retries = 3; startPeriod = 30
    }
  }])
}

# ECS Service — Auto Scaling
resource "aws_ecs_service" "api" {
  name            = "sepang-api-${var.env}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.env == "production" ? 2 : 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }
  deployment_circuit_breaker { enable = true; rollback = true }
}

# Auto Scaling
resource "aws_appautoscaling_target" "api" {
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = var.env == "production" ? 2 : 1
  max_capacity       = var.env == "production" ? 10 : 2
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "sepang-api-cpu-${var.env}"
  service_namespace  = "ecs"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  policy_type        = "TargetTrackingScaling"
  target_tracking_scaling_policy_configuration {
    target_value       = 60.0
    predefined_metric_specification { predefined_metric_type = "ECSServiceAverageCPUUtilization" }
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# SSM Parameter Store (시크릿)
resource "aws_ssm_parameter" "db_url" {
  name  = "/sepang/${var.env}/database-url"
  type  = "SecureString"
  value = var.database_url
}
resource "aws_ssm_parameter" "redis_url" {
  name  = "/sepang/${var.env}/redis-url"
  type  = "SecureString"
  value = var.redis_url
}
resource "aws_ssm_parameter" "jwt_secret" {
  name  = "/sepang/${var.env}/jwt-secret"
  type  = "SecureString"
  value = "placeholder"  # terraform apply 후 콘솔에서 변경
  lifecycle { ignore_changes = [value] }
}

output "alb_dns_name"         { value = aws_lb.main.dns_name }
output "ecs_cluster_name"     { value = aws_ecs_cluster.main.name }
output "api_tg_arn"           { value = aws_lb_target_group.api.arn }
output "api_green_tg_arn"     { value = aws_lb_target_group.api_green.arn }
output "https_listener_arn"   { value = aws_lb_listener.https.arn }
