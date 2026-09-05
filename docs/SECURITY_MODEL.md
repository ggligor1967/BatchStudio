# Security model

BatchStudio is a local desktop batch processor. Its controls reduce accidental path escape and unsafe report content; they do not sandbox untrusted documents or third-party parsers.

## Demonstrated controls

### Resolved output-root containment

`resolve_safe_output` applies any required final suffix before resolving the candidate against the configured output root. It rejects paths outside that root and existing final-component symbolic links (including dangling links). PDF merge enforces `.pdf` at this boundary. End-to-end and output-ownership tests cover traversal-shaped names and final-suffix link containment.

### Safe output naming

`sanitize_filename` removes path separators, traversal fragments, Windows-invalid characters, leading/trailing dots and spaces, and supplies `output` when nothing remains. Run naming supports only literal substitution of `{original}`, `{timestamp}`, and `{counter}`.

### Final destination ownership

`Operation.execute` resolves operation-specific names and suffixes before batch allocation. `OutputPathAllocator` reserves canonical final paths under a mutex, checks existing paths, and adds `_001`, `_002`, and later counters. Reservations remain unique across preferred-name aliases such as `same`, `same`, and `same_001`.

All registered per-file writers and aggregate PDF finalization use `exclusive_output`: exclusive creation (`x`/`xb`) followed by writes through the created handle. An occupied destination, including one created after reservation, causes an explicit failure without truncating or replacing it. Direct operation calls receive the same write protection; batch calls can allocate an alternative final path. Successful results identify the actual destination. Report export is a separate, unchanged write path.

Operation instances shallow-copy their configuration mappings. Rename counters are injected only into worker-local operation configuration; nested values are not mutated or blindly deep-copied. Successful intermediate outputs are recorded with filesystem identity, and cleanup skips missing or identity-mismatched paths. Failed writes remove only the exclusively created partial file while its identity matches. These checks are not a defense against hostile replacement during the identity-check/unlink interval.

Normal output-directory validation uses `tempfile.NamedTemporaryFile` for a uniquely named, exclusively created probe and removes that owned probe. Existing `.write_test` files and colliding probe names remain unchanged. These guarantees are exercised in [the focused regressions](../tests/test_output_ownership.py).

### Dry-run output suppression

Registered operations avoid their normal output writes during dry run, aggregate merge does not create a writer, and the UI skips automatic report generation. Tests assert that an existing output directory remains without operation output. This is not a strict zero-filesystem-touch promise: output-directory validation may create the directory and creates then removes an exclusively owned probe.

### Report encoding

Dynamic HTML report values pass through `html.escape`. CSV fields that begin with `=`, `+`, `-`, or `@` are prefixed with an apostrophe to reduce spreadsheet formula execution. The regression suite covers both behaviors.

### Input and operation validation

Input paths must exist, be files, use the processor extension allow-list, and be no larger than 500 MiB. Workflow compilation rejects unknown operations, invalid schema values, incompatible per-file type transitions, missing declared capabilities, and non-final aggregates. Individual operations validate parseability before processing.

### Typed operation output

All operation lifecycle calls return `OperationResult`. The processor rejects a successful per-file result without an output path and records exceptions as failures rather than silently treating them as success.

## Security limitations

- There is no process, filesystem, or resource sandbox. Libraries parse files with the user's privileges.
- Exclusive creation protects occupied final entries at the write boundary; input validation, directory resolution, and cleanup are not protected against arbitrary hostile concurrent filesystem/link replacement.
- There is no atomic recovery guarantee for every OS/filesystem failure. Interrupted processing can leave owned intermediate or partial artifacts; failed cleanup is reported as an error.
- The 500 MiB per-file limit does not bound total batch memory, decompressed image size, PDF complexity, or external OCR resource use.
- CSV neutralization covers common leading formula characters; it is not a complete policy for every spreadsheet consumer.
- Workflow JSON is structurally loaded but has no authenticity signature or trust metadata.
- Reports and settings are local plaintext and may contain file paths or error details.
- External Tesseract and Poppler binaries are trusted components outside BatchStudio's update and integrity controls.

Report suspected vulnerabilities through [SECURITY.md](../SECURITY.md).
