# BatchStudio maintainer contract

This file is the canonical instruction set for human maintainers and coding agents working in this repository.

## Evidence and scope

- Inspect current source and tests before changing behavior or documenting it.
- Keep requested work bounded. Preserve unrelated changes and never rewrite a published tag.
- Prefer the standard library and existing dependencies. Add a dependency only when the change requires it and the maintainer approves it.
- Make the smallest coherent change, use descriptive names, and report failed or unavailable verification honestly.
- Runtime behavior is defined by `main.py`, `ui/`, and `core/`. Tests provide supporting evidence; documentation does not override code.

## Required verification

Choose checks proportionate to the changed surface. Documentation-only changes still require link, stale-claim, diff, and runtime-source invariants. Release-critical changes use the commands in [Testing](docs/TESTING.md) and [Release process](docs/RELEASE_PROCESS.md).

Never claim a command passed unless its exit code was observed. Never claim an artifact, file, tag, or release exists without verifying it in the relevant filesystem or service.

## GitHub governance

- Changes to `main` must arrive through pull requests; direct pushes, force pushes, and branch deletion are prohibited by the active `main-protection` ruleset.
- Required GitHub check names and local validation commands are canonical in [Testing](docs/TESTING.md).
- Workflows must declare minimum permissions, avoid untrusted secret exposure, and pin every external action to a full 40-character commit SHA from its official upstream repository.
- Published release tags matching `v*` cannot be updated or deleted. Follow the canonical [Release process](docs/RELEASE_PROCESS.md).

## Documentation governance

- **DOC-01** One canonical document per subject.
- **DOC-02** Every implemented-feature claim must be traceable to current source/test evidence.
- **DOC-03** Planned features belong only in `docs/ROADMAP.md`.
- **DOC-04** Release facts must come from Git/tag/artifact evidence.
- **DOC-05** Documentation drift is a release blocker.
- **DOC-06** Generated agent transcripts/status dumps must never be committed as canonical docs.
- **DOC-07** Performance numbers require a reproducible benchmark definition.

When implementation and documentation disagree, fix the documentation unless the user separately authorizes a behavior change. Record unsupported behavior in [Limitations](docs/LIMITATIONS.md), and record architectural decisions in `docs/adr/`.
