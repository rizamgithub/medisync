# ---------------------------------------------------------------------------
# Remote state — Azure Blob backend
# ---------------------------------------------------------------------------
# State lives in an Azure Storage container instead of on a laptop. This gives:
#   - durability (laptop loss no longer loses the record of what's deployed),
#   - shared access (CI can run Terraform), and
#   - locking — the azurerm backend takes a blob *lease* for the duration of
#     every apply, so two runs can't corrupt state. No separate lock table.
#
# CHICKEN-AND-EGG: the storage account named below is the ONE resource that is
# intentionally NOT managed by Terraform. Terraform cannot create the storage
# that holds its own state. It is bootstrapped once with `az` — see runbook 07.
# Everything else in this repo stays 100% Terraform-managed (context.md rule 3);
# this single documented exception is the standard pattern for a state backend.
#
# Auth: `use_azuread_auth` makes the backend authenticate with the caller's
# Azure AD identity (the medisync-admin SP locally, medisync-deploy in CI) via
# the ARM_* environment variables. No storage account keys are used or stored.

terraform {
  backend "azurerm" {
    resource_group_name  = "rg-medisync-prod"
    storage_account_name = "medisynctfstate2n3ccl"
    container_name       = "tfstate"
    key                  = "infra.tfstate"
    use_azuread_auth     = true
  }
}

# infra/probe/ deliberately keeps its own LOCAL state — it's a throwaway smoke
# test, not worth a remote backend.
