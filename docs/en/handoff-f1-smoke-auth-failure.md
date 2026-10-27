# Handoff: OAI RFsim Dashboard/F1 Smoke Test Failure

> **Resolution (2026-07-03):** the central blocker described here — AMF/AUSF
> `CONTEXT_NOT_FOUND` authentication failure for IMSI `001010000000001` — was
> **resolved** by the subscriber-seed fix in PR #17 (numeric and `imsi-`-prefixed
> auth aliases). Validate the seed with `python3 scripts/validate_cn_subscriber.py`;
> see "F1 smoke-test subscriber diagnostics" in `dashboard/README.md`. The passive
> CU telnet polling stability note remains relevant and is addressed by keeping
> telnet polling disabled by default. This document is retained as historical
> context.

Date: 2026-07-01
Repository: `fsnobre/oai-rfsim-handover-testbed`
Current branch when last tested: `main`
Current main at last known state: `75b025c Fix dashboard frontend React plugin config (#16)`
Relevant topology: `f1` / RFsim / CU-DU split
Main symptom: F1 smoke test reaches UE data-plane readiness stage, but `oaitun_ue1` is never created inside `oai-nr-ue`, so the test times out.

---

## 1. Executive summary

The dashboard itself now renders and can launch actions, after fixing the missing Vite React plugin config in PR #16. The dashboard-triggered F1 smoke then exposed several deployment/runtime issues, some fixed locally and some still pending as permanent repo changes.

The current functional blocker is not the React dashboard and not basic RFsim radio synchronization. The current blocker is that the UE reaches radio/RRC setup, the AMF receives the Registration Request for IMSI `001010000000001`, but AMF/AUSF authentication fails with:

```text
Got UE Authentication from AUSF: {"cause":"CONTEXT_NOT_FOUND"}
Request Authentication Vectors failure
Create Registration Reject and send to UE
```

Because registration/authentication fails, the UE never completes NAS/PDU session setup, and `oaitun_ue1` is never created. The smoke test then times out at:

```text
[ue-data] target 192.168.71.135 via oaitun_ue1: not reachable after 180s
```

There is also a separate dashboard stability bug: passive CU telnet polling sends repeated `help` commands to the OAI CU telnet server, which previously caused the CU to crash with:

```text
*** buffer overflow detected ***: terminated
```

That telnet polling issue should still be fixed independently, because it can destabilize OAI CU during dashboard use.

---

## 2. Known resolved issues

### 2.1 Blank dashboard / blue screen after PR #15

Symptom:

- Browser showed only the dark/blue background.
- Earlier console error was:

```text
ReferenceError: React is not defined
```

Diagnosis:

- `dashboard/frontend/vite.config.js` was missing from `main`.
- `@vitejs/plugin-react` existed in `package.json`, but Vite was not configured to use it.

Fix:

- PR #16 added:

```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
});
```

Status:

- PR #16 was squash-merged.
- Latest known `main`: `75b025c Fix dashboard frontend React plugin config (#16)`.
- Dashboard now renders.

Recommended clean rebuild after this fix:

```bash
cd ~/Documents/repos/oai-rfsim-handover-testbed
git checkout main
git pull

docker compose -f dashboard/docker-compose.dashboard.yml down
docker compose -f dashboard/docker-compose.dashboard.yml build --no-cache dashboard-frontend

DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

---

### 2.2 Dashboard actions disabled

Symptom:

```text
Actions are disabled. Set DASHBOARD_ENABLE_ACTIONS=true to enable controlled experiment actions.
```

Diagnosis:

- `DASHBOARD_ENABLE_ACTIONS` is read by the backend at startup.
- Setting it after the backend is already running does not change the running backend.

Fix/use:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

or recreate only the backend:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up -d --force-recreate dashboard-backend
```

Status:

- Works when backend is started with the variable already set.

---

### 2.3 `/dev/net/tun` visible on host but not inside dashboard backend

Symptom from dashboard-triggered F1 smoke:

```text
[FAIL] /dev/net/tun missing — sudo modprobe tun
```

Host verification showed TUN exists:

```bash
sudo modprobe tun
lsmod | grep '^tun'
ls -l /dev/net/tun
```

Output:

```text
crw-rw-rw- 1 root root 10, 200 ... /dev/net/tun
```

Diagnosis:

- The dashboard backend container runs the smoke through Docker socket access.
- `network_mode: host` does not automatically expose `/dev/net/tun` inside the dashboard backend container.
- The preflight script checks `[[ -c /dev/net/tun ]]` from the context where it runs, which for dashboard-triggered actions is the backend container.

Local workaround that worked:

```yaml
# dashboard/docker-compose.dashboard.local.yml
services:
  dashboard-backend:
    devices:
      - /dev/net/tun:/dev/net/tun
```

Start with both compose files:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose \
  -f dashboard/docker-compose.dashboard.yml \
  -f dashboard/docker-compose.dashboard.local.yml \
  up --build
