class ModelGatewayError(Exception):
    """Base class for safe, internal model gateway failures."""


class DuplicateOutputSchemaError(ModelGatewayError):
    pass


class UnknownOutputSchemaError(ModelGatewayError):
    pass


class DuplicatePromptTemplateError(ModelGatewayError):
    pass


class UnknownPromptTemplateError(ModelGatewayError):
    pass


class DuplicateProviderError(ModelGatewayError):
    pass


class UnknownProviderError(ModelGatewayError):
    pass


class PrivacyDeniedError(ModelGatewayError):
    pass


class ExternalRoutingDisabledError(ModelGatewayError):
    pass


class ExternalProviderNotApprovedError(ModelGatewayError):
    pass


class ProviderTimeoutError(ModelGatewayError):
    def __init__(self, message: str, *, attempt_count: int = 1) -> None:
        self.attempt_count = attempt_count
        super().__init__(message)


class ProviderResponseError(ModelGatewayError):
    def __init__(
        self,
        message: str,
        *,
        provider_response_id: str | None = None,
        observed_model: str | None = None,
        latency_ms: int | None = None,
        attempt_count: int = 1,
    ) -> None:
        self.provider_response_id = provider_response_id
        self.observed_model = observed_model
        self.latency_ms = latency_ms
        self.attempt_count = attempt_count
        super().__init__(message)


class ProviderRefusalError(ProviderResponseError):
    """Provider explicitly declined the request; this is not an empty prediction."""


class ProviderIncompleteError(ProviderResponseError):
    """Provider returned an incomplete response that cannot be interpreted."""


class ProviderSchemaError(ProviderResponseError):
    """Provider rejected or failed the requested strict structured-output schema."""


class ProviderOutputBudgetError(ModelGatewayError):
    pass


class OutputSchemaMismatchError(ModelGatewayError):
    pass


class StructuredOutputError(ModelGatewayError):
    category: str

    def __init__(
        self,
        message: str = "",
        repair_hint: str | None = None,
        diagnostic: object | None = None,
    ) -> None:
        super().__init__(message)
        self.repair_hint = repair_hint
        self.diagnostic = diagnostic


class InvalidModelJsonError(StructuredOutputError):
    category = "invalid_model_json"


class InvalidModelOutputShapeError(StructuredOutputError):
    category = "invalid_model_output_shape"


class ModelOutputValidationError(StructuredOutputError):
    category = "model_output_validation_failed"


class StructuredOutputFailedError(ModelGatewayError):
    def __init__(self, category: str, diagnostic: object | None = None) -> None:
        self.category = category
        self.diagnostic = diagnostic
        super().__init__(f"Structured output failed: {category}")
