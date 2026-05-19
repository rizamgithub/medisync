# Backend left LOCAL for now. State file lives at infra/terraform.tfstate
# (gitignored). Upgrade to azurerm backend once we have resources worth
# protecting and/or CI needs to run apply.
#
# Upgrade recipe (when ready):
#
#   1. As Global Admin, create a storage account + container for state:
#        az group create -n rg-medisync-tfstate -l southeastasia
#        az storage account create -n sttfstatemedisync -g rg-medisync-tfstate \
#          -l southeastasia --sku Standard_LRS --kind StorageV2 \
#          --allow-blob-public-access false --min-tls-version TLS1_2
#        az storage container create -n tfstate --account-name sttfstatemedisync
#   2. Grant medisync-admin "Storage Blob Data Contributor" on the SA.
#   3. Uncomment the block below.
#   4. Run: terraform init -migrate-state
#
# terraform {
#   backend "azurerm" {
#     resource_group_name  = "rg-medisync-tfstate"
#     storage_account_name = "sttfstatemedisync"
#     container_name       = "tfstate"
#     key                  = "medisync.tfstate"
#     use_oidc             = true   # for GitHub Actions
#   }
# }
