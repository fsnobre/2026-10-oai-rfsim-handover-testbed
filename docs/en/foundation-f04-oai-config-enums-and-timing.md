# OAI Configuration Enums and Radio Timing

> **Document type:** Foundation (`F04`)
>
> **Required reading:** None

## Configuration values may be enum indexes

Several OAI libconfig fields use integer enum indexes rather than literal protocol values. Comments near the field usually describe the mapping.

For example:

```text
# 1,2,4,8,10,20,40,80
ra_ResponseWindow = 4;
```

Here `4` is the zero-based enum selection for 10 slots. It does not mean a four-slot response window.

| Enum index | Effective RA response window |
|---:|---:|
| `0` | 1 slot |
| `1` | 2 slots |
| `2` | 4 slots |
| `3` | 8 slots |
| `4` | 10 slots |
| `5` | 20 slots |
| `6` | 40 slots |
| `7` | 80 slots |

Supplying literal `8` is outside the valid enum range and caused the OAI RACH configuration encoder to assert.

## Diagnosing PRACH/Msg2 timing

```text
Initiating RA procedure with preamble ...
exceeded RA window: preamble at 503.19 now 504.10 (diff 11),
ra_ResponseWindow 4/10 slots
cannot schedule Msg2
```

Interpretation:

1. RF synchronization and SIB1 decoding succeeded.
2. The UE transmitted PRACH.
3. The DU detected the preamble.
4. The DU attempted to schedule the response too late.
5. The UE reported RAR failure and returned to idle.

This differs from no RFsim connection, PBCH/SIB1 failure, PRACH below threshold, or NAS authentication failure.

## Applied correction

The observed delay was 11 slots. Index `4` allowed 10 slots. The setting changed to index `5`, allowing 20 slots:

```text
ra_ResponseWindow = 5;
```

## General rule

Before changing an integer radio parameter:

1. Read its mapping comment.
2. Determine whether it is an enum or literal.
3. Compare logs with the effective decoded value.
4. Select the smallest valid value covering the condition.
5. Retest synchronization, random access, registration, and data traffic.

Do not infer units solely from the field name.
