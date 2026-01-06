using './main.bicep'

param location = 'swedencentral'
param namingPrefix = 'sbm'
param namingSuffix = '001'
param aiSearchSku = 'free'
param deployments = [
  {
    name: 'llm-deployment'
    model: {
      format: 'OpenAI'
      name: 'gpt-4.1-mini'
      version: '2025-04-14'
    }
    sku: {
      capacity: 150
      name: 'GlobalStandard'
    }
  }
  {
    name: 'embedding-deployment'
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
    sku: {
      capacity: 150
      name: 'GlobalStandard'
    }
  }
]

