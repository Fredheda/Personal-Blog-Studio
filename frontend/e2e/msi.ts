import { createServer } from "node:http";

import { MSI_PORT } from "./ports.ts";

// A stand-in for the managed-identity token endpoint the web app's proxy asks:
// every request gets a dummy token. The studio API behind it checks no token
// (the platform does that in production).
createServer((_request, response) => {
  response.writeHead(200, { "content-type": "application/json" });
  response.end(
    JSON.stringify({
      access_token: "e2e-token",
      expires_on: String(Math.floor(Date.now() / 1000) + 3600),
      resource: "e2e",
      token_type: "Bearer",
    }),
  );
}).listen(Number(process.env.E2E_MSI_PORT ?? MSI_PORT), "127.0.0.1");
