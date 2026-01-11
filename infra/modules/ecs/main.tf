locals {
  api_tg_name = "${var.name}-api-tg"
  ui_tg_name  = "${var.name}-ui-tg"
}

data "aws_region" "current" {}

resource "aws_ecs_cluster" "this" {
  name = "${var.name}-cluster"
  tags = var.tags
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.name}/api"
  retention_in_days = 14
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "ui" {
  name              = "/ecs/${var.name}/ui"
  retention_in_days = 14
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "qdrant" {
  name              = "/ecs/${var.name}/qdrant"
  retention_in_days = 14
  tags              = var.tags
}

# ---------------------------
# Service Discovery (Cloud Map)
# ---------------------------
# Namespace privado dentro del VPC para descubrir servicios por DNS interno.
# Resultado: qdrant.${var.name}.local -> IP del task de Qdrant
resource "aws_service_discovery_private_dns_namespace" "this" {
  name = "${var.name}.local"
  vpc  = var.vpc_id
  tags = var.tags
}

resource "aws_service_discovery_service" "qdrant" {
  name = "qdrant"

  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.this.id
    routing_policy = "MULTIVALUE"

    dns_records {
      ttl  = 10
      type = "A"
    }
  }

  # Health check "custom" (sin integrar con un endpoint real)
  health_check_custom_config {
    failure_threshold = 1
  }

  tags = var.tags
}

# ---------------------------
# Security Groups
# ---------------------------

# SG para servicios API/UI (reciben tráfico SOLO desde el SG del ALB)
resource "aws_security_group" "app" {
  name        = "${var.name}-app-sg"
  description = "API/UI tasks SG"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.name}-app-sg" })
}

resource "aws_security_group_rule" "app_ingress_api_from_alb" {
  type                     = "ingress"
  security_group_id        = aws_security_group.app.id
  from_port                = var.api_port
  to_port                  = var.api_port
  protocol                 = "tcp"
  source_security_group_id = var.alb_sg_id
}

resource "aws_security_group_rule" "app_ingress_ui_from_alb" {
  type                     = "ingress"
  security_group_id        = aws_security_group.app.id
  from_port                = var.ui_port
  to_port                  = var.ui_port
  protocol                 = "tcp"
  source_security_group_id = var.alb_sg_id
}

# SG Qdrant (solo acepta desde SG app y permite NFS hacia EFS)
resource "aws_security_group" "qdrant" {
  name        = "${var.name}-qdrant-sg"
  description = "Qdrant tasks SG"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.name}-qdrant-sg" })
}

resource "aws_security_group_rule" "qdrant_ingress_from_app" {
  type                     = "ingress"
  security_group_id        = aws_security_group.qdrant.id
  from_port                = var.qdrant_port
  to_port                  = var.qdrant_port
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.app.id
}

# Importante: permitir NFS (2049) desde SG qdrant hacia SG EFS.
resource "aws_security_group_rule" "efs_ingress_from_qdrant" {
  type                     = "ingress"
  security_group_id        = var.efs_sg_id
  from_port                = 2049
  to_port                  = 2049
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.qdrant.id
}

# ---------------------------
# Target Groups + Listener Rules
# ---------------------------

resource "aws_lb_target_group" "api" {
  name        = local.api_tg_name
  port        = var.api_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/api/"
    protocol            = "HTTP"
    matcher             = "200"
    healthy_threshold   = 2
    unhealthy_threshold = 5
    interval            = 15
    timeout             = 5
  }

  tags = var.tags
}

resource "aws_lb_target_group" "ui" {
  name        = local.ui_tg_name
  port        = var.ui_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/"
    protocol            = "HTTP"
    matcher             = "200-399"
    healthy_threshold   = 2
    unhealthy_threshold = 5
    interval            = 15
    timeout             = 5
  }

  tags = var.tags
}

# /api/* -> API
resource "aws_lb_listener_rule" "api" {
  listener_arn = var.alb_listener_http_arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }
}

