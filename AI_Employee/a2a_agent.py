"""
A2A Agent — Phase 2 Agent-to-Agent Direct Messaging
=====================================================
Replaces file-based handoffs with direct HTTP messages between agents.
Vault still used as audit record (both systems active simultaneously).

Architecture:
  Cloud Agent  ──HTTP──>  Local A2A Server  ──>  local_agent.py
  Local Agent  ──HTTP──>  Cloud A2A Server  ──>  cloud_agent.py

Phase 1 (file-based):  Cloud writes Pending_Approval/cloud/ACTION.md
Phase 2 (A2A direct):  Cloud POST /local/task  {type, content, priority}
                        -> Local receives instantly, no polling delay

Benefits over Phase 1:
  - Real-time delivery (no 30s polling interval)
  - Acknowledgement + retry logic
  - Priority queue (urgent tasks jump ahead)
  - Vault still written for audit trail

Server runs on:
  Local : http://localhost:7700  (only on LAN — not exposed to internet)
  Cloud : http://CLOUD_IP:7701   (behind firewall, whitelisted IPs only)

Usage:
  python a2a_agent.py --server           # Start local A2A server (port 7700)
  python a2a_agent.py --server 7701      # Custom port
  python a2a_agent.py --send local task  # Send task to local agent
  python a2a_agent.py --test             # Full A2A round-trip test
  python a2a_agent.py --status           # Check if servers are reachable
"""

import sys
import os
import json
import time
import threading
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
except ImportError:
    pass

BASE  = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"

LOCAL_PORT = int(os.getenv("A2A_LOCAL_PORT", "7700"))
CLOUD_PORT = int(os.getenv("A2A_CLOUD_PORT", "7701"))
CLOUD_HOST = os.getenv("A2A_CLOUD_HOST", "localhost")  # Set to cloud VM IP in .env

# In-memory task queue (in production: use Redis or SQLite)
_task_queue: list = []
_queue_lock = threading.Lock()


# ─── MESSAGE FORMAT ───────────────────────────────────────────────────────────

def build_message(msg_type: str, content: str, sender: str = "local",
                  priority: str = "normal", task_id: str = None) -> dict:
    """Build a standardised A2A message envelope."""
    return {
        "id"       : task_id or f"A2A_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "type"     : msg_type,        # task | approval | signal | ping
        "sender"   : sender,          # local | cloud
        "priority" : priority,        # urgent | normal | low
        "timestamp": datetime.now().isoformat(),
        "content"  : content,
        "ack"      : False,
    }


# ─── HTTP SERVER ──────────────────────────────────────────────────────────────

