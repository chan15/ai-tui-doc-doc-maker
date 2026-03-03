"""
fetch_and_translate.py

Fetches slash command documentation from:
  1. Google Gemini CLI (GitHub raw markdown)
  2. GitHub Copilot CLI (docs HTML page)

Translates both into Traditional Chinese using the Gemini API,
then writes a combined markdown file: output.md

On each run, diffs the raw source content against the previous run,
prepends changes to changelog.md if anything changed, and skips
translation entirely when the source is unchanged.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from difflib import unified_diff
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

GEMINI_CLI_URL = "https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/reference/commands.md"
GITHUB_COPILOT_URL = "https://docs.github.com/en/copilot/reference/cli-command-reference"
OPENAI_CODEX_URL = "https://developers.openai.com/codex/cli/slash-commands"

OUTPUT_FILE = "output.md"
CACHE_FILE = "_cache.json"
CHANGELOG_FILE = "changelog.md"
TRANSLATE_MODEL = "gemini-2.0-flash"
CHANGELOG_MAX_ENTRIES = int(os.environ.get("CHANGELOG_MAX_ENTRIES", "10"))

CHANGELOG_HEADER = ("###### tags: `ai` `gemini` `copilot` `codex`\n\n"
                    "# Gemini, GitHub Copilot & OpenAI Codex CLI 指令更新 Changelog\n\n")
ENTRY_SEPARATOR = "\n---\n\n"


# ── Changelog helpers ──────────────────────────────────────────────────────────


def parse_changelog(content: str) -> tuple[str, list[str]]:
    """
    Split changelog content into (header, entries).
    Each entry starts with '## ' and is separated by ENTRY_SEPARATOR.
    """
    if content.startswith("###### tags"):
        # Header ends at the first '## ' entry
        idx = content.find("\n## ")
        if idx == -1:
            return content, []
        header = content[: idx + 1]  # include the trailing newline
        body = content[idx + 1:]
    else:
        header = CHANGELOG_HEADER
        body = content

    # Split on separator; filter empty chunks
    raw_entries = body.split(ENTRY_SEPARATOR)
    entries = [e for e in raw_entries if e.strip().startswith("## ")]
    return header, entries


def build_changelog(header: str, entries: list[str]) -> str:
    """Reassemble header + entries into a changelog string."""
    if not entries:
        return header
    return header + ENTRY_SEPARATOR.join(entries) + ENTRY_SEPARATOR


# ── Cache helpers ──────────────────────────────────────────────────────────────


def load_cache() -> dict:
    """Load the previous run's raw source content from cache."""
    path = Path(CACHE_FILE)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_cache(data: dict) -> None:
    Path(CACHE_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Diff helper ────────────────────────────────────────────────────────────────


def build_diff_markdown(old: str, new: str, title: str) -> str:
    """
    Return a markdown section showing unified diff between old and new source.
    Returns an empty string if there are no changes.
    """
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = list(unified_diff(old_lines, new_lines, fromfile="上一版", tofile="本次", lineterm=""))
    if not diff:
        return ""
    body = "".join(diff)
    return f"### {title}\n\n```diff\n{body}\n```\n"


# ── Fetch helpers ──────────────────────────────────────────────────────────────


def fetch_gemini_cli_docs() -> str:
    """Fetch the Gemini CLI commands reference as raw markdown."""
    print(f"Fetching Gemini CLI docs from {GEMINI_CLI_URL} …")
    resp = requests.get(GEMINI_CLI_URL, timeout=30)
    resp.raise_for_status()
    return resp.text


def fetch_github_copilot_docs() -> str:
    """
    Fetch the GitHub Copilot CLI reference page and extract the meaningful
    text content while preserving table structure as markdown.
    """
    print(f"Fetching GitHub Copilot CLI docs from {GITHUB_COPILOT_URL} …")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; copilot-catch/1.0)"}
    resp = requests.get(GITHUB_COPILOT_URL, timeout=30, headers=headers)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # GitHub Docs puts the main article content in <article> or the main div
    article = soup.find("article") or soup.find("main") or soup.body

    lines: list[str] = []
    for elem in article.descendants:
        # Only process direct tag nodes (skip NavigableString children we'll
        # handle via their parent)
        if not hasattr(elem, "name"):
            continue

        tag = elem.name

        if tag in ("h2", "h3", "h4"):
            level = int(tag[1])
            text = elem.get_text(strip=True)
            if text:
                lines.append(f"\n{'#' * level} {text}\n")

        elif tag == "table":
            # Convert HTML table to markdown table
            rows = elem.find_all("tr")
            for i, row in enumerate(rows):
                cells = [c.get_text(separator=" ", strip=True).replace("|", r"\|") for c in row.find_all(["th", "td"])]
                if not any(cells):
                    continue
                lines.append("| " + " | ".join(cells) + " |")
                if i == 0:
                    lines.append("| " + " | ".join(["---"] * len(cells)) + " |")

        elif tag == "p":
            text = elem.get_text(strip=True)
            if text and elem.parent.name not in ("td", "th", "li"):
                lines.append(f"\n{text}\n")

    # De-duplicate consecutive blank lines
    content = "\n".join(lines)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def fetch_openai_codex_docs() -> str:
    """
    Fetch the OpenAI Codex CLI reference page and extract the meaningful
    text content while preserving table structure as markdown.
    """
    print(f"Fetching OpenAI Codex CLI docs from {OPENAI_CODEX_URL} …")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; codex-catch/1.0)"}
    resp = requests.get(OPENAI_CODEX_URL, timeout=30, headers=headers)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # OpenAI docs usually use <main> or <article>
    article = soup.find("main") or soup.find("article") or soup.body

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
                cells = [c.get_text(separator=" ", strip=True).replace("|", r"\|") for c in row.find_all(["th", "td"])]
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
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


