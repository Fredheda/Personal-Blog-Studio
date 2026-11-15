import { ManagedIdentityCredential } from "@azure/identity";

let credential: ManagedIdentityCredential | undefined;

/** A bearer token for the studio API, from this app's own managed identity. */
export async function getStudioToken(): Promise<string> {
  const clientId = process.env.AZURE_CLIENT_ID;
  const audience = process.env.STUDIO_API_AUDIENCE;
  if (!clientId || !audience) {
    throw new Error("the studio API identity is not configured");
  }
  credential ??= new ManagedIdentityCredential({ clientId });
  const token = await credential.getToken(`${audience}/.default`);
  return token.token;
}
