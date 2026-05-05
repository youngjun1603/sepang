variable "aws_region"   { default = "ap-northeast-2" }
variable "environment"  { default = "production" }
variable "db_password"  { sensitive = true }
variable "jwt_secret"   { sensitive = true }
variable "fcm_server_key" { sensitive = true }
