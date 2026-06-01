using '../main.bicep'

param environmentName = 'prod'
param location = 'southeastasia'
param workloadName = 'archgen'

// Foundry — verified in SEA on 2026-05-29.
param foundryModelName = 'gpt-5.4'
param foundryModelVersion = '2026-03-05'
param foundryTpmCapInThousands = 50

// AI Search Free tier (no PE) — see docs/icon-compliance.md waiver.
param searchSku = 'free'

// Front Door Standard — see docs/architecture.md for WAF Premium deviation.
param frontDoorSku = 'Standard_AzureFrontDoor'
param frontDoorEndpointName = 'diagramarchitecturegenerator'

// GitHub repo for OIDC federation.
param githubRepo = 'NormanMul/DiagramArchitectureGenerator'
param githubBranch = 'main'

// Networking.
param vnetAddressSpace = '10.40.0.0/16'
param subnetAca = '10.40.0.0/23'
param subnetPe = '10.40.2.0/27'

// Cost guardrail.
param monthlyBudgetUsd = 550

// Optional human admin (Object ID). Leave empty to skip user role assignments.
param adminPrincipalId = ''

param tags = {
  workload: 'archgen'
  env: 'prod'
  managedBy: 'bicep'
  source: 'https://github.com/NormanMul/DiagramArchitectureGenerator'
  costCenter: 'mcaps-personal'
}
