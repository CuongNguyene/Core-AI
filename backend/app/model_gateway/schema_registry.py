from pydantic import BaseModel

from app.model_gateway.errors import DuplicateOutputSchemaError, UnknownOutputSchemaError


class OutputSchemaRegistry:
    """Trusted application schemas available to structured inference only."""

    def __init__(self) -> None:
        self._schemas: dict[tuple[str, str], type[BaseModel]] = {}

    def register(self, schema_id: str, schema_version: str, schema: type[BaseModel]) -> None:
        key = (schema_id, schema_version)
        if key in self._schemas:
            raise DuplicateOutputSchemaError(f"Output schema already registered: {key}")
        self._schemas[key] = schema

    def resolve(self, schema_id: str, schema_version: str) -> type[BaseModel]:
        try:
            return self._schemas[(schema_id, schema_version)]
        except KeyError as exc:
            raise UnknownOutputSchemaError(
                f"Output schema is not registered: {(schema_id, schema_version)}"
            ) from exc
