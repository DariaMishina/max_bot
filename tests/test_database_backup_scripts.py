import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKUP_SCRIPT = REPO_ROOT / "scripts" / "backup_databases.sh"
RESTORE_SCRIPT = REPO_ROOT / "scripts" / "restore_database_backup.sh"


class DatabaseBackupScriptsTest(unittest.TestCase):
    def test_shell_scripts_have_valid_bash_syntax(self) -> None:
        subprocess.run(
            ["bash", "-n", str(BACKUP_SCRIPT), str(RESTORE_SCRIPT)],
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

    def test_timer_is_persistent_and_uses_moscow_time(self) -> None:
        timer = (REPO_ROOT / "deploy" / "postgres-backup.timer").read_text()
        self.assertIn("Persistent=true", timer)
        self.assertIn("03:00:00 Europe/Moscow", timer)


if __name__ == "__main__":
    unittest.main()
