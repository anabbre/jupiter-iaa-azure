output "efs_id" { value = aws_efs_file_system.this.id }
output "efs_sg_id" { value = aws_security_group.efs.id }
output "access_point_id" { value = aws_efs_access_point.qdrant.id }
