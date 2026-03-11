from __future__ import annotations

import shutil
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: copy_ci_workflow.py <template_root> <destination_root>")

    template_root = Path(sys.argv[1]).resolve()
    destination_root = Path(sys.argv[2]).resolve()

    source = template_root / ".github" / "workflows" / "ci.yml"
    target = destination_root / ".github" / "workflows" / "ci.yml"

    if not source.is_file():
        raise SystemExit(f"canonical workflow not found: {source}")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