```

Verification:

```bash
docker exec oai-dashboard-backend sh -lc 'ls -l /dev/net/tun; test -c /dev/net/tun && echo TUN_VISIBLE'
```

Status:

- Local override fixed the preflight failure.
- Permanent PR still recommended: mount `/dev/net/tun` into `dashboard-backend`.

---

### 2.4 Docker-outside-of-Docker bind mount path mismatch

Symptom after TUN fix:

```text
Error response from daemon: failed to create task for container:
error mounting "/repo/oai-cn5g/conf/config.yaml" to rootfs at "/openair-nrf/etc/config.yaml":
mount src=/repo/oai-cn5g/conf/config.yaml ... not a directory
```

Diagnosis:

- The dashboard backend container sees the repo at `/repo`.
- It controls the host Docker daemon through `/var/run/docker.sock`.
- Docker bind mounts are interpreted by the host daemon, not by the backend container filesystem.
- The host does not have the repo at `/repo`; real path is:

```text
/home/nobre/Documents/repos/oai-rfsim-handover-testbed
```

Local workaround that worked:

```bash
cd ~/Documents/repos/oai-rfsim-handover-testbed
REPO="$(pwd)"

cat > dashboard/docker-compose.dashboard.local.yml <<EOF
services:
  dashboard-backend:
    environment:
      DASHBOARD_REPO_ROOT: ${REPO}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ${REPO}:${REPO}:ro
      - ${REPO}/results:${REPO}/results:rw
    devices:
      - /dev/net/tun:/dev/net/tun
EOF
```

Start with both compose files:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose \
  -f dashboard/docker-compose.dashboard.yml \
  -f dashboard/docker-compose.dashboard.local.yml \
  up --build
```

Verification:

```bash
docker exec oai-dashboard-backend sh -lc \
  'echo DASHBOARD_REPO_ROOT=$DASHBOARD_REPO_ROOT; ls -l "$DASHBOARD_REPO_ROOT/oai-cn5g/conf/config.yaml"; ls -l /dev/net/tun'
```

Status:

- Local override fixed the bind-mount failure.
- Permanent repo fix still recommended: dashboard backend should use the host repo path when it will drive the host Docker daemon.

---

## 3. Pending issue A: dashboard passive telnet polling can crash OAI CU

### Observed symptom

During dashboard use, CU logs showed repeated telnet `help` commands:

```text
[TELNETSRV] Command received: readc 5 filled 5 "help"
[TELNETSRV] Telnet Client disconnected.
...
*** buffer overflow detected ***: terminated
[INFO  tini (1)] Main child exited with signal (with signal 'Aborted')
```

AMF then showed:

```text
gNB Status: Disconnected
UE State: 5GMM-DEREGISTERED
```

### Diagnosis

The dashboard backend currently calls `telnet_poller.poll()` during every state build. `telnet_poller.poll()` sends `help` to the CU telnet server in order to discover supported commands. The dashboard default polling interval is 1 second, so this can result in approximately one `help` command per second while the dashboard is open.

That appears to destabilize the OAI CU telnet server and can cause the CU process to abort.

### Recommended fix

Create a dashboard hotfix:

- Add `DASHBOARD_ENABLE_TELNET_POLLING=false|true`.
- Default to `false`.
- When false, do not call `TelnetPoller.poll()` from `build_state()`.
- Return an explicit safe telnet state saying passive telnet polling is disabled.
- Keep explicit actions separate; smoke tests and handover triggers should still work when `DASHBOARD_ENABLE_ACTIONS=true`.
- If telnet polling is enabled for debugging, do not send `help` on every poll. Add caching/rate limiting, minimum interval at least 30 seconds, preferably 60 seconds or more.

---

## 4. Pending issue B: F1 smoke test times out because UE authentication fails

### Terminal smoke result

Command:

```bash
./scripts/run_smoke_test.sh
```

Result:

```text
[up] Waiting for UE registration and data plane (180s)
[ue-data] attempt 1: not ready (180s remaining)
...
[ue-data] attempt 60: not ready (0s remaining)
[ue-data] target 192.168.71.135 via oaitun_ue1: not reachable after 180s
```

### UE interface state

Inside `oai-nr-ue`:

```text
eth0: 192.168.70.181/26
eth1: 192.168.71.181/26
default via 192.168.70.129 dev eth0
Device "oaitun_ue1" does not exist.
```

Therefore the ping failure is expected: the smoke test waits for `oaitun_ue1`, but it never appears.

### UE logs

Relevant UE log lines:

```text
imsi = "001010000000001";
dnn= "oai";
nssai_sst=1;
will request PDU session ID 10, type 1, DNN oai, NSSAI 1.ffffff
Generate Initial NAS Message: Registration Request
Received NAS_DOWNLINK_DATA_IND type FGS_REGISTRATION_REJECT
Received Registration reject message too short
```

### AMF logs

Relevant AMF log lines:

