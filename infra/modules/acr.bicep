// =============================================================================
// Azure Container Registry (Basic) + role assignments for image pullers.
// =============================================================================

param name string
param location string
param tags object
param pullerPrincipalIds array

// AcrPull built-in role
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource acr 'Microsoft.ContainerRegistry/registries@2024-11-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled' // Basic doesn't support PE; required for ACR Tasks (az acr build) anyway
    anonymousPullEnabled: false
  }
}

resource pullRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (principalId, i) in pullerPrincipalIds: {
  scope: acr
  name: guid(acr.id, principalId, acrPullRoleId)
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
  }
}]

output id string = acr.id
output name string = acr.name
output loginServer string = acr.properties.loginServer
