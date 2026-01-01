param appEnvironmentName string

param location string = resourceGroup().location

param shareName string

param storageAccountName string

param appEnvironmentStorageName string

resource appEnvironment 'Microsoft.App/managedEnvironments@2025-10-02-preview' = {
  name: appEnvironmentName
  location: location
  properties: {
    publicNetworkAccess: 'Enabled'
    zoneRedundant: false
    vnetConfiguration: {
      internal: false
    }
  }
}

resource appEnvironmentStorage 'Microsoft.App/managedEnvironments/storages@2025-10-02-preview' = {
  name: appEnvironmentStorageName
  parent: appEnvironment
  properties: {
    azureFile: {
      shareName: shareName
      accessMode: 'ReadWrite'
      accountName: storageAccountName
    }
  }
}

output appEnvironmentResourceId string = appEnvironment.id
output appEnvironmentStorageName string = appEnvironmentStorage.name
