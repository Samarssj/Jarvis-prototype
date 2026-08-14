"""Persistent startup splash for Jarvis."""

from __future__ import annotations

import argparse
import base64
import json
import os
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT_FILE = Path(os.getenv("JARVIS_SPLASH_PORT_FILE", "/tmp/jarvis_splash_port.txt"))
STATE_FILE = Path(os.getenv("JARVIS_SPLASH_STATE_FILE", "/tmp/jarvis_splash_state.json"))


def _logo_b64() -> str:
    logo = Path("/Users/mac/Downloads/jarvis.png")
    return base64.b64encode(logo.read_bytes()).decode("ascii") if logo.exists() else ""


HTML = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>JARVIS HUD</title>
  <style>
    html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:radial-gradient(circle at center,#071626 0%,#020913 70%);}}
    body{{display:grid;place-items:center;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#e8fbff;}}
    .frame{{position:relative;width:min(90vmin,820px);aspect-ratio:1;border-radius:50%;background:radial-gradient(circle at center,rgba(6,22,37,.45) 0%,rgba(2,9,19,.92) 56%,rgba(2,9,19,1) 100%);box-shadow:0 0 0 2px rgba(79,232,255,.12),0 0 140px rgba(26,168,255,.18);transition:all 0.5s ease;}}
    .ring{{position:absolute;border-radius:50%;border:2px solid rgba(79,232,255,.24);inset:14%;animation:spin 12s linear infinite;transition:border-color 0.5s ease;}}
    .ring.two{{inset:22%;animation-duration:18s;}}
    .ring.three{{inset:31%;animation-duration:28s;border-color:rgba(26,168,255,.35);}}
    .scan{{position:absolute;inset:0;border-radius:50%;background:conic-gradient(from 90deg,transparent 0 72%,rgba(79,232,255,.38) 78%,transparent 82% 100%);mix-blend-mode:screen;animation:spin 2.8s linear infinite;filter:blur(2px);opacity:.8;}}
    .ticks{{position:absolute;inset:6%;border-radius:50%;background:repeating-conic-gradient(from 0deg,rgba(79,232,255,.85) 0 1deg,transparent 1deg 8deg);-webkit-mask:radial-gradient(circle,transparent 0 66%,#000 67% 100%);mask:radial-gradient(circle,transparent 0 66%,#000 67% 100%);opacity:.5;animation:spin 24s linear infinite reverse;}}
    .center{{position:absolute;inset:28%;border-radius:50%;display:grid;place-items:center;background:radial-gradient(circle at center,rgba(255,255,255,.06) 0%,rgba(79,232,255,.1) 20%,rgba(2,9,19,.85) 60%,rgba(2,9,19,1) 100%);box-shadow:inset 0 0 60px rgba(79,232,255,.18),0 0 70px rgba(26,168,255,.15);overflow:hidden;}}
    .center::before{{content:"";position:absolute;inset:7%;border-radius:50%;border:1px solid rgba(79,232,255,.35);animation:pulse 2.8s ease-in-out infinite;}}
    .logo{{width:84%;max-width:420px;filter:drop-shadow(0 0 18px rgba(79,232,255,.55)) drop-shadow(0 0 36px rgba(26,168,255,.35));animation:float 3.2s ease-in-out infinite;z-index:2;}}
    .title,.status,.sub{{position:absolute;left:50%;transform:translateX(-50%);text-transform:uppercase;letter-spacing:.18em;text-align:center;}}
    .title{{bottom:10%;font-size:clamp(18px,2vmin,28px);font-weight:700;text-shadow:0 0 14px rgba(79,232,255,.8);}}
    .status{{bottom:5%;font-size:16px;font-weight:bold;color:#72f4ff;transition:color 0.4s ease;}}
    .sub{{bottom:2.5%;font-size:13px;color:#7ecfe0;letter-spacing:.15em;width:80%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
    .mic{{position:absolute;top:10%;left:50%;transform:translateX(-50%);width:16px;height:16px;border-radius:50%;background:#4fe8ff;box-shadow:0 0 18px #4fe8ff;animation:pulse 1.2s ease-in-out infinite;transition:all 0.3s ease;}}
    
    /* State Modifiers */
    body.listening .status {{ color: #00ffcc; text-shadow: 0 0 12px #00ffcc; }}
    body.listening .mic {{ background: #00ffcc; box-shadow: 0 0 20px #00ffcc; opacity: 1; }}
    body.thinking .status {{ color: #b86bff; text-shadow: 0 0 12px #b86bff; }}
    body.thinking .scan {{ animation-duration: 1.2s; background: conic-gradient(from 90deg,transparent 0 72%,rgba(184,107,255,.6) 78%,transparent 82% 100%); }}
    body.speaking .status {{ color: #ffd700; text-shadow: 0 0 12px #ffd700; }}
    body.speaking .mic {{ opacity: 0.3; }}

    @keyframes spin{{to{{transform:rotate(360deg);}}}}
    @keyframes float{{0%,100%{{transform:translateY(0) scale(1);}}50%{{transform:translateY(-8px) scale(1.01);}}}}
    @keyframes pulse{{0%,100%{{opacity:.45;transform:scale(.94);}}50%{{opacity:1;transform:scale(1.08);}}}}
  </style>
</head>
<body>
  <div class="frame" id="frame">
    <div class="ring"></div><div class="ring two"></div><div class="ring three"></div>
    <div class="ticks"></div><div class="scan"></div><div class="mic" id="mic"></div>
    <div class="center"><img class="logo" src="data:image/png;base64,{_logo_b64()}" alt="JARVIS" /></div>
    <div class="title">J.A.R.V.I.S.</div>
    <div class="status" id="status">BOOTING</div>
    <div class="sub" id="sub">Voice interface online</div>
  </div>
  <script>
    async function refresh(){{
      try {{
        const r = await fetch('/state?ts=' + Date.now());
        const s = await r.json();
        const statusStr = s.status || 'BOOTING';
        document.getElementById('status').textContent = statusStr;
        document.getElementById('sub').textContent = s.detail || 'Voice interface online';
        document.getElementById('mic').style.opacity = s.mic === 'on' ? '1' : '.35';
        
        document.body.className = statusStr.toLowerCase();
      }} catch (e) {{}}
    }}
    refresh();
    setInterval(refresh, 200);
  </script>
</body>
</html>
"""

STATE = {"status": "BOOTING", "detail": "Starting up", "mic": "off"}
STATE_LOCK = threading.Lock()
SERVER = None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/shutdown"):
            self.send_response(200)
            self.end_headers()
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if self.path.startswith("/state"):
            with STATE_LOCK:
                if STATE_FILE.exists():
                    try:
                        data = json.loads(STATE_FILE.read_text())
                        STATE.update(data)
                    except Exception:
                        pass
                payload = json.dumps(STATE).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def set_state(status: str | None = None, detail: str | None = None, mic: str | None = None) -> None:
    with STATE_LOCK:
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                STATE.update(data)
            except Exception:
                pass
        if status is not None:
            STATE["status"] = status
        if detail is not None:
            STATE["detail"] = detail
        if mic is not None:
            STATE["mic"] = mic
        STATE_FILE.write_text(json.dumps(STATE))


def _open_browser(url: str) -> None:
    import webbrowser
    webbrowser.open(url)


def run_server() -> int:
    global SERVER
    SERVER = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = SERVER.server_address[1]
    PORT_FILE.write_text(str(port))
    _open_browser(f"http://127.0.0.1:{port}/")
    SERVER.serve_forever()
    SERVER.server_close()
    return port


def shutdown_server(port: int) -> None:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/shutdown", timeout=2).read()
    except Exception:
        pass


def get_running_port() -> int | None:
    try:
        return int(PORT_FILE.read_text().strip())
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shutdown", type=int)
    parser.add_argument("--set-status")
    parser.add_argument("--set-detail")
    parser.add_argument("--mic")
    args = parser.parse_args()
    if args.shutdown:
        shutdown_server(args.shutdown)
        return
    if args.set_status or args.set_detail or args.mic:
        set_state(args.set_status, args.set_detail, args.mic)
        return
    run_server()


if __name__ == "__main__":
    main()
