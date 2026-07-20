from __future__ import annotations

import base64
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNKS = ROOT / ".binder-upload"
OUTPUT = ROOT / "docs" / "project-records" / "print"

FILES = {
    "volume1": (
        "FXD_Engineering_Binder_Volume_1_Milestones_01-25_Final.pdf",
        "92747bbe94d12a7551f58bf1f36d8ca8d3c10304aae3b47e096e1c650db681be",
    ),
    "volume2": (
        "FXD_Engineering_Binder_Volume_2_Milestones_26-31_Final.pdf",
        "fcbf8424b7e3d733bf2a39f231bf558cc6623b272f679666bfc5c9a18f87bc3d",
    ),
}


def reconstruct(key: str, filename: str, expected_sha256: str) -> None:
    parts = sorted(CHUNKS.glob(f"{key}.part*"))
    if not parts:
        raise RuntimeError(f"No upload chunks found for {key}")
    encoded = "".join(part.read_text(encoding="ascii").strip() for part in parts)
    payload = base64.b64decode(encoded, validate=True)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected_sha256:
        raise RuntimeError(f"SHA-256 mismatch for {filename}: {actual}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / filename).write_bytes(payload)
    print(f"reconstructed {filename}: {len(payload)} bytes, {actual}")


if __name__ == "__main__":
    for key, (filename, expected_sha256) in FILES.items():
        reconstruct(key, filename, expected_sha256)
