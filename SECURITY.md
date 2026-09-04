# Security policy

## Supported release

BatchStudio 1.0.1 is the current release. Security fixes are evaluated against the current `main` branch and identified for a future release; published tags and release assets remain immutable.

## GitHub security controls

The following repository settings were read back from GitHub on 2026-09-04:

- dependency graph and Dependabot alerts are enabled;
- Dependabot security updates are enabled;
- secret scanning and push protection are enabled;
- CodeQL default setup is configured for Python with the default query suite and weekly analysis;
- the required `dependency-review` pull-request check fails on newly introduced high or critical known vulnerabilities.

Workflow tokens default to read-only, cannot approve pull requests, and external Actions must use full commit SHA pins. These controls supplement the application boundaries in [Security model](docs/SECURITY_MODEL.md); they do not prove that every input or dependency is safe.

## Reporting a vulnerability

Use the repository's [private vulnerability reporting page](https://github.com/ggligor1967/BatchStudio/security/advisories/new) when available. Include the affected version, operating system, input type, minimal reproduction, impact, and whether untrusted files or paths are required. Do not include secrets or sensitive sample documents in a public issue.

For non-sensitive defects, use [GitHub Issues](https://github.com/ggligor1967/BatchStudio/issues).

## Response boundaries

The project does not promise a fixed response or disclosure timetable. Reports are assessed according to impact and reproducibility. A report is not considered fixed until the relevant code, tests, and documentation are verified.

The implemented security controls and their limits are documented in [Security model](docs/SECURITY_MODEL.md).
