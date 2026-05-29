// =============================================================================
// VNet + subnets + NSGs + private DNS zones.
// =============================================================================

param vnetName string
param location string
param tags object
param vnetAddressSpace string
param subnetAcaCidr string
param subnetPeCidr string

// -----------------------------------------------------------------------------
// NSGs
// -----------------------------------------------------------------------------

resource nsgAca 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-${vnetName}-aca'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'allow-vnet-inbound'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: '*'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '*'
        }
      }
      {
        name: 'deny-internet-inbound'
        properties: {
          priority: 4000
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: 'Internet'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

resource nsgPe 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-${vnetName}-pe'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'allow-vnet-inbound'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: '*'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

// -----------------------------------------------------------------------------
// VNet + subnets
// -----------------------------------------------------------------------------

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [vnetAddressSpace]
    }
    subnets: [
      {
        name: 'snet-aca'
        properties: {
          addressPrefix: subnetAcaCidr
          networkSecurityGroup: { id: nsgAca.id }
          delegations: [
            {
              name: 'aca-delegation'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: 'snet-pe'
        properties: {
          addressPrefix: subnetPeCidr
          networkSecurityGroup: { id: nsgPe.id }
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

// -----------------------------------------------------------------------------
// Private DNS zones + VNet links
// -----------------------------------------------------------------------------

var dnsZoneNames = [
  'privatelink.openai.azure.com'
  'privatelink.documents.azure.com'
  'privatelink.blob.${environment().suffixes.storage}'
  'privatelink.vaultcore.azure.net'
  'privatelink.search.windows.net'
]

resource dnsZones 'Microsoft.Network/privateDnsZones@2024-06-01' = [for zoneName in dnsZoneNames: {
  name: zoneName
  location: 'global'
  tags: tags
}]

resource dnsZoneLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (zoneName, i) in dnsZoneNames: {
  parent: dnsZones[i]
  name: 'link-${vnetName}'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}]

output vnetId string = vnet.id
output subnetAcaId string = vnet.properties.subnets[0].id
output subnetPeId string = vnet.properties.subnets[1].id

output dnsZones object = {
  openai: dnsZones[0].id
  cosmos: dnsZones[1].id
  blob:   dnsZones[2].id
  vault:  dnsZones[3].id
  search: dnsZones[4].id
}
