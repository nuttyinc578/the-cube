"use strict";

const http = require("node:http");
const { URL } = require("node:url");

const PROTOCOL = "CPE/1";
const MAX_BODY_BYTES = 256 * 1024;
const MAX_COMMANDS = 5000;

const OPCODES = Object.freeze({
  spawn_box: 1,
  spawn_circle: 2,
  spawn_polygon: 3,
  gravity: 10,
  impulse: 11,
  force: 12,
  particle_burst: 20,
  clear: 30,
  pause: 40,
});

function numeric(value, label, low, high, integer = false) {
  const result = Number(value);
  if (!Number.isFinite(result)) {
    throw new Error(`${label} must be a finite number`);
  }
  const bounded = Math.max(low, Math.min(high, result));
  return integer ? Math.round(bounded) : bounded;
}

function color(value = [238, 108, 56]) {
  if (!Array.isArray(value) || value.length !== 3) {
    throw new Error("color must contain three RGB numbers");
  }
  return value.map((channel) => numeric(channel, "color", 0, 255, true));
}

function encode(sequence, opcode, values = []) {
  return [PROTOCOL, sequence, opcode, ...values].join(" ");
}

function compileCommand(sequence, payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("command payload must be an object");
  }
  const action = String(payload.action ?? payload.command ?? "").trim().toLowerCase();

  if (["spawn", "spawn_box", "spawn_circle", "spawn_polygon"].includes(action)) {
    let shape = String(payload.shape ?? "box").trim().toLowerCase();
    if (action.startsWith("spawn_")) shape = action.slice(6);
    if (!["box", "circle", "polygon"].includes(shape)) {
      throw new Error("shape must be box, circle, or polygon");
    }
    const x = numeric(payload.x ?? 320, "x", -10000, 10000);
    const y = numeric(payload.y ?? 80, "y", -10000, 10000);
    const size = numeric(payload.size ?? payload.radius ?? 28, "size", 4, 250);
    const mass = numeric(payload.mass ?? 1, "mass", 0.05, 1000);
    const rgb = color(payload.color);
    if (shape === "polygon") {
      const sides = numeric(payload.sides ?? 6, "sides", 3, 12, true);
      return encode(sequence, OPCODES.spawn_polygon, [x, y, sides, size, mass, ...rgb]);
    }
    return encode(sequence, OPCODES[`spawn_${shape}`], [x, y, size, mass, ...rgb]);
  }

  if (["gravity", "set_gravity"].includes(action)) {
    const gx = numeric(payload.x ?? payload.gx ?? 0, "gravity x", -5000, 5000);
    const gy = numeric(payload.y ?? payload.gy ?? 900, "gravity y", -5000, 5000);
    return encode(sequence, OPCODES.gravity, [gx, gy]);
  }

  if (["impulse", "force"].includes(action)) {
    const id = numeric(payload.id, "entity id", 1, 2147483647, true);
    const xName = action === "impulse" ? "ix" : "fx";
    const yName = action === "impulse" ? "iy" : "fy";
    const x = numeric(payload.x ?? payload[xName] ?? 0, "x", -100000, 100000);
    const y = numeric(payload.y ?? payload[yName] ?? 0, "y", -100000, 100000);
    return encode(sequence, OPCODES[action], [id, x, y]);
  }

  if (["burst", "particle_burst", "particles"].includes(action)) {
    const x = numeric(payload.x ?? 320, "x", -10000, 10000);
    const y = numeric(payload.y ?? 180, "y", -10000, 10000);
    const count = numeric(payload.count ?? 28, "count", 1, 500, true);
    const speed = numeric(payload.speed ?? 260, "speed", 0, 5000);
    const lifetime = numeric(payload.lifetime ?? 1.1, "lifetime", 0.05, 20);
    const rgb = color(payload.color ?? [250, 198, 72]);
    return encode(sequence, OPCODES.particle_burst, [x, y, count, speed, lifetime, ...rgb]);
  }

  if (action === "clear") return encode(sequence, OPCODES.clear);

  if (["pause", "resume"].includes(action)) {
    let paused = action === "pause";
    if (Object.hasOwn(payload, "paused")) paused = Boolean(payload.paused);
    return encode(sequence, OPCODES.pause, [paused ? 1 : 0]);
  }

  throw new Error(`unknown CPE action: ${action || "<empty>"}`);
}

function sendJson(response, status, payload) {
  const body = Buffer.from(JSON.stringify(payload));
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": body.length,
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Cache-Control": "no-store",
  });
  response.end(body);
}

