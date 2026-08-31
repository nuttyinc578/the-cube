"use strict";
const http = require("http");

function start() {
  const requested = Number(process.argv[process.argv.indexOf("--port") + 1] || 0);
  const secret = process.env.NUTTYMOD_BRIDGE_SECRET || "";
  if (!secret) throw new Error("missing NuttyMod bridge secret");
  const runtime = process.versions.electron ? "electron" : "node-electron-compatible";
  const server = http.createServer((req, res) => {
    res.setHeader("Content-Type", "application/json");
    res.setHeader("Cache-Control", "no-store");
    if (req.headers["x-nuttymod-bootstrap"] !== secret) {
      res.writeHead(401);
      return res.end(JSON.stringify({ok: false, error: "unauthorized"}));
    }
    if (req.method === "GET" && req.url === "/health") {
      res.writeHead(200);
      return res.end(JSON.stringify({ok: true, service: "nuttymod-electron", runtime}));
    }
    res.writeHead(404);
    res.end(JSON.stringify({ok: false}));
  });
  server.listen(requested, "127.0.0.1", () => {
    process.stdout.write(JSON.stringify({
      ready: true,
      service: "electron",
      runtime,
      port: server.address().port
    }) + "\n");
  });
}

try {
  const electron = require("electron");
  if (electron && electron.app && typeof electron.app.whenReady === "function") {
    electron.app.whenReady().then(start);
  } else {
    start();
  }
} catch (_) {
  start();
}
