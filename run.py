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
import textwrap
import platform
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



import argparse
import os
import platform
import subprocess
import sys
import textwrap
from pathlib import Path

DEFAULT_DOMAIN = "vitrine.ahbab.dev"
DEFAULT_GATEWAY_PORT = 8000
COMPOSE_FILE = "docker-compose.cloud.yml"

DRY = False
APP_DIR = Path("/opt/vitrine")


def cloud_c(text: str, code: str) -> str:
    return text if not sys.stdout.isatty() else f"\033[{code}m{text}\033[0m"


def cloud_info(msg: str) -> None:
    print(cloud_c("* ", "36") + msg)


def cloud_ok(msg: str) -> None:
    print(cloud_c("+ ", "32") + msg)


def cloud_warn(msg: str) -> None:
    print(cloud_c("! ", "33") + msg)


def cloud_die(msg: str) -> None:
    sys.exit(cloud_c("x ", "31") + msg)


def run(
    cmd: list[str] | str,
    *,
    shell: bool = False,
    check: bool = True,
    timeout: int | None = None,
    cwd: Path | None = None,
) -> int:
    pretty = cmd if isinstance(cmd, str) else " ".join(cmd)
    if DRY:
        where = f" (cwd={cwd})" if cwd else ""
        print(cloud_c("  [dry-run] ", "90") + pretty + where)
        return 0
    cloud_info(pretty)
    try:
        return subprocess.run(
            cmd,
            shell=shell,
            check=check,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
        ).returncode
    except subprocess.TimeoutExpired:
        cloud_die(f"Command timed out after {timeout}s: {pretty}")
        return 1


def sudo(cmd: list[str], *, check: bool = True, timeout: int | None = None, cwd: Path | None = None) -> int:
    return run(["sudo", *cmd], check=check, timeout=timeout, cwd=cwd)


def write_file(path: Path, content: str, *, root: bool = False, mode: str | None = None) -> None:
    if DRY:
        print(cloud_c(f"  [dry-run] write {path} ({len(content)} bytes)", "90"))
        return
    if root:
        p = subprocess.Popen(["sudo", "tee", str(path)], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)
        p.communicate(content.encode())
        if p.returncode:
            cloud_die(f"Failed to write {path}")
    else:
        path.write_text(content)
    if mode:
        (sudo if root else run)(["chmod", mode, str(path)])
    cloud_ok(f"wrote {path}")


def require_linux() -> None:
    if platform.system() != "Linux" and not DRY:
        cloud_die("cloudrun.py provisions a Linux VM. Use --dry-run to preview elsewhere.")


def command_ok(cmd: list[str]) -> bool:
    if DRY:
        return True
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def compose_base() -> list[str]:
    if command_ok(["sudo", "docker", "compose", "version"]):
        return ["sudo", "docker", "compose", "-f", COMPOSE_FILE]
    if command_ok(["sudo", "docker-compose", "version"]):
        return ["sudo", "docker-compose", "-f", COMPOSE_FILE]
    cloud_die("Docker Compose is not available after install.")
    return []


def compose(args: list[str], *, check: bool = True, timeout: int | None = None) -> int:
    return run([*compose_base(), *args], check=check, timeout=timeout, cwd=APP_DIR)


def install_docker() -> None:
    cloud_info("Installing Docker engine + Compose plugin if needed...")
    sudo(["apt-get", "update", "-y"])
    sudo([
        "apt-get",
        "install",
        "-y",
        "ca-certificates",
        "curl",
        "git",
        "rsync",
        "docker.io",
        "docker-compose-plugin",
    ], check=False, timeout=600)
    if not command_ok(["sudo", "docker", "version"]):
        cloud_warn("apt did not provide a working Docker install; falling back to Docker's install script.")
        run("curl -fsSL https://get.docker.com | sudo sh", shell=True, timeout=600)
    sudo(["systemctl", "enable", "--now", "docker"])
    cloud_ok("Docker is ready.")


def sync_checkout() -> None:
    cloud_info(f"Syncing this checkout to {APP_DIR}...")
    sudo(["mkdir", "-p", str(APP_DIR)])
    sudo([
        "rsync",
        "-a",
        "--delete",
        "--exclude",
        ".git",
        "--exclude",
        ".venv",
        "--exclude",
        "__pycache__",
        "--exclude",
        "node_modules",
        "--exclude",
        "frontend/node_modules",
        "--exclude",
        "files",
        f"{Path.cwd()}/",
        f"{APP_DIR}/",
    ])
    cloud_ok("Checkout synced.")


