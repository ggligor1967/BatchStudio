# ADR-0002: Explicit aggregate operations

## Status

Accepted

## Context

Most operations transform one input independently. PDF merge instead consumes an ordered group and produces one output. Hidden per-file session state would make lifecycle, concurrency, cleanup, and cross-run isolation difficult to reason about.

## Decision

Model PDF merge as `AggregateOperation` with explicit `begin`, `consume`, and `finalize` calls. Adopt Contract A: an aggregate must be the **only enabled workflow step** and executes through a dedicated batch path. Disabled predecessors do not participate; enabled per-file predecessors, multiple aggregates, and non-final aggregate structures are rejected with actionable compile errors.

Validate and compile the workflow even with no inputs. Return one batch-level error for valid empty aggregate input before output preparation or `begin`. Check cooperative stop after pause handling and immediately before `finalize`, which is the physical write boundary. Publish the common output only after successful finalization; dry run reports a planned destination without producing a file.

## Consequences

Each independent batch owns a fresh operation instance and writer, so page/input state and output identity do not accumulate across success, failure, or stop. Input and page order remain explicit. Processing counts describe consumed inputs and do not establish that a merged output exists; failed finalization and stop leave no completed output path.

A stop observed before finalization prevents output. Once finalization starts, hard cancellation and atomic rollback are not promised. Canonical reservation, containment, exclusive creation, and execution-owned cleanup remain the output contract. Transformed intermediates feeding aggregate execution, new aggregate types, changed partial-invalid-input policy, and global write-free dry-run validation are outside this decision.
