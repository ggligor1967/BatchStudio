# ADR-0001: Thread-pool execution

## Status

Accepted

## Context

Batch processing must keep the Tkinter event loop responsive while multiple independent file operations perform filesystem and third-party library work. The existing processor needs bounded concurrency plus pause/stop control over future submissions.

## Decision

Use `ThreadPoolExecutor` for non-aggregate per-file workflows. Keep worker count bounded and marshal UI updates to the Tk main thread. Aggregate PDF merge remains sequential because it writes one ordered document.

## Consequences

Threads have low coordination overhead and share workflow/result state conveniently. They can overlap I/O and native-library work that releases the GIL. They cannot hard-terminate a running call and do not guarantee CPU-bound Python speedup because of the GIL. A future `ProcessPoolExecutor` would be justified only by a reproducible CPU-bound benchmark and a design for serializable tasks, cancellation, process startup, and intermediate-file ownership.
