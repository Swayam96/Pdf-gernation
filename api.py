"""
Standalone HTTP API for the PDF Report dashboard.
No third-party deps — uses only Python stdlib (http.server, json, threading, uuid).

Endpoints:
  POST /api/pdf-report        { month: string }   -> { job_id }
  GET  /api/jobs/:id                               -> poll job status + progress
  GET  /api/reports/:filename                      -> download a finished PDF
  GET  /                                            -> serves dashboard.html

Runs pdf_report_generator.py as a subprocess per job. The PDF is written to
./generated_reports/ (not the user's Downloads folder, and not auto-opened)
so the dashboard can offer it as an explicit download.
"""

import http.server
import json
import os
import sys
import threading
import traceback
import uuid
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# load .env manually (no python-dotenv needed)
_env_path = os.path.join(ROOT, ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

# ── job store ────────────────────────────────────────────────────────────────
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


REPORTS_DIR = os.path.join(ROOT, "generated_reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def _new_job(kind: str, params: dict) -> str:
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {"id": job_id, "kind": kind, "params": params,
                         "status": "pending", "result": None, "error": None,
                         "progress": {"stage": "queued", "label": "Queued — waiting to start…", "pct": 0}}
    return job_id


def _run_job(job_id: str) -> None:
    with _jobs_lock:
        job = _jobs[job_id]
        job["status"] = "running"

    try:
        result = _dispatch(job_id, job["kind"], job["params"])
        with _jobs_lock:
            job["status"] = "done"
            job["result"] = result
            job["progress"] = {"stage": "done", "label": "PDF ready", "pct": 100}
    except Exception as exc:
        with _jobs_lock:
            job["status"] = "error"
            job["error"] = traceback.format_exc()
            print(f"[job {job_id}] ERROR: {exc}", flush=True)


def _set_progress(job_id: str, progress: dict) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is not None:
            job["progress"] = progress


def _dispatch(job_id: str, kind: str, params: dict):
    if kind == "pdf_report":
        import subprocess
        script = os.path.join(ROOT, "pdf_report_generator.py")
        env = dict(os.environ)
        env["PDF_REPORT_MACHINE"] = "1"
        env["PDF_REPORT_NO_OPEN"] = "1"
        env["PDF_REPORT_OUTPUT_DIR"] = REPORTS_DIR

        proc = subprocess.Popen(
            [sys.executable, script, params["month"]],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=ROOT, env=env, bufsize=1
        )

        lines = []
        for line in proc.stdout:
            line = line.rstrip("\n")
            if not line:
                continue
            lines.append(line)
            print(f"[job {job_id}] {line}", flush=True)
            if line.startswith("##PROGRESS## "):
                try:
                    _set_progress(job_id, json.loads(line[len("##PROGRESS## "):]))
                except Exception:
                    pass

        returncode = proc.wait(timeout=600)
        if returncode != 0:
            raise RuntimeError("\n".join(lines)[-2000:] if lines else "Unknown error")

        pdf_line = next((l for l in lines if "PDF saved:" in l), None)
        pdf_path = None
        if pdf_line:
            pdf_path = pdf_line.split("PDF saved:", 1)[1].strip().rsplit("(", 1)[0].strip()
        if not pdf_path or not os.path.exists(pdf_path):
            raise RuntimeError("Generator finished but no PDF file was found")

        filename = os.path.basename(pdf_path)
        return {"message": f"PDF saved: {filename}", "filename": filename,
                "size_kb": os.path.getsize(pdf_path) // 1024}

    raise ValueError(f"Unknown job kind: {kind}")


def _start_job(kind: str, params: dict) -> str:
    job_id = _new_job(kind, params)
    t = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    t.start()
    return job_id


# ── HTTP handler ─────────────────────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}", flush=True)

    def _send(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/")

        if path in ("", "/", "/dashboard"):
            html_path = os.path.join(ROOT, "dashboard.html")
            try:
                with open(html_path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError:
                self._send(404, {"error": "dashboard.html not found"})
            return

        if path.startswith("/api/jobs/"):
            job_id = path[len("/api/jobs/"):]
            with _jobs_lock:
                job = _jobs.get(job_id)
            if job is None:
                self._send(404, {"error": "Job not found"})
            else:
                self._send(200, job)
            return

        if path == "/api/reports":
            reports = []
            for fname in os.listdir(REPORTS_DIR):
                if not fname.lower().endswith(".pdf"):
                    continue
                fpath = os.path.join(REPORTS_DIR, fname)
                st = os.stat(fpath)
                reports.append({"filename": fname, "size_kb": st.st_size // 1024, "mtime": st.st_mtime})
            reports.sort(key=lambda r: r["mtime"], reverse=True)
            self._send(200, {"reports": reports})
            return

        if path.startswith("/api/reports/"):
            filename = path[len("/api/reports/"):]
            if not filename or "/" in filename or "\\" in filename or filename in (".", ".."):
                self._send(400, {"error": "Invalid filename"})
                return
            file_path = os.path.join(REPORTS_DIR, filename)
            if not os.path.abspath(file_path).startswith(os.path.abspath(REPORTS_DIR) + os.sep) \
               or not os.path.isfile(file_path):
                self._send(404, {"error": "Report not found"})
                return
            size = os.path.getsize(file_path)
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            return

        self._send(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        try:
            body = self._read_json()
        except Exception:
            self._send(400, {"error": "Invalid JSON body"})
            return

        if path == "/api/pdf-report":
            if not body.get("month"):
                self._send(400, {"error": "month is required"})
                return
            job_id = _start_job("pdf_report", body)
            self._send(202, {"job_id": job_id, "status": "pending"})
            return

        self._send(404, {"error": "Not found"})


# ── entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import socket
    port = int(os.environ.get("PORT") or os.environ.get("API_PORT", 8001))

    class DualStackServer(http.server.HTTPServer):
        address_family = socket.AF_INET6
        def server_bind(self):
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            super().server_bind()

    try:
        server = DualStackServer(("::", port), Handler)
    except Exception:
        server = http.server.HTTPServer(("0.0.0.0", port), Handler)

    print(f"PDF Report dashboard running on http://localhost:{port}", flush=True)
    server.serve_forever()