# ── Translation ────────────────────────────────────────────────────────────────


def translate_with_gemini(content: str, source_title: str) -> str:
    """
    Send content to Gemini API and return translated Traditional Chinese markdown.
    Command names (e.g. /slash-command, @symbol, !bang) are preserved as-is.
    """
    print(f"Translating '{source_title}' via Gemini API …")
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""你是一位技術文件翻譯專家。請將以下 markdown 內容翻譯成繁體中文，並遵守以下規則：

1. 保留所有 markdown 格式（標題、表格、程式碼區塊、清單等）。
2. 指令名稱（如 `/command`、`@symbol`、`!bang`、`--flag`、`UPPER_CASE` 變數）**不翻譯**，原樣保留。
3. 技術術語可保留英文，在首次出現時於括號內附上繁體中文說明。
4. 翻譯後的說明文字使用自然流暢的繁體中文。

來源：{source_title}

---

{content}
"""

    response = client.models.generate_content(model=TRANSLATE_MODEL, contents=prompt, )
    return response.text


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY is not set. Add it to your .env file.", file=sys.stderr)
        sys.exit(1)

    now_dt = datetime.now(timezone.utc)
    now_str = now_dt.strftime("%Y-%m-%d %H:%M UTC")

    # 1. Load previous cache
    cache = load_cache()

    # 2. Fetch raw content
    gemini_cli_raw = fetch_gemini_cli_docs()
    github_copilot_raw = fetch_github_copilot_docs()
    openai_codex_raw = fetch_openai_codex_docs()

    # 3. Compute diffs against cached source
    diff_gemini = build_diff_markdown(cache.get("gemini_cli", ""), gemini_cli_raw, "Google Gemini CLI")
    diff_copilot = build_diff_markdown(cache.get("github_copilot", ""), github_copilot_raw, "GitHub Copilot CLI")
    diff_codex = build_diff_markdown(cache.get("openai_codex", ""), openai_codex_raw, "OpenAI Codex CLI")

    # 4. Prepend to changelog.md if anything changed
    if diff_gemini or diff_copilot or diff_codex:
        is_first_run = not cache
        diff_note = "（首次執行，無前次資料可比較）" if is_first_run else ""
        diff_sections = (
                (diff_gemini or "### Google Gemini CLI\n\n（無變更）\n") + "\n" +
                (diff_copilot or "### GitHub Copilot CLI\n\n（無變更）\n") + "\n" +
                (diff_codex or "### OpenAI Codex CLI\n\n（無變更）\n")
        )
        new_entry = f"## {now_str} {diff_note}\n\n{diff_sections}"

        changelog_path = Path(CHANGELOG_FILE)
        existing = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else ""
        header, entries = parse_changelog(existing)
        entries = [new_entry] + entries
        if CHANGELOG_MAX_ENTRIES > 0:
            entries = entries[:CHANGELOG_MAX_ENTRIES]
        changelog_path.write_text(build_changelog(header if existing else CHANGELOG_HEADER, entries), encoding="utf-8")
        print(f"📋  Changelog updated: {CHANGELOG_FILE} ({len(entries)} entries)")
    else:
        print("📋  No source changes detected, skipping changelog.")

    # 5. Save updated cache
    save_cache({
        "gemini_cli": gemini_cli_raw,
        "github_copilot": github_copilot_raw,
        "openai_codex": openai_codex_raw
    })

    # 6. If nothing changed, skip translation entirely
    if not diff_gemini and not diff_copilot and not diff_codex:
        print("⏭️   No changes detected, skipping translation.")
        return

    # 7. Translate all
    gemini_cli_translated = translate_with_gemini(gemini_cli_raw, "Google Gemini CLI")
    github_copilot_translated = translate_with_gemini(github_copilot_raw, "GitHub Copilot CLI")
    openai_codex_translated = translate_with_gemini(openai_codex_raw, "OpenAI Codex CLI")

    # 8. Assemble output markdown
    output = f"""###### tags: `ai` `gemini` `copilot` `codex`

# Gemini, GitHub Copilot & OpenAI Codex CLI 指令參考

> 自動抓取並翻譯，更新時間：{now_str}
>
> 原始來源：
> - [Google Gemini CLI commands]({GEMINI_CLI_URL})
> - [GitHub Copilot CLI reference]({GITHUB_COPILOT_URL})
> - [OpenAI Codex CLI reference]({OPENAI_CODEX_URL})

## 目錄

- [Google Gemini CLI](#Google-Gemini-CLI)
- [GitHub Copilot CLI](#GitHub-Copilot-CLI)
- [OpenAI Codex CLI](#OpenAI-Codex-CLI)

---

## Google Gemini CLI

{gemini_cli_translated}

---

## GitHub Copilot CLI

{github_copilot_translated}

---

## OpenAI Codex CLI

{openai_codex_translated}
"""

    # 9. Write output file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"✅  Done! Output written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
