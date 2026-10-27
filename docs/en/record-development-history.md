## Development Session Notes — RFsim F1 Handover Baseline

> **Document type:** Historical record
>
> **Required reading:** None

### 1. Initial problem we started working on

The starting point was the need to turn a **manually executed OpenAirInterface RFsimulator F1 handover setup** into a **reproducible research testbed**.

You already had validated the OAI handover tutorial manually with:

```text
1 UE
2 DUs
1 CU
1 OAI 5GC
1 static UPF
manual F1 handover through CU Telnet
```

The manual handover command was:

```bash
echo ci trigger_f1_ho | nc -N 192.168.70.150 9090 && echo
```

The research objective was not yet dynamic UPF relocation or DRL/xApp integration. We intentionally scoped the first milestone to:

```text
static UPF placement
manual/scripted F1 handover
repeatable startup
automated readiness checks
metrics collection
logs/results organization
```

This was a good simplification because it created a stable baseline before adding DRL/GNN, xApp control, or multi-UPF logic.

---

### 2. Repository and automation harness creation

We created a new repository:

```text
oai-rfsim-handover-testbed
```

The first major task was to transform the OAI tutorial files into a cleaner project structure with automation scripts, experiment folders, logs, metrics, and results.

The service/container names were simplified from verbose `oai-*` names to:

```text
amf
smf
upf
cu
du0
du1
nr-ue
ext-dn
```

The first automation layer included scripts such as:

```text
scripts/up.sh
scripts/down.sh
scripts/restart.sh
scripts/status.sh
scripts/wait_ready.sh
scripts/trigger_handover.sh
scripts/collect_logs.sh
scripts/run_smoke_test.sh
```

The initial workflow reproduced your manual process:

```text
start core
start CU
start DU0
start DU1
verify nr-ue is running
trigger handover
collect logs and run metadata
```

One important operational note was that **Tailscale could interfere with the `nc` command** used to trigger handover. The scripts were updated to warn when Tailscale appeared active.

---

### 3. Readiness and startup-order improvements

At first, containers were started one after another. You correctly pointed out that OAI documentation recommends waiting for some services to become healthy before starting dependent components.

We then improved the startup logic with bounded readiness gates:

```text
start 5GC
wait for AMF/SMF/UPF healthy or running
start CU
wait for CU running and Telnet port reachable
start DU0
wait for DU0 running
start DU1
wait for DU1 and nr-ue running
```

This made the testbed more robust and reduced the risk of false failures caused by starting components too early.

---

### 4. First successful automated handover

After the automation scripts were created, you ran the smoke test successfully.

The scripts verified:

```text
amf: running
smf: running
upf: running
cu: running
du0: running
du1: running
nr-ue: running
CU Telnet 192.168.70.150:9090 reachable
```

The handover trigger worked through the script:

```text
RRC F1 handover triggered for UE 1
```

This validated the first important milestone:

```text
manual OAI handover tutorial → automated reproducible handover workflow
```

---

### 5. Ping metric pipeline and first issue

The next step was to collect data-plane metrics during handover. We added ping capture around the handover event.

The first implementation attempted to ping:

```text
192.168.71.135
```

from inside `nr-ue`, but the ping produced no valid samples. The summary showed:

```text
packets_transmitted: 0
packets_received: 0
```

We investigated inside `nr-ue` and found that the UE was registered and had a PDU session:

```text
oaitun_ue1: 10.0.0.2/24
```

but the default route still went through Docker `eth0`, not the UE tunnel.

So we added support for binding ping to the UE tunnel interface:

```bash
ping -I oaitun_ue1 ...
```

At that point, ping to `8.8.8.8` worked, confirming that the UE data plane was functional.

---

### 6. UE data-plane readiness gate

We added a specific UE data-plane readiness check before running handover metrics.

The new script repeatedly tested whether the UE could reach the configured ping target through the PDU session interface:

```bash
docker exec nr-ue ping -I oaitun_ue1 -c 1 -W 1 <target>
```

