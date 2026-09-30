# Frontend module document

`frontend/` is reserved for the mini-app UI. It has no runtime implementation
in PR-010A.

The approved target is Next.js App Router, React, TypeScript strict, Tailwind
CSS, next-intl and Zod. It will use only the PAI API; it must never access
Redis, object storage, model providers, service secrets or authorization roles
directly. The UI must not treat CV matching, course completion or AI output as
verified competency.

Update this document when the frontend module structure, build contract, API
client behavior or localization convention changes.
