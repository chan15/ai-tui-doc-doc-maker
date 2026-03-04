import re
from abc import ABC, abstractmethod

import requests
from bs4 import BeautifulSoup


class DocFetcher(ABC):
    """Abstract base class for all document fetchers."""
    NAME = ""
    URL = ""

    @abstractmethod
    def fetch(self) -> str:
        """Fetch content from the source and return as markdown string."""
        pass


class HtmlFetcher(DocFetcher):
    """Base fetcher for HTML-based docs that need conversion to markdown."""
    USER_AGENT = "Mozilla/5.0 (compatible; generic-catch/1.0)"
    CONTAINERS = ["main", "article"]

    def fetch(self) -> str:
        print(f"Fetching {self.NAME} from {self.URL} …")
        headers = {"User-Agent": self.USER_AGENT}
        resp = requests.get(self.URL, timeout=30, headers=headers)
        resp.raise_for_status()
        return self._parse_html_to_md(resp.text)

    def _parse_html_to_md(self, html_content: str) -> str:
        soup = BeautifulSoup(html_content, "html.parser")
        article = None
        for tag in self.CONTAINERS:
            article = soup.find(tag)
            if article:
                break
        article = article or soup.body

        lines: list[str] = []
        for elem in article.descendants:
            if not hasattr(elem, "name"):
                continue

            tag = elem.name
            if tag in ("h2", "h3", "h4"):
                level = int(tag[1])
                text = elem.get_text(strip=True)
                if text:
                    lines.append(f"\n{'#' * level} {text}\n")
            elif tag == "table":
                rows = elem.find_all("tr")
                for i, row in enumerate(rows):
                    cells = [c.get_text(separator=" ", strip=True).replace("|", r"\|") for c in
                             row.find_all(["th", "td"])]
                    if not any(cells):
                        continue
                    lines.append("| " + " | ".join(cells) + " |")
                    if i == 0:
                        lines.append("| " + " | ".join(["---"] * len(cells)) + " |")
            elif tag == "p":
                text = elem.get_text(strip=True)
                if text and elem.parent.name not in ("td", "th", "li"):
                    lines.append(f"\n{text}\n")
            elif tag == "li":
                text = elem.get_text(strip=True)
                if text and elem.parent.name in ("ul", "ol"):
                    prefix = "1." if elem.parent.name == "ol" else "-"
                    lines.append(f"{prefix} {text}")

        content = "\n".join(lines)
        return re.sub(r"\n{3,}", "\n\n", content).strip()
