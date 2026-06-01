using '../main.bicep'

param environmentName = 'dev'
param location = 'southeastasia'
param workloadName = 'archgen'

param foundryModelName = 'gpt-5.4-mini'  // cheaper for dev iteration
param foundryModelVersion = '2026-03-17'
param foundryTpmCapInThousands = 10

param searchSku = 'free'

param frontDoorSku = 'Standard_AzureFrontDoor'
param frontDoorEndpointName = 'diagramarchitecturegenerator-dev'

param githubRepo = 'NormanMul/DiagramArchitectureGenerator'
param githubBranch = 'main'

// /24 to leave room for prod alongside in shared dev/prod scenarios.
param vnetAddressSpace = '10.50.0.0/16'
param subnetAca = '10.50.0.0/23'
param subnetPe = '10.50.2.0/27'

param monthlyBudgetUsd = 100

param adminPrincipalId = ''

param tags = {
  workload: 'archgen'
  env: 'dev'
  managedBy: 'bicep'
  source: 'https://github.com/NormanMul/DiagramArchitectureGenerator'
  costCenter: 'mcaps-personal'
}
