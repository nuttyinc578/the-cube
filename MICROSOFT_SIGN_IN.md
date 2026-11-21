# Microsoft sign-in setup

The Windows game requires Microsoft sign-in for GameLift Online. Solo, LAN and the existing GitHub contribution sign-in are unchanged. The PLUS page in GitHub Pages also asks for Microsoft sign-in before showing the Memberful account link. The page contains no private membership data; only Memberful grants and manages paid subscriptions, and its own account URL remains separate.

## In Microsoft Entra

The configured public client is `f34d69f0-add1-412f-8c96-9a5b7ea4aa4b`, in tenant `8b8c20a6-c2d7-45e0-b24f-15e6cae52c60`. This implementation uses that tenant-specific authority. It does not accept personal Microsoft accounts outside that tenant. Do not create or put a client secret in the game, the site, or the repository.

1. Open the Cube Beta client under **App registrations → Authentication**. Under **Mobile and desktop applications**, register `http://localhost` for the game's system-browser callback. Under **Single-page application**, register the exact URL `https://nuttyinc578.github.io/the-cube/microsoft-callback.html`. Leave implicit grants off. These are separate platform entries.
2. For online play, create a separate, single-tenant **Cube Beta Online API** app registration. Under **Expose an API**, use its default Application ID URI `api://<online-api-app-id>` and expose the delegated scope `Cube.Online`. In that API app's manifest set `api.requestedAccessTokenVersion` to `2`.
3. On the Cube Beta client registration, add that custom API's delegated **Cube.Online** permission. Grant consent if your tenant requires it. Copy the **Application (client) ID of the Online API**. That public ID is different from the sign-in client's ID. Microsoft Graph permissions are not required.

See Microsoft's [desktop redirect configuration](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration), [SPA redirect bridge](https://learn.microsoft.com/en-us/entra/msal/javascript/browser/redirect-bridge), and [exposing a web API scope](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-configure-app-expose-web-apis).

## GameLift and GitHub Pages

Deploy the updated reservation handler through the existing API Gateway HTTP API with a JWT authorizer. Use issuer `https://login.microsoftonline.com/8b8c20a6-c2d7-45e0-b24f-15e6cae52c60/v2.0`, the Online API application ID as the audience, and require `Cube.Online` on `POST /sessions/reserve`. Only the protected route should invoke the Lambda. Its claim checks also require the Cube Beta client and tenant. For a newly approved bounded test, supply the Online API app ID to `tools/Deploy-GameLiftTest.py` via `--microsoft-api-app-id`. This change does not start hosting.

In the compiled game's folder, put the deployed HTTPS reservation backend URL and the same Online API ID in `gamelift.json`:

```json
{
  "backend_url": "https://YOUR-GAMELIFT-RESERVATION-API",
  "microsoft_api_app_id": "YOUR-ONLINE-API-APPLICATION-ID"
}
```

The GitHub Pages workflow builds the pinned Microsoft browser library before deployment. To build locally, run `npm ci --ignore-scripts` and `npm run build` in `tools/site-auth`. Test the site on HTTPS or localhost. Do not paste login codes, access tokens, or session URLs into the repository.

Provider configuration and hosting must be completed before an end-to-end sign-in test. Verify one allowed account and one denied attempt, and confirm solo and LAN still work.