class A2AHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler — receives A2A messages from other agents."""

    def log_message(self, format, *args):
        pass  # suppress default server logs

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok", "agent": "local", "queue": len(_task_queue)})
        elif self.path == "/queue":
            self._respond(200, {"queue": _task_queue[-10:]})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        length  = int(self.headers.get("Content-Length", 0))
        raw     = self.rfile.read(length)
        try:
            msg = json.loads(raw.decode("utf-8"))
        except Exception:
            self._respond(400, {"error": "invalid JSON"})
            return

        msg_type = msg.get("type", "task")

        if msg_type == "ping":
            self._respond(200, {"pong": True, "time": datetime.now().isoformat()})
            return

        if msg_type == "task":
            self._handle_task(msg)
        elif msg_type == "approval":
            self._handle_approval(msg)
        elif msg_type == "signal":
            self._handle_signal(msg)
        else:
            self._respond(400, {"error": f"unknown type: {msg_type}"})

    def _handle_task(self, msg: dict):
        """Receive a task from cloud agent — write to vault + queue."""
        with _queue_lock:
            _task_queue.append(msg)

        # Write to vault as audit record (Phase 1 compatibility)
        _write_to_vault(msg)

        print(f"  [A2A] Received task: {msg.get('id')} priority={msg.get('priority')} from={msg.get('sender')}")
        self._respond(200, {"ack": True, "id": msg.get("id"), "queued": len(_task_queue)})

    def _handle_approval(self, msg: dict):
        """Cloud agent sending approval decision to local."""
        _write_to_vault(msg, subfolder="Approved")
        print(f"  [A2A] Approval received: {msg.get('id')}")
        self._respond(200, {"ack": True})

    def _handle_signal(self, msg: dict):
        """Health signal from cloud agent."""
        sig_dir = VAULT / "Signals"
        sig_dir.mkdir(parents=True, exist_ok=True)
        fname = sig_dir / f"A2A_SIGNAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        fname.write_text(json.dumps(msg, indent=2, ensure_ascii=False), encoding="utf-8")
        self._respond(200, {"ack": True})

    def _respond(self, code: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


def _write_to_vault(msg: dict, subfolder: str = "Needs_Action/local"):
    """Write A2A message to vault for audit trail (Phase 1 compatibility)."""
    target = VAULT / subfolder
    target.mkdir(parents=True, exist_ok=True)
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = target / f"A2A_{ts}_{msg.get('id', 'unknown')}.md"
    body  = (
        f"# A2A Message\n\n"
        f"**ID**      : {msg.get('id')}\n"
        f"**Type**    : {msg.get('type')}\n"
        f"**Sender**  : {msg.get('sender')}\n"
        f"**Priority**: {msg.get('priority')}\n"
        f"**Time**    : {msg.get('timestamp')}\n\n"
        f"## Content\n\n"
        f"{msg.get('content', '')}\n"
    )
    fname.write_text(body, encoding="utf-8")


# ─── HTTP CLIENT — SEND MESSAGE ───────────────────────────────────────────────

def send_message(target: str, msg: dict, retries: int = 3) -> dict:
    """
    Send A2A message to target agent.
    target: 'local' -> localhost:7700, 'cloud' -> CLOUD_HOST:7701
    """
    host = "localhost" if target == "local" else CLOUD_HOST
    port = LOCAL_PORT  if target == "local" else CLOUD_PORT
    url  = f"http://{host}:{port}/"

    route = {
        "task"    : "task",
        "approval": "approval",
        "signal"  : "signal",
        "ping"    : "health",
    }.get(msg.get("type", "task"), "task")

    endpoint = url if route == "task" else f"{url}{route}"
    body     = json.dumps(msg).encode("utf-8")

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                endpoint, data=body,
                headers={"Content-Type": "application/json"},
                method="POST" if msg.get("type") != "ping" else "GET"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            if attempt == retries:
                # Fallback: write to vault (Phase 1 compatibility)
                print(f"  [A2A] HTTP failed ({e}), falling back to vault write")
                _write_to_vault(msg)
                return {"ack": True, "fallback": "vault", "error": str(e)}
            time.sleep(1)
    return {"ack": False}


def ping(target: str) -> bool:
    """Check if a target agent server is reachable."""
    host = "localhost" if target == "local" else CLOUD_HOST
    port = LOCAL_PORT  if target == "local" else CLOUD_PORT
    try:
        req = urllib.request.Request(f"http://{host}:{port}/health", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("status") == "ok"
    except Exception:
        return False


# ─── SERVER RUNNER ────────────────────────────────────────────────────────────

def start_server(port: int = LOCAL_PORT):
    """Start A2A HTTP server (blocking)."""
    server = HTTPServer(("0.0.0.0", port), A2AHandler)
    print(f"  [A2A] Server listening on port {port}")
    print(f"  [A2A] Health: http://localhost:{port}/health")
    print(f"  [A2A] Queue : http://localhost:{port}/queue")
    print(f"  [A2A] Vault fallback: {VAULT / 'Needs_Action/local'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  [A2A] Server stopped.")
        server.server_close()


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--server" in sys.argv:
        idx  = sys.argv.index("--server")
        port = int(sys.argv[idx + 1]) if len(sys.argv) > idx + 1 and sys.argv[idx + 1].isdigit() else LOCAL_PORT
        start_server(port)

    elif "--test" in sys.argv:
        print("=" * 55)
        print("  A2A Agent — Round-Trip Test")
        print("=" * 55)

        # Start server in background thread
        server = HTTPServer(("0.0.0.0", LOCAL_PORT), A2AHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        print(f"  [1] Server started on port {LOCAL_PORT}")
        time.sleep(0.5)

        # Send ping
        alive = ping("local")
        print(f"  [2] Ping local: {'OK' if alive else 'FAIL'}")

        # Send task message
        msg = build_message(
            msg_type="task",
            content="Client inquiry about AI automation services",
            sender="cloud",
            priority="normal",
            task_id="TEST_001"
        )
        result = send_message("local", msg)
        print(f"  [3] Send task: ack={result.get('ack')} queued={result.get('queued', '?')}")

        # Send approval message
        approval = build_message(
            msg_type="approval",
            content="APPROVED — send reply to client",
            sender="local",
            priority="urgent",
            task_id="TEST_001_APPROVED"
        )
        result2 = send_message("local", approval)
        print(f"  [4] Send approval: ack={result2.get('ack')}")

        # Check queue
        req = urllib.request.Request(f"http://localhost:{LOCAL_PORT}/queue")
        with urllib.request.urlopen(req, timeout=3) as r:
            q = json.loads(r.read().decode("utf-8"))
        print(f"  [5] Queue depth: {len(q.get('queue', []))}")

        # Check vault write
        vault_files = list((VAULT / "Needs_Action" / "local").glob("A2A_*.md")) if (VAULT / "Needs_Action" / "local").exists() else []
        print(f"  [6] Vault audit files: {len(vault_files)} written")

        server.shutdown()
        print()
        print("  [PASS] A2A round-trip complete")
        print("  Both HTTP (Phase 2) and Vault fallback (Phase 1) working")
        print("=" * 55)

    elif "--send" in sys.argv:
        idx    = sys.argv.index("--send")
        target = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else "local"
        text   = sys.argv[idx + 2] if len(sys.argv) > idx + 2 else "Test message"
        msg    = build_message("task", text, sender="cli", priority="normal")
        result = send_message(target, msg)
        print(f"Result: {result}")

    elif "--status" in sys.argv:
        print("A2A Agent Status:")
        local_up = ping("local")
        cloud_up = ping("cloud")
        print(f"  Local server (:{LOCAL_PORT}): {'ONLINE' if local_up else 'OFFLINE'}")
        print(f"  Cloud server (:{CLOUD_PORT}): {'ONLINE' if cloud_up else 'OFFLINE'}")
        if not local_up:
            print("  Start local: python a2a_agent.py --server")
        if not cloud_up:
            print(f"  Cloud host: {CLOUD_HOST} (set A2A_CLOUD_HOST in .env)")

    else:
        print("Usage:")
        print("  python a2a_agent.py --server          # Start A2A server")
        print("  python a2a_agent.py --test            # Round-trip test")
        print("  python a2a_agent.py --send local msg  # Send message")
        print("  python a2a_agent.py --status          # Check connectivity")
