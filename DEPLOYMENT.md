# PixAgent VPS Runbook

## Scope

- Host: SSH alias `oracle-cpamp`, ARM64 Ubuntu.
- Source: `/opt/pixagent/source`, initial commit `3626def` plus uncommitted deployment changes.
- Compose project/network prefix: `pixagent`.
- Secrets: `/opt/pixagent/source/.env.vps`, mode `0600`; parent `/opt/pixagent` mode `0700`.
- Never print Compose rendered environment, copy another project's credentials, or commit secrets.
- User authorized the two PixAgent HTTPS hostnames and private entry protection on 2026-09-17.
- Preserve other sites and firewall rules. Caddy now imports `/etc/caddy/pixagent.caddy`.

## Access

Open `https://pixagent.softk.ccwu.cc/auth`; an SSH tunnel is no longer required.
First enter the HTTP Basic entry credentials, then sign in to the application.
Credentials are stored only in `/opt/pixagent/access.env` (owner ubuntu, mode 0600):
`ENTRY_USER` / `ENTRY_PASSWORD` protect the entry; `APP_USER` / `APP_PASSWORD` are the
separate owner account (`pixagent_owner`). Do not post these values into chat or Git.

`APP_ENV=production`, `REGISTRATION_ENABLED=false`. Session cookies use Secure,
HttpOnly and SameSite=Lax. Account invitations require explicit operator provisioning.
S3 public endpoint is `https://pixagent-s3.softk.ccwu.cc`; only GET/HEAD of application
object paths and CORS preflight are proxied. MinIO still requires a valid expiring S3
signature. The console, bucket listings and public writes are not exposed.
Editing provider remains mock; no paid call was authorized by the HTTPS change.
See Generation Modes below for the separately authorized generation-only integration.

## Generation Modes

- The generation form queries authenticated `/api/generation-modes`, displays configured
  providers, and remembers the last available selection in browser localStorage.
- Domestic mode uses the existing DashScope adapter and is now enabled with the
  user-authorized key in `.env.vps` (0600). GPT remains the default generation mode.
  The generation form and API default to one image; larger batches require explicit selection.
  A single separately authorized DashScope 3.0 Pro test produced a 1024x1024 PNG.
  The user confirmed a free quota and approximately CNY 0.30/image afterward; inspect
  the provider console for current remaining quota and actual billing, not this document.
  Enabling the mode itself performs no inference and no recharge.
- GPT mode uses the l0veyou account session and the observed webpage API, not the paid
  batch API. A zero-balance server probe succeeded; future free availability is not guaranteed.
- GPT exposes three selectable site models: GPT Image 2 (`l0veyou`), GPT Image 2.5
  极速版 (`l0veyou-gpt-image-2-5-flare`), and GPT Image 2.5 满血版
  (`l0veyou-gpt-image-2-5-full`). Each mode maps to a fixed upstream `model` value
  server-side; the browser only submits the mode ID. GPT supports 1, 2 or 4 originals
  per application task using sequential single-image upstream requests, with per-image
  submission and asset checkpoints. Worker timeout is 1200 seconds to allow the
  four-image path. Ratios: 1:1, 3:4, 9:16, 16:9. Reference images and seeds are
  rejected. Negative prompts are appended as instructions.
- Original images are downloaded only from the trusted HTTPS hosts listed in
  `backend/app/providers/l0veyou.py` (`IMAGE_HOSTS`). On 2026-09-20 the site moved its
  CDN to `cdn.ng-resource.com`; the previous single-host constant rejected every valid
  original, so the current host is now the primary entry and the legacy CloudFront host
  is retained for the GPT Image 2 path. Re-verify this list if downloads start failing.
- Configure credentials only at `/opt/pixagent/secrets/l0veyou/session.token`, mode 0600,
  parent directory 0700. The optional `compose.gpt.yml` mounts that directory read-only.
  Never put the session credential into Git, an image, browser responses, or logs.
- `GENERATION_PROVIDER=l0veyou` affects generation only. `IMAGE_PROVIDER` still controls
  editing tools. Individual generation tasks persist the explicitly selected provider.
- Use both compose files for all deployed app/worker recreations:
  `docker compose --env-file .env.vps -f compose.vps.yml -f compose.gpt.yml up -d --no-deps app worker`.
- Session expiry returns an actionable error; no silent fallback or paid API switching.
  Update the credential file after authorized login renewal. No automatic refresh is implemented.
