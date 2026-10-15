"""Extract a local GTFS ZIP and locate feed directories."""
import argparse
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REFERENCE = ROOT / "data" / "reference"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", default=str(RAW / "mumbai_gtfs.zip"), help="Path to downloaded GTFS/repository ZIP")
    args = parser.parse_args()
    zip_path = Path(args.zip)
    if not zip_path.exists():
        raise SystemExit(
            f"ZIP not found: {zip_path}\n"
            "Download the ZIP from https://github.com/croyla/mumbai-gtfs "
            "and save it as data/raw/mumbai_gtfs.zip."
        )

    extract_dir = REFERENCE / "gtfs_extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        # Avoid path traversal from untrusted archive entries.
        for info in zf.infolist():
            target = (extract_dir / info.filename).resolve()
            if extract_dir.resolve() not in target.parents and target != extract_dir.resolve():
                raise ValueError(f"Unsafe ZIP path: {info.filename}")
        zf.extractall(extract_dir)

    feeds = []
    for routes in extract_dir.rglob("routes.txt"):
        folder = routes.parent
        if (folder / "stops.txt").exists():
            feeds.append(folder)

    if not feeds:
        raise SystemExit(
            "No GTFS feed folder with both routes.txt and stops.txt was found. "
            "Inspect the downloaded ZIP; the repository structure or filenames may have changed."
        )

    print(f"Extracted to: {extract_dir}")
    print("GTFS feed folders found:")
    for feed in feeds:
        print(f" - {feed}")
    print("\nNext: python -m processing.process_gtfs")

if __name__ == "__main__":
    main()
