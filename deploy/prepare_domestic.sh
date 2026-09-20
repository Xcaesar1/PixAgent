#!/bin/sh
set -eu
umask 077
cd /opt/pixagent/source
backup="/opt/pixagent/domestic-backup-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup"
tar -czf "$backup/source.tar.gz" frontend/src/components/GenerateForm.tsx backend/app/schemas/run.py backend/tests/test_generation_modes.py deploy/check_generation_modes.py
docker image tag pixagent:local pixagent:before-domestic
tar -xzf /opt/pixagent/domestic-update.tar.gz -C /opt/pixagent/source
docker compose --env-file .env.vps -f compose.vps.yml -f compose.gpt.yml build app > /opt/pixagent/domestic-build.log 2>&1
docker run --rm --network pixagent_default --env-file .env.vps --cpus 0.75 --memory 2g -v /opt/pixagent/source/deploy:/checks:ro pixagent:local python /checks/test_generation_modes.py > /opt/pixagent/domestic-tests.log 2>&1
tail -n 3 /opt/pixagent/domestic-tests.log
printf 'Build and isolated regression passed; live containers unchanged.\n'
