// =============================================================================
// archgen — main.bicep (subscription scope)
// =============================================================================
// Deploys the full Genesis Azure Architecture Diagram Generator stack into
// a single resource group in Southeast Asia.
//
// Idempotent. Re-run safely via `az deployment sub create`.
//
// PRECONDITIONS (created out-of-band, see docs/operations.md):
//   - User-assigned managed identity exists (created by this template if not).
//   - GitHub OIDC federation on the MI (configured via `az identity federated-credential create`
//     after first run, see docs/operations.md).
// =============================================================================

targetScope = 'subscription'

// -----------------------------------------------------------------------------
// Parameters
// -----------------------------------------------------------------------------

@description('Environment label: dev | prod. Used in resource naming.')
@allowed(['dev', 'prod'])
param environmentName string = 'prod'

@description('Primary deployment region. Default SEA per spec §3.1.')
param location string = 'southeastasia'

@description('Workload name token. Used in resource naming.')
@minLength(3)
@maxLength(8)
param workloadName string = 'archgen'

@description('Foundry model name (kept stable; version is the moving part).')
param foundryModelName string = 'gpt-5.4'

@description('Foundry model version. Verified available in SEA on 2026-05-29.')
param foundryModelVersion string = '2026-03-05'

@description('TPM cap on the Foundry deployment (in thousands). 50 = 50k TPM.')
@minValue(1)
@maxValue(1000)
param foundryTpmCapInThousands int = 50

@description('AI Search SKU. Free has no private endpoint support — see docs/operations.md for waiver.')
@allowed(['free', 'basic', 'standard'])
param searchSku string = 'free'

@description('Front Door SKU. Standard = WAF Standard (custom rules only); Premium adds DRS + bot manager.')
@allowed(['Standard_AzureFrontDoor', 'Premium_AzureFrontDoor'])
param frontDoorSku string = 'Standard_AzureFrontDoor'

@description('Front Door endpoint name (becomes <name>.azurefd.net).')
param frontDoorEndpointName string = 'diagramarchitecturegenerator'

@description('GitHub repository (org/repo) for OIDC federation.')
param githubRepo string = 'mprawironego_microsoft/Genesis-DiagramArchitectureGenerator'

@description('Branch the federated credential trusts for deploys.')
param githubBranch string = 'main'

@description('Object ID of the human admin who needs portal access (RBAC). Optional.')
param adminPrincipalId string = ''

@description('VNet address space.')
param vnetAddressSpace string = '10.40.0.0/16'

@description('Subnet for Container Apps environment (delegated to Microsoft.App/environments).')
param subnetAca string = '10.40.0.0/23'

@description('Subnet for private endpoints.')
param subnetPe string = '10.40.2.0/27'

@description('Monthly budget threshold in USD. Alerts fire at 50/80/100%.')
@minValue(50)
param monthlyBudgetUsd int = 550

@description('Tags applied to all resources.')
param tags object = {
  workload: 'archgen'
  env: environmentName
  managedBy: 'bicep'
  source: 'https://github.com/${githubRepo}'
}

// -----------------------------------------------------------------------------
// Naming
// -----------------------------------------------------------------------------

var regionShort = 'sea' // southeastasia
var nameSuffix = '${workloadName}-${environmentName}-${regionShort}'

var names = {
  rg: 'rg-${nameSuffix}'
  identity: 'id-${nameSuffix}'
  vnet: 'vnet-${nameSuffix}'
  logAnalytics: 'log-${nameSuffix}'
  appInsights: 'appi-${nameSuffix}'
  storage: toLower(replace('st${workloadName}${environmentName}${regionShort}', '-', ''))
  keyVault: 'kv-${nameSuffix}'
  acr: toLower(replace('cr${workloadName}${environmentName}${regionShort}', '-', ''))
  cosmos: 'cosmos-${nameSuffix}'
  search: 'srch-${nameSuffix}'
  foundry: 'fdy-${workloadName}-${regionShort}-01'
  foundryDeployment: '${workloadName}-gpt54'
  acaEnvironment: 'cae-${nameSuffix}'
  acaApi: 'ca-${workloadName}-api-${environmentName}-${regionShort}'
  acaWeb: 'ca-${workloadName}-web-${environmentName}-${regionShort}'
  afdProfile: 'afd-${workloadName}-${environmentName}'
  afdEndpoint: frontDoorEndpointName
  budget: 'budget-${nameSuffix}'
}

// -----------------------------------------------------------------------------
// Resource group
// -----------------------------------------------------------------------------

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: names.rg
  location: location
  tags: tags
}

// -----------------------------------------------------------------------------
// Modules (RG-scoped)
// -----------------------------------------------------------------------------

module identity 'modules/identity.bicep' = {
  scope: rg
  name: 'identity'
  params: {
    name: names.identity
    location: location
    tags: tags
    githubRepo: githubRepo
    githubBranch: githubBranch
  }
}

