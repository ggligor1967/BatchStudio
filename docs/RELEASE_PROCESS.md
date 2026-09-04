# Release process

This process preserves source, tag, and artifact identity from verification through publication.

## 1. Establish the release commit

Run release-critical tests, commit the verified tree, and record both `git rev-parse HEAD` and `git rev-parse HEAD^{tree}`. Require an empty `git status --short`. Version and changelog must already agree with the intended release.

## 2. Build and verify artifacts

Build wheel and source distribution from that exact clean commit with `python -m build`. Install the wheel in a fresh temporary environment, import the required modules, and load the GUI entrypoint. Audit archive members for repository/build/cache material. Record filename, byte size, and SHA-256 for each artifact.

## 3. Verify remote state

Confirm the intended `origin`, authenticated GitHub repository, remote default branch, existing branch SHA, existing tag state, and existing release state. Stop on ambiguity or a conflicting branch, tag, or release. Never change the remote as an implicit repair.

## 4. Tag and push without rewriting history

Create an annotated version tag that points explicitly to the verified release commit. Push `main` without force, then push only the release tag. Read back the remote branch SHA and the annotated tag's peeled SHA; both must match the recorded commit.

The following are prohibited:

```text
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
