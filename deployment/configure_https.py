"""Install a managed Apache block, verifying redirects before enabling HSTS.

Run on the hosting account only, after deploying the application.
Existing Passenger/cPanel directives are preserved; failures restore the file.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

BEGIN = "# BEGIN SBZ CANONICAL HTTPS"
END = "# END SBZ CANONICAL HTTPS"
REDIRECT = """<IfModule mod_rewrite.c>
RewriteEngine On
RewriteCond %{HTTPS} !=on [OR]
RewriteCond %{HTTP_HOST} !^sbzpart\\.ir$ [NC]
RewriteRule ^ https://sbzpart.ir%{REQUEST_URI} [R=301,L,NE]
</IfModule>
"""
HSTS = """<IfModule mod_headers.c>
Header always set Strict-Transport-Security "max-age=31536000" "expr=%{HTTPS} == 'on'"
</IfModule>
"""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def head(url):
    try:
        response = build_opener(NoRedirect).open(Request(url, method="HEAD"), timeout=30)
    except HTTPError as error:
        response = error
    with response:
        return response.status, response.headers


def content(existing, hsts=False):
    remaining = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", "", existing, flags=re.S)
    return BEGIN + "\n" + REDIRECT + (HSTS if hsts else "") + END + "\n\n" + remaining.lstrip("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-root", type=Path, required=True)
    args = parser.parse_args()
    path = args.document_root.resolve() / ".htaccess"
    # Fail closed on a wrong path instead of creating a second configuration.
    if not path.is_file():
        raise SystemExit("Existing public .htaccess is required.")
    original = path.read_bytes()
    existing = original.decode("utf-8")
    backup_dir = Path(__file__).resolve().parents[1] / "tmp" / "deployment-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    shutil.copy2(path, backup_dir / f"htaccess-{timestamp}.bak")
    try:
        path.write_text(content(existing), encoding="utf-8")
        for prefix in ("http://sbzpart.ir", "http://www.sbzpart.ir", "https://www.sbzpart.ir"):
            for suffix in ("/", "/catalog/?category=probe&page=2"):
                status, headers = head(prefix + suffix)
                if status != 301 or headers.get("Location") != "https://sbzpart.ir" + suffix:
                    raise RuntimeError(f"Unexpected redirect for {prefix + suffix}: {status}")
        status, _ = head("https://sbzpart.ir/")
        if status != 200:
            raise RuntimeError(f"Canonical homepage is not healthy: {status}")
        print("All redirects verified. Enabling HSTS.", flush=True)
        path.write_text(content(existing, hsts=True), encoding="utf-8")
        status, headers = head("https://sbzpart.ir/")
        if status != 200 or headers.get("Strict-Transport-Security") != "max-age=31536000":
            raise RuntimeError("HSTS verification failed.")
        print("HTTPS, canonical redirects and HSTS verified.")
    except Exception:
        path.write_bytes(original)
        raise


if __name__ == "__main__":
    main()
