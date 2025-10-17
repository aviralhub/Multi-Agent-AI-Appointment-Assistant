import os
from typing import Dict, Any, Optional

try:
    import anthropic  # type: ignore
except Exception:
    anthropic = None


class LLMProvider:
    def generate(self, prompt: str, **kwargs: Any) -> str:
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    def __init__(self, model: Optional[str] = None) -> None:
        if anthropic is None:
            raise RuntimeError("anthropic package not available")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=int(os.getenv("ANTHROPIC_MAX_TOKENS", "512")),
            temperature=float(os.getenv("ANTHROPIC_TEMPERATURE", "0.2")),
            messages=[{"role": "user", "content": prompt}],
        )
        # Extract plain text from Anthropic content blocks
        parts = []
        for block in message.content or []:
            text = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else None)
            if text:
                parts.append(text)
        return "\n".join(parts)


class LocalEchoProvider(LLMProvider):
    def generate(self, prompt: str, **kwargs: Any) -> str:
        return f"[local] {prompt[:200]}"


def get_provider(name: str) -> LLMProvider:
    name = name.lower()
    if name == "anthropic":
        return AnthropicProvider()
    return LocalEchoProvider()
