import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKUP_SCRIPT = REPO_ROOT / "scripts" / "backup_databases.sh"
RESTORE_SCRIPT = REPO_ROOT / "scripts" / "restore_database_backup.sh"
BILLING_HEALTH_SCRIPT = REPO_ROOT / "scripts" / "billing_health_report.sh"
ANDROID_RELEASE_SCRIPT = REPO_ROOT / "scripts" / "check_android_release.sh"


class DatabaseBackupScriptsTest(unittest.TestCase):
    def test_shell_scripts_have_valid_bash_syntax(self) -> None:
        subprocess.run(
            [
                "bash", "-n",
                str(BACKUP_SCRIPT),
                str(RESTORE_SCRIPT),
                str(BILLING_HEALTH_SCRIPT),
                str(ANDROID_RELEASE_SCRIPT),
            ],
            check=True,
            cwd=REPO_ROOT,
        )

    def test_restore_refuses_production_database_by_default(self) -> None:
        with tempfile.NamedTemporaryFile() as archive:
            result = subprocess.run(
                [
                    str(RESTORE_SCRIPT),
                    "--archive",
                    archive.name,
                    "--target-db",
                    "max_bot_db",
                    "--confirm",
                    "max_bot_db",
                ],
                check=False,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing production target max_bot_db", result.stderr)

    def test_restore_refuses_new_app_environment_databases_by_default(self) -> None:
        for database in ("app_bot_prod_db",):
            with self.subTest(database=database), tempfile.NamedTemporaryFile() as archive:
                result = subprocess.run(
                    [
                        str(RESTORE_SCRIPT),
                        "--archive", archive.name,
                        "--target-db", database,
                        "--confirm", database,
                    ],
                    check=False,
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(f"Refusing production target {database}", result.stderr)

    def test_timer_is_persistent_and_uses_moscow_time(self) -> None:
        timer = (REPO_ROOT / "deploy" / "postgres-backup.timer").read_text()
        self.assertIn("Persistent=true", timer)
        self.assertIn("03:00:00 Europe/Moscow", timer)

    def test_retention_keeps_three_latest_completed_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            keys_file = temp_path / "keys.txt"
            deleted_file = temp_path / "deleted.txt"
            fake_aws = temp_path / "aws"

            timestamps = [
                "20261014T000000Z",
                "20261015T000000Z",
                "20261016T000000Z",
                "20261017T000000Z",
            ]
            keys = []
            for timestamp in timestamps:
                keys.extend(
                    [
                        f"daily/max_bot_db/2026/10/14/max_bot_db-{timestamp}.dump.age",
                        f"daily/app_bot_db/2026/10/14/app_bot_db-{timestamp}.dump.age",
                        f"daily/manifests/2026/10/14/manifest-{timestamp}.txt.age",
                    ]
                )
            orphan_timestamp = "20261013T000000Z"
            orphan_key = (
                "daily/max_bot_db/2026/10/13/"
                f"max_bot_db-{orphan_timestamp}.dump.age"
            )
            keys.append(orphan_key)
            keys_file.write_text("\t".join(keys) + "\n")
            fake_aws.write_text(
                """#!/usr/bin/env bash
set -eu
if [[ " $* " == *" list-objects-v2 "* ]]; then
  cat "$FAKE_KEYS_FILE"
  exit 0
fi
if [[ " $* " == *" delete-object "* ]]; then
  while (($#)); do
    if [[ "$1" == "--key" ]]; then
      printf '%s\\n' "$2" >>"$FAKE_DELETED_FILE"
      exit 0
    fi
    shift
  done
fi
exit 2
"""
            )
            fake_aws.chmod(0o755)

            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{temp_path}:{environment['PATH']}",
                    "FAKE_KEYS_FILE": str(keys_file),
                    "FAKE_DELETED_FILE": str(deleted_file),
                    "BACKUP_S3_ENDPOINT": "https://example.invalid",
                    "BACKUP_S3_BUCKET": "test-bucket",
                    "BACKUP_S3_PREFIX": "daily",
                    "BACKUP_RETENTION_SUCCESSFUL_RUNS": "3",
                }
            )
            subprocess.run(
                [
                    "bash",
                    "-c",
                    f"source {BACKUP_SCRIPT!s}; prune_old_successful_runs",
                ],
                check=True,
                cwd=REPO_ROOT,
                env=environment,
            )

            deleted = set(deleted_file.read_text().splitlines())
            oldest = timestamps[0]
            self.assertEqual(
                deleted,
                {
                    f"daily/max_bot_db/2026/10/14/max_bot_db-{oldest}.dump.age",
                    f"daily/app_bot_db/2026/10/14/app_bot_db-{oldest}.dump.age",
                    f"daily/manifests/2026/10/14/manifest-{oldest}.txt.age",
                },
            )
            self.assertNotIn(orphan_key, deleted)


if __name__ == "__main__":
    unittest.main()
