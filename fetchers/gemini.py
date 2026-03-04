import requests

from .base import DocFetcher


class GeminiFetcher(DocFetcher):
    """Fetcher for Gemini CLI docs (raw markdown)."""
    NAME = "Google Gemini CLI"
    URL = "https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/reference/commands.md"

    def fetch(self) -> str:
        print(f"Fetching {self.NAME} from {self.URL} …")
        resp = requests.get(self.URL, timeout=30)
        resp.raise_for_status()
        return resp.text
