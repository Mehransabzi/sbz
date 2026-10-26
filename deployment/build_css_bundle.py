"""Build minified CSS bundles with the Python-only rcssmin package."""
from pathlib import Path
import re



ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "store" / "storefront" / "static"
STOREFRONT = [
    "storefront/css/site.css",
    "storefront/css/theme.css",
    "storefront/css/navigation.css",
    "storefront/css/customer.css",
    "../../support/static/support/support.css",
    "storefront/css/light.css",
    "storefront/css/announcements.css",
]
CONTROL_PANEL = [
    "storefront/css/site.css",
    "storefront/css/theme.css",
    "../../controlpanel/static/controlpanel/panel.css",
    "../../support/static/support/support.css",
    "../../controlpanel/static/controlpanel/admin-theme.css",
    "storefront/css/announcements.css",
]


def build(name, sources):
    content = "\n".join((STATIC / source).read_text(encoding="utf-8") for source in sources)
    output = STATIC / "storefront" / "css" / name
    output.write_text(minify_css(content), encoding="utf-8")
    source_size = sum((STATIC / source).stat().st_size for source in sources)
    print(f"{name}: {source_size} -> {output.stat().st_size} bytes")


def minify_css(source):
    """Collapse CSS whitespace without changing strings or selector spacing."""
    out = []
    quote = None
    escaped = False
    in_comment = False
    pending_space = False
    i = 0
    while i < len(source):
        char = source[i]
        next_char = source[i + 1] if i + 1 < len(source) else ""
        if in_comment:
            if char == "*" and next_char == "/":
                in_comment = False
                pending_space = True
                i += 2
                continue
            i += 1
            continue
        if quote:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            i += 1
            continue
        if char == "/" and next_char == "*":
            in_comment = True
            i += 2
            continue
        if char in {"'", '"'}:
            if pending_space and out and out[-1] not in "{};,":
                out.append(" ")
            pending_space = False
            quote = char
            out.append(char)
            i += 1
            continue
        if char.isspace():
            pending_space = True
            i += 1
            continue
        if pending_space and out and char not in "{};," and out[-1] not in "{};,":
            out.append(" ")
        pending_space = False
        out.append(char)
        i += 1
    return re.sub(r"\s+$", "", "".join(out))


if __name__ == "__main__":
    build("site-bundle.min.css", STOREFRONT)
    build("admin-bundle.min.css", CONTROL_PANEL)
