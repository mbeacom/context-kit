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

One exception, and it is mechanical rather than stylistic. When a plugin also
publishes a Python package whose **distribution name differs from the plugin
directory name**, the tag prefix is the *distribution* name:

| Plugin | Package | Tag prefix |
|---|---|---|
| `plugins/indexkit` | `indexkit` | `indexkit/v…` |
| `plugins/memory` | `memorykit` | `memorykit/v…` |

`scripts/release_version.py` refuses a tag whose prefix is not the distribution
name — "the tag prefix and the distribution name must agree" — because the tag
is what names an irreversible PyPI upload, and `memory/v0.6.0` would not say
which package was published. It is still one tag per release: it releases the
plugin *and* the package, exactly as `indexkit/v…` does. See ADR-0009.

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
  --tag indexkit/v<version> \
  --plugin-dir plugins/indexkit
```

Package and plugin versions are held at parity. If a release genuinely needs
them to diverge, pass `--allow-plugin-drift` and say why in the release notes.
The flag is narrow: it never relaxes the package's own surfaces, and never lets
`plugin.json` and `apm.yml` disagree with *each other* — that lockstep is
ADR-0005's and holds unconditionally.

Then:

1. **Correct the README first, if it hedges about publication.** The plugin
   README is the package's `readme`, so it becomes the PyPI project page. A
   "not on PyPI yet" note that is true when written is false the moment the
   upload succeeds, and it cannot be fixed on the published page without a new
   release. Both `indexkit` and `memorykit` shipped their first release with
   that note still in place. Do this before the tag, not as follow-up.
2. **Rehearse.** Run the workflow via `workflow_dispatch` with the intended tag.
   Dispatch runs verification only and never publishes, so this exercises the
   guard, tests, `uv build`, `twine check --strict`, and the built-artifact
   assertion without spending a tag. Rehearse before every release: the
   dispatch path is the only place a build-stage bug can surface while the tag
   is still free to move.
3. **Tag and push**, as above. The `publish` job runs only on a tag push, and
   only if `verify` succeeded.
4. **Confirm** the release on <https://pypi.org/p/indexkit>.
5. **Confirm provenance.** Publishing emits PEP 740 attestations for **both**
   distributions; check that both landed, using the endpoint below rather than
   the obvious one.

Attestations are verified through PyPI's integrity endpoint, which is per-file —
so the wheel and the sdist have separate URLs and must be checked separately:

```bash
set -o pipefail  # without this, a 404 from curl is masked by the exit of jq
version=<version>
for file in "indexkit-${version}-py3-none-any.whl" "indexkit-${version}.tar.gz"; do
  echo "== ${file}"
  curl -fsS -H 'Accept: application/vnd.pypi.integrity.v1+json' \
    "https://pypi.org/integrity/indexkit/${version}/${file}/provenance" \
    | jq -e '.attestation_bundles[0].publisher | {repository, workflow}' || echo "MISSING"
done
```

Both files must report `repository: "mbeacom/context-kit"` and `workflow:
"release-indexkit.yml"`. That pair is the point of the check: a stored bundle
alone only proves *some* attestation exists, while the publisher identity is what
binds the artifact to this repository's release workflow. Do not reduce this to a
presence test, and do not truncate the response with `head` — the identity fields
sit past the first few hundred bytes. `pipefail` is load-bearing for the same
reason `-f` is: a pipeline reports its *last* command's status, so without it a
`404` from curl is reported as a pass by whatever runs next.

If either file is missing an attestation:

- Retry once after ~60s. PyPI indexes the integrity endpoint asynchronously, so a
  `404` immediately after publish can be indexing lag rather than a real gap.
- If it is still absent, **fix forward**. Attestations cannot be added to an
  already-published file, and the upload is irreversible. Note the gap on the
  GitHub release, then correct the workflow and cut the next patch version.

This step is manual by design. A post-publish CI gate would race that same
indexing delay, and a red job after an irreversible upload reports a problem it
cannot fix. See ADR-0008 for the full reasoning.

Do **not** judge any of this from the JSON API's `provenance` field: it reads
`null` for every file on PyPI, attested or not, so it reports a false negative on
a perfectly good release.

The build stage asserts that `dist/` holds exactly the two distributions the tag
asked for, catching a stale wheel or a backend that ignored the declared
version:

```bash
cd plugins/indexkit && uv build --out-dir dist
python3 ../../scripts/check_dist_artifacts.py \
  --dist-dir dist --package indexkit --version <version>
```

Only `*.whl` and `*.tar.gz` count as artifacts. `uv build` also writes a
`dist/.gitignore`, which is build-tool bookkeeping rather than something
publishable; the workflow uploads the two distributions by explicit path so
nothing else can reach the publish job.

Prerequisites a maintainer must configure once, outside this repository:

- A PyPI **pending publisher** for `indexkit` — owner `mbeacom`, repository
  `context-kit`, workflow `release-indexkit.yml`, environment `pypi`. Publishing
  uses Trusted Publishing (OIDC); no PyPI API token is stored in this repository.
- The `pypi` GitHub environment, and whether it requires a reviewer.

Because Trusted Publishing binds to `(owner, repo, workflow filename,
environment)`, **renaming `release-indexkit.yml` breaks publishing** until the
PyPI configuration is updated to match.

## Publishing memorykit to PyPI

`memory` also ships its contract, validator, and MCP server as the `memorykit`
Python package (ADR-0006 item 3, ADR-0009). The procedure is identical to
`indexkit` above — same guard, same rehearsal, same per-file attestation check —
so it is not repeated. Only these differ:

| | `indexkit` | `memorykit` |
|---|---|---|
| Tag | `indexkit/v<version>` | `memorykit/v<version>` |
| Workflow | `release-indexkit.yml` | `release-memorykit.yml` |
| Plugin dir | `plugins/indexkit` | `plugins/memory` |
| Project page | <https://pypi.org/p/indexkit> | <https://pypi.org/p/memorykit> |
| Runtime deps | `turbovec`, `httpx` | **none** |

```bash
python3 scripts/release_version.py \
  --package memorykit \
  --tag memorykit/v<version> \
  --plugin-dir plugins/memory
```

Substitute `memorykit` for `indexkit` in the attestation check too; both files
must report `workflow: "release-memorykit.yml"`.

`release-memorykit.yml` is a **copy** of `release-indexkit.yml`, not a call into
a shared reusable workflow. PyPI does not accept a reusable workflow as a Trusted
Publisher (the OIDC claim names the calling workflow), so the duplication is
forced. Fixes to release hardening must be applied to both files; ADR-0009
records this so the duplication is not mistaken for an oversight.

The same one-time prerequisites apply, with `memorykit` values: a PyPI **pending
publisher** for `memorykit` — owner `mbeacom`, repository `context-kit`, workflow
`release-memorykit.yml`, environment `pypi`. Both are configured, and
`memorykit` 0.6.0 published on 2026-08-09.

**A plugin README that is also a PyPI long description has to be corrected
before the tag, not after.** Both `indexkit` and `memorykit` shipped their first
release with a "Not on PyPI yet" note still in the README, so each project page
launched saying the project was not published. `indexkit` was corrected in
PR #45 and `memorykit` after 0.6.0; the note above was written to prevent the
second occurrence and did not, because it lived here rather than in the release
checklist. It is now step 1 of that checklist.

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
