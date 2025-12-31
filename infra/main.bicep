targetScope = 'subscription'

param location string = deployment().location

param namingSuffix string = 'sbm'

param resourceGroupName string = 'rg-${namingSuffix}-infra'

param acrName string = 'acrportfolio${namingSuffix}infra'

param containerAppsIdentityName string = 'uai-${namingSuffix}-apps-infra'

param storageAccountName string = 'stg${namingSuffix}infra'

param foundryAccountName string = 'foundry-${namingSuffix}-infra'

param foundryProjectName string = '${foundryAccountName}-project'

param keyVaultName string = 'kv-${namingSuffix}-infra'

param aiSearchName string = 'aisearch${namingSuffix}infra'

param containerAppsEnvironmentName string = 'cae-${namingSuffix}-infra'

param containerAppName string = 'ca-${namingSuffix}-infra'

param containerAppAstroName string = 'ca-astro-${namingSuffix}-infra'

param aiSearchSku string = 'basic'

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

resource rg 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: resourceGroupName
  location: location
}

module containerAppsIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.3' = {
  scope: rg
  params: {
    name: containerAppsIdentityName
    location: location
  }
}
module storageAccount 'br/public:avm/res/storage/storage-account:0.31.0' = {
  scope: rg
  params: {
    name: storageAccountName
    location: location
    skuName: 'Standard_LRS'
    kind: 'StorageV2'
    accessTier: 'Cold'
    allowBlobPublicAccess: false
    publicNetworkAccess: 'Disabled'
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    roleAssignments: [
      {
        principalId: aiSearch.outputs.?systemAssignedMIPrincipalId ?? ''
        roleDefinitionIdOrName: '/providers/Microsoft.Authorization/roleDefinitions/2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
        description: 'Storage Blob Data Reader'
      }
      {
        principalId: containerAppsIdentity.outputs.principalId
        roleDefinitionIdOrName: '/providers/Microsoft.Authorization/roleDefinitions/2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
        description: 'Storage Blob Data Reader'
      }
      {
        principalId: deployer().objectId
        roleDefinitionIdOrName: '/providers/Microsoft.Authorization/roleDefinitions/ba92f5b4-2d11-453d-a403-e96b0029c9fe'
        description: 'Storage Blob Data Contributor'
      }
    ]
  }
}

module acr 'br/public:avm/res/container-registry/registry:0.9.3' = {
  scope: rg
  params: {
    name: acrName
    location: location
    acrSku: 'Basic'
    acrAdminUserEnabled: false
    anonymousPullEnabled: false
    networkRuleBypassOptions: 'None'
    zoneRedundancy: 'Disabled'
    roleAssignments: [
      {
        principalId: containerAppsIdentity.outputs.principalId
        roleDefinitionIdOrName: '/providers/Microsoft.Authorization/roleDefinitions/7f951dda-4ed3-4680-a7ca-43fe172d538d'
        description: 'AcrPull'
      }
    ]
  }
}

module foundry 'modules/foundry.bicep' = {
  scope: rg
  params: {
    deployments: deployments
    foundryAccountName: foundryAccountName
    foundryProjectName: foundryProjectName
    location: location
    namingSuffix: namingSuffix
    aiSearchPrincipalId: aiSearch.outputs.?systemAssignedMIPrincipalId
    containerAppsPrincipalId: containerAppsIdentity.outputs.principalId
  }
}

module aiSearch 'br/public:avm/res/search/search-service:0.12.0' = {
  scope: rg
  params: {
    name: aiSearchName
    location: location
    managedIdentities: {
      systemAssigned: true
    }
    sku: aiSearchSku
    disableLocalAuth: true
    roleAssignments: [
      {
        principalId: containerAppsIdentity.outputs.principalId
        roleDefinitionIdOrName: '/providers/Microsoft.Authorization/roleDefinitions/1407120a-92aa-4202-b7e9-c0e197c71c8f'
        description: 'Search Index Data Reader'
      }
      {
        principalId: deployer().objectId
        roleDefinitionIdOrName: '/providers/Microsoft.Authorization/roleDefinitions/1407120a-92aa-4202-b7e9-c0e197c71c8f'
        description: 'Search Index Data Reader'
      }
    ]
  }
}

module keyVault 'br/public:avm/res/key-vault/vault:0.13.3' = {
  scope: rg
  params: {
    name: keyVaultName
    location: location
    sku: 'standard'
    enableRbacAuthorization: true
    enableSoftDelete: false
    enablePurgeProtection: false
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      bypass: 'AzureServices'
    }
    secrets: [
      {
        name: 'foundryendpoint'
        value: foundry.outputs.foundryEndpoint
      }
      {
        name: 'searchendpoint'
        value: aiSearch.outputs.endpoint
      }
      {
        name: 'ragindexname'
        value: 'test'
      }
    ]
    roleAssignments: [
      {
        principalId: containerAppsIdentity.outputs.principalId
        roleDefinitionIdOrName: '/providers/Microsoft.Authorization/roleDefinitions/4633458b-17de-408a-b874-0445c86b69e6'
        description: 'Key Vault Secrets User'
      }
      {
        principalId: deployer().objectId
        roleDefinitionIdOrName: '/providers/Microsoft.Authorization/roleDefinitions/00482a5a-887f-4fb3-b363-3b7fe8e74483'
        description: 'Key Vault Administrator'
      }
      {
        principalId: deployer().objectId
        roleDefinitionIdOrName: '/providers/Microsoft.Authorization/roleDefinitions/4633458b-17de-408a-b874-0445c86b69e6'
        description: 'Key Vault Secrets User'
      }
    ]
  }
}

