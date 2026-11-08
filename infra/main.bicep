// Azure Container Apps deployment for the blog studio and the blog read API.
//
// Provisions, into an existing resource group (rg-chatbot):
//   - a Container Apps environment (no Log Analytics: appLogsConfiguration is omitted)
//   - four user-assigned managed identities: one for ACR pulls, one runtime
//     identity per app (least privilege: the read API identity can only read)
//   - the studio web app (external ingress, Easy Auth)
//   - the studio API (internal ingress, Entra token validation, web identity only)
//   - the read API (external ingress, Entra token validation, approved callers only)
//   - the blog containers and their roles on the shared storage account (storage.bicep)
//
// Easy Auth and token validation are NOT optional: the Entra app registrations
// are created by the setup scripts first and their IDs are required parameters,
// so this template cannot deploy an unauthenticated app.
//
// Deploy with infra/deploy.sh <full-commit-sha>; never directly.

@description('Region for all resources. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('Existing Azure Container Registry name.')
param acrName string = 'acrchatbotfredheda'

param environmentName string = 'cae-blogstudio'
param webAppName string = 'ca-blogstudio-web'
param studioApiAppName string = 'ca-blogstudio-api'
param blogApiAppName string = 'ca-blogapi'

param acrPullIdentityName string = 'id-blogstudio-acrpull'
param webIdentityName string = 'id-blogstudio-web'
param studioApiIdentityName string = 'id-blogstudio-api'
param blogApiIdentityName string = 'id-blogapi'

@description('Existing shared storage account that holds the blog containers.')
param storageAccountName string = 'fhstorageportfolio'

@description('Resource group of the shared storage account.')
param storageResourceGroup string = 'FrederikHedaPlayground'

@description('Full 40-character commit SHA of the images to run.')
param imageTag string

@description('Entra tenant ID.')
param tenantId string

@description('Client ID of the Entra app registration behind Easy Auth on the studio web app.')
param webClientId string

@description('Client secret of that app registration. Stored only as a container app secret.')
@secure()
param webClientSecret string

@description('Client ID of the Entra app registration that is the audience of the studio API.')
param studioApiClientId string

@description('Client ID of the Entra app registration that is the audience of the read API.')
param blogApiClientId string

@description('Client IDs of the managed identities allowed to call the read API. At least one: an empty list could let any caller with a valid token through.')
@minLength(1)
param approvedClientIds array

// Built-in AcrPull role definition ID (constant across all tenants).
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var loginServer = '${acrName}.azurecr.io'
var issuer = '${environment().authentication.loginEndpoint}${tenantId}/v2.0'
var storageBlobUrl = 'https://${storageAccountName}.blob.${environment().suffixes.storage}'

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource acrPullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: acrPullIdentityName
  location: location
}

resource webIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: webIdentityName
  location: location
}

resource studioApiIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: studioApiIdentityName
  location: location
}

resource blogApiIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: blogApiIdentityName
  location: location
}

// AcrPull on the registry only, for the pull identity only.
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, acrPullIdentity.id, acrPullRoleId)
  scope: acr
  properties: {
    principalId: acrPullIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
  }
}

// Environment with NO Log Analytics - the one meter that silently accrues. Omitting
// appLogsConfiguration is how you get no logs; live logs remain available via
// `az containerapp logs show --follow`.
resource appEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: environmentName
  location: location
  properties: {}
}

