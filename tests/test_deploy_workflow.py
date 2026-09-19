"""Exercise the deployment shell script with fake git, pip and systemctl.

No server, network, package installation or real service is used.
"""
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
with open(os.environ['DEPLOY_TEST_LOG'], 'a') as log:
    log.write(json.dumps([name, *args]) + '\\n')
if name == 'git':
    if args[:1] == ['rev-parse']:
        print('previous-commit')
    elif args[:1] == ['diff']:
        sys.exit(int(os.environ['DEPLOY_TEST_REQUIREMENTS_CHANGED']))
elif name in ('python', 'python3') and args[:2] == ['-m', 'venv']:
    activate = Path(args[2]) / 'bin' / 'activate'
    activate.parent.mkdir(parents=True)
    activate.write_text('# fake virtual environment\\n')
elif name == 'sudo' and args[:2] in (['systemctl', 'is-active'], ['systemctl', 'status']):
    sys.exit(0 if os.environ['DEPLOY_TEST_BOT_ACTIVE'] == '1' else 3)
elif name == 'pip':
    raise SystemExit('Use python -m pip; do not upgrade pip during deployment')
"""


class DeploymentTests(unittest.TestCase):
    def simulate(self, *, changed=False, new_environment=False, active=True):
        workflow = (ROOT / '.github/workflows/deploy.yml').read_text()
        script = textwrap.dedent(workflow.split('          script: |\n', 1)[1])
        with tempfile.TemporaryDirectory(prefix='max-deploy-test-') as directory:
            root = Path(directory)
            project = root / 'project'
            project.mkdir()
            if not new_environment:
                activate = project / 'venv/bin/activate'
                activate.parent.mkdir(parents=True)
                activate.write_text('# fake virtual environment\n')
            commands = root / 'commands'
            commands.mkdir()
            for name in ('git', 'python', 'python3', 'pip', 'sudo', 'sleep'):
                command = commands / name
                command.write_text(f'#!{sys.executable}\n' + FAKE_COMMAND)
                command.chmod(0o755)
            # Isolate the project directory without changing the user's HOME.
            script = script.replace('PROJECT_DIR="$HOME/max_bot"', f'PROJECT_DIR="{project}"')
            script = script.replace('${{ secrets.SSH_USER }}', 'test-user')
            log = root / 'commands.jsonl'
            env = dict(os.environ)
            env.update(
                PATH=str(commands) + os.pathsep + env['PATH'],
                DEPLOY_TEST_LOG=str(log),
                DEPLOY_TEST_REQUIREMENTS_CHANGED=str(int(changed)),
                DEPLOY_TEST_BOT_ACTIVE=str(int(active)),
            )
            result = subprocess.run(
                ['/bin/bash', '-e', '-c', script], cwd=project, env=env,
                capture_output=True, text=True, timeout=15,
            )
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            return result, calls

    def test_unchanged_requirements_keep_installed_dependencies(self):
        result, calls = self.simulate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(call[0] in ('python', 'python3', 'pip') for call in calls))
        self.assertIn(['sudo', 'systemctl', 'restart', 'max-bot.service'], calls)
        self.assertFalse(any('app-api' in arg or 'psql' in arg for call in calls for arg in call))

    def test_changed_requirements_are_installed(self):
        result, calls = self.simulate(changed=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(['python', '-m', 'pip', 'install', '-r', 'requirements.txt', '--quiet'], calls)

    def test_new_environment_installs_even_without_dependency_changes(self):
        result, calls = self.simulate(new_environment=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(['python', '-m', 'pip', 'install', '-r', 'requirements.txt', '--quiet'], calls)

    def test_failed_bot_start_fails_deployment(self):
        result, calls = self.simulate(active=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(['sudo', 'systemctl', 'is-active', '--quiet', 'max-bot.service'], calls)
        self.assertNotIn('Деплой завершен успешно', result.stdout)


if __name__ == '__main__':
    unittest.main()
