#!/usr/bin/env python3
"""
Vitrine — top-level launcher.

    python run.py                # local dev (default)  -> localrun.py
    python run.py local [...]    # local dev, pass-through flags
    python run.py cloud [...]    # native cloud VM deploy -> cloudrun.py

This is a thin dispatcher. The real work lives in:
    - localrun.py  : native local orchestration (services + agent workers + Vite)
    - cloudrun.py  : native cloud VM deploy (systemd + nginx, no Docker)

See README.md (§13) and backend.md (§13/§14) for the full plan.
"""
from __future__ import annotations

import os
import subprocess
import sys

PY_MIN = (3, 11)
ROOT = os.path.dirname(os.path.abspath(__file__))

BANNER = r"""
 __      ___ _        _
 \ \    / (_) |_ _ _ (_)_ _  ___
  \ \/\/ /| |  _| '_|| | ' \/ -_)
   \_/\_/ |_|\__|_|  |_|_||_\___|   try the software, then own it.
"""


def _check_python() -> None:
    if sys.version_info < PY_MIN:
        sys.exit(
            f"Vitrine needs Python >= {PY_MIN[0]}.{PY_MIN[1]} "
            f"(found {sys.version.split()[0]})."
        )


def _dispatch(script: str, args: list[str]) -> int:
    path = os.path.join(ROOT, script)
    if not os.path.exists(path):
        sys.exit(f"Missing {script} next to run.py — cannot continue.")
    # Re-use the current interpreter so the right venv/python is honored.
    return subprocess.call([sys.executable, path, *args])


def main() -> int:
    _check_python()
    print(BANNER)

    argv = sys.argv[1:]
    mode = "local"
    if argv and argv[0] in {"local", "cloud"}:
        mode, argv = argv[0], argv[1:]
    elif argv and argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0

    if mode == "local":
        print(">> Starting Vitrine in LOCAL mode (localrun.py)\n")
        return _dispatch("localrun.py", argv)

    if mode == "cloud":
        print(">> Deploying Vitrine to CLOUD VM (cloudrun.py)\n")
        # default sub-action is `deploy` if none given
        if not argv or argv[0].startswith("-"):
            argv = ["deploy", *argv]
        return _dispatch("cloudrun.py", argv)

    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
