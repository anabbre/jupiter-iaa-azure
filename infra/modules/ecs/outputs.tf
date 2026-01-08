output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "api_tg_arn" { value = aws_lb_target_group.api.arn }
output "ui_tg_arn" { value = aws_lb_target_group.ui.arn }

output "app_sg_id" { value = aws_security_group.app.id }
output "qdrant_sg_id" { value = aws_security_group.qdrant.id }
