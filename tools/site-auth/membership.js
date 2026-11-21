import { PublicClientApplication } from "@azure/msal-browser";

const clientId = "f34d69f0-add1-412f-8c96-9a5b7ea4aa4b";
const tenantId = "8b8c20a6-c2d7-45e0-b24f-15e6cae52c60";
const authority = `https://login.microsoftonline.com/${tenantId}`;
const redirectUri = new URL("./microsoft-callback.html", window.location.href).href;
const memberfulAccount = "https://the-cube-beta-marketplace.memberful.com/account";

const button = document.getElementById("microsoft-login");
const status = document.getElementById("microsoft-status");
const membership = document.getElementById("membership-account");

function unlockMembership() {
  const link = document.createElement("a");
  link.className = "button primary";
  link.href = memberfulAccount;
  link.referrerPolicy = "no-referrer";
  link.textContent = "Open Memberful membership account";
  membership.replaceChildren(link);
  membership.hidden = false;
}

try {
  const auth = new PublicClientApplication({
    auth: { clientId, authority, redirectUri },
    cache: { cacheLocation: "memoryStorage" },
  });
  await auth.initialize();
  button.disabled = false;
  status.textContent = "Sign in with a Microsoft account in the Cube Beta organization to continue.";
  button.addEventListener("click", async () => {
    button.disabled = true;
    membership.hidden = true;
    membership.replaceChildren();
    status.textContent = "Waiting for Microsoft sign-in…";
    try {
      const result = await auth.loginPopup({ scopes: ["openid", "profile"], prompt: "select_account" });
      if (result.account?.tenantId !== tenantId || result.idTokenClaims?.tid !== tenantId
          || result.idTokenClaims?.aud !== clientId) {
        throw new Error("Unexpected Microsoft account");
      }
      unlockMembership();
      button.textContent = "Switch Microsoft account";
      status.textContent = "Microsoft sign-in complete. Continue to Memberful to manage your subscription.";
    } catch {
      status.textContent = "Sign-in didn’t finish. Allow pop-ups and try again with an account in the Cube Beta organization.";
    } finally {
      button.disabled = false;
    }
  });
} catch {
  status.textContent = "Microsoft sign-in is unavailable. Try reloading this page.";
}