# default -> UI  (más simple: ponemos regla /* con prioridad > api)
resource "aws_lb_listener_rule" "ui" {
  listener_arn = var.alb_listener_http_arn
  priority     = 20

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ui.arn
  }

  condition {
    path_pattern {
      values = ["/*"]
    }
  }
}

# ---------------------------
# IAM (Task Execution Role)
# ---------------------------

data "aws_iam_policy_document" "ecs_task_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_execution" {
  name               = "${var.name}-task-exec-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "task_exec_attach" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# (Opcional futuro: acceso S3, etc. Si lo necesitamos lo añadimos después)

# ---------------------------
# Task Definitions
# ---------------------------

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.task_execution.arn

  container_definitions = jsonencode([{
    name      = "api"
    image     = var.api_image
    essential = true
    portMappings = [{
      containerPort = var.api_port
      hostPort      = var.api_port
      protocol      = "tcp"
    }]
    environment = [
      { name = "OPENAI_API_KEY", value = var.openai_api_key },
      { name = "LOG_LEVEL", value = var.log_level },

      # ✅ Qdrant por DNS interno (Cloud Map)
      # Resuelve a: qdrant.${var.name}.local
      { name = "QDRANT_URL", value = "http://qdrant.${aws_service_discovery_private_dns_namespace.this.name}:6333" },

      { name = "UPLOADS_INDEX_NAME", value = var.uploads_index_name },
      { name = "KB_INDEX_NAME", value = var.kb_index_name },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.api.name
        awslogs-region        = data.aws_region.current.name
        awslogs-stream-prefix = "ecs"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:${var.api_port}/api/')\" || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 20
    }
  }])

  tags = var.tags
}

resource "aws_ecs_task_definition" "ui" {
  family                   = "${var.name}-ui"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.task_execution.arn

  container_definitions = jsonencode([{
    name      = "ui"
    image     = var.ui_image
    essential = true
    portMappings = [{
      containerPort = var.ui_port
      hostPort      = var.ui_port
      protocol      = "tcp"
    }]
    environment = [
      { name = "API_URL", value = "http://${var.alb_dns_name}/api" },
      { name = "LOG_LEVEL", value = var.log_level },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ui.name
        awslogs-region        = data.aws_region.current.name
        awslogs-stream-prefix = "ecs"
      }
    }
  }])

  tags = var.tags
}

# Qdrant en Fargate con EFS
resource "aws_ecs_task_definition" "qdrant" {
  family                   = "${var.name}-qdrant"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.task_execution.arn

  volume {
    name = "qdrant_data"
    efs_volume_configuration {
      file_system_id     = var.efs_id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = var.efs_access_point_id
        iam             = "DISABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name = "qdrant"

    # ✅ No usar latest (buena práctica)
    image = "qdrant/qdrant:v1.10.1"

    essential = true
    portMappings = [{
      containerPort = var.qdrant_port
      hostPort      = var.qdrant_port
      protocol      = "tcp"
    }]
    mountPoints = [{
      sourceVolume  = "qdrant_data"
      containerPath = "/qdrant/storage"
      readOnly      = false
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.qdrant.name
        awslogs-region        = data.aws_region.current.name
        awslogs-stream-prefix = "ecs"
      }
    }
  }])

  tags = var.tags
}

# ---------------------------
# Services
# ---------------------------

resource "aws_ecs_service" "qdrant" {
  name            = "${var.name}-qdrant"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.qdrant.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  # ✅ Registro en Cloud Map (DNS interno)
  service_registries {
    registry_arn = aws_service_discovery_service.qdrant.arn
  }

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [aws_security_group.qdrant.id]
    assign_public_ip = true
  }

  tags = var.tags
}

resource "aws_ecs_service" "api" {
  name            = "${var.name}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = var.api_port
  }

  depends_on = [aws_ecs_service.qdrant]
  tags       = var.tags
}

resource "aws_ecs_service" "ui" {
  name            = "${var.name}-ui"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.ui.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.ui.arn
    container_name   = "ui"
    container_port   = var.ui_port
  }

  tags = var.tags
}
