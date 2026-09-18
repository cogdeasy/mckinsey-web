"""Write the OpenAPI document to services/api/openapi.json for the drift check (FR-093)."""

from __future__ import annotations

import json
from pathlib import Path

from claims_intake.config import Settings
from claims_intake.main import create_app

TARGET = Path(__file__).resolve().parents[1] / "openapi.json"


def main() -> None:
    app = create_app(Settings(environment="test", auth_disabled=True))
    TARGET.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
