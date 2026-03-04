from .base import HtmlFetcher


class OpenAICodexFetcher(HtmlFetcher):
    """Fetcher for OpenAI Codex CLI docs."""
    NAME = "OpenAI Codex CLI"
    URL = "https://developers.openai.com/codex/cli/slash-commands"
    USER_AGENT = "Mozilla/5.0 (compatible; codex-catch/1.0)"
    CONTAINERS = ["main", "article"]
