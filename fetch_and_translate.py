"""
fetch_and_translate.py

Fetches slash command documentation from multiple sources.
Translates them into Traditional Chinese using Gemini API and maintains a changelog.
"""

import json
import os
import sys
from datetime import datetime, timezone
from difflib import unified_diff
from pathlib import Path

from dotenv import load_dotenv
from google import genai

# 從外部 package 導入 Fetcher 邏輯
from fetchers.factory import SOURCES, FetcherFactory

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

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
    if content.startswith("###### tags"):
        idx = content.find("\n## ")
        if idx == -1:
            return content, []
        header = content[: idx + 1]
        body = content[idx + 1:]
    else:
        header = CHANGELOG_HEADER
        body = content

    raw_entries = body.split(ENTRY_SEPARATOR)
    entries = [e for e in raw_entries if e.strip().startswith("## ")]
    return header, entries


def build_changelog(header: str, entries: list[str]) -> str:
    if not entries:
        return header
    return header + ENTRY_SEPARATOR.join(entries) + ENTRY_SEPARATOR


# ── Cache & Diff helpers ──────────────────────────────────────────────────────

def load_cache() -> dict:
    path = Path(CACHE_FILE)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_cache(data: dict) -> None:
    Path(CACHE_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_diff_markdown(old: str, new: str, title: str) -> str:
    diff = list(unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                             fromfile="上一版", tofile="本次", lineterm=""))
    if not diff:
        return ""
    return f"### {title}\n\n```diff\n{''.join(diff)}\n```\n"


# ── Translation ────────────────────────────────────────────────────────────────

def translate_with_gemini(content: str, source_title: str) -> str:
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
    response = client.models.generate_content(model=TRANSLATE_MODEL, contents=prompt)
    return response.text


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cache = load_cache()

    # 1. Fetch all using Factory
    raw_contents = {}
    for sid in SOURCES:
        fetcher = FetcherFactory.create_fetcher(sid)
        raw_contents[sid] = fetcher.fetch()

    # 2. Compute diffs
    diffs = {sid: build_diff_markdown(cache.get(sid, ""), content, SOURCES[sid].NAME)
             for sid, content in raw_contents.items()}
    any_changed = any(diffs.values())

    # 3. Update Changelog
    if any_changed:
        is_first_run = not cache
        diff_note = "（首次執行，無前次資料可比較）" if is_first_run else ""
        diff_sections = "\n".join([diffs[sid] or f"### {SOURCES[sid].NAME}\n\n（無變更）\n" for sid in SOURCES])
        new_entry = f"## {now_str} {diff_note}\n\n{diff_sections}"

        changelog_path = Path(CHANGELOG_FILE)
        existing = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else ""
        header, entries = parse_changelog(existing)
        entries = [new_entry] + entries
        if CHANGELOG_MAX_ENTRIES > 0:
            entries = entries[:CHANGELOG_MAX_ENTRIES]
        changelog_path.write_text(build_changelog(header if existing else CHANGELOG_HEADER, entries), encoding="utf-8")
        print(f"📋  Changelog updated.")
    else:
        print("📋  No source changes detected.")

    # 4. Save cache
    save_cache(raw_contents)

    if not any_changed:
        print("⏭️   No changes detected, skipping translation.")
        return

    # 5. Translate all
    translated = {sid: translate_with_gemini(content, SOURCES[sid].NAME)
                  for sid, content in raw_contents.items()}

    # 6. Assemble output markdown
    toc_items = [f"- [{SOURCES[sid].NAME}](#{SOURCES[sid].NAME.replace(' ', '-')})" for sid in SOURCES]
    source_links = [f"- [{SOURCES[sid].NAME}]({SOURCES[sid].URL})" for sid in SOURCES]
    content_sections = [f"## {SOURCES[sid].NAME}\n\n{translated[sid]}" for sid in SOURCES]

    final_output = f"""###### tags: `ai` `gemini` `copilot` `codex`

# Gemini, GitHub Copilot & OpenAI Codex CLI 指令參考

> 自動抓取並翻譯，更新時間：{now_str}

> 原始來源：
{"\n".join(source_links)}

## 目錄

{"\n".join(toc_items)}

---

{"\n\n---\n\n".join(content_sections)}
"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(final_output)

    print(f"✅  Done! Output written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
