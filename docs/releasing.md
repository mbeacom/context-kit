# Releasing plugins

`context-kit` distributes independently versioned plugins from the hand-authored
marketplace on `main`. Git tags and GitHub releases provide immutable provenance
and release notes; they do not publish a separate package or replace the existing
Copilot, APM, or Claude Code install flows.

## Version and changelog

Prepare only the plugins whose shipped content changed:

1. Choose the next semantic version for each affected plugin.
2. Set that version in both `.claude-plugin/plugin.json` and `apm.yml`.
3. Add the same version as the first release entry in `CHANGELOG.md`, with an ISO
   date and concise user-visible changes.
4. Update the hand-authored `.claude-plugin/marketplace.json` only when catalog
   metadata or shipped membership changed. Never regenerate it with `apm pack`.
5. Do not bump unrelated plugins. A coordinated change may release multiple
   plugins from the same commit, but each keeps its own version and changelog.

Run the release-critical checks before merge:

```bash
claude plugin validate . --strict
for p in plugins/*/; do [ -f "$p/.claude-plugin/plugin.json" ] && claude plugin validate "$p" --strict; done
bash plugins/plugin-forge/scripts/check-manifests.sh
bash plugins/plugin-forge/scripts/check-release-readiness.sh
bash plugins/plugin-forge/scripts/test-release-readiness.sh
pre-commit run --all-files
```

The release-readiness gate requires every shipped catalog source to resolve to a
complete plugin with release metadata and assets. It also requires the manifest
version to be the latest changelog release and compares direct and transitive
dependencies from `plugin.json` with APM sibling paths.

## Tags and GitHub releases

After the release PR is merged, create one annotated tag per released plugin:

```text
<plugin-name>/v<semantic-version>
```

For example, `plugin-forge/v0.4.0` identifies plugin-forge independently of every
other plugin version. This convention is forward-only: existing versions do not
need historical tags, and the first tag for each plugin starts with its first
release under this policy.

Point the tag at the exact merged `main` commit, push it, and create a GitHub
release with the same tag. Use the matching changelog entry as the release notes;
add dependency or migration details only when they affect installation or use.
When one commit releases several plugins, create separate tags and releases that
all point to that commit.

## Recovery

- **Before merge:** correct the release PR in place; do not tag it.
- **After merge or tag:** do not move a published tag, reuse its version, or
  silently rewrite its GitHub release. Fix forward with the next patch version,
  a new changelog entry, and a new tag/release.
- Mark a faulty GitHub release as superseded and link to the corrective release.
  If urgent, the corrective patch may revert behavior, but it still receives a
  new version so host caches cannot confuse the two states.
- If only an unpushed local tag is wrong, delete it locally and recreate it at the
  correct merged commit before publishing.
