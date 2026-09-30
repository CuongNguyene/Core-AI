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
    pass


class ProviderResponseError(ModelGatewayError):
    pass


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
