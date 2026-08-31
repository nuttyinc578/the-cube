"use strict";

const assert = require("node:assert/strict");
const http = require("node:http");
const test = require("node:test");

const { compileCommand, createServer } = require("../server.js");

test("compiles readable commands into CPE numeric lines", () => {
  assert.equal(
    compileCommand(7, { action: "spawn", shape: "polygon", x: 12, y: 34, sides: 5, size: 20, mass: 2, color: [1, 2, 3] }),
    "CPE/1 7 3 12 34 5 20 2 1 2 3",
  );
  assert.equal(compileCommand(8, { action: "clear" }), "CPE/1 8 30");
  assert.throws(() => compileCommand(9, { action: "execute_code", source: "anything" }), /unknown CPE action/);
});

test("serves health, commands, and engine state", async (context) => {
  const server = createServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  context.after(() => new Promise((resolve) => server.close(resolve)));
  const { port } = server.address();
  const base = `http://127.0.0.1:${port}`;

  const health = await fetch(`${base}/health`).then((response) => response.json());
  assert.equal(health.ok, true);
  assert.equal(health.protocol, "CPE/1");

  const accepted = await fetch(`${base}/commands`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "burst", x: 90, y: 120, count: 12 }),
  }).then((response) => response.json());
  assert.match(accepted.line, /^CPE\/1 1 20 /);

  const queue = await fetch(`${base}/commands?after=0`).then((response) => response.json());
  assert.equal(queue.commands.length, 1);

  await fetch(`${base}/state`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ engine: "CPE", bodies: [{ id: 1 }], particle_count: 12 }),
  });
  const state = await fetch(`${base}/state`).then((response) => response.json());
  assert.equal(state.state.bodies[0].id, 1);
});
test("forwards cube_core cache to the Go port", async (context) => {
  let cached = null;
  const goCache = http.createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    cached = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    response.writeHead(202, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ ok: true, version: 3 }));
  });
  await new Promise((resolve) => goCache.listen(0, "127.0.0.1", resolve));
  context.after(() => new Promise((resolve) => goCache.close(resolve)));
  const goAddress = goCache.address();

  const bridge = createServer({ goCacheUrl: `http://127.0.0.1:${goAddress.port}` });
  await new Promise((resolve) => bridge.listen(0, "127.0.0.1", resolve));
  context.after(() => new Promise((resolve) => bridge.close(resolve)));
  const bridgeAddress = bridge.address();

  const result = await fetch(`http://127.0.0.1:${bridgeAddress.port}/state`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ engine: "CPE", cache_source: "cube_core", bodies: [{ id: 9 }] }),
  }).then((response) => response.json());

  assert.equal(result.go_cache.ok, true);
  assert.equal(result.go_cache.version, 3);
  assert.equal(cached.cache_source, "cube_core");
  assert.equal(cached.bodies[0].id, 9);
});
