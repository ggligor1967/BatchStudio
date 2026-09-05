# ADR-0003: Safe output boundary

## Status

Accepted

## Context

User naming patterns, source basenames, concurrent duplicate names, and operation-specific output filenames can otherwise escape the destination or overwrite one another.

## Decision

Resolve one canonical output root and compute each operation's final name/suffix before reservation. Sanitize generated names, reject resolved candidates outside that root and existing final symbolic links, and reserve canonical destinations through one lock-protected `OutputPathAllocator`. A reservation set prevents preferred-name aliases from returning the same path.

Use the shared `exclusive_output` helper for every registered writer, including aggregate PDF finalization. Create the actual destination exclusively and write through that handle; never reopen it with a truncating mode. Direct entrypoints must use the same boundary even without a batch allocator. Failed writes attempt cleanup only for the file created by that call.

Copy operation configuration mappings so injected rename counters are execution-local. Record successful intermediate identities and check them before cleanup. Use an exclusively created temporary file for ordinary output-directory probes. Advertise an aggregate output only after successful finalization.

## Consequences

Occupied unrelated outputs are preserved, including collisions introduced between reservation and creation. Direct calls fail explicitly; batch allocation can select a distinct final path. Returned successful destinations are the actual written paths. The [V11-01 regressions](../../tests/test_output_ownership.py) exercise counter interleaving, aliases, final-suffix containment, writer collisions, and ownership-aware cleanup/probes.

The boundary is not a filesystem sandbox. It does not defend against arbitrary hostile concurrent directory/link replacement or guarantee recovery from every OS/filesystem failure. Dry-run validation can still create a directory and an owned probe. Aggregate compilation and stop/finalize lifecycle behavior and OCR extraction semantics are unchanged.
