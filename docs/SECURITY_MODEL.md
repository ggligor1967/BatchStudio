# Security model

BatchStudio is a local desktop batch processor. Its controls reduce accidental path escape and unsafe report content; they do not sandbox untrusted documents or third-party parsers.

## Demonstrated controls

### Resolved output-root containment

`resolve_safe_output` resolves both the configured output root and candidate path and rejects a candidate that is not relative to the root. PDF merge also enforces a `.pdf` suffix at this boundary. End-to-end tests cover traversal-shaped run naming and PDF merge output names.

### Safe output naming

`sanitize_filename` removes path separators, traversal fragments, Windows-invalid characters, leading/trailing dots and spaces, and supplies `output` when nothing remains. Run naming supports only literal substitution of `{original}`, `{timestamp}`, and `{counter}`.

### Duplicate basename allocation

`OutputPathAllocator` owns a resolved output root, uses a mutex, checks existing paths, and adds `_001`, `_002`, and later counters. Tests exercise concurrent-batch duplicate basenames.

### Dry-run output suppression

Registered operations avoid their normal output writes during dry run, aggregate merge does not create a writer, and the UI skips automatic report generation. Tests assert that an existing output directory remains without operation output. This is not a strict zero-filesystem-touch promise: output-directory validation may create the directory and creates then removes a `.write_test` probe.

### Report encoding

Dynamic HTML report values pass through `html.escape`. CSV fields that begin with `=`, `+`, `-`, or `@` are prefixed with an apostrophe to reduce spreadsheet formula execution. The regression suite covers both behaviors.

### Input and operation validation

Input paths must exist, be files, use the processor extension allow-list, and be no larger than 500 MiB. Workflow compilation rejects unknown operations, invalid schema values, incompatible per-file type transitions, missing declared capabilities, and non-final aggregates. Individual operations validate parseability before processing.

### Typed operation output

All operation lifecycle calls return `OperationResult`. The processor rejects a successful per-file result without an output path and records exceptions as failures rather than silently treating them as success.

## Security limitations

- There is no process, filesystem, or resource sandbox. Libraries parse files with the user's privileges.
- File validation and output allocation are subject to ordinary time-of-check/time-of-use races, including filesystem link changes.
- The allocator protects the initially requested suffix/name. Operations that subsequently change the suffix or final name can encounter an existing destination; callers must not assume universal no-overwrite protection.
- The 500 MiB per-file limit does not bound total batch memory, decompressed image size, PDF complexity, or external OCR resource use.
- CSV neutralization covers common leading formula characters; it is not a complete policy for every spreadsheet consumer.
- Workflow JSON is structurally loaded but has no authenticity signature or trust metadata.
- Reports and settings are local plaintext and may contain file paths or error details.
- External Tesseract and Poppler binaries are trusted components outside BatchStudio's update and integrity controls.

Report suspected vulnerabilities through [SECURITY.md](../SECURITY.md).
