"use strict";
const http = require("http");
const fs = require("fs");
const path = require("path");

const requested = Number(process.argv[process.argv.indexOf("--port") + 1] || 0);
const bootstrapPath = path.join(__dirname, "nuttymod_bootstrap.html");
const secret = process.env.NUTTYMOD_BRIDGE_SECRET || "";
if (!secret) {
  process.stderr.write("missing NuttyMod bridge secret\n");
  process.exit(2);
}
const respond = (res, status, value, type = "application/json") => {
  res.writeHead(status, {"Content-Type": type, "Cache-Control": "no-store"});
  res.end(type === "application/json" ? JSON.stringify(value) : value);
};
const server = http.createServer((req, res) => {
  if (req.headers["x-nuttymod-bootstrap"] !== secret) {
    return respond(res, 401, {ok: false, error: "unauthorized"});
  }
  if (req.method === "GET" && req.url === "/health") {
    return respond(res, 200, {service: "nuttymod-node", ok: true, node: process.versions.node});
  }
  if (req.method === "GET" && req.url === "/nuttymod_bootstrap") {
    return respond(res, 200, fs.readFileSync(bootstrapPath, "utf8"), "text/html; charset=utf-8");
  }
  if (req.method === "POST" && req.url === "/finalize") {
    let body = "";
    let rejected = false;
    req.on("data", chunk => {
      if (rejected) return;
      if (Buffer.byteLength(body) + chunk.length > 65536) {
        rejected = true;
        respond(res, 413, {ok: false, error: "request too large"});
        return;
      }
      body += chunk;
    });
    req.on("end", () => {
      if (rejected) return;
      try {
        const value = JSON.parse(body || "{}");
        if (!value.authenticated || !value.go_port || !value.electron_port) {
          throw new Error("incomplete connection payload");
        }
        respond(res, 200, {
          ok: true,
          service: "nuttymod_bootstrap",
          session: `nm-${Date.now().toString(36)}`
        });
      } catch (error) {
        respond(res, 400, {ok: false, error: String(error.message || error)});
      }
    });
    return;
  }
  respond(res, 404, {ok: false, error: "not found"});
});

server.listen(requested, "127.0.0.1", () => {
  const address = server.address();
  process.stdout.write(JSON.stringify({ready: true, service: "node", port: address.port}) + "\n");
});
