// =============================================================================
// Azure AI Foundry (AI Services account) + GPT model deployment + PE + RBAC.
//
// IMPORTANT: This is a Cognitive Services account of kind="AIServices" with
// a custom subdomain — required for OpenAI-compatible inference via private
// endpoint.
//
// Endpoint shape: https://<customSubdomain>.openai.azure.com/openai/v1/
// =============================================================================

param name string
param location string
param tags object
param subnetPeId string
param privateDnsZoneId string

@description('Foundry model name (e.g., gpt-5.4).')
param modelName string

@description('Foundry model version (e.g., 2026-03-05).')
param modelVersion string

@description('Deployment name (used as the model alias in the API path).')
param deploymentName string

@description('TPM cap in thousands (50 = 50k TPM).')
@minValue(1)
param tpmCapInThousands int

@description('Principal IDs that get Cognitive Services OpenAI User on this account.')
param openaiUserPrincipalIds array

// Cognitive Services OpenAI User
var openaiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: name
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: name  // required for private endpoint to OpenAI surface
    publicNetworkAccess: 'Disabled'
    disableLocalAuth: true
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: account
  name: deploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: tpmCapInThousands
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
    raiPolicyName: 'Microsoft.DefaultV2'
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
}

resource pe 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: 'pe-${name}'
  location: location
  tags: tags
  properties: {
    subnet: { id: subnetPeId }
    privateLinkServiceConnections: [
      {
        name: 'account'
        properties: {
          privateLinkServiceId: account.id
          groupIds: ['account']
        }
      }
    ]
  }
}

resource peDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: pe
  name: 'dns'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'openai'
        properties: { privateDnsZoneId: privateDnsZoneId }
      }
    ]
  }
}

resource openaiUserAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (principalId, i) in openaiUserPrincipalIds: {
  scope: account
  name: guid(account.id, principalId, openaiUserRoleId)
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openaiUserRoleId)
  }
}]

output id string = account.id
output name string = account.name
output endpoint string = 'https://${account.properties.customSubDomainName}.openai.azure.com/'
output deploymentName string = deployment.name
