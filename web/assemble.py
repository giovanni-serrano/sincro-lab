"""Assemble static assets with the normal, current-checkout SincroLab wheel."""

from __future__ import annotations

import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


ASSETS = (
    "index.html", "presentation.html", "presentation.css", "styles.css", "app.js", "plots.js", "runtime.js",
    "worker.js", "pyodide-config.js", "visuals.js",
    "transient-lab.js", "transient-lab.css",
    "design.json", "smib.svg", "rotor-angle.svg", "timeline.svg", "causal-chain.svg",
)


SHARED_ASSETS = {"design.json", "smib.svg", "rotor-angle.svg", "timeline.svg", "causal-chain.svg"}


def asset_path(name: str, root: Path) -> Path:
    """Use an explicit shared resource set, never arbitrary package files."""
    if name not in ASSETS:
        raise ValueError("Unknown web asset")
    folder = root / "src/sincrolab/interfaces/assets" if name in SHARED_ASSETS else root / "web"
    return folder / name


def assemble(wheel: Path, output: Path, *, root: Path | None = None) -> dict[str, object]:
    """Verify package sources byte-for-byte before copying a fixed asset set.

    No case data or calculated outputs are generated. Existing unrelated files
    are rejected, not deleted. The SHA-256 names the exact bytes installed by
    the browser; package sources additionally bind them to this checkout.
    """
    root = (root or Path(__file__).resolve().parents[1]).resolve()
    wheel = wheel.resolve(strict=True)
    output = output.resolve()
    if output == root or output in (root / "web").parents or output.is_relative_to(root / "web"):
        raise ValueError("Output must be separate from web sources")
    if not wheel.name.startswith("sincrolab-") or not wheel.name.endswith("-py3-none-any.whl"):
        raise ValueError("Use the normal SincroLab pure-Python wheel")
    with zipfile.ZipFile(wheel) as archive:
        package_files = {
            path.relative_to(root / "src").as_posix(): path.read_bytes()
            for path in (root / "src/sincrolab").rglob("*")
            if path.is_file() and (path.suffix in {".py", ".json"} or path.relative_to(root / "src/sincrolab").as_posix() in {f"interfaces/assets/{name}" for name in SHARED_ASSETS})
        }
        if "sincrolab/interfaces/web/bridge.py" not in package_files:
            raise ValueError("Checkout is missing the web bridge")
        for name, content in package_files.items():
            if name not in archive.namelist() or archive.read(name) != content:
                raise ValueError(f"Wheel does not match checkout source: {name}")
        packaged = {name for name in archive.namelist() if name.startswith("sincrolab/") and not name.endswith("/")}
        if packaged != set(package_files):
            raise ValueError("Wheel contains unexpected package files")
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError("Wheel must contain exactly one package metadata record")
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        if metadata["Name"] != "sincrolab":
            raise ValueError("Unexpected wheel package")
    manifest = {
        "wheel": wheel.name,
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "package_version": metadata["Version"],
        "package_source_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(package_files.items())},
        "asset_sha256": {name: hashlib.sha256(asset_path(name, root).read_bytes()).hexdigest() for name in ASSETS},
    }
    allowed = {*ASSETS, wheel.name, "manifest.json"}
    output.mkdir(parents=True, exist_ok=True)
    if any(path.is_symlink() or not path.is_file() or path.name not in allowed for path in output.iterdir()):
        raise ValueError("Output contains unrelated files; choose an empty directory")
    for name in ASSETS:
        shutil.copyfile(asset_path(name, root), output / name)
    shutil.copyfile(wheel, output / wheel.name)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = assemble(args.wheel, args.output)
    print(f"Assembled {manifest['wheel']} SHA-256 {manifest['wheel_sha256']}")


if __name__ == "__main__":
    main()
