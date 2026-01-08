resource "aws_security_group" "efs" {
  name        = "${var.name}-efs-sg"
  description = "EFS SG"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.name}-efs-sg" })
}

resource "aws_efs_file_system" "this" {
  encrypted = true
  tags      = merge(var.tags, { Name = "${var.name}-efs" })
}

resource "aws_efs_mount_target" "mt" {
  for_each        = toset(var.private_subnet_ids)
  file_system_id  = aws_efs_file_system.this.id
  subnet_id       = each.value
  security_groups = [aws_security_group.efs.id]
}

resource "aws_efs_access_point" "qdrant" {
  file_system_id = aws_efs_file_system.this.id

  root_directory {
    path = "/qdrant"
    creation_info {
      owner_uid   = 1000
      owner_gid   = 1000
      permissions = "0777"
    }
  }

  posix_user {
    uid = 1000
    gid = 1000
  }

  tags = merge(var.tags, { Name = "${var.name}-efs-ap-qdrant" })
}
