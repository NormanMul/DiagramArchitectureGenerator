// =============================================================================
// Key Vault (RBAC-mode) + private endpoint + role assignments.
// Used for any *operational* secrets we cannot avoid (e.g., third-party API
// keys if we ever add them). App-to-Azure auth uses managed identity, so the
// vault is currently a placeholder.
// =============================================================================

param name string
param location string
param tags object
param subnetPeId string
param privateDnsZoneId string
param secretsUserPrincipalIds array

@description('Optional human admin who gets Key Vault Administrator (full access). Set to empty string to skip.')
param adminPrincipalId string = ''

// Key Vault Secrets User (read secrets at runtime)
var secretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
// Key Vault Administrator (manage secrets — for human admin only)
var kvAdminRoleId = '00482a5a-887f-4fb3-b363-3b7fe8e74483'

resource kv 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: true
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
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
        name: 'vault'
        properties: {
          privateLinkServiceId: kv.id
          groupIds: ['vault']
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
        name: 'vault'
        properties: { privateDnsZoneId: privateDnsZoneId }
      }
    ]
  }
}

resource secretsUserAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (principalId, i) in secretsUserPrincipalIds: {
  scope: kv
  name: guid(kv.id, principalId, secretsUserRoleId)
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', secretsUserRoleId)
  }
}]

resource adminAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(adminPrincipalId)) {
  scope: kv
  name: guid(kv.id, adminPrincipalId, kvAdminRoleId)
  properties: {
    principalId: adminPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvAdminRoleId)
  }
}

output id string = kv.id
output name string = kv.name
output uri string = kv.properties.vaultUri
