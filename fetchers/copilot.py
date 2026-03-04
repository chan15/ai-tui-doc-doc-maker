from .base import HtmlFetcher


class GitHubCopilotFetcher(HtmlFetcher):
    """Fetcher for GitHub Copilot CLI docs."""
    NAME = "GitHub Copilot CLI"
    URL = "https://docs.github.com/en/copilot/reference/cli-command-reference"
    USER_AGENT = "Mozilla/5.0 (compatible; copilot-catch/1.0)"
    CONTAINERS = ["article", "main"]
