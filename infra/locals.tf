locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    project     = var.project_name
    environment = var.environment
    owner       = var.owner_email
    managed_by  = "terraform"
  }
}

data "azurerm_resource_group" "main" {
  name = var.resource_group_name
}
