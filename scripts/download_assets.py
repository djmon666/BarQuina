from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen

ASSETS = {
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css": "bootstrap.min.css",
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js": "bootstrap.bundle.min.js",
    "https://cdn.socket.io/4.7.2/socket.io.min.js": "socket.io.min.js",
}

DEST = Path(__file__).resolve().parent.parent / "app" / "static" / "vendor"


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for url, filename in ASSETS.items():
        target = DEST / filename
        print(f"Downloading {url} -> {target}")
        with urlopen(url) as resp:
            target.write_bytes(resp.read())
    print("Assets stored in", DEST)


if __name__ == "__main__":
    main()
