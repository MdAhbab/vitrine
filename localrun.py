#!/usr/bin/env python3
"""
Vitrine — native LOCAL dev orchestrator (no Docker).

Bootstraps and launches the whole stack on your machine:
    venv + deps -> Postgres/pgvector + migrations + seed -> all FastAPI
    services + AI workers + the Vite frontend, with prefixed logs.

Usage:
    python localrun.py                      # bootstrap + start everything
    python localrun.py --seed               # also seed demo data
    python localrun.py --fresh-db           # drop & recreate DB first
    python localrun.py --only gateway,catalog,ai-orchestrator
    python localrun.py --no-frontend
    python localrun.py --setup-only         # bootstrap, don't launch
    python localrun.py --skip-bootstrap     # just launch (deps already set up)

Prereqs (install natively): Python 3.11+, Node 18+, PostgreSQL 15+ (with the
pgvector extension), Redis 7+. Copy .env.example -> .env and fill OPENAI_API_KEY.

This is the orchestration described in backend.md §13. Steps degrade gracefully
with clear guidance when a component (e.g. backend/ code) isn't present yet, so
it doubles as a project bootstrapper.
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV = ROOT / ".venv"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"

IS_WIN = os.name == "nt"
VENV_BIN = VENV / ("Scripts" if IS_WIN else "bin")
VENV_PY = VENV_BIN / ("python.exe" if IS_WIN else "python")

# service module path -> port  (matches backend.md §2)
SERVICES: dict[str, tuple[str, int]] = {
    "gateway":         ("backend.gateway.app:app",                8000),
    "identity":        ("backend.services.identity.app:app",      8001),
    "catalog":         ("backend.services.catalog.app:app",       8002),
    "search":          ("backend.services.search.app:app",        8003),
    "orders":          ("backend.services.orders.app:app",        8004),
    "notifications":   ("backend.services.notifications.app:app", 8005),
    "hosting":         ("backend.services.hosting.app:app",       8006),
    "reviews":         ("backend.services.reviews.app:app",       8007),
    "chats":           ("backend.services.chats.app:app",         8008),
    "ai-orchestrator": ("backend.ai.app:app",                     8010),
}
AI_WORKERS = 2  # backend.ai.workers stream consumers


def _env(key: str, default: str) -> str:
    """Cheap .env reader (no dependency) for orchestration decisions."""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    return default


def _is_sqlite() -> bool:
    return _env("DATABASE_URL", "sqlite+aiosqlite:///./vitrine.db").startswith("sqlite")


def _is_monolith() -> bool:
    # In-memory event bus only works in ONE process -> run the gateway monolith
    # (it includes every router + wires the agent pipeline).
    return _env("EVENT_BUS", "memory") == "memory"

# ----- pretty logging ---------------------------------------------------------
COLORS = ["36", "32", "33", "35", "34", "31", "92", "93", "94", "95", "96"]


def c(text: str, code: str = "0") -> str:
    if IS_WIN or not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def info(msg: str) -> None:
    print(c("• ", "36") + msg)


def warn(msg: str) -> None:
    print(c("! ", "33") + msg)


def die(msg: str) -> None:
    sys.exit(c("✗ ", "31") + msg)


def ok(msg: str) -> None:
    print(c("✓ ", "32") + msg)


# ----- preflight --------------------------------------------------------------
def have(binname: str) -> bool:
    return shutil.which(binname) is not None


def preflight() -> None:
    info("Preflight: checking native prerequisites...")
    zero_dep = _is_sqlite() and _is_monolith()
    if zero_dep:
        ok("mode: SQLite + in-memory bus (no Postgres/Redis needed)")
    missing = []
    checks = {"python3": sys.version_info >= (3, 11), "node": have("node"), "npm": have("npm")}
    for name, present in checks.items():
        (ok if present else warn)(f"{name}: {'found' if present else 'MISSING'}")
        if not present:
            missing.append(name)

    # Postgres/Redis only matter when NOT in zero-dep mode.
    if not zero_dep:
        if have("redis-cli"):
            r = subprocess.run(["redis-cli", "ping"], capture_output=True, text=True)
            (ok if "PONG" in r.stdout else warn)(
                "redis: reachable" if "PONG" in r.stdout else "redis: not responding")
        if have("pg_isready"):
            r = subprocess.run(["pg_isready"], capture_output=True, text=True)
            (ok if r.returncode == 0 else warn)(
                "postgres: reachable" if r.returncode == 0 else "postgres: not ready")

    if missing:
        warn(f"Missing tools: {', '.join(missing)} — install them, then re-run.")
    if not ENV_FILE.exists():
        if ENV_EXAMPLE.exists():
            shutil.copy(ENV_EXAMPLE, ENV_FILE)
            warn(f"Created .env from .env.example — set OPENAI_API_KEY before using AI.")
        else:
            warn("No .env found. Create one (see backend.md §15) before running AI.")


# ----- bootstrap --------------------------------------------------------------
def ensure_venv() -> None:
    if not VENV_PY.exists():
        info("Creating virtualenv (.venv)...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    req = BACKEND / "requirements.txt"
    if req.exists():
        info("Installing backend requirements...")
        subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "-q",
                               "--upgrade", "pip"])
        subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "-q",
                               "-r", str(req)])
        ok("Backend deps installed.")
    else:
        warn(f"{req} not found — backend code not present yet. "
             "Scaffold backend/ per backend.md, then re-run.")


def setup_database(fresh: bool, seed: bool) -> None:
    if not (BACKEND / "shared" / "db_setup.py").exists():
        warn("backend/shared/db_setup.py not found — skipping DB setup.")
        return
    try:
        if _is_sqlite():
            # SQLite: create_all is the schema (no Alembic, no createdb/pgvector).
            info("Setting up SQLite database (create_all)...")
            arg = "--drop-create" if fresh else "--ensure"
            subprocess.check_call([str(VENV_PY), "-m", "backend.shared.db_setup", arg],
                                  cwd=str(ROOT))
            ok("SQLite schema ready.")
        else:
            # Postgres: run Alembic migrations (and assume DB/pgvector exist).
            info("Setting up Postgres database (alembic upgrade)...")
            if fresh:
                subprocess.check_call([str(VENV_PY), "-m", "backend.shared.db_setup",
                                       "--drop-create"], cwd=str(ROOT))
            subprocess.check_call([str(VENV_PY), "-m", "alembic", "upgrade", "head"],
                                  cwd=str(BACKEND))
            ok("Migrations applied.")
        if seed:
            subprocess.check_call([str(VENV_PY), "-m", "backend.seed"], cwd=str(ROOT))
            ok("Demo data seeded.")
    except subprocess.CalledProcessError as e:
        warn(f"DB setup step failed ({e}). Check DATABASE_URL in .env.")


def ensure_frontend() -> None:
    if not FRONTEND.exists():
        warn("frontend/ not present yet — build it from frontend.md, then re-run.")
        return
    if not (FRONTEND / "node_modules").exists():
        info("Installing frontend deps (npm install)...")
        subprocess.check_call(["npm", "install"], cwd=str(FRONTEND))
        ok("Frontend deps installed.")


# ----- process supervisor -----------------------------------------------------
class Proc:
    def __init__(self, name: str, cmd: list[str], color: str, cwd: Path | None = None):
        self.name = name
        self.cmd = cmd
        self.color = color
        self.cwd = cwd
        self.popen: subprocess.Popen | None = None

    def start(self) -> bool:
        try:
            self.popen = subprocess.Popen(
                self.cmd, cwd=str(self.cwd or ROOT),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
        except FileNotFoundError:
            warn(f"[{self.name}] cannot start: {self.cmd[0]} not found.")
            return False
        threading.Thread(target=self._pump, daemon=True).start()
        return True

    def _pump(self) -> None:
        assert self.popen and self.popen.stdout
        tag = c(f"{self.name:>15} │ ", self.color)
        for line in self.popen.stdout:
            sys.stdout.write(tag + line)
        sys.stdout.flush()

    def stop(self) -> None:
        if self.popen and self.popen.poll() is None:
            self.popen.terminate()


def build_processes(selected: list[str], with_frontend: bool) -> list[Proc]:
    procs: list[Proc] = []
    ci = 0
    for name, (target, port) in SERVICES.items():
        if selected and name not in selected:
            continue
        mod_path = ROOT / Path(target.split(":")[0].replace(".", "/")).with_suffix(".py")
        if not mod_path.exists():
            warn(f"[{name}] {target} not found — skipping (scaffold per backend.md).")
            continue
        cmd = [str(VENV_PY), "-m", "uvicorn", target,
               "--port", str(port), "--reload", "--host", "127.0.0.1"]
        procs.append(Proc(name, cmd, COLORS[ci % len(COLORS)]))
        ci += 1

    # AI stream workers
    if (not selected or "ai-orchestrator" in selected) and (BACKEND / "ai" / "workers.py").exists():
        for i in range(AI_WORKERS):
            procs.append(Proc(f"ai-worker-{i}",
                              [str(VENV_PY), "-m", "backend.ai.workers"],
                              COLORS[(ci + i) % len(COLORS)]))

    # frontend
    if with_frontend and FRONTEND.exists() and (FRONTEND / "package.json").exists():
        procs.append(Proc("frontend", ["npm", "run", "dev"],
                          COLORS[-1], cwd=FRONTEND))
    return procs


def supervise(procs: list[Proc]) -> None:
    if not procs:
        warn("Nothing to launch yet. Build backend/ and frontend/ from the .md "
             "plans, then run `python localrun.py` again.")
        return

    started = [p for p in procs if p.start()]
    time.sleep(1.0)
    print()
    ok(f"Launched {len(started)} process(es).")
    print(c("  Storefront:  http://localhost:5173", "32"))
    print(c("  API gateway: http://localhost:8000", "32"))
    print(c("  Press Ctrl-C to stop everything.\n", "33"))

    stopping = threading.Event()

    def shutdown(*_):
        if stopping.is_set():
            return
        stopping.set()
        print()
        info("Shutting down...")
        for p in reversed(started):
            p.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while not stopping.is_set():
            time.sleep(0.5)
            for p in started:
                if p.popen and p.popen.poll() is not None and not stopping.is_set():
                    warn(f"[{p.name}] exited (code {p.popen.returncode}).")
                    started.remove(p)
                    break
            if not started:
                break
    finally:
        shutdown()
        time.sleep(1.0)
        ok("Stopped.")


# ----- main -------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Vitrine local dev orchestrator")
    ap.add_argument("--seed", action="store_true", help="seed demo data")
    ap.add_argument("--fresh-db", action="store_true", help="drop & recreate DB first")
    ap.add_argument("--only", default="", help="comma list of services to run")
    ap.add_argument("--all", action="store_true",
                    help="force every service as separate processes (needs EVENT_BUS=redis)")
    ap.add_argument("--no-frontend", action="store_true")
    ap.add_argument("--setup-only", action="store_true", help="bootstrap, don't launch")
    ap.add_argument("--skip-bootstrap", action="store_true", help="launch only")
    args = ap.parse_args()

    selected = [s.strip() for s in args.only.split(",") if s.strip()]
    # Monolith default: in-memory bus only works in one process, so run just the
    # gateway (it includes every router + wires the agent pipeline).
    if not selected and not args.all and _is_monolith():
        selected = ["gateway"]
        info("Monolith mode: launching the gateway only (set EVENT_BUS=redis + --all "
             "to run microservices separately).")

    preflight()
    if not args.skip_bootstrap:
        ensure_venv()
        setup_database(fresh=args.fresh_db, seed=args.seed)
        if not args.no_frontend:
            ensure_frontend()

    if args.setup_only:
        ok("Setup complete (--setup-only).")
        return 0

    if not VENV_PY.exists():
        warn("No venv/backend yet — ran preflight + bootstrap guidance only.")
        return 0

    supervise(build_processes(selected, with_frontend=not args.no_frontend))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