```text
Received IMSI 001010000000001
A new UE (IMSI 001010000000001) has been successfully added!
5GMM-REGISTERED
Start to generate Authentication Vectors
Get Authentication Vectors from AUSF
Got UE Authentication from AUSF: {"cause":"CONTEXT_NOT_FOUND"}
Could not parse UE Authentication from Json
Request Authentication Vectors failure
Create Registration Reject and send to UE
```

Interpretation:

- The UE reaches AMF.
- AMF decodes the Registration Request and IMSI.
- AMF asks AUSF for authentication vectors.
- AUSF/UDM/UDR lookup returns `CONTEXT_NOT_FOUND`.
- AMF sends Registration Reject.
- UE never completes authentication.
- No PDU session is established.
- `oaitun_ue1` is never created.

This points to a subscriber database/init problem, not a basic RFsim/DU problem.

### DU/RFsim state

DU logs show radio/RRC side is alive:

```text
UE RNTI ... in-sync
average RSRP -43
BLER 0.00000
LCID 1: TX 18 RX 44 bytes
```

So the RFsim radio link is not the primary blocker.

### Suspicious supporting observation

`docker ps` showed:

```text
mysql Up ... (unhealthy)
```

Even though other core services were healthy. This should be investigated, because subscriber/authentication lookup depends on CN database contents and UDR/UDM/AUSF access.

---

## 5. zsh glob issue encountered

This command failed:

```bash
grep -RniE '...' conf-nr-ue.conf oai-cn5g/conf oai-cn5g/*.sql oai-cn5g/database
```

Error:

```text
zsh: no matches found: oai-cn5g/*.sql
```

This is a `zsh` unmatched glob behavior. Use `find` instead:

```bash
find conf-nr-ue.conf oai-cn5g -type f \
  \( -name '*.conf' -o -name '*.yaml' -o -name '*.yml' -o -name '*.sql' -o -name '*.json' \) \
  -print0 \
| xargs -0 grep -RniE 'imsi|key|opc|op |dnn|sst|sd|nssai|internet|00101|0000000001|000000001'
```

---

## 6. Next recommended manual checks

Run these from repo root after the failed smoke, while containers are still present.

### 6.1 Stop dashboard backend to isolate OAI smoke

```bash
docker stop oai-dashboard-backend
docker rm -f oai-amf oai-smf oai-upf oai-cu oai-du0 oai-du1 oai-nr-ue 2>/dev/null || true

cd ~/Documents/repos/oai-rfsim-handover-testbed
./scripts/run_smoke_test.sh
```

This ensures dashboard telnet polling is not influencing CU behavior.

### 6.2 Check MySQL databases

Try root password `linux` first, because that is common in OAI docker-compose deployments:

```bash
docker exec mysql sh -lc 'mysql -uroot -plinux -e "SHOW DATABASES;"'
```

If this fails, inspect compose/env for credentials:

```bash
docker inspect mysql --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -Ei 'MYSQL|MARIADB|DATABASE|USER|PASSWORD'
```

Then list DBs with the actual password.

### 6.3 Check tables

Assuming DB name is `oai_db`:

```bash
docker exec mysql sh -lc 'mysql -uroot -plinux oai_db -e "SHOW TABLES;"'
```

### 6.4 Search all tables for the UE IMSI/SUPI

```bash
docker exec mysql sh -lc '
mysql -uroot -plinux oai_db -N -e "SHOW TABLES" |
while read t; do
  echo "=== $t ==="
  mysql -uroot -plinux oai_db -e "SELECT * FROM \`$t\` LIMIT 5;" 2>/dev/null | grep -i "001010000000001\|imsi-001010000000001" || true
done
'
```

### 6.5 Check authentication/subscription tables

```bash
docker exec mysql sh -lc '
mysql -uroot -plinux oai_db -e "
SHOW TABLES LIKE \"%Authentication%\";
SHOW TABLES LIKE \"%authentication%\";
SHOW TABLES LIKE \"%Subscription%\";
SHOW TABLES LIKE \"%subscription%\";
"
'
```

### 6.6 Check SQL init file in repo

```bash
find oai-cn5g -type f -name '*.sql' -print
find oai-cn5g -type f -name '*.sql' -print0 \
| xargs -0 grep -RniE '001010000000001|imsi-001010000000001|AuthenticationSubscription|authentication|subscription|fec86ba6eb70|opc|key|dnn|sst|sd|oai'
```

### 6.7 If DB subscriber is missing, recreate CN DB volume

Only do this if this lab DB is disposable:

```bash
cd ~/Documents/repos/oai-rfsim-handover-testbed

docker rm -f oai-amf oai-smf oai-upf oai-cu oai-du0 oai-du1 oai-nr-ue 2>/dev/null || true

cd oai-cn5g
docker compose down -v
docker compose up -d mysql
docker logs -f mysql
```

Wait for MySQL initialization, then:

```bash
docker compose up -d
cd ..
./scripts/run_smoke_test.sh
```

