// The blog's two containers on the shared storage account, and who may use
// them. Deployed as a module scoped to the storage account's own resource
// group (see main.bicep). Passwordless: roles for managed identities only.
//
// blog-drafts    studio API only (drafts, uploads, working media)
// blog-published studio API writes, read API reads (immutable snapshots)
//
// The Delegator role is needed at account scope so an identity whose data role
// is scoped to a container can still sign a user-delegation SAS; it grants no
// data access by itself.

targetScope = 'resourceGroup'

@description('Existing shared storage account.')
param storageAccountName string

@description('Principal ID of the studio API runtime identity.')
param studioApiPrincipalId string

@description('Principal ID of the read API runtime identity.')
param blogApiPrincipalId string

param draftsContainerName string = 'blog-drafts'
param publishedContainerName string = 'blog-published'

var contributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
var readerRoleId = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1' // Storage Blob Data Reader
var delegatorRoleId = 'db58b8e5-c6ad-4a2a-8342-4190687cbf4a' // Storage Blob Delegator

resource account 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' existing = {
  parent: account
  name: 'default'
}

resource drafts 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: draftsContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource published 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: publishedContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource studioApiDrafts 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(drafts.id, studioApiPrincipalId, contributorRoleId)
  scope: drafts
  properties: {
    principalId: studioApiPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', contributorRoleId)
  }
}

resource studioApiPublished 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(published.id, studioApiPrincipalId, contributorRoleId)
  scope: published
  properties: {
    principalId: studioApiPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', contributorRoleId)
  }
}

resource blogApiPublished 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(published.id, blogApiPrincipalId, readerRoleId)
  scope: published
  properties: {
    principalId: blogApiPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', readerRoleId)
  }
}

resource studioApiDelegator 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, studioApiPrincipalId, delegatorRoleId)
  scope: account
  properties: {
    principalId: studioApiPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', delegatorRoleId)
  }
}

resource blogApiDelegator 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, blogApiPrincipalId, delegatorRoleId)
  scope: account
  properties: {
    principalId: blogApiPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', delegatorRoleId)
  }
}
