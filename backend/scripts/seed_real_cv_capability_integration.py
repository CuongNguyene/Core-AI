import asyncio
import json

from app.capability_analysis.integration_seed import seed_real_cv_capability_target
from app.main import create_app


async def _run() -> None:
    app = create_app()
    try:
        result = await seed_real_cv_capability_target(app.state.database.session_factory)
        print(
            json.dumps(
                {
                    "target_profile_id": result.target_profile_id,
                    "target_profile_version": result.target_profile_version,
                    "source_jd_profile_id": result.source_jd_profile_id,
                },
                sort_keys=True,
            )
        )
    finally:
        await app.state.database.dispose()


if __name__ == "__main__":
    asyncio.run(_run())
