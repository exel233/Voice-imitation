from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = ROOT / "logs"


def remove_logs_from(directory: Path) -> tuple[int, int]:
    removed = 0
    skipped = 0
    if not directory.exists():
        return removed, skipped

    for path in directory.glob("*.log"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            skipped += 1
    return removed, skipped


def main() -> int:
    removed_root, skipped_root = remove_logs_from(ROOT)
    removed_logs, skipped_logs = remove_logs_from(LOGS_DIR)
    total_removed = removed_root + removed_logs
    total_skipped = skipped_root + skipped_logs
    print(f"Removed {total_removed} log file(s).")
    if total_skipped:
        print(f"Skipped {total_skipped} log file(s) still in use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