def _read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env_values(path: Path, values: dict[str, str]) -> None:
    lines = path.read_text().splitlines() if path.exists() else []
    out: list[str] = []
    seen: set[str] = set()
    for raw in lines:
        key = raw.split("=", 1)[0].strip() if "=" in raw and not raw.strip().startswith("#") else ""
        if key in values:
            out.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            out.append(raw)
    for key, value in values.items():
        if key not in seen:
            out.append(f"{key}={value}")
    write_file(path, "\n".join(out).rstrip() + "\n", root=True, mode="600")


def ensure_cloud_env(domain: str) -> None:
    env_path = APP_DIR / ".env.cloud"
    if not DRY and not env_path.exists():
        source = APP_DIR / ".env"
        if not source.exists():
            source = APP_DIR / ".env.example"
        if source.exists():
            sudo(["cp", str(source), str(env_path)])
        else:
            write_file(env_path, "", root=True, mode="600")

    required = {
        "ENV": "prod",
        "FRONTEND_ORIGIN": f"https://{domain}",
        "PUBLIC_DOMAIN": domain,
        "DATABASE_URL": "sqlite+aiosqlite:////data/vitrine.db",
        "EVENT_BUS": "memory",
        "CACHE": "memory",
        "REDIS_URL": "redis://redis:6379/0",
        "FILES_ROOT": "files",
    }
    write_env_values(env_path, required)
    cloud_ok(f"Cloud env ready for https://{domain}.")


def caddyfile(domain: str) -> str:
    return textwrap.dedent(f"""\
        {{
            email admin@{domain}
        }}

        {domain} {{
            encode zstd gzip

            header {{
                X-Frame-Options "SAMEORIGIN"
                X-Content-Type-Options "nosniff"
                Referrer-Policy "strict-origin-when-cross-origin"
            }}

            handle_path /api/* {{
                reverse_proxy app:{DEFAULT_GATEWAY_PORT} {{
                    flush_interval -1
                    header_up X-Real-IP {{remote_host}}
                    header_up X-Forwarded-For {{remote_host}}
                    header_up X-Forwarded-Proto {{scheme}}
                }}
            }}

            handle {{
                reverse_proxy app:{DEFAULT_GATEWAY_PORT}
            }}
        }}
    """)


def compose_yaml() -> str:
    return textwrap.dedent(f"""\
        services:
          app:
            build:
              context: .
              dockerfile: Dockerfile
              args:
                VITE_API_BASE: /api
            image: vitrine-app:latest
            restart: unless-stopped
            env_file:
              - .env.cloud
            volumes:
              - vitrine-data:/data
              - vitrine-files:/app/files
            expose:
              - "{DEFAULT_GATEWAY_PORT}"
            healthcheck:
              test: ["CMD", "curl", "-fsS", "http://127.0.0.1:{DEFAULT_GATEWAY_PORT}/health"]
              interval: 30s
              timeout: 5s
              retries: 5
              start_period: 20s

          web:
            image: caddy:2-alpine
            restart: unless-stopped
            depends_on:
              app:
                condition: service_started
            ports:
              - "80:80"
              - "443:443"
              - "443:443/udp"
            volumes:
              - ./Caddyfile:/etc/caddy/Caddyfile:ro
              - caddy-data:/data
              - caddy-config:/config

        volumes:
          vitrine-data:
          vitrine-files:
          caddy-data:
          caddy-config:
    """)


def write_runtime_files(domain: str) -> None:
    write_file(APP_DIR / "Caddyfile", caddyfile(domain), root=True, mode="644")
    write_file(APP_DIR / COMPOSE_FILE, compose_yaml(), root=True, mode="644")


def docker_build(no_cache: bool = False) -> None:
    cloud_info("Building app image with Docker...")
    args = ["build", "--pull", "app"]
    if no_cache:
        args.append("--no-cache")
    compose(args, timeout=1800)
    cloud_ok("Docker image built.")


def docker_up() -> None:
    cloud_info("Starting containers...")
    compose(["up", "-d", "--remove-orphans"], timeout=600)
    cloud_ok("Containers are running.")


def seed_if_requested(seed: bool) -> None:
    if not seed:
        return
    cloud_info("Seeding demo data inside the app container...")
    # Wait for the container to be healthy before seeding
    for i in range(15):
        r = subprocess.run([*compose_base(), "ps", "app", "--format", "json"], capture_output=True, text=True, cwd=APP_DIR)
        if '"Health":"healthy"' in r.stdout:
            break
        time.sleep(2)
    
    compose(["exec", "-T", "app", "python", "-m", "backend.seed"], check=False, timeout=300)


