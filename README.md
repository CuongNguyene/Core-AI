# Core AI

Monorepo for the PAI service and its Frappe integration app.

## Layout

- `services/pai-backend`: FastAPI service, workers, migrations, and local PAI infrastructure.
- `apps/pai_frappe`: Frappe app that provides the LMS-to-PAI integration boundary.

The services remain independently deployable. A development Compose entry point will be added after
the Frappe bench runtime contract is verified.
