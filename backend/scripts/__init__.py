"""Operator scripts — diagnostics and one-off maintenance.

These are deliberately NOT part of any runtime path (unlike `backend/seed.py`,
which run.py, the Docker entrypoint and run_onVM.py all invoke). Nothing imports
from this package; each module is run on demand from the repo root:

    python -m backend.scripts.check_ai     # verify every AI provider + agent
    python -m backend.scripts.reembed      # rebuild the catalogue's vectors
"""
