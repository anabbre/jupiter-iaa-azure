output "vpc_id" {
  value = module.network.vpc_id
}

output "public_subnet_ids" {
  value = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  value = module.network.private_subnet_ids
}

output "ecr_repository_urls" {
  value = module.ecr.repository_urls
}

output "alb_dns_name" {
  description = "DNS público del ALB"
  value       = module.alb.alb_dns_name
}

output "alb_arn" {
  value = module.alb.alb_arn
}

output "alb_listener_http_arn" {
  value = module.alb.listener_http_arn
}

output "alb_sg_id" {
  value = module.alb.alb_sg_id
}
