"""Non-destructive learning-profile migration command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from deeptutor.services.learning_profiles.migration import LearningProfileMigrator


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True, help="Account workspace directory")
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = LearningProfileMigrator(args.workspace).migrate(args.profile_id, dry_run=args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
