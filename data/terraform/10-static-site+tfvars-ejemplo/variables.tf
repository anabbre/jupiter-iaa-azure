variable "project" {
  type    = string
  default = "static-site"
}

variable "location" {
  type    = string
  default = "westeurope"
}

variable "resource_group_name" {
  type    = string
  default = "rg-static-site-demo"
}

variable "storage_account_name" {
  type    = string
  default = "ststaticsitedemo123"
}

variable "index_document" {
  type    = string
  default = "index.html"
}

variable "error_document" {
  type    = string
  default = "404.html"
}

variable "tags" {
  type = map(string)
  default = {
    env     = "dev"
    project = "static-site"
    owner   = "demo"
  }
}
