param location string = resourceGroup().location

param namingSuffix string = 'sbmo'

param foundryAccountName string = 'foundry${namingSuffix}infra'

param foundryProjectName string = '${foundryAccountName}-project'

param aiSearchPrincipalId string = ''

param containerAppsPrincipalId string = ''

param deployments array = [
  {
    name: 'llm-deployment'
    model: {
      format: 'DeepSeek'
      name: 'DeepSeek-V3.2'
      version: '1'
    }
    sku: {
      capacity: 250
      name: 'GlobalStandard'
    }
  }
  {
    name: 'embedding-deployment'
    model: {
      format: 'OpenAI'
      name: 'text-embedding-ada-002'
      version: '2'
    }
    sku: {
      capacity: 3
      name: 'Standard'
    }
  }
]


resource foundry 'Microsoft.CognitiveServices/accounts@2025-10-01-preview' = {
  name: foundryAccountName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
    customSubDomainName: foundryAccountName
    allowProjectManagement: true
    associatedProjects: [
      foundryProjectName
    ]
    networkAcls: {
      defaultAction: 'Allow'
    }
    restore: false
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-10-01-preview' = {
  name: foundryProjectName
  parent: foundry
  identity: {
    type: 'SystemAssigned'
  }
  location: location
  properties: {
    displayName: foundryProjectName
  }
}

@batchSize(1)
resource deployModels 'Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview' = [for deployment in deployments: {
  name: deployment.name
  parent: foundry
  sku: {
    name: deployment.sku.name
    capacity: deployment.sku.capacity
  }
  properties: {
    model: {
      format: deployment.model.format
      name: deployment.model.name
      version: deployment.model.version
    }
  }
}]

module searchFoundryRoleAssignment 'br/public:avm/ptn/authorization/resource-role-assignment:0.1.2' = {
  params: {
    principalId: aiSearchPrincipalId
    resourceId: foundry.id
    roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
    description: 'Cognitive Services OpenAI User'
  }
}

module containerAppsFoundryRoleAssignment 'br/public:avm/ptn/authorization/resource-role-assignment:0.1.2' = {
  params: {
    principalId: containerAppsPrincipalId
    resourceId: foundryProject.id
    roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
    description: 'Cognitive Services OpenAI User'
  }
}

output foundryProjectResourceId string = foundryProject.id
output foundryEndpoint string = foundry.properties.endpoints['OpenAI Language Model Instance API']