- Upstream task IDs are checkpointed before polling. Interrupted submissions without a
  confirmed ID fail rather than resubmit. Completed originals are stored in private MinIO.
- Regression tests use dedicated DB `pixagent_modes_test_20260917` and Redis DB 1.
  Do not run the suite on the production DB or reopen registration to test.
- Acceptance: 176 tests passed; browser switching, stored selection, GPT payload and
  desktop/mobile rendering passed. Live GPT worker replay downloaded and stored the
  prior 1024x1024 original without new upstream submissions. HTTPS/auth/mock SSE passed.
  All five deployed services are healthy. No domestic paid inference was performed.
- Backup: `/opt/pixagent/backups/modes-20260917T055303Z`; previous image retained as
  `pixagent:before-generation-modes`. No production schema migration was needed.

### GPT Image 2.5 Modes And Credential Renewal (2026-09-20)

- The session credential was renewed from the authenticated site login. The previous
  file is retained beside it as `/opt/pixagent/secrets/l0veyou/session.token.<UTC>.bak`
  (mode 0600, parent 0700). Replacement is atomic: write `<dir>/.session.token.new`,
  `chmod 600`, then `mv`. The token value must never be printed or copied into Git.
- Both new variants were confirmed live with the same prompt at `1:1`: each returned
  exactly one 1024x1024 PNG original, downloaded from the trusted host under the 20 MB
  cap with no resubmission. Artifacts and a sanitized summary stay outside the
  repository. Rendering matched the intended subject with no text, logo or watermark
  (the application's own OCR engine found zero text boxes in both originals).
- Mode IDs stay server-mapped: the browser only ever submits `l0veyou`,
  `l0veyou-gpt-image-2-5-flare` or `l0veyou-gpt-image-2-5-full`.
- Acceptance: 73 generation-mode tests passed (1 warning) and the full isolated suite
  reported 234 passed (1 warning) against disposable PostgreSQL, Redis and MinIO; ruff,
  frontend lint and the production frontend build were all clean.

## Operations

```sh
cd /opt/pixagent/source
docker compose --env-file .env.vps -f compose.vps.yml -f compose.gpt.yml ps
docker compose --env-file .env.vps -f compose.vps.yml -f compose.gpt.yml config --quiet
docker compose --env-file .env.vps -f compose.vps.yml -f compose.gpt.yml build
docker compose --env-file .env.vps -f compose.vps.yml -f compose.gpt.yml run --rm app alembic upgrade head
docker compose --env-file .env.vps -f compose.vps.yml -f compose.gpt.yml up -d
```

Stop/rollback this initial deployment without deleting data:

```sh
cd /opt/pixagent/source
docker compose --env-file .env.vps -f compose.vps.yml stop
```

Resume using `up -d`. Do not use `down -v`, Docker prune, or remove volumes.
Before any subsequent schema upgrade, take a restricted PostgreSQL dump and consistent
MinIO backup, record the running image ID, and retain that image for rollback.

## Isolation And Budget

- Only app `127.0.0.1:17302` and S3 `127.0.0.1:17313` have host bindings.
- PostgreSQL, Redis and MinIO console have no host bindings.
- Separate PostgreSQL, Redis, MinIO, model and cache volumes; no JourneyOps mounts.
- Aggregate configured CPU cap: 2 cores; memory caps: 8 GiB (API 4, worker 2.75, dependencies 1.25). These are limits, not measured usage.
- SAM runs in the API process and exceeded a 3.25 GiB cap in testing; do not reduce the API cap without profiling.
- Worker concurrency: 1; ONNX/BLAS thread count: 1.
- Upload file limit: 20 MiB; image pixel limit: 50 million, checked before full decoding.
- U2NET_HOME points to the shared persistent model volume.
- Matting explicitly selects `u2netp`; default rembg `bria-rmbg` exceeded the 4 GiB worker cap.
- Disable ONNX CPU arenas for matting and SAM; constrain RapidOCR threads to prevent cumulative model memory exhaustion.
- Redis relies on isolated Docker networking; it is not publicly exposed.
- Images are private S3 objects with expiring signed URLs, not a public bucket.

## Verification

```sh
cd /opt/pixagent/source
docker run --rm --network pixagent_default --env-file .env.vps --cpus 0.75 --memory 2g -v /opt/pixagent/source/deploy:/checks:ro pixagent:local python /checks/test_generation_modes.py
docker run --rm --network host --env-file .env.vps --env-file /opt/pixagent/access.env --cpus 0.25 --memory 256m -v /opt/pixagent/source/deploy:/checks:ro pixagent:local python /checks/check_https.py
docker exec -i pixagent-app-1 python < backend/scripts/vps_cv_smoke.py
docker exec -i -e CV_ROLE=worker pixagent-worker-1 python < backend/scripts/vps_cv_smoke.py
```

Run the suite only on the private trial database or a dedicated test database: fixtures
delete users prefixed `test_`; never assign that prefix to a real user. Tests force mock,
corner matting and no OCR; the separate CV script uses strict real local models.
The live smoke script creates a random `smoke_` account and retained synthetic assets.
`vps_smoke.py` is historical loopback-trial acceptance and is not compatible with closed
registration/Secure cookies. Use `deploy/check_https.py` for the deployed HTTPS service.
The full pytest suite assumes registration enabled and APP_ENV=tunnel; run it only in
an isolated test environment, never by enabling registration on the public app.

Evidence on host: `/opt/pixagent/build.log`, `tests.log`, `cv-tests.log`,
`baseline.txt`, `after.txt`. Logs may contain synthetic test data; do not publish them blindly.

2026-09-17 acceptance: ARM image/frontend build, database migrations, 161-test suite,
live auth/upload/private signed images/mock worker/SSE, browser candidate rendering,
horizontal flip and edit-page reload persistence passed. Strict local U2NetP, quantized
SAM and RapidOCR passed sequentially in the worker after memory tuning. OCR returned
`PIXAGENT TEST 123`. No cloud-model inference was performed. Existing service container
IDs, images and restart counts initially matched the pre-deployment baseline. A later
check observed an independent JourneyOps staging app/worker image replacement; this
task did not operate those services. Production, demo, mail and proxy baseline remained
unchanged. Recheck current health rather than assuming staging's original image persists.

The final 4 GiB API container also passed sequential U2NetP/SAM/OCR checks without OOM.
SAM is only used by the API selection endpoints. Worker-role acceptance excludes SAM
and checks matting plus OCR under its separate 2.75 GiB limit.
Running application image: `sha256:b62807efbcd7205cfef4232e6990062f9e3ec800f603777767ad1cb8c3351c42`.
Concurrent multi-user load and large-image peak-memory behavior remain unverified.

## Public Launch Gate

HTTPS and entry protection were completed on 2026-09-17. Verified public TLS, redirects,
missing/wrong entry credentials (401), owner login, Secure cookie, registration denied
(403), upload, signed HTTPS images/CORS, unsigned image denial, console/write denial,
mock async task and SSE (5 frames). Both certificates were issued successfully.
Caddy's existing site blocks were preserved; only one import line was added.
Configuration backup: `/opt/pixagent/backups/https-20260917T034646Z` (root-only).

To withdraw just the public entry: remove only `import /etc/caddy/pixagent.caddy` from
the current `/etc/caddy/Caddyfile`, validate it, then `sudo systemctl reload caddy`.
Do not restore an old whole Caddyfile over possible later changes to other sites.
To also restore the former PixAgent environment, copy `env.vps` from the restricted
backup to `/opt/pixagent/source/.env.vps`, retain mode 0600, and recreate only app/worker.
Do not reopen registration on a publicly reachable app. No data or account deletion is
required to withdraw the entry.

Remaining cloud-provider steps and reference launch checklist:

1. Obtain explicit approval for the exact domain, DNS and additive Caddy configuration.
2. Back up shared Caddy configuration before changes. Do not replace existing sites.
3. Configure HTTPS, private entry protection, request-body limit and SSE without buffering.
4. Set `APP_ENV=production`, `REGISTRATION_ENABLED=false` after creating invited accounts.
5. Set `S3_PUBLIC_ENDPOINT` to the actual reachable HTTPS S3 hostname; preserve Host for signing.
6. Keep MinIO console, DB and Redis private. Test images in the browser after endpoint changes.
7. Enter `DASHSCOPE_API_KEY` directly using an SSH editor in `.env.vps`, never in chat.
8. Set `IMAGE_PROVIDER=dashscope` only after authorization for paid calls; recreate app/worker.
9. Perform a separately authorized real cloud generation/edit test. Mock success is not cloud acceptance.
10. Add login/request throttling and review provider budgets before broadening access beyond trusted users.

Do not push deployment code without user approval.
