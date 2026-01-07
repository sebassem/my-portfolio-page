param location string = resourceGroup().location

param domainName string

param appEnvironmentName string

resource managedEnvironmentManagedCertificate 'Microsoft.App/managedEnvironments/managedCertificates@2025-10-02-preview' = {
  name: '${appEnvironmentName}/${domainName}-cert'
  location: location
  properties: {
    subjectName: domainName
    domainControlValidation: 'CNAME'
  }
}
