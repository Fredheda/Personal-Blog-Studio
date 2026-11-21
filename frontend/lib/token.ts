import "server-only";

import { ManagedIdentityCredential } from "@azure/identity";

let credential: ManagedIdentityCredential | undefined;

/** A bearer token for the studio API, from this app's own managed identity.
 *  Null when no audience is configured (a local run): the proxy then sends no
 *  Authorization header. A deployed app always has the audience (Bicep); without
 *  it the studio API's platform check answers 401, so this fails closed. */
export async function getStudioToken(): Promise<string | null> {
  const audience = process.env.STUDIO_API_AUDIENCE;
  if (!audience) return null;
  const clientId = process.env.AZURE_CLIENT_ID;
  if (!clientId) {
    throw new Error("the studio API identity is not configured");
  }
  credential ??= new ManagedIdentityCredential({ clientId });
  const token = await credential.getToken(`${audience}/.default`);
  return token.token;
}
