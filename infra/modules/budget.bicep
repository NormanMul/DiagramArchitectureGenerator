// =============================================================================
// Resource-group-scoped budget with 50/80/100% notifications.
// Email targets are picked up from the deploying identity by default; override
// via parameters if you want a distribution list.
// =============================================================================

param name string
param monthlyAmountUsd int

@description('Emails to notify (in addition to the deploying user).')
param contactEmails array = []

@description('Budget start (UTC) in YYYY-MM-01T00:00:00Z. Default = first day of the deployment month.')
param startDate string = '${utcNow('yyyy-MM')}-01T00:00:00Z'

resource budget 'Microsoft.Consumption/budgets@2024-08-01' = {
  name: name
  properties: {
    timePeriod: {
      startDate: startDate
    }
    timeGrain: 'Monthly'
    amount: monthlyAmountUsd
    category: 'Cost'
    notifications: {
      'actual-50': {
        enabled: true
        operator: 'GreaterThan'
        threshold: 50
        contactEmails: contactEmails
        thresholdType: 'Actual'
      }
      'actual-80': {
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        contactEmails: contactEmails
        thresholdType: 'Actual'
      }
      'forecasted-100': {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        contactEmails: contactEmails
        thresholdType: 'Forecasted'
      }
    }
  }
}

output id string = budget.id
