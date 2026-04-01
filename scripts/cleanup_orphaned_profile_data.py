from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.storage import PROFILE_DATA, PROFILES, ensure_storage


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove profile_data directories that no longer have a matching profile JSON file."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete orphaned directories. Without this flag, the script only reports what would be removed.",
    )
    args = parser.parse_args()

    ensure_storage()

    live_profile_ids = {path.stem for path in PROFILES.glob("*.json")}
    orphaned_dirs = sorted(
        path for path in PROFILE_DATA.iterdir() if path.is_dir() and path.name not in live_profile_ids
    )

    mode = "apply" if args.apply else "dry-run"
    print(f"[cleanup_orphaned_profile_data] mode={mode}")
    print(f"[cleanup_orphaned_profile_data] live_profiles={len(live_profile_ids)}")

    if not orphaned_dirs:
        print("[cleanup_orphaned_profile_data] No orphaned profile_data directories found.")
        return 0

    print("[cleanup_orphaned_profile_data] Orphaned directories:")
    for orphaned_dir in orphaned_dirs:
        print(f" - {orphaned_dir.resolve()}")

    if not args.apply:
        print("[cleanup_orphaned_profile_data] Dry run only. Re-run with --apply to delete these directories.")
        return 0

    for orphaned_dir in orphaned_dirs:
        shutil.rmtree(orphaned_dir)
        print(f"[cleanup_orphaned_profile_data] Removed {orphaned_dir.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
