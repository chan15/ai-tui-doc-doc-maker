from .base import DocFetcher
from .codex import OpenAICodexFetcher
from .copilot import GitHubCopilotFetcher
from .gemini import GeminiFetcher

# 映射 ID 到對應的 Class
SOURCES = {
    "gemini_cli": GeminiFetcher,
    "github_copilot": GitHubCopilotFetcher,
    "openai_codex": OpenAICodexFetcher
}


class FetcherFactory:
    """Factory to create the appropriate fetcher."""

    @staticmethod
    def create_fetcher(source_id: str) -> DocFetcher:
        fetcher_class = SOURCES.get(source_id)
        if not fetcher_class:
            raise ValueError(f"Unknown source ID: {source_id}")

        return fetcher_class()
