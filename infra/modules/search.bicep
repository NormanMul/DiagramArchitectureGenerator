// =============================================================================
// Azure AI Search — RAG over patterns_corpus/.
//
// NOTE on SKU + private endpoint:
//   - Free tier: 50 MB, no PE, no SLA. Fine for ~15 markdown patterns.
//   - Basic+:    supports PE, public access can be disabled.
//
// At Free we waive the spec §8 "PE only" rule for AI Search specifically;
// rationale: indexed data is public AAC reference architecture docs.
// =============================================================================

param name string
param location string
param tags object

@description('SKU. "free" disables PE; "basic"+ enables PE.')
@allowed(['free', 'basic', 'standard'])
param sku string = 'free'

param subnetPeId string = ''
param privateDnsZoneId string = ''
param indexDataContributorPrincipalIds array = []

var skuMap = {
  free: 'free'
  basic: 'basic'
  standard: 'standard'
}

// Search Index Data Contributor
var indexDataContributorRoleId = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'

resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: name
  location: location
  tags: tags
  sku: { name: skuMap[sku] }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'Default'
    publicNetworkAccess: sku == 'free' ? 'enabled' : 'disabled'
    disableLocalAuth: true  // Entra auth only
    authOptions: null
    semanticSearch: sku == 'free' ? 'disabled' : 'standard'
  }
  identity: { type: 'SystemAssigned' }
}

resource pe 'Microsoft.Network/privateEndpoints@2024-05-01' = if (sku != 'free') {
  name: 'pe-${name}'
  location: location
  tags: tags
  properties: {
    subnet: { id: subnetPeId }
    privateLinkServiceConnections: [
      {
        name: 'searchService'
        properties: {
          privateLinkServiceId: search.id
          groupIds: ['searchService']
        }
      }
    ]
  }
}

resource peDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (sku != 'free') {
  parent: pe
  name: 'dns'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'search'
        properties: { privateDnsZoneId: privateDnsZoneId }
      }
    ]
  }
}

resource indexDataRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (principalId, i) in indexDataContributorPrincipalIds: {
  scope: search
  name: guid(search.id, principalId, indexDataContributorRoleId)
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', indexDataContributorRoleId)
  }
}]

output id string = search.id
output name string = search.name
output endpoint string = 'https://${search.name}.search.windows.net/'
