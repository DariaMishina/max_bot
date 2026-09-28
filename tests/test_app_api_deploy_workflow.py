"""Exercise the App API deployment script without a server or network."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
FAKE_COMMAND = """import json
import os
from pathlib import Path
import sys

name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['APP_DEPLOY_TEST_LOG'], 'a') as log:
    log.write(json.dumps([name, *args]) + '\\n')

if name == 'git':
    if args == ['diff', '--quiet'] or args == ['diff', '--cached', '--quiet']:
        sys.exit(1 if os.environ['APP_DEPLOY_TEST_DIRTY'] == '1' else 0)
    if args[:1] == ['rev-parse']:
        print('target-commit' if args[1] == 'origin/main' else 'previous-commit')
    elif args[:2] == ['merge-base', '--is-ancestor']:
        sys.exit(0)
    elif args[:1] == ['diff'] and args[-1:] == ['requirements.txt']:
        sys.exit(0 if os.environ['APP_DEPLOY_TEST_REQUIREMENTS_CHANGED'] == '0' else 1)
    elif args[:1] == ['diff'] and 'app/migrations' in args:
        sys.exit(0 if os.environ['APP_DEPLOY_TEST_MIGRATIONS_CHANGED'] == '0' else 1)
elif name in ('python', 'python3') and args[:2] == ['-m', 'venv']:
    activate = Path(args[2]) / 'bin' / 'activate'
    activate.parent.mkdir(parents=True)
    activate.write_text('# fake virtual environment\\n')
elif name == 'sudo':
    if args[:2] == ['systemctl', 'is-active']:
        sys.exit(0 if os.environ['APP_DEPLOY_TEST_ACTIVE'] == '1' else 3)
elif name == 'curl':
    if os.environ['APP_DEPLOY_TEST_HEALTHY'] == '1':
        print('OK')
        sys.exit(0)
    sys.exit(22)
"""


class AppApiDeploymentTests(unittest.TestCase):
    def simulate(
        self, *, requirements_changed=False, migrations_changed=False,
        migrations_confirmed=False, dirty=False, active=True, healthy=True,
    ):
        workflow = (ROOT / '.github/workflows/deploy-app-api.yml').read_text()
        script = textwrap.dedent(workflow.split('          script: |\n', 1)[1])
        with tempfile.TemporaryDirectory(prefix='app-api-deploy-test-') as directory:
            root = Path(directory)
            project = root / 'project'
            project.mkdir()
            activate = project / 'venv/bin/activate'
            activate.parent.mkdir(parents=True)
            activate.write_text('# fake virtual environment\n')
            commands = root / 'commands'
            commands.mkdir()
            for name in ('git', 'python', 'python3', 'sudo', 'curl', 'sleep'):
                command = commands / name
                command.write_text(f'#!{sys.executable}\n' + FAKE_COMMAND)
                command.chmod(0o755)

            script = script.replace('PROJECT_DIR="$HOME/max_bot"', f'PROJECT_DIR="{project}"')
            script = script.replace('${{ secrets.SSH_USER }}', 'test-user')
            log = root / 'commands.jsonl'
            env = dict(os.environ)
            env.update(
                PATH=str(commands) + os.pathsep + env['PATH'],
                APP_DEPLOY_TEST_LOG=str(log),
                APP_DEPLOY_TEST_REQUIREMENTS_CHANGED=str(int(requirements_changed)),
                APP_DEPLOY_TEST_MIGRATIONS_CHANGED=str(int(migrations_changed)),
                APP_DEPLOY_TEST_DIRTY=str(int(dirty)),
                APP_DEPLOY_TEST_ACTIVE=str(int(active)),
                APP_DEPLOY_TEST_HEALTHY=str(int(healthy)),
                MIGRATIONS_CONFIRMED=str(migrations_confirmed).lower(),
                DEPLOY_EVENT='push',
                DEPLOY_BEFORE='event-before',
                DEPLOY_SHA='event-target',
            )
            result = subprocess.run(
                ['/bin/bash', '-c', script], cwd=project, env=env,
                capture_output=True, text=True, timeout=30,
            )
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            return result, calls

    def test_deploy_restarts_only_app_api_and_checks_health(self):
        result, calls = self.simulate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(['git', 'merge', '--ff-only', 'origin/main'], calls)
        self.assertIn(['sudo', 'systemctl', 'restart', 'app-api'], calls)
        self.assertIn(['sudo', 'systemctl', 'is-active', '--quiet', 'app-api'], calls)
        self.assertTrue(any(call[0] == 'curl' and call[-1].endswith('/health') for call in calls))
        self.assertFalse(any('max-bot.service' in arg or 'psql' in arg for call in calls for arg in call))
        self.assertFalse(any(call[:3] == ['git', 'reset', '--hard'] for call in calls))

    def test_workflow_covers_app_api_dependencies_and_shares_deploy_lock(self):
        app_workflow = (ROOT / '.github/workflows/deploy-app-api.yml').read_text()
        bot_workflow = (ROOT / '.github/workflows/deploy.yml').read_text()
        for path in (
            'app/**', 'app_api_server.py', 'handlers/tarot_cards.py',
            'main/config_reader.py', 'main/llm_divination.py',
            'static/images/**', 'init_app_db.sql', 'requirements.txt',
        ):
            self.assertIn(f'"{path}"', app_workflow)
        self.assertIn('group: production-vm-deploy', app_workflow)
        self.assertIn('group: production-vm-deploy', bot_workflow)

    def test_changed_requirements_are_installed(self):
        result, calls = self.simulate(requirements_changed=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(['python', '-m', 'pip', 'install', '-r', 'requirements.txt', '--quiet'], calls)

    def test_unconfirmed_migration_stops_before_update_and_restart(self):
        result, calls = self.simulate(migrations_changed=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(['git', 'merge', '--ff-only', 'origin/main'], calls)
        self.assertNotIn(['sudo', 'systemctl', 'restart', 'app-api'], calls)

    def test_confirmed_migration_allows_deploy(self):
        result, calls = self.simulate(migrations_changed=True, migrations_confirmed=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(['sudo', 'systemctl', 'restart', 'app-api'], calls)

    def test_dirty_tracked_files_stop_before_fetch(self):
        result, calls = self.simulate(dirty=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(call[:2] == ['git', 'fetch'] for call in calls))
        self.assertNotIn(['sudo', 'systemctl', 'restart', 'app-api'], calls)

    def test_failed_health_check_fails_deploy(self):
        result, calls = self.simulate(healthy=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(['sudo', 'systemctl', 'status', 'app-api', '--no-pager', '-l'], calls)
        self.assertNotIn('App API deploy completed', result.stdout)


if __name__ == '__main__':
    unittest.main()
