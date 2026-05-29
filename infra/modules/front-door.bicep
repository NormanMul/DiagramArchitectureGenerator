// =============================================================================
// Azure Front Door (Standard) + WAF policy + 2 origins to internal Container
// Apps via Private Link.
//
// LIMITATION (locked default): SKU Standard ⇒ WAF Standard:
//   - Custom rules: yes (we use one — 60 req/min/IP on /api/generate)
//   - Microsoft Default Rule Set: Premium only
//   - Bot manager: Premium only
// Spec §8 wanted DRS + bot rules. Documented deviation in docs/architecture.md.
// =============================================================================

param profileName string
param endpointName string

@allowed(['Standard_AzureFrontDoor', 'Premium_AzureFrontDoor'])
param sku string = 'Standard_AzureFrontDoor'

param tags object

param apiHostname string
param webHostname string

@description('Resource ID of the target supporting Private Link (the ACA managed environment).')
param apiPrivateLinkResourceId string
param webPrivateLinkResourceId string

param plLocation string = 'southeastasia'

resource profile 'Microsoft.Cdn/profiles@2025-04-15' = {
  name: profileName
  location: 'global'
  sku: { name: sku }
  tags: tags
  identity: { type: 'SystemAssigned' }
}

resource endpoint 'Microsoft.Cdn/profiles/afdEndpoints@2025-04-15' = {
  parent: profile
  name: endpointName
  location: 'global'
  tags: tags
  properties: {
    enabledState: 'Enabled'
  }
}

// --- Origin groups ---

resource apiOriginGroup 'Microsoft.Cdn/profiles/originGroups@2025-04-15' = {
  parent: profile
  name: 'og-api'
  properties: {
    loadBalancingSettings: {
      sampleSize: 4
      successfulSamplesRequired: 3
      additionalLatencyInMilliseconds: 50
    }
    healthProbeSettings: {
      probePath: '/healthz'
      probeRequestType: 'GET'
      probeProtocol: 'Https'
      probeIntervalInSeconds: 100
    }
    sessionAffinityState: 'Disabled'
  }
}

resource webOriginGroup 'Microsoft.Cdn/profiles/originGroups@2025-04-15' = {
  parent: profile
  name: 'og-web'
  properties: {
    loadBalancingSettings: {
      sampleSize: 4
      successfulSamplesRequired: 3
      additionalLatencyInMilliseconds: 50
    }
    healthProbeSettings: {
      probePath: '/api/health'
      probeRequestType: 'GET'
      probeProtocol: 'Https'
      probeIntervalInSeconds: 100
    }
    sessionAffinityState: 'Disabled'
  }
}

resource apiOrigin 'Microsoft.Cdn/profiles/originGroups/origins@2025-04-15' = {
  parent: apiOriginGroup
  name: 'aca-api'
  properties: {
    hostName: apiHostname
    httpPort: 80
    httpsPort: 443
    originHostHeader: apiHostname
    priority: 1
    weight: 1000
    enabledState: 'Enabled'
    enforceCertificateNameCheck: true
    sharedPrivateLinkResource: {
      privateLink: { id: apiPrivateLinkResourceId }
      privateLinkLocation: plLocation
      requestMessage: 'AFD origin for ${apiHostname}'
      groupId: 'managedEnvironments'
    }
  }
}

resource webOrigin 'Microsoft.Cdn/profiles/originGroups/origins@2025-04-15' = {
  parent: webOriginGroup
  name: 'aca-web'
  properties: {
    hostName: webHostname
    httpPort: 80
    httpsPort: 443
    originHostHeader: webHostname
    priority: 1
    weight: 1000
    enabledState: 'Enabled'
    enforceCertificateNameCheck: true
    sharedPrivateLinkResource: {
      privateLink: { id: webPrivateLinkResourceId }
      privateLinkLocation: plLocation
      requestMessage: 'AFD origin for ${webHostname}'
      groupId: 'managedEnvironments'
    }
  }
}

// --- Routes ---

resource apiRoute 'Microsoft.Cdn/profiles/afdEndpoints/routes@2025-04-15' = {
  parent: endpoint
  name: 'route-api'
  dependsOn: [apiOrigin]
  properties: {
    originGroup: { id: apiOriginGroup.id }
    supportedProtocols: ['Https']
    patternsToMatch: ['/api/*']
    forwardingProtocol: 'HttpsOnly'
    httpsRedirect: 'Enabled'
    linkToDefaultDomain: 'Enabled'
    enabledState: 'Enabled'
    cacheConfiguration: null // no caching on API
  }
}

resource webRoute 'Microsoft.Cdn/profiles/afdEndpoints/routes@2025-04-15' = {
  parent: endpoint
  name: 'route-web'
  dependsOn: [webOrigin]
  properties: {
    originGroup: { id: webOriginGroup.id }
    supportedProtocols: ['Https']
    patternsToMatch: ['/*']
    forwardingProtocol: 'HttpsOnly'
    httpsRedirect: 'Enabled'
    linkToDefaultDomain: 'Enabled'
    enabledState: 'Enabled'
  }
}

// --- WAF policy + security policy ---

resource waf 'Microsoft.Network/FrontDoorWebApplicationFirewallPolicies@2025-03-01' = {
  name: replace('waf${profileName}', '-', '')
  location: 'global'
  sku: { name: sku }
  properties: {
    policySettings: {
      enabledState: 'Enabled'
      mode: 'Prevention'
      requestBodyCheck: 'Enabled'
    }
    customRules: {
      rules: [
        {
          name: 'RateLimitGenerate'
          priority: 100
          ruleType: 'RateLimitRule'
          rateLimitDurationInMinutes: 1
          rateLimitThreshold: 60
          matchConditions: [
            {
              matchVariable: 'RequestUri'
              operator: 'Contains'
              negateCondition: false
              matchValue: ['/api/generate']
              transforms: ['Lowercase']
            }
          ]
          action: 'Block'
        }
      ]
    }
  }
}

resource securityPolicy 'Microsoft.Cdn/profiles/securityPolicies@2025-04-15' = {
  parent: profile
  name: 'sp-default'
  properties: {
    parameters: {
      type: 'WebApplicationFirewall'
      wafPolicy: { id: waf.id }
      associations: [
        {
          domains: [{ id: endpoint.id }]
          patternsToMatch: ['/*']
        }
      ]
    }
  }
}

output profileId string = profile.id
output endpointId string = endpoint.id
output endpointHostname string = endpoint.properties.hostName
output wafPolicyId string = waf.id
