"""Local NuttyMod connection, authentication, and repair orchestration.

Every network listener created here binds to 127.0.0.1. The helper stack uses
Node.js for the bootstrap bridge, Go for local account authentication,
PowerShell for first-account enrollment, and Electron (or a Node compatibility
host when Electron is unavailable) for the final handshake.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


CONNECTION_VERSION = "1.0.0"
BOOTSTRAP_DIRECTORY = "nuttymod_bootstrap"
CONNECTION_STATE_FILE = ".nuttymod_connection_state.json"
REPAIR_MANIFEST_FILE = ".nuttymod_connection_manifest.json"


NODE_BRIDGE = r'''"use strict";
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
'''

ELECTRON_BRIDGE = r'''"use strict";
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
'''

BOOTSTRAP_HTML = r'''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>NuttyMod Bootstrap</title></head>
<body data-service="nuttymod_bootstrap">
  <main>
    <h1>NuttyMod Bootstrap</h1>
    <p>Local Node, Go Auth, and Electron connection bridge.</p>
  </main>
</body>
</html>
'''


# Compact TCP implementation used by the current connection protocol. Keeping
# the service on raw loopback TCP avoids a slow net/http toolchain build while
# preserving the Go-owned random port and authenticated JSON handshake.
GO_AUTH = r'''package main
import("crypto/rand";"crypto/subtle";"encoding/hex";"encoding/json";"flag";"fmt";"io";"net";"os";"path/filepath";"regexp";"strings";"time")
type Account struct{Username string `json:"username"`;Token string `json:"token"`}
type Request struct{Secret string `json:"secret"`;Action string `json:"action"`;Username string `json:"username"`;Proof string `json:"proof"`;Token string `json:"token"`}
type Response struct{OK bool `json:"ok"`;Service string `json:"service,omitempty"`;Account bool `json:"account,omitempty"`;Username string `json:"username,omitempty"`;Error string `json:"error,omitempty"`}
var validName=regexp.MustCompile(`^[A-Za-z0-9_.-]{3,32}$`)
func readAccount(path string)(Account,error){var v Account;b,e:=os.ReadFile(path);if e!=nil{return v,e};e=json.Unmarshal(b,&v);return v,e}
func writeAccount(path string,v Account)error{if e:=os.MkdirAll(filepath.Dir(path),0700);e!=nil{return e};b,e:=json.MarshalIndent(v,"","  ");if e!=nil{return e};t:=path+".new";if e=os.WriteFile(t,append(b,'\n'),0600);e!=nil{return e};return os.Rename(t,path)}
func newToken()(string,error){b:=make([]byte,32);if _,e:=rand.Read(b);e!=nil{return "",e};return hex.EncodeToString(b),nil}
func send(c net.Conn,v Response){_ = json.NewEncoder(c).Encode(v)}
func handle(c net.Conn,secret,path string){defer c.Close();_ = c.SetDeadline(time.Now().Add(10*time.Second));var q Request;if json.NewDecoder(io.LimitReader(c,65536)).Decode(&q)!=nil{send(c,Response{Error:"invalid request"});return};if subtle.ConstantTimeCompare([]byte(q.Secret),[]byte(secret))!=1{send(c,Response{Error:"forbidden"});return};switch q.Action{case"health":_,e:=readAccount(path);send(c,Response{OK:true,Service:"nuttymod-go-auth",Account:e==nil});case"register":if !validName.MatchString(q.Username)||len(q.Proof)<4{send(c,Response{Error:"Use a 3-32 character account name and an auth phrase of at least 4 characters."});return};t,e:=newToken();if e!=nil||writeAccount(path,Account{q.Username,t})!=nil{send(c,Response{Error:"account could not be saved"});return};send(c,Response{OK:true,Username:q.Username});case"login":a,e:=readAccount(path);ok:=e==nil&&subtle.ConstantTimeCompare([]byte(strings.TrimSpace(q.Token)),[]byte(a.Token))==1;if !ok{send(c,Response{Error:"login failed"});return};send(c,Response{OK:true,Username:a.Username});default:send(c,Response{Error:"unknown action"})}}
func main(){port:=flag.Int("port",0,"local TCP port");path:=flag.String("account","","local account file");flag.Parse();secret:=os.Getenv("NUTTYMOD_AUTH_SECRET");if secret==""||*path==""{fmt.Fprintln(os.Stderr,"missing auth configuration");os.Exit(2)};listener,e:=net.Listen("tcp",fmt.Sprintf("127.0.0.1:%d",*port));if e!=nil{fmt.Fprintln(os.Stderr,e);os.Exit(3)};actual:=listener.Addr().(*net.TCPAddr).Port;ready,_:=json.Marshal(map[string]any{"ready":true,"service":"go-auth","port":actual});fmt.Println(string(ready));for{c,e:=listener.Accept();if e!=nil{os.Exit(4)};go handle(c,secret,*path)}}
'''

POWERSHELL_AUTH = r'''$ErrorActionPreference = "Stop"
$port = $env:NUTTYMOD_AUTH_PORT
$secret = $env:NUTTYMOD_AUTH_SECRET
if ([string]::IsNullOrWhiteSpace($port) -or [string]::IsNullOrWhiteSpace($secret)) { throw "NuttyMod Auth is missing its local settings." }
$host.UI.RawUI.WindowTitle = "NuttyMod Auth"
Write-Host ""; Write-Host "NUTTYMOD AUTH" -ForegroundColor Cyan
Write-Host "Create a local account. Your auth phrase is never stored." -ForegroundColor White
$username = Read-Host "NuttyMod account name"
$secure = Read-Host "NuttyMod auth phrase" -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $phrase = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $request = @{ secret=$secret; action="register"; username=$username; proof=$phrase } | ConvertTo-Json -Compress
    $client = [Net.Sockets.TcpClient]::new("127.0.0.1", [int]$port)
    try {
        $stream=$client.GetStream(); $writer=[IO.StreamWriter]::new($stream,[Text.UTF8Encoding]::new($false),1024,$true); $reader=[IO.StreamReader]::new($stream,[Text.Encoding]::UTF8,$false,1024,$true)
        $writer.WriteLine($request); $writer.Flush(); $result=($reader.ReadLine() | ConvertFrom-Json)
    } finally { if($writer){$writer.Dispose()}; if($reader){$reader.Dispose()}; $client.Dispose() }
    if(-not $result.ok){$message=if($result.error){[string]$result.error}else{"NuttyMod Auth rejected the account."};throw $message}
    Write-Host "Signed in as $($result.username). You can return to the game." -ForegroundColor Green; Start-Sleep -Seconds 2
} finally { if($pointer -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)}; $phrase=$null }
'''
NODE_PACKAGE = r'''{
  "name": "nuttymod-bootstrap",
  "private": true,
  "type": "commonjs",
  "engines": {"node": ">=22"}
}
'''

RUNTIME_FILES = {
    "package.json": NODE_PACKAGE,
    "nuttymod_node_bridge.js": NODE_BRIDGE,
    "nuttymod_auth.go": GO_AUTH,
    "nuttymod_auth.ps1": POWERSHELL_AUTH,
    "nuttymod_electron_bridge.js": ELECTRON_BRIDGE,
    "nuttymod_bootstrap.html": BOOTSTRAP_HTML,
}
SHIPPED_GO_SOURCE_SHA256 = "87f923879c355e5823e41758662f3b677621163715e10d2fbab224266f00afd1"
SHIPPED_GO_BINARY_SHA256 = "38a638a4f357c3284cc76167574a14f429fac6ce1e82beef2954ec4ccd2c40b6"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.urandom(6).hex()}.new")
    try:
        with temporary.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, indent=2).encode("utf-8") + b"\n")


def _ensure_go_auth_binary(bootstrap: Path, repair_root: Path) -> tuple[dict[str, str], dict[str, str]]:
    source = bootstrap / "nuttymod_auth.go"
    binary = bootstrap / "nuttymod_auth.exe"
    state_path = bootstrap / ".nuttymod_go_build.json"
    source_hash = _sha256(source.read_bytes())
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    binary_hash = _sha256(binary.read_bytes()) if binary.is_file() else ""
    binary_shape_valid = (
        bool(binary_hash)
        and binary.stat().st_size > 1_000_000
        and binary.read_bytes()[:2] == b"MZ"
    )
    state_valid = (
        isinstance(state, dict)
        and state.get("source_sha256") == source_hash
        and state.get("binary_sha256") == binary_hash
    )
    shipped_valid = (
        source_hash == SHIPPED_GO_SOURCE_SHA256
        and binary_hash == SHIPPED_GO_BINARY_SHA256
    )
    if binary_shape_valid and (state_valid or shipped_valid):
        if not state_valid:
            _atomic_json(state_path, {
                "connection_version": CONNECTION_VERSION,
                "source_sha256": source_hash,
                "binary_sha256": binary_hash,
                "shipped_binary": True,
                "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
        return ({"file": binary.name, "action": "verified"}, {
            "sha256": binary_hash, "source_sha256": source_hash, "action": "verified",
        })

    action = "installed" if not binary.exists() else "rebuilt"
    if binary.is_file():
        _atomic_write(repair_root / binary.name, binary.read_bytes())
    go = shutil.which("go")
    if not go:
        raise RuntimeError("Go is required to rebuild the NuttyMod Auth executable")
    temporary = bootstrap / f".nuttymod_auth.{os.urandom(6).hex()}.exe"
    environment = os.environ.copy()
    environment.update({"GOTOOLCHAIN": "local", "CGO_ENABLED": "0"})
    try:
        completed = subprocess.run(
            [go, "build", "-trimpath", "-ldflags", "-s -w", "-o", str(temporary), str(source)],
            cwd=str(bootstrap), env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", creationflags=_creation_flags(),
            timeout=105, check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Go Auth rebuild failed: {completed.stdout.strip()}")
        payload = temporary.read_bytes()
        if len(payload) <= 1_000_000 or payload[:2] != b"MZ":
            raise RuntimeError("Go Auth rebuild produced an invalid Windows executable")
        os.replace(temporary, binary)
    finally:
        temporary.unlink(missing_ok=True)
    binary_hash = _sha256(binary.read_bytes())
    _atomic_json(state_path, {
        "connection_version": CONNECTION_VERSION,
        "source_sha256": source_hash,
        "binary_sha256": binary_hash,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    return ({"file": binary.name, "action": action}, {
        "sha256": binary_hash, "source_sha256": source_hash, "action": action,
    })

def ensure_runtime_files(addons_dir: Path) -> list[dict[str, str]]:
    """Atomically repair helper files from embedded, reviewed sources."""
    addons = Path(addons_dir).resolve()
    bootstrap = addons / BOOTSTRAP_DIRECTORY
    bootstrap.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    repair_root = addons / "update_backups" / f"{timestamp}-connection-repair"
    repaired: list[dict[str, str]] = []
    manifest: dict[str, Any] = {"version": CONNECTION_VERSION, "files": {}}

    for name, source in RUNTIME_FILES.items():
        payload = source.encode("utf-8")
        expected = _sha256(payload)
        target = bootstrap / name
        current = target.read_bytes() if target.is_file() else None
        action = "verified"
        if current is None or _sha256(current) != expected:
            action = "installed" if current is None else "rewritten"
            if current is not None:
                backup = repair_root / name
                _atomic_write(backup, current)
            _atomic_write(target, payload)
            if _sha256(target.read_bytes()) != expected:
                raise OSError(f"Repair verification failed for {name}")
            repaired.append({"file": name, "action": action})
        manifest["files"][name] = {"sha256": expected, "action": action}

    binary_repair, binary_manifest = _ensure_go_auth_binary(bootstrap, repair_root)
    manifest["files"]["nuttymod_auth.exe"] = binary_manifest
    if binary_repair["action"] != "verified":
        repaired.append(binary_repair)

    manifest["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest["backup_directory"] = str(repair_root) if repair_root.exists() else ""
    _atomic_json(bootstrap / REPAIR_MANIFEST_FILE, manifest)
    return repaired


def _auth_home() -> Path:
    override = os.environ.get("NUTTYMOD_AUTH_HOME", "").strip()
    if override:
        return Path(override).resolve()
    local = os.environ.get("LOCALAPPDATA", "").strip()
    return (Path(local) if local else Path.home() / "AppData" / "Local") / "NuttyMod"


def _read_account(path: Path) -> dict[str, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(value, dict):
        return {}
    username = str(value.get("username", "")).strip()
    token = str(value.get("token", "")).strip()
    if not username or len(token) < 32:
        return {}
    return {"username": username, "token": token}


def local_account_status() -> dict[str, Any]:
    """Return public local-account state without exposing the login token."""
    account_file = _auth_home() / "auth.json"
    account = _read_account(account_file)
    return {
        "signed_in": bool(account),
        "username": str(account.get("username", "")),
        "credential_present": account_file.is_file(),
        "account_file": str(account_file),
    }


def logout_local_account(addons_dir: Path) -> tuple[bool, str]:
    """Remove the active local credential and the last public connection state."""
    account_file = _auth_home() / "auth.json"
    account = _read_account(account_file)
    username = str(account.get("username", "")).strip() or "local account"
    connection_state = Path(addons_dir).resolve() / CONNECTION_STATE_FILE
    failures: list[str] = []
    credential_removed = account_file.is_file()
    for path, label in (
        (account_file, "local account credential"),
        (connection_state, "connection state"),
    ):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            failures.append(f"{label}: {exc}")
    if failures:
        return False, "Logout could not remove " + "; ".join(failures)
    if credential_removed:
        return True, (
            f"Logged out {username}. The active local token was removed; "
            "restart to create or connect another account."
        )
    return True, "No active local NuttyMod account was found."

def _json_request(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 4.0,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, method="GET" if data is None else "POST")
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Local connection failed: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Local service returned an invalid response")
    return result


def _go_request(port: int, secret: str, action: str, **values: Any) -> dict[str, Any]:
    request = {"secret": secret, "action": action, **values}
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=4.0) as connection:
            connection.settimeout(4.0)
            stream = connection.makefile("rwb")
            stream.write(json.dumps(request).encode("utf-8") + b"\n")
            stream.flush()
            line = stream.readline(65537)
    except OSError as exc:
        raise RuntimeError(f"Go Auth local connection failed: {exc}") from exc
    if not line or len(line) > 65536:
        raise RuntimeError("Go Auth returned an invalid response size")
    try:
        result = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Go Auth returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Go Auth returned an invalid response")
    return result


def _node_major_version(node: str) -> int:
    try:
        completed = subprocess.run(
            [node, "--version"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            creationflags=_creation_flags(), timeout=8, check=False,
        )
        value = completed.stdout.strip().lstrip("vV").split(".", 1)[0]
        return int(value) if completed.returncode == 0 else 0
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0

def _read_startup(process: subprocess.Popen[str], timeout: float) -> dict[str, Any]:
    messages: queue.Queue[str | None] = queue.Queue()

    def reader() -> None:
        if process.stdout is None:
            messages.put(None)
            return
        for line in process.stdout:
            messages.put(line)
        messages.put(None)

    threading.Thread(target=reader, daemon=True).start()
    deadline = time.monotonic() + max(0.1, timeout)
    diagnostics: list[str] = []
    while time.monotonic() < deadline:
        try:
            line = messages.get(timeout=max(0.01, deadline - time.monotonic()))
        except queue.Empty:
            break
        if line is None:
            detail = diagnostics[-1] if diagnostics else f"exit code {process.poll()}"
            raise RuntimeError(f"Local service exited before startup ({detail})")
        stripped = line.strip()
        if not stripped:
            continue
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            diagnostics.append(stripped[:240])
            diagnostics = diagnostics[-3:]
            continue
        if (
            isinstance(value, dict)
            and value.get("ready") is True
            and isinstance(value.get("port"), int)
        ):
            return value
        diagnostics.append(stripped[:240])
        diagnostics = diagnostics[-3:]
    detail = diagnostics[-1] if diagnostics else "no readiness record"
    raise RuntimeError(f"Local service did not publish its random port in time ({detail})")


def _creation_flags(visible: bool = False) -> int:
    if os.name != "nt":
        return 0
    return int(
        getattr(subprocess, "CREATE_NEW_CONSOLE" if visible else "CREATE_NO_WINDOW", 0)
    )


class ConnectionSession:
    """Run one paced local NuttyMod connection handshake."""

    def __init__(self, addons_dir: Path, duration: float = 120.0) -> None:
        self.addons_dir = Path(addons_dir).resolve()
        self.duration = max(0.2, float(duration))
        self._started_at = 0.0
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._processes: list[subprocess.Popen[str]] = []
        self._snapshot: dict[str, Any] = {
            "stage": "PREPARING CONNECTION",
            "detail": "Starting the local NuttyMod connection stack",
            "done": False,
            "success": False,
            "error": "",
            "account_required": False,
            "username": "",
            "node_port": 0,
            "go_port": 0,
            "electron_port": 0,
            "electron_runtime": "",
            "bootstrap_url": "",
            "session": "",
            "repaired": [],
        }

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("Connection session already started")
        self._started_at = time.monotonic()
        self._thread = threading.Thread(target=self._run_guarded, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()
        self._stop_processes()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            value = dict(self._snapshot)
        elapsed = max(0.0, time.monotonic() - self._started_at) if self._started_at else 0.0
        value["elapsed"] = elapsed
        value["progress"] = min(1.0, elapsed / self.duration)
        return value

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def _update(self, **changes: Any) -> None:
        with self._lock:
            self._snapshot.update(changes)

    def _pace(self, ratio: float) -> None:
        target = self._started_at + (self.duration * ratio)
        while time.monotonic() < target:
            if self._cancel.wait(min(0.1, target - time.monotonic())):
                raise RuntimeError("Connection cancelled")

    def _launch(
        self,
        command: list[str],
        *,
        cwd: Path,
        environment: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> tuple[subprocess.Popen[str], dict[str, Any]]:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creation_flags(),
        )
        self._processes.append(process)
        try:
            ready = _read_startup(process, timeout)
        except Exception:
            self._stop_process(process)
            raise
        return process, ready

    def _launch_auth_prompt(self, script: Path, port: int, secret: str) -> None:
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if not powershell:
            raise RuntimeError("PowerShell is required to create a NuttyMod account")
        environment = os.environ.copy()
        environment["NUTTYMOD_AUTH_PORT"] = str(port)
        environment["NUTTYMOD_AUTH_SECRET"] = secret
        process = subprocess.Popen(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            cwd=str(script.parent),
            env=environment,
            creationflags=_creation_flags(visible=True),
        )
        self._processes.append(process)
        while process.poll() is None:
            if self._cancel.wait(0.1):
                self._stop_process(process)
                raise RuntimeError("Connection cancelled")
        if process.returncode != 0:
            raise RuntimeError("NuttyMod Auth was cancelled or could not create the account")

    def _run_guarded(self) -> None:
        try:
            result = self._run()
            self._update(done=True, success=True, **result)
        except Exception as exc:
            self._update(done=True, success=False, error=str(exc), stage="CONNECTION FAILED")
        finally:
            self._stop_processes()

    def _run(self) -> dict[str, Any]:
        bootstrap = self.addons_dir / BOOTSTRAP_DIRECTORY
        self._update(stage="VERIFYING CONNECTION FILES", detail="Checking protected helper fingerprints")
        repaired = ensure_runtime_files(self.addons_dir)
        self._update(repaired=repaired)

        node = shutil.which("node")
        if not node:
            raise RuntimeError("Node.js was not found; install Node.js v22 or newer")
        node_major = _node_major_version(node)
        if node_major < 22:
            raise RuntimeError(f"NuttyMod requires Node.js v22 or newer; found v{node_major or 'unknown'}")
        go_auth = bootstrap / "nuttymod_auth.exe"
        if not go_auth.is_file():
            raise RuntimeError("The compiled NuttyMod Go Auth service is missing")
        secret = os.urandom(32).hex()
        bridge_headers = {"X-NuttyMod-Bootstrap": secret}
        environment = os.environ.copy()
        environment["NUTTYMOD_AUTH_SECRET"] = secret
        environment["NUTTYMOD_BRIDGE_SECRET"] = secret

        self._pace(0.12)
        self._update(stage="CONNECTING NODE.JS", detail="Requesting a random local Node.js port")
        _, node_ready = self._launch(
            [node, str(bootstrap / "nuttymod_node_bridge.js"), "--port", "0"],
            cwd=bootstrap,
            environment=environment,
        )
        node_port = int(node_ready["port"])
        node_health = _json_request(
            f"http://127.0.0.1:{node_port}/health",
            headers=bridge_headers,
        )
        if node_health.get("ok") is not True:
            raise RuntimeError("Node.js bridge health check failed")
        self._update(node_port=node_port, detail=f"Node.js connected on local port {node_port}")

        self._pace(0.28)
        self._update(stage="CONNECTING GO AUTH", detail="Starting NuttyMod Auth on a random Go port")
        account_file = _auth_home() / "auth.json"
        account_file.parent.mkdir(parents=True, exist_ok=True)
        _, go_ready = self._launch(
            [str(go_auth), "--port", "0", "--account", str(account_file)],
            cwd=bootstrap,
            environment=environment,
            timeout=10.0,
        )
        go_port = int(go_ready["port"])
        health = _go_request(go_port, secret, "health")
        if health.get("ok") is not True:
            raise RuntimeError("Go Auth health check failed")
        self._update(go_port=go_port, detail=f"NuttyMod Go Auth connected on local port {go_port}")

        self._pace(0.45)
        account = _read_account(account_file)
        if not account:
            if account_file.exists():
                corrupt = account_file.with_name(
                    f"auth.corrupt-{time.strftime('%Y%m%d-%H%M%S')}.json"
                )
                os.replace(account_file, corrupt)
            self._update(
                stage="NUTTYMOD AUTH REQUIRED",
                detail="Use the PowerShell window to create your local NuttyMod account",
                account_required=True,
            )
            self._launch_auth_prompt(bootstrap / "nuttymod_auth.ps1", go_port, secret)
            account = _read_account(account_file)
            if not account:
                raise RuntimeError("NuttyMod Auth did not create a valid local account")

        self._update(stage="LOGGING IN", detail=f"Authenticating {account['username']} with the Go port")
        login = _go_request(
            go_port,
            secret,
            "login",
            token=account["token"],
        )
        if login.get("ok") is not True:
            raise RuntimeError("NuttyMod account login failed")
        username = str(login.get("username", account["username"]))
        self._update(username=username, account_required=False)

        self._pace(0.65)
        bootstrap_url = f"http://127.0.0.1:{node_port}/nuttymod_bootstrap"
        self._update(stage="CONNECTING NUTTYMOD_BOOTSTRAP", detail=bootstrap_url, bootstrap_url=bootstrap_url)
        try:
            bootstrap_request = Request(bootstrap_url, headers=bridge_headers)
            with urlopen(bootstrap_request, timeout=4.0) as response:
                bootstrap_page = response.read().decode("utf-8")
        except (URLError, OSError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"nuttymod_bootstrap could not be opened: {exc}") from exc
        if "nuttymod_bootstrap" not in bootstrap_page:
            raise RuntimeError("nuttymod_bootstrap returned the wrong website")

        self._pace(0.80)
        electron = shutil.which("electron")
        runtime_name = "Electron" if electron else "Electron-compatible Node"
        self._update(
            stage="CONNECTING ELECTRON PORT",
            detail=f"Starting the {runtime_name} finalization bridge",
        )
        electron_command = electron or node
        _, electron_ready = self._launch(
            [electron_command, str(bootstrap / "nuttymod_electron_bridge.js"), "--port", "0"],
            cwd=bootstrap,
            environment=environment,
        )
        electron_port = int(electron_ready["port"])
        electron_health = _json_request(
            f"http://127.0.0.1:{electron_port}/health",
            headers=bridge_headers,
        )
        if electron_health.get("ok") is not True:
            raise RuntimeError("Electron bridge health check failed")
        electron_runtime = str(electron_health.get("runtime", "unknown"))
        self._update(
            electron_port=electron_port,
            electron_runtime=electron_runtime,
            detail=f"Electron port {electron_port} connected ({electron_runtime})",
        )

        self._pace(0.93)
        self._update(stage="FINALIZING CONNECTION", detail="Completing the NuttyMod bootstrap handshake")
        final = _json_request(
            f"http://127.0.0.1:{node_port}/finalize",
            payload={
                "authenticated": True,
                "username": username,
                "go_port": go_port,
                "electron_port": electron_port,
            },
            headers=bridge_headers,
        )
        if final.get("ok") is not True:
            raise RuntimeError("NuttyMod bootstrap finalization failed")

        self._pace(1.0)
        result = {
            "stage": "CONNECTION COMPLETE",
            "detail": f"Signed in as {username}; NuttyMod is ready",
            "username": username,
            "node_port": node_port,
            "go_port": go_port,
            "electron_port": electron_port,
            "electron_runtime": electron_runtime,
            "bootstrap_url": bootstrap_url,
            "session": str(final.get("session", "")),
            "repaired": repaired,
        }
        public_state = dict(result)
        public_state.update(
            {
                "version": CONNECTION_VERSION,
                "connected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "services_closed_after_handshake": True,
            }
        )
        _atomic_json(self.addons_dir / CONNECTION_STATE_FILE, public_state)
        return result

    def _stop_process(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=_creation_flags(),
                    timeout=5,
                    check=False,
                )
            else:
                process.terminate()
                process.wait(timeout=3)
        except (OSError, subprocess.SubprocessError):
            try:
                process.kill()
            except OSError:
                pass

    def _stop_processes(self) -> None:
        for process in reversed(self._processes):
            self._stop_process(process)
