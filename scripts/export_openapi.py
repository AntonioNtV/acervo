"""Write the API's OpenAPI to `docs/openapi.json`, the source of the web client. CI fails when it is stale.

uv run python scripts/export_openapi.py
"""

import json
from pathlib import Path

from acervo.api.main import create_app

OUT = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"


def main() -> None:
    OUT.write_text(json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
