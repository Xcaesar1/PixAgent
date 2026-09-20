#!/bin/sh
set -eu
umask 077
cd /opt/pixagent/source
backup="/opt/pixagent/backups/modes-$(date -u +%Y%m%dT%H%M%SZ)"
sudo install -d -m 700 -o "$(id -un)" -g "$(id -gn)" "$backup"
tar --exclude=.git --exclude=.env.vps -czf "$backup/source.tar.gz" .
cp .env.vps "$backup/env.vps"
docker image tag pixagent:local pixagent:before-generation-modes
printf '%s\n' "$backup" > /opt/pixagent/modes-backup-path
mkdir -p /opt/pixagent/secrets/l0veyou
chmod 700 /opt/pixagent/secrets /opt/pixagent/secrets/l0veyou
if [ ! -f /opt/pixagent/secrets/l0veyou/session.token ]; then
    install -m 600 /opt/pixagent/provider-probe/session.token /opt/pixagent/secrets/l0veyou/session.token
fi
tar -xzf /opt/pixagent/generation-modes-update.tar.gz -C /opt/pixagent/source
docker compose --env-file .env.vps -f compose.vps.yml -f compose.gpt.yml config --quiet
docker compose --env-file .env.vps -f compose.vps.yml -f compose.gpt.yml build app > /opt/pixagent/modes-build.log 2>&1
printf 'Build completed; no running containers replaced yet.\n'
