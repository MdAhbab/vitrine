#!/usr/bin/env python3
"""
Vitrine local launcher.

Usage:
    python run.py                         # bootstrap + start API + frontend
    python run.py --seed                  # also seed demo data
    python run.py --fresh-db              # drop & recreate DB first
    python run.py --only gateway          # run selected backend service(s)
    python run.py --no-frontend
    python run.py --setup-only            # install deps + DB setup, don't launch
    python run.py --skip-bootstrap        # launch only
    python run.py cloud ...               # dispatch to cloudrun.py

The default local mode runs a monolith FastAPI gateway for SQLite/in-memory dev.
If the preferred ports are occupied, it picks the next available ports and
prints the real URLs.
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

PY_MIN = (3, 11)
ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV = ROOT / ".venv"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"

IS_WIN = os.name == "nt"
VENV_BIN = VENV / ("Scripts" if IS_WIN else "bin")
VENV_PY = VENV_BIN / ("python.exe" if IS_WIN else "python")

SERVICES: dict[str, tuple[str, int]] = {
    "gateway": ("backend.gateway.app:app", 8000),
    "identity": ("backend.services.identity.app:app", 8001),
    "catalog": ("backend.services.catalog.app:app", 8002),
    "search": ("backend.services.search.app:app", 8003),
    "orders": ("backend.services.orders.app:app", 8004),
    "notifications": ("backend.services.notifications.app:app", 8005),
    "hosting": ("backend.services.hosting.app:app", 8006),
    "reviews": ("backend.services.reviews.app:app", 8007),
    "chats": ("backend.services.chats.app:app", 8008),
    "ai-orchestrator": ("backend.ai.app:app", 8010),
}

AI_WORKERS = 2
COLORS = ["36", "32", "33", "35", "34", "31", "92", "93", "94", "95", "96"]

BANNER = r"""
 __      ___ _        _
 \ \    / (_) |_ _ _ (_)_ _  ___
  \ \/\/ /| |  _| '_|| | ' \/ -_)
   \_/\_/ |_|\__|_|  |_|_||_\___|   try the software, then own it.
