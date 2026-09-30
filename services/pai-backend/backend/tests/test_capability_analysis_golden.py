import json
from pathlib import Path

import pytest

from app.authorization.fixtures import LEARNER_ID
from tests.test_capability_analysis_api import capability_client, valid_ids


@pytest.mark.asyncio
async def test_capability_portfolio_output_matches_golden_fixture() -> None:
    client = await capability_client()
    async with client:
        response = await client.post(
            "/capability-gap-portfolios",
            headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
            json=valid_ids(),
        )

    expected = json.loads(
        (Path(__file__).parent / "golden" / "capability_gap_portfolio.json").read_text()
    )
    assert response.json() == expected
