variable "name_prefix" {
  type    = string
  default = "jup-dev"
}

variable "location" {
  type    = string
  default = "westeurope"
}

variable "common_tags" {
  type = map(string)
  default = {
    project = "Jupiter"
    env     = "dev"
  }
}
