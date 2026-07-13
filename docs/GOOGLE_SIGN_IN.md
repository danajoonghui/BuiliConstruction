# Google sign-in activation

BUILI uses Google Identity Services in popup/JavaScript callback mode. The browser receives a Google ID token and sends it to `POST /v1/auth/oidc/exchange`; the API verifies the Google discovery document, asymmetric signature, issuer, audience, expiry, subject, and verified email before creating a BUILI session. There is no Google client secret in this flow. The Web client ID is public; only backend/runtime secrets belong in Secrets Manager.

## 1. Create the Google Auth project

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create a dedicated production project such as `buili-production-auth`.
2. Open **Google Auth Platform → Branding**.
3. Set:
   - App name: `BUILI`
   - User support email: an actively monitored BUILI address
   - Home page: `https://builiconstruction.com`
   - Privacy policy: `https://builiconstruction.com/privacy`
   - Terms: `https://builiconstruction.com/terms`
   - Authorized domain: `builiconstruction.com`
4. Under **Audience**, choose **External**. While testing, add only the intended Google accounts as test users. Publish to production only after the login, account-linking, logout, deletion, privacy, and support paths are ready.
5. Under **Data Access**, request only the basic identity scopes needed for sign-in: `openid`, `email`, and `profile`. BUILI does not need Drive, Gmail, Calendar, or other Google API scopes for authentication.

## 2. Create the Web client

1. Open **Google Auth Platform → Clients → Create client**.
2. Choose **Web application** and name it `BUILI Production Web`.
3. Add these **Authorized JavaScript origins** exactly:

   ```text
   https://builiconstruction.com
   https://www.builiconstruction.com
   https://app.builiconstruction.com
   http://localhost:3000
   ```

4. Do not add a redirect URI for the current popup/callback implementation. A redirect URI is needed only if BUILI is changed to Google's redirect UX mode.
5. Copy the resulting value ending in `.apps.googleusercontent.com`. This is the `OIDC_CLIENT_ID`/`BUILI_OIDC_CLIENT_ID`, not a password.

## 3. Configure the backend

For local Docker development, put the client ID in an uncommitted environment file:

```text
BUILI_OIDC_ISSUER=https://accounts.google.com
BUILI_OIDC_CLIENT_ID=<google-web-client-id>
```

For AWS production, update the JSON value of the Secrets Manager secret created by Terraform. Keep all existing keys and set:

```json
{
  "OIDC_CLIENT_ID": "<google-web-client-id>"
}
```

Do not overwrite the secret with only this one key: the same JSON record also contains database URLs, JWT/origin secrets, and optional provider keys. Terraform injects `OIDC_CLIENT_ID` into API, worker, and migration task definitions as `BUILI_OIDC_CLIENT_ID`.

The public `GET /v1/auth/capabilities` response exposes the same client ID to the browser. This is intentional and removes the need to rebuild the frontend when the Google client ID changes. The API still treats only a token whose `aud` exactly matches this ID as valid.

## 4. Restart and validate

1. Force a new deployment of the API service after updating Secrets Manager.
2. Open `https://api.builiconstruction.com/v1/auth/capabilities` and confirm:

   ```json
   {
     "data": {
       "google_oidc_enabled": true,
       "google_client_id": "...apps.googleusercontent.com"
     }
   }
   ```

3. Open `https://app.builiconstruction.com/login` in a normal top-level browser window, click **Continue with Google**, and test:
   - a new Google account provisions one BUILI user and one starter organization;
   - a returning Google subject resolves to the same user;
   - an email that already has a password account is rejected with `OIDC_LINK_REQUIRED` until explicitly linked while signed in;
   - logout clears the BUILI host-only session cookies;
   - an ID token issued to another client ID is rejected;
   - a non-verified email claim is rejected.

## 5. Common failures

- `origin_mismatch`: the exact scheme/hostname is missing from Authorized JavaScript origins. Ports matter on localhost.
- `Google sign-in is not configured`: `OIDC_CLIENT_ID` is absent from the running API secret or the API has not restarted.
- `OIDC_TOKEN_INVALID`: frontend and backend are using different client IDs, or the token expired.
- One Tap/popup not displayed: third-party cookie/privacy settings or popup blocking prevented the prompt. Test in a top-level HTTPS window, not an embedded browser.
- `OIDC_LINK_REQUIRED`: an existing password account owns the email; sign in with that method and use the explicit identity-link route rather than silently merging accounts.

## Release note

Google production branding normally expects public home, privacy, and terms URLs under the authorized domain. These pages and their wording should be reviewed against BUILI's actual retention, subprocessors, support, deletion, and customer-contract practices before publishing the OAuth app.
