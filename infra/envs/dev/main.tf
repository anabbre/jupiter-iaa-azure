locals {
  name = "${var.prefix}-${var.environment}"
  tags = {
    Project     = var.prefix
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

module "network" {
  source = "../../modules/network"

  name     = local.name
  vpc_cidr = var.vpc_cidr

  # 2 AZs
  azs = slice(data.aws_availability_zones.available.names, 0, var.az_count)

  # Subnets /20 -> 4096 IPs cada una (suficiente y cómodo)
  public_subnet_cidrs  = ["10.20.0.0/20", "10.20.16.0/20"]
  private_subnet_cidrs = ["10.20.128.0/20", "10.20.144.0/20"]

  tags = local.tags
}

module "ecr" {
  source = "../../modules/ecr"

  name = local.name
  tags = local.tags

  repositories = ["api", "ui"]
}

module "alb" {
  source            = "../../modules/alb"
  name              = local.name
  vpc_id            = module.network.vpc_id
  public_subnet_ids = module.network.public_subnet_ids
  tags              = local.tags
}

module "efs" {
  source             = "../../modules/efs"
  name               = local.name
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids
  tags               = local.tags
}

module "ecs" {
  source = "../../modules/ecs"

  name               = local.name
  vpc_id             = module.network.vpc_id
  public_subnet_ids  = module.network.public_subnet_ids
  private_subnet_ids = module.network.private_subnet_ids
  alb_dns_name       = module.alb.dns_name


  tags = local.tags

  # Images (tag dev)
  api_image = "${module.ecr.repository_urls.api}:dev-202601081240"
  ui_image  = "${module.ecr.repository_urls.ui}:dev"

  # ALB
  alb_listener_http_arn = module.alb.listener_http_arn
  alb_sg_id             = module.alb.alb_sg_id

  # Ports
  api_port = 8008
  ui_port  = 7860

  # EFS
  efs_id              = module.efs.efs_id
  efs_access_point_id = module.efs.access_point_id
  efs_sg_id           = module.efs.efs_sg_id

  # App
  openai_api_key     = var.openai_api_key
  uploads_index_name = var.uploads_index_name
  kb_index_name      = var.kb_index_name
  log_level          = "INFO"
}
