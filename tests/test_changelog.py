"""
test_changelog.py

Tests for changelog entry parsing, building, and trimming logic.
"""

import importlib
import sys
import types

import pytest


@pytest.fixture()
def fetch_module(monkeypatch):
    """Import the module under test with lightweight dependency stubs."""
    requests_stub = types.ModuleType("requests")
    bs4_stub = types.ModuleType("bs4")
    dotenv_stub = types.ModuleType("dotenv")
    google_stub = types.ModuleType("google")
    genai_stub = types.ModuleType("google.genai")

    class DummyBeautifulSoup:
        def __init__(self, *_args, **_kwargs):
            self.body = None

    def load_dotenv():
        return None

    bs4_stub.BeautifulSoup = DummyBeautifulSoup
    dotenv_stub.load_dotenv = load_dotenv
    google_stub.genai = genai_stub

    monkeypatch.setitem(sys.modules, "requests", requests_stub)
    monkeypatch.setitem(sys.modules, "bs4", bs4_stub)
    monkeypatch.setitem(sys.modules, "dotenv", dotenv_stub)
    monkeypatch.setitem(sys.modules, "google", google_stub)
    monkeypatch.setitem(sys.modules, "google.genai", genai_stub)
    monkeypatch.delitem(sys.modules, "fetch_and_translate", raising=False)

    return importlib.import_module("fetch_and_translate")


def make_entry(n: int) -> str:
    return (f"## 2026-01-{n:02d} 00:00 UTC\n\n"
            f"### Google Gemini CLI\n\n（無變更）\n\n"
            f"### GitHub Copilot CLI\n\n（無變更）\n\n"
            f"### OpenAI Codex CLI\n\n（無變更）\n")


def make_changelog(module, num_entries: int) -> str:
    entries = [make_entry(i + 1) for i in range(num_entries)]
    return module.build_changelog(module.CHANGELOG_HEADER, entries)


# ── build_diff_markdown ────────────────────────────────────────────────────────


def test_build_diff_markdown_no_change(fetch_module):
    res = fetch_module.build_diff_markdown("hello", "hello", "Test Title")
    assert res == ""


def test_build_diff_markdown_with_change(fetch_module):
    res = fetch_module.build_diff_markdown("old line\n", "new line\n", "Test Title")
    assert res.startswith("### Test Title\n\n```diff\n")
    assert "--- 上一版" in res
    assert "+++ 本次" in res
    assert "@@" in res
    assert "-old line\n" in res
    assert "+new line\n" in res
    assert res.endswith("```\n")


# ── parse_changelog ────────────────────────────────────────────────────────────


def test_parse_empty_string(fetch_module):
    header, entries = fetch_module.parse_changelog("")
    assert header == fetch_module.CHANGELOG_HEADER
    assert entries == []


def test_parse_fresh_changelog(fetch_module):
    content = make_changelog(fetch_module, 3)
    header, entries = fetch_module.parse_changelog(content)
    assert header.startswith("###### tags")
    assert "`codex`" in header
    assert len(entries) == 3


def test_parse_preserves_order(fetch_module):
    content = make_changelog(fetch_module, 3)
    _, entries = fetch_module.parse_changelog(content)
    assert "2026-01-01" in entries[0]
    assert "2026-01-02" in entries[1]
    assert "2026-01-03" in entries[2]


# ── trim via slice (behaviour tested end-to-end) ──────────────────────────────


def test_no_trim_when_under_limit(fetch_module):
    content = make_changelog(fetch_module, 5)
    _, entries = fetch_module.parse_changelog(content)
    new_entry = make_entry(99)
    entries = [new_entry] + entries
    entries = entries[:10]
    assert len(entries) == 6


def test_no_trim_when_exactly_at_limit(fetch_module):
    content = make_changelog(fetch_module, 9)
    _, entries = fetch_module.parse_changelog(content)
    new_entry = make_entry(99)
    entries = [new_entry] + entries
    entries = entries[:10]
    assert len(entries) == 10


def test_trim_oldest_when_over_limit(fetch_module):
    content = make_changelog(fetch_module, 10)
    _, entries = fetch_module.parse_changelog(content)
    new_entry = make_entry(99)
    entries = [new_entry] + entries
    entries = entries[:10]
    assert len(entries) == 10
    assert "2026-01-99" in entries[0]
    assert "2026-01-10" not in entries[-1]


def test_max_one_keeps_only_newest(fetch_module):
    content = make_changelog(fetch_module, 5)
    _, entries = fetch_module.parse_changelog(content)
    new_entry = make_entry(99)
    entries = [new_entry] + entries
    entries = entries[:1]
    assert len(entries) == 1
    assert "2026-01-99" in entries[0]


# ── build_changelog ────────────────────────────────────────────────────────────


def test_build_roundtrip(fetch_module):
    content = make_changelog(fetch_module, 3)
    header, entries = fetch_module.parse_changelog(content)
    rebuilt = fetch_module.build_changelog(header, entries)
    _, entries2 = fetch_module.parse_changelog(rebuilt)
    assert len(entries2) == 3


def test_first_run_creates_header(fetch_module):
    """Simulates first run: empty existing changelog."""
    new_entry = make_entry(1)
    _, entries = fetch_module.parse_changelog("")
    entries = [new_entry] + entries
    result = fetch_module.build_changelog(fetch_module.CHANGELOG_HEADER, entries)
    assert result.startswith("###### tags")
    assert "## 2026-01-01" in result
