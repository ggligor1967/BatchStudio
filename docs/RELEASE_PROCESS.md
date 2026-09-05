# Release process

This process preserves source, tag, and artifact identity from verification through publication.

## Governance prerequisites

Release source changes reach `main` only through the protected integration path: topic branch, pull request, all exact required checks in [Testing](TESTING.md#required-github-checks) green, then a squash or rebase merge into protected `main`. Operators never push `main` directly; the `main-protection` ruleset blocks direct pushes, force pushes, and branch deletion. The active `release-tag-protection` ruleset allows creation of a new tag matching `v*` but permanently blocks updating or deleting it afterward, so a mistaken tag cannot be corrected in place. Never move or recreate an existing release tag.

Repository release immutability is enabled for releases published after the setting was activated on 2026-09-04; it is not retroactive. The existing v1.0.0 and v1.0.1 releases and assets remain unchanged historical evidence. For every future release, finish the draft, upload every asset, and verify stored bytes before publication because the tag, release metadata, and assets cannot be replaced afterward.

## 1. Establish the release commit

Select the release commit from `main` after its preparation pull request has merged through the protected path above. Run release-critical tests against that exact tree, and record both `git rev-parse HEAD` and `git rev-parse HEAD^{tree}`. Require an empty `git status --short`. The canonical version in `core/_version.py` (resolved into packaging metadata, the runtime banner, and the UI displays) and the changelog section must already agree with the intended release.

## 2. Build and verify artifacts

Build wheel and source distribution from that exact clean commit with `python -m build`. Install the wheel in a fresh temporary environment, import the required modules, and load the GUI entrypoint. Audit archive members for repository/build/cache material. Record filename, byte size, and SHA-256 for each artifact.

## 3. Verify remote state

Confirm the intended `origin`, authenticated GitHub repository, remote default branch, existing branch SHA, existing tag state, and existing release state. Stop on ambiguity or a conflicting branch, tag, or release. Never change the remote as an implicit repair.

## 4. Tag the already-merged release commit without rewriting history

`main` already points at the verified release commit through the merged preparation pull request; the release operation adds only a tag. Do not push `main`. Create an annotated version tag that points explicitly to that recorded commit and push only the tag. Read back the remote `main` SHA and the annotated tag's peeled SHA; both must equal the recorded commit.

Because `release-tag-protection` permanently blocks updating or deleting a `v*` tag once it exists, treat the first push of the tag as final: verify the target commit before pushing, and never attempt to move or recreate it afterward.

The following are prohibited:

```text
git push origin main
git push --force
git push --force-with-lease
git tag -f
```

Never delete, move, or recreate a published release tag.

## 5. Create a draft release

Prepare evidence-backed notes outside the repository. Create a GitHub Release as a draft with `--verify-tag` and upload exactly the canonical wheel and source distribution. Read back tag, title, draft/prerelease flags, and the complete asset set. Do not publish if metadata or asset count differs.

## 6. Verify bytes stored by GitHub

Download both assets from the draft into a fresh temporary directory. Independently measure their byte sizes and SHA-256 digests. They must exactly match the pre-upload canonical identities. On mismatch, stop and leave the release as a draft; do not silently delete or replace an asset.

## 7. Publish and re-verify

Immediately before publication, recheck the clean local HEAD/tree, remote main SHA, and peeled tag SHA. Publish only after every invariant passes. Read back that the release is public, not a prerelease, and marked latest when intended. Finish with the same local and remote invariant checks and record the release URL.

Published tags, notes, and assets are immutable release evidence. Corrections belong in a later release unless a security process explicitly requires a documented exception.
