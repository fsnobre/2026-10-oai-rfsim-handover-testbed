# SMF IPv4v6 DNN Fix Report

> **Document type:** Report
>
> **Context:** [USRP X310 + COTS UE guide](guide-usrp-x310-cots.md) and [F02 — User-plane and DN reachability](foundation-f02-dn-reachability.md)

**Date:** May 5, 2026 (written up October 27, 2026)
**Scope:** OAI 5G Core SMF with a commercial UE (Telit FN990)
**Status:** Fixed in a locally built SMF image; not part of this repository's default stack

## Executive summary

A Telit FN990 registered with the AMF, but the SMF rejected every PDU session as "unknown requested DNN" (5GSM cause `0x1b`), right after logging `DNN matched!`. The UE requests an IPv4v6 session and the DNN was configured as IPv4. The SMF DNN validation only accepted an exact type match. A local change to that validation lets the SMF accept the request and select IPv4. After the change, the FN990 received `PDU Session Establishment Accept` and an IPv4 address.

## Symptom

```text
Requested DNN: internet
DNN matched!
unknown requested DNN internet
PDU Session Establishment Reject (5GSM Cause: 0x1b)
```

`0x1b` is "missing or unknown DNN". The DNN name matched, which made the log misleading.

## Root cause

The DNN validation in the SMF (`src/smf_app/smf_config.cpp`, `develop` source obtained April 21, 2026) returned a match only when the requested PDU session type equalled the configured one. The FN990 requests **IPv4v6**; the DNN was **IPv4**. The function returned "not found" after the name comparison succeeded, so the SMF rejected the session before its address-selection logic could choose IPv4.

The problem was reproduced in RFsim by setting the OAI NR-UE PDU session type to `IPv4v6`, which ruled out the radio side.

## Fix

Two cases were added after the existing equality check:

| Requested type | Configured DNN type | Before | After |
|---|---|---|---|
| IPv4v6 | IPv4 | rejected (`0x1b`) | accepted; SMF selects IPv4 |
| IPv4v6 | IPv6 | rejected (`0x1b`) | accepted; SMF selects IPv6 |
| any | same type | accepted | accepted (unchanged) |

Each new case logs a warning. Address selection itself was not changed. The modified source file is not published because of the OAI SMF licence (`LicenseRef-CSSL-1.0`).

## Relevance to this testbed

This repository's core (`oai-cn5g/docker-compose.yaml`) uses the stock `oaisoftwarealliance/oai-smf:develop` image, and the default `oai` DNN in `oai-cn5g/conf/config.yaml` is `IPV4`. The RFsim topologies are not affected, because the OAI NR-UE config (`conf-nr-ue.conf`) requests IPv4.

A COTS UE that requests IPv4v6 on the `oai` DNN can hit this rejection with the stock image. Check the SMF log for the sequence above before debugging the radio side.

## Where the fix was used

The patched SMF was built as `oai-smf:ipv4v6-dnn-fallback` and `oai-smf:ipv4v6-dnn-fallback-smf_context-fix` and used in the slicing scenarios of the companion `cerise_nobre` repository. The full record is `oai/docs/oai_smf_ipv4v6_dnn_fix.md` there.
