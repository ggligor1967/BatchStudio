# Reproducible performance baseline

## Purpose and evidence boundary

V12-PERF defines a versioned measurement baseline. It does not optimize production code, set a marketing target, certify other hardware, or replace correctness, packaging, release, or OCR qualification gates. A timing is admissible only when its complete raw session record reports `PASS` and the fixture, repository, environment, configuration, and correctness identities match this contract.

Authoritative v1 evidence is retained under `benchmarks/evidence/v1/<environment_id>/`. Files below `.benchmarks/` are local scratch evidence and are ignored. Shared GitHub-hosted runner timings are correctness/validity evidence only; they are not authoritative performance numbers because runner hardware is not stable.

## Frozen workload and fixture contract

| Workload | Production operation | Fixed input | Mode | Performance profile |
| --- | --- | --- | --- | --- |
| B1 | `file_rename` | F1 repeated as 256 batch entries | one worker | small-file processor and orchestration overhead |
| B2 | `image_resize` | one 4096 x 3072 RGB BMP, resized to 2048 x 1536 | one worker | image decode, resample, and encode |
| B3 | `pdf_watermark` | one 64-page mixed-geometry PDF | one worker | page-aware PDF transform |
| B4 | `pdf_merge` | 16 six-page PDFs repeated four times, 64 inputs and 384 output pages | aggregate, one worker | ordered PDF parse and write |
| B5 | `image_resize` | eight 2048 x 1536 RGB BMPs repeated four times, 32 batch entries | four workers | multi-file image throughput and scheduling |

`benchmarks/fixtures.py` generates every input without downloads, random state, fonts, or current timestamps. `benchmarks/fixture_manifest_v1.json` records every file size, SHA-256, dimension/page contract, generator, and expected output class. Its SHA-256 is `4bf99714cd2d50fd8da48e86d94ee026c06ca17e6f393f8ec0e85f9a1b196e24`.

The fixture groups have these fixed identities:

- F1: one 65,536-byte TXT, SHA-256 `1e6c59b77930b21ef2bdfa5234083d0673cfcf769b5656094c381ae775bc7219`.
- F2: one 37,748,790-byte BMP, SHA-256 `40e121aec0158a0a2117a019ebed6299c54e2d60b57e2c5577091d0040751a5b`.
- F3: one 9,614-byte PDF, SHA-256 `c51ee84ad8e47039ee47ac8508dde8555b840434301911f8376430eb552a4708`.
- F4: 16 PDFs. Their individual hashes are canonical in the manifest; B4 verifies all of them before execution and verifies all 384 output page dimensions in order.
- F5: eight 9,437,238-byte BMPs. Their individual hashes are canonical in the manifest; B5 verifies all of them before and after every iteration.

Generate and verify the fixtures independently:

```powershell
python -m benchmarks.fixtures --output-dir .benchmarks/fixtures-v1 --verify
```

## Environment identity

Every session record contains the environment ID, OS and version, architecture, CPU, logical processor count, RAM bytes, Python version, installed distribution versions, repository commit and tree, worker counts, storage description, power mode, external-tool statement, and clock properties. `benchmarks/constraints.txt` freezes the Python dependency identity used for the v1 Windows baseline.

Install the checkout with the frozen identity:

```powershell
python -m pip install -c benchmarks/constraints.txt -e .
python -m pip check
```

The authoritative local environment is Windows 11 Home 10.0.26200 build 26200 on AMD64, Intel Core i7-1260P, 16 logical processors, 16,876,888,064 RAM bytes, Python 3.13.14, a fixed local ReFS `D:` volume, and the Windows Balanced power scheme. This identity describes evidence; it does not imply stable dedicated hardware or hardware-normalized results.

OCR is excluded from B1-B5. The exact V11-06 Ubuntu 24.04/Python 3.12.11 Tesseract, Poppler, and English trained-data environment is available only in its dedicated GitHub job. Mixing an uncontrolled Windows OCR installation into this baseline would weaken reproducibility.

## Timing and statistics policy

The suite is warm in-process: each workload runs in a fresh Python subprocess; Python startup and imports are excluded; each timed iteration creates a fresh `BatchProcessor` and `Workflow`. Warm-ups initialize interpreter-level, library, and filesystem state inside that subprocess. Filesystem cache eviction is not attempted, so the suite does not claim cold-cache measurement. Cold and warm observations are never mixed.

