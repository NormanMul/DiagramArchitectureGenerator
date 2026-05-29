// =============================================================================
// Container Apps environment (internal-only, VNet-integrated) + 2 apps:
//   - api: FastAPI + diagrams + MCP server
//   - web: Next.js 15 SSR
//
// Both apps:
//   - Use user-assigned MI for ACR pull + runtime Azure access (no secrets).
//   - Scale to zero; min 0, max 3, http concurrency 20.
//   - Start with a placeholder image (mcr.microsoft.com/azuredocs/aci-helloworld);
//     real image is rolled out by deploy-app.yml / deploy-frontend.yml via
//     az containerapp update --image ...
// =============================================================================

param environmentName string
param apiAppName string
param webAppName string
param location string
param tags object

param subnetId string
param logAnalyticsCustomerId string
@secure()
param logAnalyticsSharedKey string
param appInsightsConnectionString string

param identityResourceId string
param identityClientId string

param acrLoginServer string

param foundryEndpoint string
param foundryDeploymentName string
param searchEndpoint string
param cosmosEndpoint string
param storageAccountName string

@description('Placeholder image (replaced by deploy-app.yml on first run).')
param placeholderImage string = 'mcr.microsoft.com/azuredocs/aci-helloworld:latest'

resource env 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: environmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
    vnetConfiguration: {
      internal: true
      infrastructureSubnetId: subnetId
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    zoneRedundant: false
  }
}

var commonIdentity = {
  type: 'UserAssigned'
  userAssignedIdentities: {
    '${identityResourceId}': {}
  }
}

var commonEnvVars = [
  { name: 'AZURE_CLIENT_ID', value: identityClientId }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
  { name: 'OTEL_RESOURCE_ATTRIBUTES', value: 'service.namespace=archgen,deployment.environment=prod' }
]

resource api 'Microsoft.App/containerApps@2025-01-01' = {
  name: apiAppName
  location: location
  tags: tags
  identity: commonIdentity
  properties: {
    environmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
        traffic: [{ latestRevision: true, weight: 100 }]
      }
      registries: [
        {
          server: acrLoginServer
          identity: identityResourceId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: placeholderImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: concat(commonEnvVars, [
            { name: 'FOUNDRY_ENDPOINT', value: foundryEndpoint }
            { name: 'FOUNDRY_DEPLOYMENT', value: foundryDeploymentName }
            { name: 'SEARCH_ENDPOINT', value: searchEndpoint }
            { name: 'COSMOS_ENDPOINT', value: cosmosEndpoint }
            { name: 'STORAGE_ACCOUNT', value: storageAccountName }
            { name: 'SERVICE_NAME', value: 'archgen-api' }
          ])
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/healthz', port: 8000 }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: { path: '/healthz', port: 8000 }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
        rules: [
          {
            name: 'http-concurrency'
            http: { metadata: { concurrentRequests: '20' } }
          }
        ]
      }
    }
  }
}

resource web 'Microsoft.App/containerApps@2025-01-01' = {
  name: webAppName
  location: location
  tags: tags
  identity: commonIdentity
  properties: {
    environmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false
        targetPort: 3000
        transport: 'http'
        allowInsecure: false
        traffic: [{ latestRevision: true, weight: 100 }]
      }
      registries: [
        {
          server: acrLoginServer
          identity: identityResourceId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'web'
          image: placeholderImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: concat(commonEnvVars, [
            // The web app talks to the api via the internal ACA cluster DNS.
            { name: 'BACKEND_API_URL', value: 'https://${api.properties.configuration.ingress.fqdn}' }
            { name: 'SERVICE_NAME', value: 'archgen-web' }
            { name: 'NODE_ENV', value: 'production' }
          ])
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/api/health', port: 3000 }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
        rules: [
          {
            name: 'http-concurrency'
            http: { metadata: { concurrentRequests: '20' } }
          }
        ]
      }
    }
  }
}

output environmentId string = env.id
output apiFqdn string = api.properties.configuration.ingress.fqdn
output webFqdn string = web.properties.configuration.ingress.fqdn
