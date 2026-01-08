param certKeyVaultName string

resource certkeyVault 'Microsoft.KeyVault/vaults@2025-05-01' existing = {
  name: certKeyVaultName
}

output certKeyVaultResourceId string = certkeyVault.id
output keyVaultUri string = certkeyVault.properties.vaultUri
