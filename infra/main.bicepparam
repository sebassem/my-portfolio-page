using './main.bicep'

param location = 'swedencentral'
param namingSuffix = 'sbm'
param aiSearchSku = 'basic'
param deployments = [
  {
    name: 'llm-deployment'
    model: {
      format: 'Microsoft'
      name: 'Phi-4'
      version: '7'
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

