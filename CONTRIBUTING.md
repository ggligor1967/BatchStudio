# Contributing to BatchStudio

## Before changing the repository

1. Read [AGENTS.md](AGENTS.md), [Architecture](docs/ARCHITECTURE.md), and the subject-specific document.
2. Open or reference an issue describing the observed behavior and evidence.
3. Keep feature, bug, documentation, and packaging changes separable.
4. Do not move or recreate published tags.

## Development workflow

Create a virtual environment, install the project and development tools, then run the focused tests while developing. Before proposing a change, run the complete validation listed in [Testing](docs/TESTING.md). Do not add generated `build/`, `dist/`, caches, coverage data, virtual environments, or agent transcripts.

Code changes should preserve the typed `OperationResult` contract, route generated output through the safe allocator, and keep Tkinter updates on the main thread. New operations require registry wiring, configuration validation, failure-path tests, and updates to [Operations](docs/OPERATIONS.md).

## Documentation governance

- **DOC-01** One canonical document per subject.
- **DOC-02** Every implemented-feature claim must be traceable to current source/test evidence.
- **DOC-03** Planned features belong only in `docs/ROADMAP.md`.
- **DOC-04** Release facts must come from Git/tag/artifact evidence.
- **DOC-05** Documentation drift is a release blocker.
- **DOC-06** Generated agent transcripts/status dumps must never be committed as canonical docs.
- **DOC-07** Performance numbers require a reproducible benchmark definition.

Use relative links for repository documents and verify every link. Do not copy architecture or release facts into competing documents; link to the canonical source.

## Pull-request evidence

Describe the changed files, tests run with exit codes, known limitations, and whether runtime files changed. Performance claims must include a repeatable workload, environment, command, and result data.