This prevented the smoke test from triggering handover when the UE data plane was not ready.

This was an important methodological improvement because:

```text
container running ≠ UE registered
UE registered ≠ PDU session usable
PDU session usable ≠ metric target reachable
```

---

### 7. Parser bug and correction

After ping capture worked, we found a parser issue.

The `ping.csv` file had many ICMP samples, but the summary incorrectly reported only:

```text
packets_transmitted: 2
packets_received: 2
```

The cause was that the parser was reading the ping precheck statistics instead of the long capture.

We fixed the parser so that:

```text
packets_received = number of parsed ICMP reply rows
packets_transmitted = final capture stats or max icmp_seq
precheck stats are ignored
```

After the fix, the parser correctly reported values like:

```text
packets_transmitted: 64
packets_received: 63
parsed_reply_count: 63
```

---

### 8. Initial repeated baseline using 8.8.8.8

Before fixing local DN reachability, the repeated test used:

```text
target: 8.8.8.8
interface: oaitun_ue1
```

A repeated run with `RUNS=5` produced:

```text
5/5 runs passed
mean interruption: ~221.81 ms
packet loss mean: ~1.245%
```

This proved that the metric pipeline worked, but `8.8.8.8` was not ideal because internet RTT introduced noise.

We then decided to fix local `ext-dn` reachability.

---

### 9. Diagnosing ext-dn reachability

The local DN target was:

```text
ext-dn: 192.168.71.135
```

Initially, the UE could not ping `ext-dn`, even though it could reach the internet through the UPF.

We created:

```text
scripts/diagnose_dn_reachability.sh
```

This diagnostic script collected:

```text
docker ps
docker networks
container IP addresses
routes
ping probes
iptables/nft state
sysctl forwarding state
```

The first diagnosis showed:

```text
UE → internet: pass
UE → ext-dn: fail
UE → UPF tun: pass
ext-dn → UE: initially inconsistent
UPF → ext-dn: ambiguous/fail
```

We also discovered that the `upf` container lacked the `ping` binary, so UPF ping failures could not be classified as real network failures.

The diagnostic script was later improved to report:

```text
tool_missing
```

instead of incorrectly reporting network failure when `ping` was absent.

---

### 10. Root cause: UPF not attached to traffic network

We inspected the compose topology and found that `ext-dn` was attached to both:

```text
public_net: 192.168.70.135
traffic_net: 192.168.71.135
```

but `upf` was only attached to:

```text
public_net: 192.168.70.134
```

So the UPF had no interface on the `192.168.71.0/26` traffic network.

You also recalled an older OAI/RFsim issue where Docker interface ordering could be nondeterministic unless `interface_name` was explicitly configured.

We updated `oai-cn5g/docker-compose.yaml` so that:

```text
upf:
  public_net  → eth0 → 192.168.70.134
  traffic_net → eth1 → 192.168.71.134

ext-dn:
  public_net  → eth0 → 192.168.70.135
  traffic_net → eth1 → 192.168.71.135
```

After restarting the stack with `down --volumes` and `up`, local DN reachability worked:

```text
UE → ext-dn: pass
ext-dn → UE: pass
UE → UPF tun: pass
```

This was a key debugging result.

---

### 11. Local ext-dn became the default smoke-test target

Once local DN reachability was fixed, we changed the default ping target from:

```text
8.8.8.8
```

to:

```text
192.168.71.135
```

with:

```text
interface: oaitun_ue1
```

This made the experiment more scientifically appropriate because it removed internet-path variability.

The fallback remained available:

```bash
PING_TARGET=8.8.8.8 PING_INTERFACE=oaitun_ue1 ./scripts/run_smoke_test.sh
```

---

### 12. Final repeated local-DN baseline

After switching to local `ext-dn`, you ran:

```bash
RUNS=5 ./scripts/run_repeated_smoke_tests.sh
```

The result was:

