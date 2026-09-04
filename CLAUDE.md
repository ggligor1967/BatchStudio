# Claude guidance

`AGENTS.md` is the authoritative engineering and documentation-maintenance contract for this repository. Claude-based agents must read and follow it before proposing or making changes.

Claude-specific expectations:

- Keep tool use and edits within the user's explicit scope.
- Cite current source, tests, Git, or release evidence for technical and historical claims.
- Preserve the published `v1.0.0` tag and release.
- Report unverified assumptions instead of converting them into documentation claims.

Architecture and operational facts belong in the canonical files under `docs/`, not in this provider-specific file.
