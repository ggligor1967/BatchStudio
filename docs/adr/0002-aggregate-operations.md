# ADR-0002: Explicit aggregate operations

## Status

Accepted

## Context

Most operations transform one input independently. PDF merge instead consumes an ordered group and produces one output. Hidden per-file session state would make lifecycle, concurrency, cleanup, and cross-run isolation difficult to reason about.

## Decision

Model PDF merge as `AggregateOperation` with explicit `begin`, `consume`, and `finalize` calls. Require an aggregate to be the final enabled workflow step and execute it through a dedicated batch path.

## Consequences

One operation instance owns one writer and one run, input order is explicit, dry run has a complete lifecycle, and finalization errors are reportable. The aggregate path is intentionally distinct from thread-pooled per-file chains; earlier per-file steps are not composed into the current merge execution path.
