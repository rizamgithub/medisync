terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = true
      recover_soft_deleted_key_vaults = true
    }
  }

  # Our medisync-admin SP only has Contributor on rg-medisync-prod.
  # Default azurerm v4 behaviour is to register every resource provider at
  # subscription scope on init, which 403s. Register RPs manually as Global
  # Admin (az provider register --namespace Microsoft.X) before referencing
  # a new service here.
  resource_provider_registrations = "none"
}

provider "azuread" {
  # Uses the same SP env vars as azurerm via ARM_*.
}