module networking 'modules/networking.bicep' = {
  scope: rg
  name: 'networking'
  params: {
    vnetName: names.vnet
    location: location
    tags: tags
    vnetAddressSpace: vnetAddressSpace
    subnetAcaCidr: subnetAca
    subnetPeCidr: subnetPe
  }
}

module observability 'modules/observability.bicep' = {
  scope: rg
  name: 'observability'
  params: {
    logAnalyticsName: names.logAnalytics
    appInsightsName: names.appInsights
    location: location
    tags: tags
  }
}

module acr 'modules/acr.bicep' = {
  scope: rg
  name: 'acr'
  params: {
    name: names.acr
    location: location
    tags: tags
    pullerPrincipalIds: [identity.outputs.principalId]
  }
}

module storage 'modules/storage.bicep' = {
  scope: rg
  name: 'storage'
  params: {
    name: names.storage
    location: location
    tags: tags
    subnetPeId: networking.outputs.subnetPeId
    privateDnsZoneId: networking.outputs.dnsZones.blob
    dataContributorPrincipalIds: [identity.outputs.principalId]
  }
}

module keyVault 'modules/keyvault.bicep' = {
  scope: rg
  name: 'keyvault'
  params: {
    name: names.keyVault
    location: location
    tags: tags
    subnetPeId: networking.outputs.subnetPeId
    privateDnsZoneId: networking.outputs.dnsZones.vault
    secretsUserPrincipalIds: [identity.outputs.principalId]
    adminPrincipalId: adminPrincipalId
  }
}

module cosmos 'modules/cosmos.bicep' = {
  scope: rg
  name: 'cosmos'
  params: {
    name: names.cosmos
    location: location
    tags: tags
    subnetPeId: networking.outputs.subnetPeId
    privateDnsZoneId: networking.outputs.dnsZones.cosmos
    dataContributorPrincipalIds: [identity.outputs.principalId]
  }
}

module foundry 'modules/foundry.bicep' = {
  scope: rg
  name: 'foundry'
  params: {
    name: names.foundry
    location: location
    tags: tags
    subnetPeId: networking.outputs.subnetPeId
    privateDnsZoneId: networking.outputs.dnsZones.openai
    modelName: foundryModelName
    modelVersion: foundryModelVersion
    deploymentName: names.foundryDeployment
    tpmCapInThousands: foundryTpmCapInThousands
    openaiUserPrincipalIds: [identity.outputs.principalId]
  }
}

module search 'modules/search.bicep' = {
  scope: rg
  name: 'search'
  params: {
    name: names.search
    location: location
    tags: tags
    sku: searchSku
    subnetPeId: networking.outputs.subnetPeId
    privateDnsZoneId: networking.outputs.dnsZones.search
    indexDataContributorPrincipalIds: [identity.outputs.principalId]
  }
}

module containerApps 'modules/container-apps.bicep' = {
  scope: rg
  name: 'container-apps'
  params: {
    environmentName: names.acaEnvironment
    apiAppName: names.acaApi
    webAppName: names.acaWeb
    location: location
    tags: tags
    subnetId: networking.outputs.subnetAcaId
    logAnalyticsCustomerId: observability.outputs.logAnalyticsCustomerId
    logAnalyticsSharedKey: observability.outputs.logAnalyticsSharedKey
    appInsightsConnectionString: observability.outputs.appInsightsConnectionString
    identityResourceId: identity.outputs.resourceId
    identityClientId: identity.outputs.clientId
    acrLoginServer: acr.outputs.loginServer
    foundryEndpoint: foundry.outputs.endpoint
    foundryDeploymentName: names.foundryDeployment
    searchEndpoint: search.outputs.endpoint
    cosmosEndpoint: cosmos.outputs.endpoint
    storageAccountName: storage.outputs.name
  }
}

module frontDoor 'modules/front-door.bicep' = {
  scope: rg
  name: 'front-door'
  params: {
    profileName: names.afdProfile
    endpointName: names.afdEndpoint
    sku: frontDoorSku
    tags: tags
    apiHostname: containerApps.outputs.apiFqdn
    webHostname: containerApps.outputs.webFqdn
    apiPrivateLinkResourceId: containerApps.outputs.environmentId
    webPrivateLinkResourceId: containerApps.outputs.environmentId
  }
}

module budget 'modules/budget.bicep' = {
  scope: rg
  name: 'budget'
  params: {
    name: names.budget
    monthlyAmountUsd: monthlyBudgetUsd
  }
}

// -----------------------------------------------------------------------------
// Outputs
// -----------------------------------------------------------------------------

@description('Resource group containing the workload.')
output resourceGroupName string = rg.name

@description('User-assigned managed identity client ID (federated to GitHub).')
output managedIdentityClientId string = identity.outputs.clientId

@description('Foundry OpenAI-compatible endpoint root.')
output foundryEndpoint string = foundry.outputs.endpoint

@description('Public Front Door hostname (the app).')
output appHostname string = frontDoor.outputs.endpointHostname

@description('Container App API internal FQDN (for diagnostics).')
output apiInternalFqdn string = containerApps.outputs.apiFqdn
