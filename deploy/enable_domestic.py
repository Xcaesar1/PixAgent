"""Install the authorized key from stdin without displaying or invoking it."""
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

os.umask(0o077)
key = sys.stdin.read().strip()
if not re.fullmatch(r"sk-[A-Za-z0-9._-]+", key):
    raise SystemExit("Expected one API key; configuration unchanged")
source = Path("/opt/pixagent/source/.env.vps")
backup = Path("/opt/pixagent/secrets/config-backups")
backup.mkdir(parents=True, exist_ok=True, mode=0o700)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
shutil.copy2(source, backup / f"env-before-domestic-{stamp}")
lines = source.read_text().splitlines()
lines = [line for line in lines if not re.match(r"^\s*DASHSCOPE_API_KEY\s*=", line)]
lines.append("DASHSCOPE_API_KEY=" + key)
fd, temporary = tempfile.mkstemp(prefix=".env-domestic-", dir=source.parent)
with os.fdopen(fd, "w") as output:
    output.write("\n".join(lines) + "\n")
os.replace(temporary, source)
print("API key configured; environment mode 0600; backup retained; no inference requested")
