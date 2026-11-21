"""Write the Excel add-in's manifest for one address, from app/desk/excel/manifest.template.xml.

Local:  uv run python scripts/make_manifest.py --base-url https://localhost:3000
Hosted: uv run python scripts/make_manifest.py --base-url https://<app>.fly.dev --auth-domain https://<issuer host> \
            --out outputs/manifest-hosted.xml
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/desk/excel/manifest.template.xml"
LOCAL = ROOT / "app/desk/excel/manifest.xml"


def render(base_url: str, auth_domain: str | None = None) -> str:
    base = base_url.rstrip("/")
    if urlparse(base).scheme != "https":
        raise SystemExit(
            "Excel only loads add-ins over HTTPS. Use an https:// address."
        )
    extra = ""
    if auth_domain:  # the sign-in provider's pages open in the add-in's dialog
        parsed = urlparse(auth_domain)
        extra = f"\n    <AppDomain>{parsed.scheme}://{parsed.netloc}</AppDomain>"
    text = (
        TEMPLATE.read_text()
        .replace("{{BASE_URL}}", base)
        .replace("{{AUTH_DOMAIN}}", extra)
    )
    ET.fromstring(text.encode())  # must stay well-formed
    return text


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", required=True)
    p.add_argument("--auth-domain")
    p.add_argument("--out", default=str(LOCAL))
    a = p.parse_args()
    Path(a.out).write_text(render(a.base_url, a.auth_domain))
    print(f"Wrote {a.out} for {a.base_url}")


if __name__ == "__main__":
    main()
