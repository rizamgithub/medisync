terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
  resource_provider_registrations = "none"
}

data "azurerm_resource_group" "prod" {
  name = "rg-medisync-prod"
}

output "rg_id" {
  value = data.azurerm_resource_group.prod.id
}

output "rg_location" {
  value = data.azurerm_resource_group.prod.location
}
