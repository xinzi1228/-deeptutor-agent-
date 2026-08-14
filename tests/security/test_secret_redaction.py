from deeptutor.services.secrets.redaction import redact_secrets


def test_recursive_redaction_removes_secret_fields_and_bearer_tokens():
    payload = {
        "api_key": "sk-secret-value",
        "nested": {
            "Authorization": "Bearer token-value",
            "safe": "visible",
        },
        "items": [{"api_token": "token"}],
    }

    redacted = redact_secrets(payload)

    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["Authorization"] == "[REDACTED]"
    assert redacted["nested"]["safe"] == "visible"
    assert redacted["items"][0]["api_token"] == "[REDACTED]"


def test_string_redaction_covers_common_provider_error_formats():
    message = "request failed api_key=sk-abcdefghijk token:opaque-value"

    redacted = redact_secrets(message)

    assert "sk-abcdefghijk" not in redacted
    assert "opaque-value" not in redacted
