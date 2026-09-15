"""Inject real figures into the Against Plan page mockup.

    python design/build_mockup.py

Runs etl/comparison_expected.py for every state the page can show and writes
design/plan-mockup.html from design/plan-mockup.src.html.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATES = [(2019, "budget"), (2019, "prior"), (2020, "budget"), (2020, "prior")]


def main() -> None:
    data = {}
    for year, comp in STATES:
        out = subprocess.run([sys.executable, str(ROOT / "etl" / "comparison_expected.py"), str(year), comp],
                             check=True, capture_output=True, text=True).stdout
        data[f"{year}_{comp}"] = json.loads(out)
    src = (ROOT / "design" / "plan-mockup.src.html").read_text(encoding="utf-8")
    (ROOT / "design" / "plan-mockup.html").write_text(src.replace("/*DATA*/", json.dumps(data)),
                                                      encoding="utf-8", newline="\n")
    print(f"design/plan-mockup.html  ({len(STATES)} states)")


if __name__ == "__main__":
    main()