// Studio web app: external ingress behind Easy Auth. Calls the studio API over
// the environment's internal DNS name.
resource web 'Microsoft.App/containerApps@2025-01-01' = {
  name: webAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${acrPullIdentity.id}': {}
      '${webIdentity.id}': {}
    }
  }
  dependsOn: [
    acrPull
  ]
  properties: {
    environmentId: appEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 3000
        transport: 'auto'
        // ARM's PUT treats the whole ingress object as authoritative. When a
        // custom domain is bound (blog-studio.frederikheda.com), declare
        // customDomains here in the same change, or the next deploy wipes it.
      }
      registries: [
        {
          server: loginServer
          identity: acrPullIdentity.id
        }
      ]
      secrets: [
        {
          name: 'microsoft-provider-authentication-secret'
          value: webClientSecret
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'blogstudio-web'
          image: '${loginServer}/blogstudio-web:${imageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'STUDIO_API_URL'
              value: 'http://${studioApiAppName}'
            }
            {
              name: 'STUDIO_API_AUDIENCE'
              value: 'api://${studioApiClientId}'
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: webIdentity.properties.clientId
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

// Studio API: internal ingress only. Reachable in-environment as
// http://ca-blogstudio-api (port 80 -> targetPort 8000).
resource studioApi 'Microsoft.App/containerApps@2025-01-01' = {
  name: studioApiAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${acrPullIdentity.id}': {}
      '${studioApiIdentity.id}': {}
    }
  }
  dependsOn: [
    acrPull
  ]
  properties: {
    environmentId: appEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: loginServer
          identity: acrPullIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'blogstudio-api'
          image: '${loginServer}/blogstudio-api:${imageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'AZURE_CLIENT_ID'
              value: studioApiIdentity.properties.clientId
            }
            {
              name: 'BLOG_STORAGE_ACCOUNT_URL'
              value: storageBlobUrl
            }
            {
              name: 'BLOG_DRAFTS_CONTAINER'
              value: 'blog-drafts'
            }
            {
              name: 'BLOG_PUBLISHED_CONTAINER'
              value: 'blog-published'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

// Read API: external hostname, but every request needs a valid Entra token from
// an approved caller. Read-only identity.
resource blogApi 'Microsoft.App/containerApps@2025-01-01' = {
  name: blogApiAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${acrPullIdentity.id}': {}
      '${blogApiIdentity.id}': {}
    }
  }
  dependsOn: [
    acrPull
  ]
  properties: {
    environmentId: appEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: loginServer
          identity: acrPullIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'blogapi'
          image: '${loginServer}/blogapi:${imageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'AZURE_CLIENT_ID'
              value: blogApiIdentity.properties.clientId
            }
            {
              name: 'BLOG_STORAGE_ACCOUNT_URL'
              value: storageBlobUrl
            }
            {
              name: 'BLOG_PUBLISHED_CONTAINER'
              value: 'blog-published'
            }
            {
              name: 'BLOG_API_AUDIENCE'
              value: 'api://${blogApiClientId}'
            }
            {
              name: 'BLOG_REQUIRED_ROLE'
              value: 'Blog.Read'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

// platform.enabled is what actually turns authentication on for an app:
// identityProviders and globalValidation alone deploy cleanly and do nothing
// without it. Never make these resources conditional.

resource webAuth 'Microsoft.App/containerApps/authConfigs@2025-01-01' = {
  parent: web
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureactivedirectory'
      excludedPaths: [
        '/healthz'
      ]
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: webClientId
          clientSecretSettingName: 'microsoft-provider-authentication-secret'
          openIdIssuer: issuer
        }
        validation: {
          allowedAudiences: [
            webClientId
          ]
        }
      }
    }
  }
}

resource studioApiAuth 'Microsoft.App/containerApps/authConfigs@2025-01-01' = {
  parent: studioApi
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      unauthenticatedClientAction: 'Return401'
      excludedPaths: [
        '/healthz'
      ]
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: studioApiClientId
          openIdIssuer: issuer
        }
        validation: {
          // The audience is api://<appId>: Entra's identifier-URI policy
          // rejects an arbitrary api://<name> string.
          allowedAudiences: [
            'api://${studioApiClientId}'
          ]
          defaultAuthorizationPolicy: {
            allowedApplications: [
              webIdentity.properties.clientId
            ]
          }
        }
      }
    }
  }
}

resource blogApiAuth 'Microsoft.App/containerApps/authConfigs@2025-01-01' = {
  parent: blogApi
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      unauthenticatedClientAction: 'Return401'
      excludedPaths: [
        '/healthz'
      ]
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: blogApiClientId
          openIdIssuer: issuer
        }
        validation: {
          allowedAudiences: [
            'api://${blogApiClientId}'
          ]
          defaultAuthorizationPolicy: {
            allowedApplications: approvedClientIds
          }
        }
      }
    }
  }
}

// Containers and roles live in the storage account's own resource group.
module storage 'storage.bicep' = {
  name: 'blog-storage'
  scope: resourceGroup(storageResourceGroup)
  params: {
    storageAccountName: storageAccountName
    studioApiPrincipalId: studioApiIdentity.properties.principalId
    blogApiPrincipalId: blogApiIdentity.properties.principalId
  }
}

output webFqdn string = web.properties.configuration.ingress.fqdn
output blogApiFqdn string = blogApi.properties.configuration.ingress.fqdn
