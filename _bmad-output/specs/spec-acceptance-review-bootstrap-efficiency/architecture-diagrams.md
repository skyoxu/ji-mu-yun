# Architecture Diagrams

## 1. Authority 与验收流程

```text
Quick Dev / VDD implementation-complete
                |
                v
Acceptance freezes baseline/current
                |
                v
complete Changed-set Manifest
                |
                v
minimal complete Consumer Closure
                |
                v
contract-projected deterministic checks
        +-------+-------------------+
        |                           |
 machine failure              deterministic pass
        |                           |
        v                           v
typed repair, zero model    Acceptance decide-bootstrap
                              +-----+--------------------+
                              |                          |
                    deterministic_only        full conformance
                              |                          |
                              v                          v
                    Acceptance continues       3 isolated roles
                                                         |
                                                         v
                                          verifier only for accepted P0/P1
                                                         |
                                                         v
                                           Acceptance import/finalize
```

## 2. Segment 执行与恢复

```text
immutable Segment Descriptor
        |
        v
canonical segment payload identity
        |
        v
segment-only frozen snapshot
        |
        v
absolute path + inherited access proof
        |
        v
child attempt
        |
        +--> liveness heartbeat (not progress)
        |
        +--> Effective Progress Event
        |
        +--> child terminal observation
                    |
                    v
          append terminal/stale event
                    |
                    v
            lease reconciliation
          +---------+-----------+
          |                     |
   bounded retry eligible   terminal blocked/complete
          |
          v
same segment identity + exact receipt fold
```

## 3. Attempt 状态机

```text
attempt-reserved
        |
        v
attempt-started
        |
        +--> attempt-liveness-heartbeat (zero or more, not progress)
        |
        +--> attempt-effective-progress (zero or more)
        |
        +--> no-progress watchdog | child terminal observation
                                      |
                                      v
             attempt-completed | attempt-failed | attempt-stale
                                      |
                                      v
                             lease reconciliation
                           +----------+-----------+
                           |                      |
                    retry-eligible       terminal blocked | role completed
```

任何 retry reservation 都发生在 reconciliation 之后；外层 job return、child terminal observation、liveness 和 Effective Progress 是不同事件。
