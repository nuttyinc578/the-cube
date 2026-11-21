import { broadcastResponseToMainFrame } from "@azure/msal-browser/redirect-bridge";

broadcastResponseToMainFrame().catch(() => {
  document.getElementById("callback-status").textContent =
    "This sign-in could not finish. Close this window and return to the PLUS page.";
});
