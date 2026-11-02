"""The only file that talks to the Claude API."""
import logging

from anthropic import Anthropic, APIError

log = logging.getLogger("mushai.claude")


class ClaudeError(Exception):
    """Any failure talking to the Claude API."""


class ClaudeClient:
    def __init__(self, api_key=None, timeout=30.0):
        # api_key=None -> the SDK falls back to the ANTHROPIC_API_KEY environment variable
        self._client = Anthropic(api_key=api_key or None, timeout=timeout, max_retries=1)

    def reply(self, system, messages, *, model, max_tokens, effort=None):
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,  # must end with a user turn
        }
        # No temperature/top_p/top_k: Claude 5.5 models reject non-default values.
        if effort:
            kwargs["output_config"] = {"effort": effort}
        try:
            response = self._client.messages.create(**kwargs)
        except APIError as exc:
            raise ClaudeError(f"{type(exc).__name__}: {exc}") from exc

        # The reply can contain thinking blocks too; keep only the text.
        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        ).strip()
        if not text:
            log.warning(
                "Empty reply (stop_reason=%s). If this is max_tokens, raise MAX_TOKENS.",
                response.stop_reason,
            )
        return text