Warning: `docker compose down -v` deletes the CN DB volume and any custom subscribers stored there.

---

## 7. Suggested permanent repo fixes

### 7.1 Dashboard backend deployment

Add `/dev/net/tun` to `dashboard-backend`:

```yaml
services:
  dashboard-backend:
    devices:
      - /dev/net/tun:/dev/net/tun
```

Also address host repo path vs `/repo` mismatch when backend uses host Docker socket:

- Either require a local override file for development deployment.
- Or change compose/docs so `DASHBOARD_REPO_ROOT` uses the host-visible repo path and the backend mounts the repo at the same absolute path.
- The key requirement: paths passed to Docker Compose actions must be paths valid on the host Docker daemon.

### 7.2 Dashboard passive telnet polling

Add safe telnet behavior:

- Default passive telnet polling disabled.
- Explicit action commands remain enabled when actions are enabled.
- Add environment flag and README documentation.
- If enabled, rate-limit and cache `help`/capability discovery.

### 7.3 Smoke diagnostics

Improve failure output when UE data-plane readiness fails:

When `wait_ue_data_ready.sh` times out, automatically print:

```bash
docker exec oai-nr-ue ip -4 addr
docker exec oai-nr-ue ip route
docker logs --tail=120 oai-nr-ue
docker logs --tail=160 oai-amf | grep -Ei 'authentication|context_not_found|registration|reject|imsi|ausf|udm|udr|supi|dnn|slice|nssai'
```

The current failure mode would have been much faster to diagnose if the script had printed:

```text
oaitun_ue1 missing
AUSF returned CONTEXT_NOT_FOUND for imsi-001010000000001
```

### 7.4 Preflight DB/subscriber check

Consider adding an optional preflight check that verifies subscriber `001010000000001` exists in the database before running the smoke test.

---

## 8. Codex prompt for analysis/fix

Use the prompt below with Codex.

