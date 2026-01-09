using './main.bicep'

param location = 'swedencentral'
param namingPrefix = 'sbm'
param namingSuffix = '001'
param aiSearchSku = 'free'
param containerAppDomain = 'seifbassem.com'
param deployments = [
  {
    name: 'llm-deployment'
    model: {
      format: 'DeepSeek'
      name: 'DeepSeek-V3.2'
      version: '1'
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

