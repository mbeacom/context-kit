# Path-Scoped Rule Examples

Path-scoped rules load only when the agent is working in a matching part of the repository. They are ideal for local conventions: backend APIs, frontend components, migrations, infrastructure, or generated files.

Hosts differ in how they express this layer. Claude Code rule files, Cursor `.cursor/rules`, nested `AGENTS.md` files, and other agent hosts all use different filenames and metadata, but the concept is the same: attach short guidance to a path or glob instead of putting it in global memory.

[`backend-api.md`](backend-api.md) is an inert template. Copy it into your repository's rule location, translate the `globs` / `applyTo` field to your host's syntax, and replace the bullets with conventions for that area.