```text
You are working in repository fsnobre/oai-rfsim-handover-testbed.

We need you to analyze and propose/fix the current F1 RFsim smoke-test failure and also account for two dashboard deployment/runtime issues discovered during testing.

Current repo main:
- main includes PR #16: Fix dashboard frontend React plugin config.
- Dashboard renders now.
- F1 smoke can be launched, but does not complete.

Relevant local deployment context:
- Repo path on host:
  /home/nobre/Documents/repos/oai-rfsim-handover-testbed
- Dashboard is normally run with:
  DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up --build
- Local compose override was needed to make dashboard-triggered Docker actions work:
  services:
    dashboard-backend:
      environment:
        DASHBOARD_REPO_ROOT: /home/nobre/Documents/repos/oai-rfsim-handover-testbed
      volumes:
        - /var/run/docker.sock:/var/run/docker.sock:ro
        - /home/nobre/Documents/repos/oai-rfsim-handover-testbed:/home/nobre/Documents/repos/oai-rfsim-handover-testbed:ro
        - /home/nobre/Documents/repos/oai-rfsim-handover-testbed/results:/home/nobre/Documents/repos/oai-rfsim-handover-testbed/results:rw
      devices:
        - /dev/net/tun:/dev/net/tun

Issue 1 already diagnosed:
- Host has /dev/net/tun, but dashboard-backend did not see it.
- network_mode: host does not expose /dev devices.
- Add /dev/net/tun device mount to dashboard-backend or document required local override.

Issue 2 already diagnosed:
- Dashboard backend controls host Docker daemon via /var/run/docker.sock.
- If backend sees repo at /repo, Docker Compose bind mounts are sent to the host daemon as /repo/...
- Host does not have repo at /repo, causing bind mount failure:
  error mounting "/repo/oai-cn5g/conf/config.yaml" ... not a directory
- Need a robust documented solution or compose support so action paths are host-visible paths.

Issue 3 already diagnosed:
- Passive dashboard telnet polling may destabilize OAI CU.
- CU logs showed repeated:
  Command received: readc 5 filled 5 "help"
- Then CU crashed:
  *** buffer overflow detected ***: terminated
- Root cause appears to be dashboard/backend/collectors/telnet_poller.py sending "help" on every poll, while dashboard/backend/main.py calls telnet_poller.poll() during each state build. Default DASHBOARD_POLL_INTERVAL_SECONDS is 1 second.
- Required fix:
  - Add DASHBOARD_ENABLE_TELNET_POLLING=false|true, default false.
  - When false, build_state() must not call telnet_poller.poll().
  - Return an explicit telnet state saying passive polling is disabled.
  - Keep explicit actions (smoke run, handover trigger) separate.
  - If enabled, rate-limit and cache capability discovery; do not send help every second.

Current main smoke failure from terminal:
Command:
  ./scripts/run_smoke_test.sh

Failure:
  [up] Waiting for UE registration and data plane (180s)
  ...
  [ue-data] target 192.168.71.135 via oaitun_ue1: not reachable after 180s

Inside oai-nr-ue:
  eth0 192.168.70.181/26
  eth1 192.168.71.181/26
  default via 192.168.70.129 dev eth0
  Device "oaitun_ue1" does not exist.

UE logs:
  imsi = "001010000000001";
  dnn= "oai";
  nssai_sst=1;
  will request PDU session ID 10, type 1, DNN oai, NSSAI 1.ffffff
  Generate Initial NAS Message: Registration Request
  Received NAS_DOWNLINK_DATA_IND type FGS_REGISTRATION_REJECT
  Received Registration reject message too short

AMF logs:
  Received IMSI 001010000000001
  A new UE (IMSI 001010000000001) has been successfully added!
  Start to generate Authentication Vectors
  Get Authentication Vectors from AUSF
  Got UE Authentication from AUSF: {"cause":"CONTEXT_NOT_FOUND"}
  Could not parse UE Authentication from Json
  Request Authentication Vectors failure
  Create Registration Reject and send to UE

DU logs:
  UE RNTI ... in-sync
  average RSRP -43
  BLER 0.00000
  LCID 1: TX 18 RX 44 bytes

Interpretation:
- RFsim/DU radio is working.
- UE reaches AMF.
- AMF asks AUSF/UDM/UDR for auth vectors.
- AUSF returns CONTEXT_NOT_FOUND for the subscriber/SUPI.
- AMF sends Registration Reject.
- UE never authenticates; PDU session is not established; oaitun_ue1 is never created.
- This is likely a CN DB/subscriber initialization or subscriber mismatch problem.
- docker ps also showed mysql as unhealthy.

Tasks:
1. Inspect repo configs:
   - conf-nr-ue.conf
   - gnb-docker-compose.yaml
   - oai-cn5g/docker-compose.yaml
   - oai-cn5g/database/oai_db.sql
   - oai-cn5g/conf/*.yaml
   - any DB init/health scripts
2. Confirm that subscriber IMSI/SUPI 001010000000001 / imsi-001010000000001 is present in oai_db.sql with matching authentication credentials, DNN, slice/NSSAI.
3. Confirm that the MySQL container is initialized from the expected SQL file.
4. Determine why AUSF returns CONTEXT_NOT_FOUND:
   - missing subscriber in DB?
   - wrong DB name?
   - SQL init not run because existing stale volume?
   - MySQL unhealthy or UDR cannot access data?
   - SUPI format mismatch: 001010000000001 vs imsi-001010000000001?
   - DNN/slice mismatch?
5. Propose and implement repo fixes where appropriate:
   - If DB init SQL is wrong/missing subscriber, patch it.
   - If smoke scripts should recreate/validate DB for lab use, add a safe documented command or preflight check.
   - Add a diagnostic to wait_ue_data_ready.sh or smoke failure path that detects missing oaitun_ue1 and prints focused UE/AMF/AUSF/UDM/UDR/MySQL hints.
   - Add preflight or validation for expected subscriber presence if feasible.
6. Separately implement dashboard safe telnet polling:
   - DASHBOARD_ENABLE_TELNET_POLLING default false.
   - no passive telnet commands unless enabled.
   - rate limit/caching if enabled.
7. Separately implement or document dashboard backend runtime requirements:
   - /dev/net/tun mount
   - host-visible repo path when using host Docker socket
   - local override example.

Validation commands:
  python3 -m compileall dashboard/backend
  PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_registry.py
  PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase2.py
  PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase3.py
  PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
  PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase5.py
  docker compose -f dashboard/docker-compose.dashboard.yml config
  cd dashboard/frontend && npm install && npm run build
  cd ../..
  git diff --check

Manual diagnostics to include in final answer:
  docker exec mysql sh -lc 'mysql -uroot -p<password> -e "SHOW DATABASES;"'
  docker exec mysql sh -lc 'mysql -uroot -p<password> oai_db -e "SHOW TABLES;"'
  docker exec mysql sh -lc 'mysql -uroot -p<password> oai_db -N -e "SHOW TABLES" | while read t; do echo === $t ===; mysql -uroot -p<password> oai_db -e "SELECT * FROM \`$t\` LIMIT 5;" 2>/dev/null | grep -i "001010000000001\|imsi-001010000000001" || true; done'

Manual smoke after fixes:
  docker stop oai-dashboard-backend || true
  docker rm -f oai-amf oai-smf oai-upf oai-cu oai-du0 oai-du1 oai-nr-ue 2>/dev/null || true
  ./scripts/run_smoke_test.sh

Success criteria:
- UE registration succeeds.
- oaitun_ue1 appears inside oai-nr-ue.
- wait_ue_data_ready.sh passes.
- F1 smoke advances past UE data-plane readiness.
- Dashboard no longer sends repeated "help" commands to CU by default.
- Dashboard-triggered smoke no longer fails due to missing /dev/net/tun or /repo bind-mount path mismatch.
```

---

## 9. Current recommended priority order

