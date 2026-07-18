---
# TEMPLATE ONLY: copy this into your own host's rules directory. It is inert here.
description: Backend API conventions
globs:
  - "src/api/**" # Host-dependent; some rule systems call this applyTo.
# applyTo:
#   - "src/api/**"
---

# Backend API Rule Template

Use this as a starting point for a path-scoped backend API rule. Adjust the scope field to match your host's rule format.

- Validate external input at the boundary before business logic runs.
- Prefer explicit schemas for request bodies, query parameters, and route params.
- Return typed errors with stable codes; do not leak stack traces or internal identifiers.
- Keep handlers thin: parse, authorize, call a service, map the response.
- Add or update focused tests for new validation branches and authorization failures.