function readJson(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    request.on("data", (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) {
        reject(new Error("request body is too large"));
        request.destroy();
        return;
      }
      chunks.push(chunk);
    });
    request.on("end", () => {
      try {
        const text = Buffer.concat(chunks).toString("utf8");
        resolve(text ? JSON.parse(text) : {});
      } catch {
        reject(new Error("request body must be valid JSON"));
      }
    });
    request.on("error", reject);
  });
}

function createServer(options = {}) {
  let sequence = 0;
  let commands = [];
  let latestState = { engine: "CPE", bodies: [], particle_count: 0 };
  let stateUpdatedAt = null;
  const goCacheUrl = String(options.goCacheUrl ?? process.env.CPE_GO_CACHE_URL ?? "").replace(/\/$/, "");
  let goCache = { configured: Boolean(goCacheUrl), ok: null, url: goCacheUrl || null, detail: "waiting for cube_core cache" };

  async function forwardToGoCache(payload) {
    if (!goCacheUrl) return goCache;
    try {
      const cacheResponse = await fetch(`${goCacheUrl}/cache`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(1500),
      });
      const result = await cacheResponse.json();
      goCache = {
        configured: true,
        ok: cacheResponse.ok && result.ok === true,
        url: goCacheUrl,
        version: result.version ?? null,
        detail: cacheResponse.ok ? "cube_core cache stored on Go port" : String(result.error ?? cacheResponse.status),
      };
    } catch (error) {
      goCache = { configured: true, ok: false, url: goCacheUrl, detail: error instanceof Error ? error.message : String(error) };
    }
    return goCache;
  }

  return http.createServer(async (request, response) => {
    if (request.method === "OPTIONS") {
      sendJson(response, 204, {});
      return;
    }
    const url = new URL(request.url, "http://cpe.local");

    try {
      if (request.method === "GET" && url.pathname === "/health") {
        sendJson(response, 200, {
          ok: true,
          service: "cube-physics-engine-node-bridge",
          protocol: PROTOCOL,
          node: process.versions.node,
          queued_commands: commands.length,
          go_cache: goCache,
        });
        return;
      }

      if (request.method === "GET" && url.pathname === "/protocol") {
        sendJson(response, 200, { protocol: PROTOCOL, opcodes: OPCODES });
        return;
      }

      if (request.method === "POST" && url.pathname === "/commands") {
        const payload = await readJson(request);
        const nextSequence = sequence + 1;
        const line = compileCommand(nextSequence, payload);
        sequence = nextSequence;
        const item = { sequence, line, received_at: new Date().toISOString() };
        commands.push(item);
        if (commands.length > MAX_COMMANDS) commands = commands.slice(-MAX_COMMANDS);
        sendJson(response, 202, { ok: true, ...item });
        return;
      }

      if (request.method === "GET" && url.pathname === "/commands") {
        const after = numeric(url.searchParams.get("after") ?? 0, "after", 0, 2147483647, true);
        const limit = numeric(url.searchParams.get("limit") ?? 100, "limit", 1, 250, true);
        const selected = commands.filter((item) => item.sequence > after).slice(0, limit);
        sendJson(response, 200, { ok: true, protocol: PROTOCOL, commands: selected, latest_sequence: sequence });
        return;
      }

      if (request.method === "POST" && url.pathname === "/state") {
        latestState = await readJson(request);
        stateUpdatedAt = new Date().toISOString();
        const cache = await forwardToGoCache(latestState);
        sendJson(response, 202, { ok: true, updated_at: stateUpdatedAt, go_cache: cache });
        return;
      }

      if (request.method === "GET" && url.pathname === "/state") {
        sendJson(response, 200, { ok: true, updated_at: stateUpdatedAt, state: latestState });
        return;
      }

      sendJson(response, 404, { ok: false, error: "route not found" });
    } catch (error) {
      sendJson(response, 400, { ok: false, error: error instanceof Error ? error.message : String(error) });
    }
  });
}

function option(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

function startFromCli() {
  const host = option("host", process.env.CPE_NODE_HOST ?? process.env.HOST ?? "127.0.0.1");
  const port = numeric(option("port", process.env.CPE_NODE_PORT ?? process.env.PORT ?? 4310), "port", 0, 65535, true);
  const server = createServer({ goCacheUrl: process.env.CPE_GO_CACHE_URL });
  server.listen(port, host, () => {
    const address = server.address();
    process.stdout.write(`${JSON.stringify({ ready: true, service: "cpe-node", host, port: address.port, protocol: PROTOCOL })}\n`);
  });
  const shutdown = () => server.close(() => process.exit(0));
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
  return server;
}

if (require.main === module) startFromCli();

module.exports = { OPCODES, PROTOCOL, compileCommand, createServer, startFromCli };
