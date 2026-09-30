from app.shared.i18n import localize_error_message, resolve_locale


def test_resolve_locale_supports_regional_vietnamese() -> None:
    assert resolve_locale("vi-VN,vi;q=0.9,en;q=0.8") == "vi"


def test_resolve_locale_falls_back_to_english() -> None:
    assert resolve_locale("fr-FR,fr;q=0.9") == "en"


def test_localize_error_message_keeps_unknown_code_fallback() -> None:
    assert (
        localize_error_message(code="unknown_code", message="Original message.", locale="vi")
        == "Original message."
    )
