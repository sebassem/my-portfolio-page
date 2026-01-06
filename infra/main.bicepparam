using './main.bicep'

param location = 'swedencentral'
param namingPrefix = 'sbm'
param namingSuffix = '001'
param aiSearchSku = 'free'
param deployments = [
  /*{
    name: 'llm-deployment'
    model: {
      format: 'DeepSeek'
      name: 'DeepSeek-V3.2'
      version: '1'
    }
    sku: {
      capacity: 20
      name: 'GlobalStandard'
    }
  }*/
  {
    name: 'llm-deployment'
    model: {
      format: 'OpenAI'
      name: 'gpt-4o-mini'
      version: '2024-07-18'
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

