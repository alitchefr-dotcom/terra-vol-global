# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
"""Terra Vol Global — Streamlit entry point.

The app is split into section files in ./sections. They run in order (by file name) in one shared namespace,
exactly as if they were one script: later sections use variables defined by earlier ones. Each file is read on
every run, so updates apply without restarting the app.
"""
from pathlib import Path

_SECTIONS_DIR = Path(__file__).resolve().parent / "sections"

for _section in sorted(_SECTIONS_DIR.glob("[0-9][0-9]_*.py")):
    exec(compile(_section.read_text(encoding="utf-8"), str(_section), "exec"), globals())
