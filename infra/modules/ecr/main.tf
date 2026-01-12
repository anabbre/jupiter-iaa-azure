resource "aws_ecr_repository" "this" {
  for_each = toset(var.repositories)

  name                 = "${var.name}-${each.key}" # jupiter-iaa-dev-api / ui
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.tags, {
    Name = "${var.name}-${each.key}"
  })
}

# (Opcional pero recomendable) policy de lifecycle para no acumular imágenes
resource "aws_ecr_lifecycle_policy" "this" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 20 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 2
        }
        action = { type = "expire" }
      }
    ]
  })
}