1. Fix/disable dashboard passive CU telnet polling. This prevents dashboard from destabilizing OAI while debugging.
2. Verify MySQL subscriber state and why AUSF returns `CONTEXT_NOT_FOUND`.
3. If DB is stale, recreate CN DB volume and retest.
4. If DB init SQL is wrong, patch repo.
5. Add better smoke diagnostics for missing `oaitun_ue1`.
6. Make dashboard backend deployment robust for `/dev/net/tun` and host-visible repo paths.


---

## 10. Follow-up fixes applied on `codex/f1-smoke-dashboard-runtime-fixes`

Date applied: 2026-07-01
Branch: `codex/f1-smoke-dashboard-runtime-fixes`

This section records the concrete repository changes made after the investigation above, why each change was made, and how it was validated.

### 10.1 Disabled passive dashboard CU telnet polling by default

Files changed:

- `dashboard/backend/config.py`
- `dashboard/backend/main.py`
- `dashboard/backend/collectors/telnet_poller.py`
- `dashboard/docker-compose.dashboard.yml`
- `dashboard/README.md`

What changed:

- Added `DASHBOARD_ENABLE_TELNET_POLLING`, defaulting to `false`.
- `build_state()` and `/api/ues` now use a `current_telnet_state()` helper.
- When telnet polling is disabled, the backend does not call `telnet_poller.poll()` and returns an explicit telnet state:

```text
Passive CU telnet polling is disabled; set DASHBOARD_ENABLE_TELNET_POLLING=true to enable it.
```

- If telnet polling is intentionally enabled, `TelnetPoller` now:
  - caches the last poll result for 5 seconds;
  - caches telnet command/capability discovery for 300 seconds;
  - avoids sending `help` every 1-second dashboard state refresh.

Reason:

- CU logs showed repeated dashboard-origin telnet commands:

```text
Command received: readc 5 filled 5 "help"
```

- The CU later crashed with:

```text
*** buffer overflow detected ***: terminated
```

- Passive observability must not destabilize the OAI CU. Explicit smoke-test and handover actions remain separate from passive telnet polling.

Validation:

- Backend compile passed:

```bash
python3 -m compileall dashboard/backend
```

- Dashboard endpoint smoke with actions enabled and default telnet setting confirmed telnet polling was disabled:

```text
/api/topology ok
telnet_enabled= False
telnet_summary= Passive CU telnet polling is disabled; set DASHBOARD_ENABLE_TELNET_POLLING=true to enable it.
```

- Full dashboard validations passed:

```bash
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_registry.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase2.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase3.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase5.py
```

### 10.2 Added `/dev/net/tun` mount to dashboard backend

Files changed:

- `dashboard/docker-compose.dashboard.yml`
- `dashboard/docker-compose.dashboard.host-actions.example.yml`
- `dashboard/backend/actions.py`
- `dashboard/backend/validate_phase4.py`
- `dashboard/README.md`

What changed:

- Added this device mount to `dashboard-backend` in the base dashboard compose file:

```yaml
devices:
  - /dev/net/tun:/dev/net/tun
```

- Added `tun_device` to action runtime checks exposed by `/api/actions/capabilities`.
- Updated Phase 4 validation to include the new runtime-check key.

Reason:

- `network_mode: host` does not expose host device nodes inside the dashboard backend container.
- Dashboard-triggered smoke tests run preflight inside `dashboard-backend`, so the script must see `/dev/net/tun` there.
- Without the device mount, preflight fails even when the host itself has TUN available.

Validation:

- Compose config showed the device mount in the rendered service:

```text
devices:
  - source: /dev/net/tun
    target: /dev/net/tun
    permissions: rwm
```

- Dashboard runtime smoke with actions enabled reported all runtime checks true, including `tun_device`:

```text
runtime_checks= {
  'bash': True,
  'docker': True,
  'docker_compose': True,
  'nc': True,
  'ip': True,
  'ss': True,
  'ping': True,
  'docker_socket': True,
  'tun_device': True,
  'results_writable': True,
  'trigger_script_exists': True,
  'smoke_script_exists': True,
  'repeated_smoke_script_exists': True
}
```

### 10.3 Added a host-visible dashboard action override

Files changed:

- `dashboard/docker-compose.dashboard.host-actions.example.yml`
- `dashboard/README.md`
- `dashboard/backend/actions.py`
- `dashboard/backend/validate_phase4.py`

What changed:

- Added a checked-in example override for action-enabled dashboard deployments:

```bash
DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build
```

- The override sets:

```yaml
DASHBOARD_REPO_ROOT: ${DASHBOARD_HOST_REPO_ROOT}
```

- It mounts the repository at the same absolute path inside the backend container as it has on the host.
- It keeps the repository read-only except for `results/`, which remains writable.
- Added `docker_socket` to action runtime checks.

Reason:

- The backend controls the host Docker daemon through `/var/run/docker.sock`.
- Docker Compose bind mounts are evaluated by the host daemon, not inside the backend container.
- If the backend runs actions from `/repo`, the host daemon tries to mount `/repo/...`, which does not exist on the host and fails with errors such as:

