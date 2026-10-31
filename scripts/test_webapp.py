"""Run tests in a separate local database; demo data remains untouched."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
args=['psql','-h','127.0.0.1','-p','55439','-U','webapp_local','-d','postgres','-Atc']
if not subprocess.check_output(args+["SELECT 1 FROM pg_database WHERE datname='max_webapp_unittest'"],text=True).strip():
    subprocess.run(args+['CREATE DATABASE max_webapp_unittest'],check=True)
psql = ['psql','-h','127.0.0.1','-p','55439','-U','webapp_local','-d','max_webapp_unittest','-v','ON_ERROR_STOP=1','-f']
subprocess.run(psql+['init_db.sql'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
for migration in sorted((ROOT/'migrations').glob('*.sql')):
    subprocess.run(psql+[str(migration)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
os.environ['WEBAPP_UNITTEST_DB']='max_webapp_unittest'
subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_webapp*.py','-v'],check=True)