- Clock: `time.perf_counter_ns()` for wall time and `time.process_time_ns()` for diagnostic CPU time.
- Warm-ups: B1/B3/B4 use five; B2/B5 use eight.
- Measured repetitions: 15 for every workload.
- Order: B1-B5 order is deterministically shuffled from the unique session ID.
- Timeout: 120 seconds for each complete workload subprocess.
- Outliers: every completed measured sample is retained; no sample is deleted or winsorized.
- Primary statistic: median wall-clock seconds.
- Additional statistics: N, minimum, maximum, arithmetic mean, sample standard deviation, nearest-rank P95, median CPU time, files/second, seconds/file, and output bytes.
- Peak memory: recorded as unavailable because the repository has no dependency-free, trustworthy cross-platform per-workload process-peak boundary.

Fixture generation, fixture hashing, output cleanup, and output validation are outside the timed region. Correctness validation follows each timed operation immediately. The timed production call still includes processor/workflow creation, operation execution, worker scheduling, and output writing.

## Correctness boundary

Every measured sample must prove successful processor statistics, expected result and unique-output counts, owned paths beneath the temporary output root, output existence, collision-sentinel preservation, and unchanged input hashes. It additionally proves byte-identical B1 content, B2/B5 BMP format/mode/dimensions, B3 PDF page count/geometry/rotation/content, and B4 page count/order/dimensions. Deterministic workloads must retain one output fingerprint across all measured repetitions. A failed guardrail prevents a valid workload or session record.

The output fingerprint stores the output-file count, distinct content hashes, and a SHA-256 over the complete sorted path-to-content-hash manifest. This keeps raw evidence bounded without discarding identity.

## Calibration, repeatability, and regression rules

Pilot data is calibration evidence, not a product performance claim. The committed `benchmarks/repeatability_thresholds_v1.json` retains all clean pilot timings and applies this prospective rule independently to each workload:

```text
repeatability threshold = ceil to 0.5 percentage points of
                          max(5.0%, 3 * pilot relative MAD%)
```

The frozen thresholds are B1 10.0%, B2 6.5%, B3 6.0%, B4 5.0%, and B5 22.5%. B5's wider envelope is an explicit limitation of four-worker scheduling and thermal variability on this local machine, not permission to hide variance.

Two complete canonical sessions with distinct IDs must use the same committed SHA, tree, environment, fixtures, workload configuration, timeout, outlier rule, validation boundary, and threshold manifest. Repeatability passes only when every absolute session-median delta is within its frozen workload threshold.

After the two sessions, the regression budget is calculated as:

```text
max allowed regression = ceil to 0.5 percentage points of
                         max(repeatability threshold, 2 * observed session delta%)
minimum targeted improvement = 2 * max allowed regression
```

These budgets are noise-derived guardrails, not optimization goals. A future optimization unit is admissible only with a proven bottleneck, an explicitly targeted canonical workload and median, improvement exceeding its minimum, no unrelated canonical regression beyond budget, and all correctness/regression checks passing.

## Running and interpreting the baseline

Canonical execution is deliberately fail-closed: the worktree must be clean, the expected SHA must equal `HEAD`, the complete B1-B5 suite is mandatory, evidence paths cannot be overwritten, and each workload runs in a bounded child process.

```powershell
$sha = git rev-parse HEAD
python -m benchmarks.run_baseline run `
  --profile canonical `
  --session-id baseline-v1-session-1 `
  --environment-id win11-i7-1260p-refs-balanced-py313-v1 `
  --storage-type "D: fixed ReFS local volume" `
  --power-mode "Balanced 381b4222-f694-41f0-9685-ff5bb260df2e" `
  --workspace-root .benchmarks/work `
  --expected-repository-sha $sha `
  --output .benchmarks/baseline-v1-session-1.json
```

Run the same command independently with session/output suffix `2`, then compare the complete sessions:

```powershell
python -m benchmarks.compare_sessions compare `
  --session-1 .benchmarks/baseline-v1-session-1.json `
  --session-2 .benchmarks/baseline-v1-session-2.json `
  --thresholds benchmarks/repeatability_thresholds_v1.json `
  --output .benchmarks/baseline-v1-comparison.json
```

Compare medians only within an identical declared environment. Results from another machine, storage device, power state, Python/dependency set, fixture version, worker count, or repository SHA form a new baseline and are not directly comparable. Inspect raw timings and sample standard deviation before acting on a median; a comparison inside the envelope establishes repeatability, not a causal bottleneck.

## Canonical v1 evidence

The authoritative session results, repeatability comparison, bounded profiling evidence, and optimization-admission conclusion are added only after both clean sessions pass this frozen methodology. No performance number is canonical merely because it appeared in a pilot or terminal log.
