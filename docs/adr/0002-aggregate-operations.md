# ADR-0002: Explicit aggregate operations

## Status

Accepted

## Context

Most operations transform one input independently. PDF merge instead consumes an ordered group and produces one output. Hidden per-file session state would make lifecycle, concurrency, cleanup, and cross-run isolation difficult to reason about.

## Decision

Model PDF merge as `AggregateOperation` with explicit `begin`, `consume`, and `finalize` calls. Adopt Contract A: an aggregate must be the **only enabled workflow step** and executes through a dedicated batch path. Disabled predecessors do not participate; enabled per-file predecessors, multiple aggregates, and non-final aggregate structures are rejected with actionable compile errors. A valid compiled plan identifies its execution mode and enabled operation IDs; an aggregate plan additionally declares `original_inputs` as its input source and records the aggregate's accepted types. An invalid compilation exposes no executable plan.

Validate and compile the workflow even with no inputs. Return one batch-level error for valid empty aggregate input before output preparation or `begin`. For nonempty input, reject any path or registry-classified type outside the compiled aggregate contract before output preparation or `begin`; no compatible subset is finalized from a type-incompatible batch. Correctly typed but unreadable PDFs retain the per-input consumption policy, so readable PDFs may still finalize. The per-file worker rejects aggregate steps defensively instead of skipping them.

Check cooperative stop after pause handling and immediately before `finalize`, which is the physical write boundary. Publish the common output only after successful finalization; dry run reports a planned destination without producing a file. Unexpected `begin`, `consume`, or `finalize` exceptions are recorded at their lifecycle boundary and return settled batch statistics.

## Consequences

Each independent batch owns a fresh operation instance and writer, so page/input state and output identity do not accumulate across success, failure, or stop. The aggregate receives the original input paths in caller order; transformed intermediates are not an alternate source. Input and page order remain explicit. Processing counts describe consumed inputs and do not establish that a merged output exists; failed finalization and stop leave no completed output path.

A stop observed before finalization prevents output. Once finalization starts, hard cancellation and atomic rollback are not promised. Canonical reservation, containment, exclusive creation, and execution-owned cleanup remain the output contract. Transformed intermediates feeding aggregate execution, new aggregate types, changed partial-invalid-input policy, and global write-free dry-run validation are outside this decision.
