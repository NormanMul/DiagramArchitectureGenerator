// =============================================================================
// Cosmos DB (serverless, SQL API) + private endpoint + RBAC.
// Stores conversation history and per-user preferences.
// Cosmos uses its own RBAC plane (Microsoft.DocumentDB/sqlRoleAssignments),
// not Azure RBAC.
// =============================================================================

param name string
param location string
param tags object
param subnetPeId string
param privateDnsZoneId string
param dataContributorPrincipalIds array

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-12-01-preview' = {
  name: name
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    capabilities: [
      { name: 'EnableServerless' }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    publicNetworkAccess: 'Disabled'
    disableLocalAuth: true  // force Entra auth (no master keys)
    networkAclBypass: 'AzureServices'
  }
}

resource db 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-12-01-preview' = {
  parent: cosmos
  name: 'archgen'
  properties: {
    resource: { id: 'archgen' }
  }
}

resource conversationsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-12-01-preview' = {
  parent: db
  name: 'conversations'
  properties: {
    resource: {
      id: 'conversations'
      partitionKey: {
        paths: ['/userId']
        kind: 'Hash'
      }
      defaultTtl: 2592000 // 30 days
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
        name: 'sql'
        properties: {
          privateLinkServiceId: cosmos.id
          groupIds: ['Sql']
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
        name: 'sql'
        properties: { privateDnsZoneId: privateDnsZoneId }
      }
    ]
  }
}

// Cosmos built-in Data Contributor role (built-in GUID, not Azure RBAC).
// 00000000-0000-0000-0000-000000000002 = Cosmos DB Built-in Data Contributor
resource sqlRoleAssignments 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-12-01-preview' = [for (principalId, i) in dataContributorPrincipalIds: {
  parent: cosmos
  name: guid(cosmos.id, principalId, '00000000-0000-0000-0000-000000000002')
  properties: {
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: principalId
    scope: cosmos.id
  }
}]

output id string = cosmos.id
output name string = cosmos.name
output endpoint string = cosmos.properties.documentEndpoint
output databaseName string = db.name
