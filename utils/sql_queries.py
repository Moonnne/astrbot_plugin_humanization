"""Load named SQL statements from the plugin's packaged resources."""

import re
from pathlib import Path


class SqlQueries:
    def __init__(self):
        root = Path(__file__).resolve().parents[1] / "resource" / "sql"
        self.statements = {}
        for path in sorted(root.glob("*.sql")):
            parts = re.split(
                r"(?m)^-- name: (\w+)\s*$", path.read_text(encoding="utf-8")
            )
            for name, body in zip(parts[1::2], parts[2::2]):
                key = f"{path.stem}.{name}"
                if key in self.statements or not body.strip():
                    raise ValueError(f"Invalid SQL resource: {key}")
                self.statements[key] = body.strip()

    def __getitem__(self, name: str) -> str:
        return self.statements[name]
