from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.audio_pipeline import build_xtts_reference, build_xtts_reference_excerpts
from backend.app.storage import list_profiles, save_profile


def main() -> int:
    count = 0
    for profile in list_profiles():
        if profile.synthesisProvider != "xtts" or not profile.samples:
            continue
        excerpt_manifest = build_xtts_reference_excerpts(profile.id, profile.samples)
        reference_path = build_xtts_reference(profile.id, profile.samples)
        if not reference_path:
            continue
        metadata = dict(profile.metadata)
        metadata["xttsReferencePath"] = reference_path
        metadata["xttsReferenceExcerpts"] = excerpt_manifest
        metadata["xttsReferenceExcerptIds"] = [excerpt["id"] for excerpt in excerpt_manifest[: min(len(excerpt_manifest), 4)]]
        updated = profile.model_copy(update={"metadata": metadata})
        save_profile(updated)
        count += 1
        print(f"Rebuilt XTTS reference for {profile.name} ({profile.id})")
    print(f"Updated {count} XTTS profile(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