```text
5/5 runs passed
packet loss: 0.0%
mean estimated interruption: 207.0664 ms
std estimated interruption: 22.3375 ms
min interruption: 170.576 ms
max interruption: 238.949 ms
mean first ping after handover: 93.309 ms
```

This became the first clean baseline for the RFsim F1 handover testbed.

We documented it in:

```text
docs/en/report-baseline-results.md
```

The baseline was interpreted as:

```text
The automation harness can repeatedly start and validate the OAI RFsim F1 handover testbed, trigger F1 handover through the CU Telnet interface, and preserve UE data-plane connectivity to local ext-dn with no packet loss across five runs.
```

A known limitation remains:

```text
RTT still includes RFsim, Docker, host scheduling, and processing spikes.
```

So the handover interruption metric is useful, but RTT should not yet be interpreted as clean protocol latency.

---

### 13. Optional iperf support and resolution

We then started adding optional `iperf3` support for richer user-plane traffic measurement.

Codex added:

```text
scripts/check_iperf_support.sh
scripts/run_iperf_test.sh
tools/parse_iperf.py
```

Both `nr-ue` and `ext-dn` had `iperf3` available.

However, both TCP and UDP iperf tests failed. The generated client command was:

```bash
docker exec nr-ue iperf3 -J -c 192.168.71.135 -t 10 -u
```

The likely problem is that `iperf3` was not being forced through the UE PDU session. Since the installed `iperf3` did not support `--bind-dev`, the next fix should use source-IP binding:

```bash
iperf3 -B 10.0.0.2 -c 192.168.71.135
```

For UDP:

```bash
iperf3 -B 10.0.0.2 -c 192.168.71.135 -u -b 1M
```

This path was completed on June 19, 2026. The runner now binds the client to the UE address discovered on `oaitun_ue1`. The working ext-dn target for iperf is `192.168.70.135`, because the UPF delivers the TCP/UDP flow on the ext-dn public-side address; using `192.168.71.135` produced an asymmetric iperf control connection.

The smoke workflow can now run iperf concurrently with ping across handover using `IPERF_ENABLED=1`. Per-run summaries include throughput, jitter, loss, and retransmission fields, and repeated runs aggregate those metrics. iperf remains optional unless `IPERF_REQUIRED=1` is set.

---

### 14. Issues I had while searching or validating older information

There were a few practical limitations during the walkthrough:

```text
1. Some GitHub searches returned no results immediately after you pushed files.
   This looked like indexing delay or the file not being pushed yet.

2. I could inspect files that were present in the GitHub repo, but not local-only changes before you pushed them.

3. I relied mainly on the current chat history, your pasted command outputs, and the GitHub repository.
   I did not perform a broad reconstruction from older separate chats.

4. Some run artifacts were intentionally ignored by .gitignore later, so future summaries should rely on selected pasted outputs, committed docs, or curated results rather than all raw run directories.

5. The initial UPF diagnostic result was ambiguous because the UPF container did not include `ping`.
   We corrected this by distinguishing `tool_missing` from true reachability failure.
```

No major uncertainty remains about the main workflow. Optional iperf measurement is now integrated and validated for UDP and TCP; future work is experimental characterization rather than basic transport enablement.

---


## Concise report-style conclusion

Over this work, we converted a manually executed OAI RFsimulator F1 handover tutorial into a reproducible research testbed. The final testbed automates container startup, readiness validation, manual F1 handover triggering through the CU Telnet interface, log and metric collection, repeated experiments, and baseline documentation. We identified and fixed several practical issues: startup ordering, UE data-plane readiness, incorrect ping target/interface selection, parser misclassification of ping statistics, local DN reachability failure, missing UPF traffic-network attachment, and Docker interface-order nondeterminism. The corrected testbed now supports a local `ext-dn` target through the UE PDU interface and produced a repeated baseline of 5/5 successful handovers, 0% packet loss, and approximately 207 ms mean estimated handover interruption. Optional iperf-based measurement now binds to the UE PDU IP, runs concurrently across handover, and is aggregated in repeated experiments.
