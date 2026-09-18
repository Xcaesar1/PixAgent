# Continuous Integration

The workflow in `workflows/ci.yml` runs on pushes, pull requests, and manual
dispatch from the repository's Actions tab. It checks code only; it does not
deploy, publish packages, or call a paid image provider. No repository secrets
are required.

## Checks

| Job | Runtime | Checks |
| --- | --- | --- |
| Backend | Python 3.13, uv | Frozen dependency install including optional extras, critical Ruff errors, Alembic migrations, full pytest suite including offline evaluation tests |
| Frontend | Node.js 22, npm | Lockfile install, Oxlint, TypeScript checks, Vite production build |

Backend tests start PostgreSQL, Redis, and MinIO using the existing
`docker-compose.yml`, with the separate Compose project name `pixagent-ci` on a
disposable GitHub-hosted runner. No API server or worker is started. The workflow
explicitly selects Mock generation, corner matting, and disabled OCR; cloud keys
and GPT credentials are empty. The checked-in service passwords are local test
values, not production credentials.

## Results and troubleshooting

1. Open **Actions > CI** and select a run.
2. Check the failing step in **Backend checks** or **Frontend checks**.
3. Download `backend-test-report` for the pytest JUnit XML, retained for seven
   days. If installation or migration fails before pytest, no report is created.
4. For service startup failures, inspect the service log step. For dependency
   failures, update the relevant lockfile locally and include it in the change;
   do not remove frozen installs to bypass an inconsistent lockfile.

Ruff currently gates fatal errors (`E9,F63,F7,F82`), matching the reference
project's critical-error check. It does not claim full style compliance. Frontend
lint warnings and Vite size warnings remain visible but are not promoted to
errors. The offline tests do not verify live provider credentials, image quality,
browser interactions, or a production deployment.

## Reference mapping

- JourneyGo's Python job is adapted to PixAgent's Python 3.13 and `uv.lock`, not
  copied as a Python 3.10 / pip setup.
- PixAgent requires MinIO in addition to PostgreSQL and Redis for its tests.
- Offline regression checks live in `backend/tests/test_eval.py` and run as part
  of pytest; JourneyGo's planner evaluation script is not applicable here.
- Existing Dockerfiles, Compose files, environment examples, and deployment
  commands remain the startup interface. No duplicate `start.sh` or root Python
  project is introduced.

Do not run the backend tests against production services: fixtures create and
remove test users and write test assets. Use disposable services for local
reproduction as well.
