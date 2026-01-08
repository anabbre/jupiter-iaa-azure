variable "name" {
  type        = string
  description = "Base name, e.g. jupiter-iaa-dev"
}

variable "tags" {
  type        = map(string)
  description = "Common tags"
  default     = {}
}

variable "repositories" {
  type        = list(string)
  description = "Repository suffixes to create (e.g. [\"api\",\"ui\"])"
  default     = ["api", "ui"]
}