module appsEnvironment 'br/public:avm/res/app/managed-environment:0.11.3' = {
  scope: rg
  params: {
    name: containerAppsEnvironmentName
    location: location
    publicNetworkAccess: 'Enabled'
    zoneRedundant: false
    internal: false
  }
}

module containerApp 'br/public:avm/res/app/container-app:0.19.0' = {
  scope: rg
  params: {
    name: containerAppName
    location: location
    managedIdentities: {
      userAssignedResourceIds: [
        containerAppsIdentity.outputs.resourceId
      ]
    }
    registries: [
      {
        server: acr.outputs.loginServer
        identity: containerAppsIdentity.outputs.resourceId
      }
    ]
    ingressExternal: false
    ingressTargetPort: 8000
    containers: [
      {
        image: '${acr.outputs.loginServer}/portfolio-api:latest'
        name: 'portfolio-api'
        imageType: 'ContainerImage'
        resources: {
          cpu: json('0.25')
          memory: '0.5Gi'
        }
        env: [
          {
            name: 'AZURE_CLIENT_ID'
            value: containerAppsIdentity.outputs.clientId
          }
          {
            name: 'AZURE_OPENAI_ENDPOINT'
            secretRef: 'foundryendpoint'
          }
          {
            name: 'AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME'
            value: 'llm-deployment'
          }
          {
            name: 'AZURE_SEARCH_DEPLOYMENT_NAME'
            value: 'embedding-deployment'
          }
          {
            name: 'AZURE_OPENAI_API_VERSION'
            value: '2024-05-01-preview'
          }
          {
            name: 'AZURE_SEARCH_ENDPOINT'
            secretRef: 'searchendpoint'
          }
          {
            name: 'AZURE_SEARCH_INDEX_NAME'
            secretRef: 'ragindexname'
          }
          {
            name: 'AZURE_SEARCH_INSTANCE_NAME'
            value: aiSearch.outputs.name
          }
        ]
      }
    ]
    scaleSettings: {
      maxReplicas: 3
      minReplicas: 0
      rules: [
        {
          name: 'http-scaling'
          http: {
            metadata: {
              concurrentRequests: '10'
            }
          }

        }
      ]
    }
    environmentResourceId: appsEnvironment.outputs.resourceId
    identitySettings: [
      {
        identity: containerAppsIdentity.outputs.resourceId
      }
    ]
    secrets: [
      {
        identity: containerAppsIdentity.outputs.resourceId
        keyVaultUrl: '${keyVault.outputs.uri}secrets/foundryendpoint'
        name: 'foundryendpoint'
      }
      {
        identity: containerAppsIdentity.outputs.resourceId
        keyVaultUrl: '${keyVault.outputs.uri}secrets/searchendpoint'
        name: 'searchendpoint'
      }
      {
        identity: containerAppsIdentity.outputs.resourceId
        keyVaultUrl: '${keyVault.outputs.uri}secrets/ragindexname'
        name: 'ragindexname'
      }
    ]
  }
}

module containerAppAstro 'br/public:avm/res/app/container-app:0.19.0' = {
  scope: rg
  params: {
    name: containerAppAstroName
    location: location
    managedIdentities: {
      userAssignedResourceIds: [
        containerAppsIdentity.outputs.resourceId
      ]
    }
    registries: [
      {
        server: acr.outputs.loginServer
        identity: containerAppsIdentity.outputs.resourceId
      }
    ]
    ingressExternal: true
    ingressTargetPort: 4321
    containers: [
      {
        image: '${acr.outputs.loginServer}/portfolio-astro:latest'
        name: 'portfolio-astro'
        imageType: 'ContainerImage'
        resources: {
          cpu: json('0.25')
          memory: '0.5Gi'
        }
      }
    ]
    scaleSettings: {
      maxReplicas: 3
      minReplicas: 0
      rules: [
        {
          name: 'http-scaling'
          http: {
            metadata: {
              concurrentRequests: '10'
            }
          }

        }
      ]
    }
    environmentResourceId: appsEnvironment.outputs.resourceId
  }
}

output foundryEndpoint string = foundry.outputs.foundryEndpoint
output acrName string = acr.outputs.name
output resourceGroupName string = rg.name
output containerAppName string = containerApp.outputs.name
output containerAppAstroName string = containerAppAstro.outputs.name
