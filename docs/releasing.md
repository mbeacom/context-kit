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

## Publishing indexkit to PyPI

`indexkit` also ships as a Python package (ADR-0006). The same
`indexkit/v<version>` tag that releases the plugin triggers
[`.github/workflows/release-indexkit.yml`](https://github.com/mbeacom/context-kit/blob/main/.github/workflows/release-indexkit.yml),
which builds and publishes it. There is no separate package tag: one release,
one identifier. See ADR-0008 for the reasoning.

A PyPI upload cannot be undone — a file can only be yanked, and the version
number is consumed permanently — so four version surfaces must agree before the
tag is pushed:

| Surface | File |
|---|---|
| Package version | `plugins/indexkit/pyproject.toml` |
| Runtime version | `plugins/indexkit/src/indexkit/__init__.py` |
| Plugin manifest | `plugins/indexkit/.claude-plugin/plugin.json` |
| APM manifest | `plugins/indexkit/apm.yml` |

plus a matching `## <version>` heading in `plugins/indexkit/CHANGELOG.md`.

Check them locally before tagging — this is the same guard CI runs first, so a
failure here is a failure there:

```bash
python3 scripts/release_version.py \
  --package indexkit \
  --tag indexkit/v0.6.0 \
  --plugin-dir plugins/indexkit
```

Package and plugin versions are held at parity. If a release genuinely needs
them to diverge, pass `--allow-plugin-drift` and say why in the release notes.
The flag is narrow: it never relaxes the package's own surfaces, and never lets
`plugin.json` and `apm.yml` disagree with *each other* — that lockstep is
ADR-0005's and holds unconditionally.

Then:

1. **Rehearse.** Run the workflow via `workflow_dispatch` with the intended tag.
   Dispatch runs verification only and never publishes, so this exercises the
   guard, tests, `uv build`, and `twine check --strict` without spending a tag.
2. **Tag and push**, as above. The `publish` job runs only on a tag push, and
   only if `verify` succeeded.
3. **Confirm** the release on <https://pypi.org/p/indexkit>.

Prerequisites a maintainer must configure once, outside this repository:

- A PyPI **pending publisher** for `indexkit` — owner `mbeacom`, repository
  `context-kit`, workflow `release-indexkit.yml`, environment `pypi`. Publishing
  uses Trusted Publishing (OIDC); no PyPI API token is stored in this repository.
- The `pypi` GitHub environment, and whether it requires a reviewer.

Because Trusted Publishing binds to `(owner, repo, workflow filename,
environment)`, **renaming `release-indexkit.yml` breaks publishing** until the
PyPI configuration is updated to match.

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
