#!/bin/bash
set -euo pipefail
umask 077
cd /opt/pixagent/source
exec 9>/opt/pixagent/https.lock
flock -n 9
test ! -e /etc/caddy/pixagent.caddy
backup=/opt/pixagent/backups/https-$(date -u +%Y%m%dT%H%M%SZ)
install -d -m 700 "$backup"
cp -a /etc/caddy/Caddyfile "$backup/Caddyfile"
cp -a .env.vps "$backup/env.vps"
docker ps -q | xargs docker inspect --format '{{.Name}}|{{.Id}}|{{.Image}}|{{.RestartCount}}|{{.State.Status}}' > "$backup/containers.txt"
original=$(sha256sum /etc/caddy/Caddyfile | cut -d ' ' -f 1)
if test -e /opt/pixagent/access.env; then
    set -a
    source /opt/pixagent/access.env
    set +a
else
    export ENTRY_USER=pixagent APP_USER=pixagent_owner
    export ENTRY_PASSWORD=$(openssl rand -hex 18)
    export APP_PASSWORD=$(openssl rand -hex 18)
    printf 'ENTRY_USER=%s\nENTRY_PASSWORD=%s\nAPP_USER=%s\nAPP_PASSWORD=%s\n' \
        "$ENTRY_USER" "$ENTRY_PASSWORD" "$APP_USER" "$APP_PASSWORD" > /opt/pixagent/access.env
    chown ubuntu:ubuntu /opt/pixagent/access.env
fi
hash=$(docker exec -e ENTRY_PASSWORD pixagent-app-1 python -c 'import bcrypt,os; print(bcrypt.hashpw(os.environ["ENTRY_PASSWORD"].encode(), bcrypt.gensalt()).decode())')
sed "s|ENTRY_HASH|$hash|" deploy/pixagent.caddy.template > /etc/caddy/pixagent.caddy
chown root:caddy /etc/caddy/pixagent.caddy
chmod 640 /etc/caddy/pixagent.caddy
cp /etc/caddy/Caddyfile "$backup/candidate"
printf '\nimport /etc/caddy/pixagent.caddy\n' >> "$backup/candidate"
caddy validate --config "$backup/candidate" --adapter caddyfile
docker exec -i -e APP_USER -e APP_PASSWORD pixagent-app-1 python < deploy/create_owner.py
awk '!/^(APP_ENV|REGISTRATION_ENABLED|S3_PUBLIC_ENDPOINT)=/' .env.vps > .env.vps.https
printf '%s\n' 'APP_ENV=production' 'REGISTRATION_ENABLED=false' \
    'S3_PUBLIC_ENDPOINT=https://pixagent-s3.softk.ccwu.cc' >> .env.vps.https
chmod 600 .env.vps.https
chown ubuntu:ubuntu .env.vps.https
mv .env.vps.https .env.vps
docker compose --env-file .env.vps -f compose.vps.yml up -d --no-deps app worker
test "$(sha256sum /etc/caddy/Caddyfile | cut -d ' ' -f 1)" = "$original"
install -m 644 -o root -g root "$backup/candidate" /etc/caddy/Caddyfile
systemctl reload caddy
printf 'Backup: %s\nCredentials: /opt/pixagent/access.env (0600)\n' "$backup"
