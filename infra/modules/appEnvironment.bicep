param containerAppsEnvironmentName string

param location string = resourceGroup().location

param containerAppsIdentityResourceId string

param keyVaultUrl string

param certificateName string

resource appEnv 'Microsoft.App/managedEnvironments@2025-10-02-preview' = {
  name: containerAppsEnvironmentName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${containerAppsIdentityResourceId}': {}
    }
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    zoneRedundant: false
    vnetConfiguration: {
    internal: false
    }
  }

}

resource appCert 'Microsoft.App/managedEnvironments/certificates@2025-10-02-preview' = {
  name: certificateName
  parent: appEnv
  location: location
  properties: {
    certificateKeyVaultProperties: {
      identity: containerAppsIdentityResourceId
      keyVaultUrl: keyVaultUrl
    }
  }
}


output appEnvResourceId string = appEnv.id
output appCertResourceId string = appCert.id