def resolve_domain(args: argparse.Namespace) -> str:
    if getattr(args, "domain", None):
        return args.domain
    env_path = APP_DIR / ".env.cloud"
    env = _read_env(env_path)
    return env.get("PUBLIC_DOMAIN") or DEFAULT_DOMAIN


def cmd_deploy(args: argparse.Namespace) -> int:
    require_linux()
    domain = resolve_domain(args)
    cloud_info(f"Deploying Vitrine to https://{domain} with Docker.")
    install_docker()
    sync_checkout()
    ensure_cloud_env(domain)
    write_runtime_files(domain)
    docker_build(no_cache=getattr(args, "no_cache", False))
    docker_up()
    seed_if_requested(args.seed)
    cmd_status(args)
    cloud_ok(f"Deployed. Visit https://{domain}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    require_linux()
    domain = resolve_domain(args)
    cloud_info(f"Updating Docker deployment for https://{domain}...")
    install_docker()
    sync_checkout()
    ensure_cloud_env(domain)
    write_runtime_files(domain)
    docker_build(no_cache=getattr(args, "no_cache", False))
    docker_up()
    if getattr(args, "seed", False):
        seed_if_requested(True)
    cmd_status(args)
    cloud_ok("Updated and restarted.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    compose(["ps"], check=False)
    compose(["exec", "-T", "app", "curl", "-fsS", f"http://127.0.0.1:{DEFAULT_GATEWAY_PORT}/health"], check=False)
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    service = args.service or "app"
    aliases = {
        "gateway": "app",
        "api": "app",
        "caddy": "web",
    }
    service = aliases.get(service, service)
    return compose(["logs", "-f", "--tail", "200", service], check=False)


def cmd_rollback(args: argparse.Namespace) -> int:
    cloud_warn("Rollback restarts the currently built Docker image. Re-deploy a previous checkout for a true code rollback.")
    compose(["restart"], check=False)
    return 0


def cmd_teardown(args: argparse.Namespace) -> int:
    cmd = ["down", "--remove-orphans"]
    if args.volumes:
        cmd.append("--volumes")
    compose(cmd, check=False)
    cloud_ok("Docker deployment stopped.")
    return 0


def cloud_main(argv: list[str]) -> int:
    global DRY, APP_DIR
    ap = argparse.ArgumentParser(description="Vitrine cloud VM deploy (Docker)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--app-dir", default=str(APP_DIR))
    ap.add_argument("--user", default="", help="deprecated; Docker deployment does not create a service user")
    ap.add_argument("--proxy", choices=["caddy", "nginx"], default="caddy", help="deprecated; Docker deployment uses Caddy")
    ap.add_argument("--gateway-port", type=int, default=DEFAULT_GATEWAY_PORT, help="deprecated; app listens on 8000 in Docker")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("deploy")
    p.add_argument("--domain", default=DEFAULT_DOMAIN)
    p.add_argument("--seed", action="store_true")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--workers", type=int, default=2, help="deprecated; monolith Docker deployment does not spawn worker units")
    p.set_defaults(func=cmd_deploy)

    u = sub.add_parser("update")
    u.add_argument("--domain")
    u.add_argument("--seed", action="store_true")
    u.add_argument("--no-cache", action="store_true")
    u.set_defaults(func=cmd_update)

    sub.add_parser("status").set_defaults(func=cmd_status)
    lp = sub.add_parser("logs")
    lp.add_argument("service", nargs="?")
    lp.set_defaults(func=cmd_logs)
    sub.add_parser("rollback").set_defaults(func=cmd_rollback)
    td = sub.add_parser("teardown")
    td.add_argument("--volumes", action="store_true", help="also delete SQLite/files/Caddy volumes")
    td.set_defaults(func=cmd_teardown)

    args = ap.parse_args(argv)
    DRY = args.dry_run
    APP_DIR = Path(args.app_dir)
    if args.proxy != "caddy":
        cloud_warn("--proxy is ignored; Docker cloud deployment uses the Caddy container.")
    if args.gateway_port != DEFAULT_GATEWAY_PORT:
        cloud_warn("--gateway-port is ignored; the app container listens on 8000.")
    if args.user:
        cloud_warn("--user is ignored; Docker cloud deployment does not create a VM service user.")
    if DRY:
        cloud_warn("DRY-RUN: no changes will be made.\n")
    return args.func(args)




def dispatch_cloud(argv: list[str]) -> int:
    return cloud_main(argv)


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
