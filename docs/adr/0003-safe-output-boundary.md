# ADR-0003: Safe output boundary

## Status

Accepted

## Context

User naming patterns, source basenames, concurrent duplicate names, and operation-specific output filenames can otherwise escape the destination or overwrite one another.

## Decision

Resolve one canonical output root, sanitize generated names, reject resolved candidates outside that root, and allocate initially unique paths through one lock-protected `OutputPathAllocator`. New output-producing paths must use this boundary.

## Consequences

Traversal-shaped names are contained and concurrent initial allocations are deterministic. The boundary is not a filesystem sandbox and cannot eliminate link races. Current operations that change the allocated suffix or final basename afterward need additional collision handling; that limitation is explicit rather than hidden.