```text
error mounting "/repo/oai-cn5g/conf/config.yaml" ... not a directory
```

- The robust fix is to run dashboard actions with `DASHBOARD_REPO_ROOT` set to a host-visible absolute path.

Validation:

- Rendered the base dashboard compose successfully:

```bash
docker compose -f dashboard/docker-compose.dashboard.yml config
```

- Rendered the host-actions override successfully:

```bash
DASHBOARD_HOST_REPO_ROOT=/home/nobre/Documents/repos/oai-rfsim-handover-testbed \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml config
```

- Started the backend through the documented host-actions override with actions enabled and verified:

```text
/health ok
/api/actions/capabilities ok
actions_enabled= True
/api/topology ok
```

### 10.4 Added `imsi-` authentication aliases to the CN database seed

Files changed:

- `oai-cn5g/database/oai_db.sql`
- `scripts/validate_cn_subscriber.py`
- `scripts/preflight_check.sh`
- `oai-cn5g/healthscripts/mysql-healthcheck.sh`
- `dashboard/README.md`

What changed:

- Preserved the existing numeric IMSI authentication rows:

```text
001010000000001
001010000000002
001010000000003
001010000000004
```

- Added canonical SUPI-string authentication aliases:

```text
imsi-001010000000001
imsi-001010000000002
imsi-001010000000003
imsi-001010000000004
```

- Added `scripts/validate_cn_subscriber.py` to statically verify that the SQL seed contains:
  - numeric IMSI auth row for `001010000000001`;
  - `imsi-001010000000001` auth alias;
  - key `fec86ba6eb707ed08905757b1bb44b8f`;
  - OPC `C42449363BBAD02B66D16BC975D77CC1`;
  - DNN `oai`;
  - slice SST `1` / SD `FFFFFF`.

- Wired that validator into `scripts/preflight_check.sh`.
- Fixed `mysql-healthcheck.sh` so a missing RFsim auth seed leaves MySQL unhealthy instead of being reset back to healthy.

Reason:

- The UE config uses numeric IMSI `001010000000001`.
- The observed AMF/AUSF failure was:

```text
Got UE Authentication from AUSF: {"cause":"CONTEXT_NOT_FOUND"}
Request Authentication Vectors failure
Create Registration Reject and send to UE
```

- This is consistent with AUSF/UDM/UDR looking up authentication data by canonical SUPI string `imsi-001010000000001` while the DB only contained numeric rows.
- Once authentication fails, NAS registration is rejected, no PDU session is established, and `oaitun_ue1` never appears.

Validation:

- Static subscriber validation passed:

```bash
python3 scripts/validate_cn_subscriber.py
```

Output:

```text
[PASS] RFsim subscriber seed contains numeric and imsi-prefixed auth aliases, DNN oai, and SST 1 / SD FFFFFF
```

- Preflight during the manual smoke reported:

```text
[PASS] RFsim subscriber seed contains expected IMSI/SUPI, key/OPC, DNN, and slice
```

- Fresh F1 smoke created a new MySQL container from the patched SQL seed and MySQL became healthy:

```text
[ready] oai-amf: healthy
[ready] oai-smf: healthy
[ready] oai-upf: healthy
```

### 10.5 Added focused UE data-plane timeout diagnostics

Files changed:

- `scripts/wait_ue_data_ready.sh`
- `dashboard/README.md`

What changed:

- On timeout, `wait_ue_data_ready.sh` now checks whether `oaitun_ue1` exists inside `oai-nr-ue`.
- It prints focused recent log snippets from:
  - `oai-nr-ue`
  - `oai-amf`
  - `oai-ausf`
  - `oai-udm`
  - `oai-udr`
- It prints MySQL container state/health and queries `AuthenticationSubscription` for:
  - `001010000000001`
  - `imsi-001010000000001`
- It prints next-step hints for `CONTEXT_NOT_FOUND`, stale/unhealthy MySQL, and PDU-session/DNN/slice problems.

Reason:

- The original smoke failure only reported a ping timeout:

```text
[ue-data] target 192.168.71.135 via oaitun_ue1: not reachable after 180s
```

- That message hides the real distinction between:
  - radio/RRC failure;
  - NAS registration/authentication failure;
  - PDU-session setup failure;
  - data-plane routing failure.

- In this case the radio side was alive, but NAS authentication failed. The failure path should direct the operator to UE/AMF/AUSF/UDM/UDR/MySQL evidence immediately.

Validation:

- Shell syntax validation passed:

```bash
bash -n scripts/wait_ue_data_ready.sh scripts/preflight_check.sh oai-cn5g/healthscripts/mysql-healthcheck.sh
```

- The successful manual smoke did not trigger the timeout path, which is the expected result after the DB seed fix.
- The diagnostic command syntax was inspected and corrected before final validation.