"""


def c(text: str, code: str = "0") -> str:
    if IS_WIN or not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def info(msg: str) -> None:
    print(c("* ", "36") + msg)


def warn(msg: str) -> None:
    print(c("! ", "33") + msg)


def ok(msg: str) -> None:
    print(c("+ ", "32") + msg)


def die(msg: str) -> None:
    sys.exit(c("x ", "31") + msg)


def have(binname: str) -> bool:
    return shutil.which(binname) is not None


def check_python() -> None:
    if sys.version_info < PY_MIN:
        die(
            f"Vitrine needs Python >= {PY_MIN[0]}.{PY_MIN[1]} "
            f"(found {sys.version.split()[0]})."
        )


def env_value(key: str, default: str) -> str:
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text().splitlines():
            line = raw.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    return default


def is_sqlite() -> bool:
    return env_value("DATABASE_URL", "sqlite+aiosqlite:///./vitrine.db").startswith("sqlite")


def is_monolith() -> bool:
    return env_value("EVENT_BUS", "memory") == "memory"


def port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) != 0


def choose_port(preferred: int, used: set[int]) -> int:
    port = preferred
    while port in used or not port_is_free(port):
        port += 1
    if port != preferred:
        warn(f"Port {preferred} is busy; using {port} instead.")
    used.add(port)
    return port


def preflight() -> None:
    info("Preflight: checking native prerequisites...")
    zero_dep = is_sqlite() and is_monolith()
    if zero_dep:
        ok("mode: SQLite + in-memory bus (no Postgres/Redis needed)")

    missing = []
    checks = {
        "python": sys.version_info >= PY_MIN,
        "node": have("node"),
        "npm": have("npm"),
    }
    for name, present in checks.items():
        (ok if present else warn)(f"{name}: {'found' if present else 'MISSING'}")
        if not present:
            missing.append(name)

    if not zero_dep:
        if have("redis-cli"):
            r = subprocess.run(["redis-cli", "ping"], capture_output=True, text=True)
            (ok if "PONG" in r.stdout else warn)(
                "redis: reachable" if "PONG" in r.stdout else "redis: not responding"
            )
        if have("pg_isready"):
            r = subprocess.run(["pg_isready"], capture_output=True, text=True)
            (ok if r.returncode == 0 else warn)(
                "postgres: reachable" if r.returncode == 0 else "postgres: not ready"
            )

    if missing:
        die(f"Missing required tools: {', '.join(missing)}")

    if not ENV_FILE.exists():
        if ENV_EXAMPLE.exists():
            shutil.copy(ENV_EXAMPLE, ENV_FILE)
            warn("Created .env from .env.example; fill OPENAI_API_KEY for live AI.")
        else:
            warn("No .env found. Create one before using AI features.")


def ensure_venv() -> None:
    if not VENV_PY.exists():
        info("Creating virtualenv (.venv)...")
        venv_base = shutil.which("python3.11") or sys.executable
        subprocess.check_call([venv_base, "-m", "venv", str(VENV)])

    req = BACKEND / "requirements.txt"
    if not req.exists():
        warn("backend/requirements.txt not found; skipping backend dependency install.")
        return

    info("Installing backend requirements...")
    subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "-q", "--upgrade", "pip"])
    subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "-q", "-r", str(req)])
    ok("Backend deps installed.")


def ensure_frontend() -> None:
    if not FRONTEND.exists():
        warn("frontend/ not found; skipping frontend dependency install.")
        return
    if not (FRONTEND / "package.json").exists():
        warn("frontend/package.json not found; skipping frontend dependency install.")
        return

    info("Installing frontend requirements...")
    npm_cmd = ["npm", "ci"] if (FRONTEND / "package-lock.json").exists() else ["npm", "install"]
    subprocess.check_call(npm_cmd, cwd=str(FRONTEND))
    ok("Frontend deps installed.")


def setup_database(fresh: bool, seed: bool) -> None:
    if not (BACKEND / "shared" / "db_setup.py").exists():
        warn("backend/shared/db_setup.py not found; skipping DB setup.")
        return

    try:
        if is_sqlite():
            info("Setting up SQLite database...")
            arg = "--drop-create" if fresh else "--ensure"
            subprocess.check_call([str(VENV_PY), "-m", "backend.shared.db_setup", arg], cwd=str(ROOT))
            ok("SQLite schema ready.")
        else:
            info("Setting up Postgres database...")
            if fresh:
                subprocess.check_call([str(VENV_PY), "-m", "backend.shared.db_setup", "--drop-create"], cwd=str(ROOT))
            subprocess.check_call([str(VENV_PY), "-m", "alembic", "upgrade", "head"], cwd=str(BACKEND))
            ok("Migrations applied.")

        if seed:
            subprocess.check_call([str(VENV_PY), "-m", "backend.seed"], cwd=str(ROOT))
            ok("Demo data seeded.")
    except subprocess.CalledProcessError as exc:
        warn(f"DB setup failed ({exc}). Check DATABASE_URL in .env.")


class Proc:
    def __init__(
        self,
        name: str,
        cmd: list[str],
        color: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        self.name = name
        self.cmd = cmd
        self.color = color
        self.cwd = cwd
        self.env = env
        self.popen: subprocess.Popen[str] | None = None

    def start(self) -> bool:
        try:
            self.popen = subprocess.Popen(
                self.cmd,
                cwd=str(self.cwd or ROOT),
                env=self.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            warn(f"[{self.name}] cannot start: {self.cmd[0]} not found.")
            return False
        threading.Thread(target=self._pump, daemon=True).start()
        return True

    def _pump(self) -> None:
        assert self.popen and self.popen.stdout
        tag = c(f"{self.name:>15} | ", self.color)
        for line in self.popen.stdout:
            sys.stdout.write(tag + line)
        sys.stdout.flush()

    def stop(self) -> None:
        if self.popen and self.popen.poll() is None:
            self.popen.terminate()

    def kill_if_needed(self) -> None:
        if self.popen and self.popen.poll() is None:
            self.popen.kill()


def build_processes(
    selected: list[str],
    with_frontend: bool,
    api_port: int,
    frontend_port: int,
) -> tuple[list[Proc], str, str]:
    procs: list[Proc] = []
    used_ports: set[int] = set()
    service_ports: dict[str, int] = {}
    ci = 0
    actual_frontend_port = choose_port(frontend_port, used_ports) if with_frontend else frontend_port
    frontend_url = f"http://localhost:{actual_frontend_port}"

    for name, (target, default_port) in SERVICES.items():
        if selected and name not in selected:
            continue
        mod_path = ROOT / Path(target.split(":")[0].replace(".", "/")).with_suffix(".py")
        if not mod_path.exists():
            warn(f"[{name}] {target} not found; skipping.")
            continue

        preferred = api_port if name == "gateway" else default_port
        port = choose_port(preferred, used_ports)
        service_ports[name] = port

        env = os.environ.copy()
        env["FRONTEND_ORIGIN"] = frontend_url
        cmd = [
            str(VENV_PY),
            "-m",
            "uvicorn",
            target,
            "--port",
            str(port),
            "--reload",
            "--host",
            "127.0.0.1",
        ]
        procs.append(Proc(name, cmd, COLORS[ci % len(COLORS)], env=env))
        ci += 1

    gateway_port = service_ports.get("gateway", api_port)
    api_url = f"http://localhost:{gateway_port}"

    if (not selected or "ai-orchestrator" in selected) and (BACKEND / "ai" / "workers.py").exists():
        for i in range(AI_WORKERS):
            procs.append(
                Proc(
                    f"ai-worker-{i}",
                    [str(VENV_PY), "-m", "backend.ai.workers"],
                    COLORS[(ci + i) % len(COLORS)],
                    env=os.environ.copy(),
                )
            )

    if with_frontend and FRONTEND.exists() and (FRONTEND / "package.json").exists():
        env = os.environ.copy()
        env["VITE_API_BASE"] = "/api"
        env["VITE_PROXY_TARGET"] = api_url
        env["VITE_USE_MOCKS"] = "false"
        procs.append(
            Proc(
                "frontend",
                [
                    "npm",
                    "run",
                    "dev",
                    "--",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(actual_frontend_port),
                    "--strictPort",
                ],
                COLORS[-1],
                cwd=FRONTEND,
                env=env,
            )
        )

    return procs, api_url, frontend_url


def supervise(procs: list[Proc], api_url: str, frontend_url: str | None) -> int:
    if not procs:
        warn("Nothing to launch.")
        return 1

    started = [p for p in procs if p.start()]
    time.sleep(1.5)

    failed = [p for p in started if p.popen and p.popen.poll() is not None]
    if failed:
        for p in failed:
            warn(f"[{p.name}] exited during startup (code {p.popen.returncode}).")
        for p in reversed(started):
            p.stop()
        time.sleep(0.5)
        for p in reversed(started):
            p.kill_if_needed()
        return 1

    print()
    ok(f"Launched {len(started)} process(es).")
    if frontend_url:
        print(c(f"  Storefront:  {frontend_url}", "32"))
    print(c(f"  API gateway: {api_url}", "32"))
    print(c("  Press Ctrl-C to stop everything.\n", "33"))

    stopping = threading.Event()

    def shutdown(*_: object) -> None:
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
            for p in list(started):
                if p.popen and p.popen.poll() is not None and not stopping.is_set():
                    warn(f"[{p.name}] exited (code {p.popen.returncode}).")
                    shutdown()
                    break
            if stopping.is_set():
                break
    except KeyboardInterrupt:
        shutdown()
    finally:
        for p in reversed(started):
            p.stop()
        time.sleep(1.0)
        for p in reversed(started):
            p.kill_if_needed()
        ok("Stopped.")

    return 0


def dispatch_cloud(argv: list[str]) -> int:
    script = ROOT / "cloudrun.py"
    if not script.exists():
        die("Missing cloudrun.py next to run.py.")
    if not argv or argv[0].startswith("-"):
        argv = ["deploy", *argv]
    return subprocess.call([sys.executable, str(script), *argv])


def parse_args(argv: list[str]) -> tuple[str, argparse.Namespace]:
    if argv and argv[0] == "cloud":
        ns = argparse.Namespace(args=argv[1:])
        return "cloud", ns
    if argv and argv[0] == "local":
        argv = argv[1:]

    ap = argparse.ArgumentParser(description="Vitrine local dev launcher")
    ap.add_argument("--seed", action="store_true", help="seed demo data")
    ap.add_argument("--fresh-db", action="store_true", help="drop & recreate DB first")
    ap.add_argument("--only", default="", help="comma list of services to run")
    ap.add_argument("--all", action="store_true", help="run all backend services separately")
    ap.add_argument("--no-frontend", action="store_true")
    ap.add_argument("--setup-only", action="store_true", help="bootstrap, don't launch")
    ap.add_argument("--skip-bootstrap", action="store_true", help="launch only")
    ap.add_argument("--api-port", type=int, default=8000)
    ap.add_argument("--frontend-port", type=int, default=5173)
    return "local", ap.parse_args(argv)


def main() -> int:
    check_python()
    print(BANNER)

    mode, args = parse_args(sys.argv[1:])
    if mode == "cloud":
        return dispatch_cloud(args.args)

    selected = [s.strip() for s in args.only.split(",") if s.strip()]
    if not selected and not args.all and is_monolith():
        selected = ["gateway"]
        info("Monolith mode: launching the gateway only (set EVENT_BUS=redis + --all for separate services).")

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
        warn("No virtualenv found; run without --skip-bootstrap first.")
        return 1

    procs, api_url, frontend_url = build_processes(
        selected,
        with_frontend=not args.no_frontend,
        api_port=args.api_port,
        frontend_port=args.frontend_port,
    )
    return supervise(procs, api_url, None if args.no_frontend else frontend_url)


if __name__ == "__main__":
    raise SystemExit(main())
