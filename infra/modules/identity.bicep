// =============================================================================
// User-assigned managed identity + GitHub OIDC federation.
// =============================================================================
// The same MI is used by:
//   - GitHub Actions (federated; no client secret)
//   - Container Apps (api + web) at runtime to call Foundry, Cosmos, Storage,
//     Key Vault, AI Search, and pull from ACR.
// =============================================================================

param name string
param location string
param tags object

@description('GitHub repo in "owner/repo" form, e.g. NormanMul/DiagramArchitectureGenerator.')
param githubRepo string

@description('Branch this credential trusts for push events.')
param githubBranch string = 'main'

resource mi 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: name
  location: location
  tags: tags
}

// Federated credential — main branch (push deploys)
resource federatedBranch 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2024-11-30' = {
  parent: mi
  name: 'github-${githubBranch}'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    audiences: ['api://AzureADTokenExchange']
    subject: 'repo:${githubRepo}:ref:refs/heads/${githubBranch}'
  }
}

// Federated credential — pull requests targeting main (what-if comments)
resource federatedPR 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2024-11-30' = {
  parent: mi
  name: 'github-pull-request'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    audiences: ['api://AzureADTokenExchange']
    subject: 'repo:${githubRepo}:pull_request'
  }
}

// Federated credential — environment "prod" (gated deploy)
resource federatedEnvProd 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2024-11-30' = {
  parent: mi
  name: 'github-env-prod'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    audiences: ['api://AzureADTokenExchange']
    subject: 'repo:${githubRepo}:environment:prod'
  }
}

output resourceId string = mi.id
output principalId string = mi.properties.principalId
output clientId string = mi.properties.clientId
output name string = mi.name