### 10.6 Updated action runtime capability checks

Files changed:

- `dashboard/backend/actions.py`
- `dashboard/backend/validate_phase4.py`

What changed:

- `/api/actions/capabilities` now includes:

```text
docker_socket
tun_device
```

Reason:

- For dashboard-started actions, the backend must be able to talk to the host Docker daemon and must see `/dev/net/tun`.
- These are operational prerequisites, so the UI/API should expose them as runtime checks.

Validation:

- Phase 4 validation was updated and passed:

```bash
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
```

- Runtime endpoint smoke confirmed both checks were true:

```text
'docker_socket': True
'tun_device': True
```

### 10.7 Manual F1 smoke-test validation after fixes

Command run:

```bash
docker stop oai-dashboard-backend || true
docker rm -f oai-amf oai-smf oai-upf oai-cu oai-du0 oai-du1 oai-nr-ue 2>/dev/null || true
./scripts/run_smoke_test.sh
```

Important note:

- No core/RAN containers were present before the run except stopped dashboard containers, so MySQL was initialized fresh from the patched `oai_db.sql`.
- If a stale MySQL container already exists, it may need to be recreated to pick up SQL seed changes:

```bash
./scripts/down.sh f1 --volumes
```

Observed validation output:

```text
[PASS] RFsim subscriber seed contains expected IMSI/SUPI, key/OPC, DNN, and slice
[ready] oai-amf: healthy
[ready] oai-smf: healthy
[ready] oai-upf: healthy
[ue-data] target 192.168.71.135 via oaitun_ue1: reachable
[PASS] oaitun_ue1 present with IP: 10.0.0.2
[PASS] UE can reach 192.168.71.135 via oaitun_ue1
RRC F1 handover triggered for UE 1
```

Run artifact:

```text
results/runs/20260701_084915_f1_handover_smoke
```

Summary metrics from `summary.json`:

```text
status=pass
ue_data_ready=True
handover_triggered=True
estimated_interruption_ms=200.924
packet_loss_percent=0.0
rtt_avg_ms=12.121538461538462
ping_metrics_valid=True
```

Conclusion:

- UE registration succeeded.
- `oaitun_ue1` appeared inside `oai-nr-ue` with IP `10.0.0.2`.
- UE data-plane readiness passed.
- F1 smoke advanced past the previous failure and completed successfully.
- The F1 handover command was accepted.

### 10.8 Full validation command set run after fixes

Commands run successfully:

```bash
python3 -m compileall dashboard/backend
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_registry.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase2.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase3.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase5.py
python3 scripts/validate_cn_subscriber.py
docker compose -f dashboard/docker-compose.dashboard.yml config
DASHBOARD_HOST_REPO_ROOT=/home/nobre/Documents/repos/oai-rfsim-handover-testbed \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml config
cd dashboard/frontend && npm install && npm run build
git diff --check
```

Frontend build result:

```text
vite v6.4.3 building for production...
✓ built
```

Dashboard endpoint smoke with host-actions override:

```bash
DASHBOARD_HOST_REPO_ROOT=/home/nobre/Documents/repos/oai-rfsim-handover-testbed \
DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up -d --build dashboard-backend
```

Verified endpoints:

```text
/health ok
/api/actions/capabilities ok
actions_enabled= True
/api/topology ok
telnet_enabled= False
```

The action-enabled dashboard backend was stopped after this validation so it was not left exposed.

### 10.9 Updated status of previously pending items

Previously pending item | Current status
--- | ---
Disable/fix passive CU telnet polling | Implemented. Default is disabled; enabled mode is rate-limited and caches `help` discovery.
Verify/patch subscriber DB seed | Implemented. Added `imsi-` auth aliases and static validation.
Handle stale/unhealthy MySQL diagnostics | Improved. Healthcheck validates RFsim auth aliases; timeout path prints MySQL/subscriber diagnostics. Existing stale containers may still need an explicit reset.
Improve missing `oaitun_ue1` diagnostics | Implemented in `wait_ue_data_ready.sh`.
Make `/dev/net/tun` available to dashboard actions | Implemented in base dashboard compose.
Handle host Docker socket path mismatch | Documented and supported with `dashboard/docker-compose.dashboard.host-actions.example.yml`.
Validate F1 smoke end-to-end | Completed successfully with run `20260701_084915_f1_handover_smoke`.

### 10.10 Remaining operational notes

- If MySQL already exists from an older seed, editing `oai_db.sql` is not enough. Recreate the core DB container/volume for lab reset:

```bash
./scripts/down.sh f1 --volumes
```

- Keep passive telnet polling disabled unless actively needed:

```bash
DASHBOARD_ENABLE_TELNET_POLLING=false
```

- For dashboard-triggered actions, use the host-actions override so OAI compose bind mounts are host-visible:

```bash
DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build
```

- The successful manual smoke left the F1 OAI stack running at the time this section was written. Stop it when done with:

```bash
./scripts/down.sh f1
```
