from __future__ import annotations

import argparse
import contextlib
import json
from pathlib import Path

from .audio_pipeline import preprocess_sample
from .services import VoiceProfileService
from .storage import profile_artifacts_dir, read_profile, save_profile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--authorized", action="store_true")
    args = parser.parse_args()

    service = VoiceProfileService()
    job = service.jobs.get(args.job_id)
    manifest_path = profile_artifacts_dir(args.profile_id) / "upload_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    try:
        samples = []
        total = max(len(manifest["samples"]), 1)
        for index, entry in enumerate(manifest["samples"], start=1):
            sample = preprocess_sample(
                args.profile_id,
                entry["sampleId"],
                Path(entry["rawPath"]),
                entry["originalName"],
            )
            samples.append(sample)
            job = service.jobs.update(
                job,
                progress=0.15 + (0.35 * index / total),
                step="Preprocessing samples",
                message=f"Processed sample {index} of {total}",
                resultId=args.profile_id,
            )
        profile = service._finalize_profile(
            args.profile_id,
            args.name,
            args.description,
            args.authorized,
            samples,
            job,
            generate_quick_preview=False,
        )
        service.jobs.update(
            job,
            status="completed",
            progress=1,
            step="Completed",
            message=f"Profile ready: {profile.name}",
            resultId=profile.id,
        )
        with contextlib.suppress(FileNotFoundError):
            manifest_path.unlink()
        return 0
    except Exception as exc:
        error_message = str(exc) or repr(exc)
        with contextlib.suppress(FileNotFoundError):
            failed = read_profile(args.profile_id)
            save_profile(
                failed.model_copy(
                    update={
                        "status": "failed",
                        "diagnostics": failed.diagnostics.model_copy(
                            update={
                                "warnings": sorted(set([*failed.diagnostics.warnings, error_message])),
                            }
                        ),
                    }
                )
            )
        service.jobs.update(job, status="failed", progress=1, step="Failed", message=error_message, resultId=args.profile_id)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
