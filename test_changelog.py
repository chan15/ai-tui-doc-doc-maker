"""
test_changelog.py

Tests for changelog entry parsing, building, and trimming logic.
"""

from fetch_and_translate import (CHANGELOG_HEADER, build_changelog, parse_changelog, build_diff_markdown)


def make_entry(n: int) -> str:
    return (f"## 2026-01-{n:02d} 00:00 UTC\n\n"
            f"### Google Gemini CLI\n\n（無變更）\n\n"
            f"### GitHub Copilot CLI\n\n（無變更）\n\n"
            f"### OpenAI Codex CLI\n\n（無變更）\n")


def make_changelog(num_entries: int) -> str:
    entries = [make_entry(i + 1) for i in range(num_entries)]
    return build_changelog(CHANGELOG_HEADER, entries)


# ── build_diff_markdown ────────────────────────────────────────────────────────


def test_build_diff_markdown_no_change():
    res = build_diff_markdown("hello", "hello", "Test Title")
    assert res == ""


def test_build_diff_markdown_with_change():
    res = build_diff_markdown("old line", "new line", "Test Title")
    assert "### Test Title" in res
    assert "```diff" in res
    assert "-old line" in res
    assert "+new line" in res


# ── parse_changelog ────────────────────────────────────────────────────────────


def test_parse_empty_string():
    header, entries = parse_changelog("")
    assert entries == []


def test_parse_fresh_changelog():
    content = make_changelog(3)
    header, entries = parse_changelog(content)
    assert header.startswith("###### tags")
    assert "`codex`" in header  # Verify the new tag is present
    assert len(entries) == 3


def test_parse_preserves_order():
    content = make_changelog(3)
    _, entries = parse_changelog(content)
    assert "2026-01-01" in entries[0]
    assert "2026-01-02" in entries[1]
    assert "2026-01-03" in entries[2]


# ── trim via slice (behaviour tested end-to-end) ──────────────────────────────


def test_no_trim_when_under_limit():
    content = make_changelog(5)
    _, entries = parse_changelog(content)
    new_entry = make_entry(99)
    entries = [new_entry] + entries
    entries = entries[:10]  # max=10, 6 entries → no trim
    assert len(entries) == 6


def test_no_trim_when_exactly_at_limit():
    content = make_changelog(9)
    _, entries = parse_changelog(content)
    new_entry = make_entry(99)
    entries = [new_entry] + entries
    entries = entries[:10]  # max=10, exactly 10 → no trim
    assert len(entries) == 10


def test_trim_oldest_when_over_limit():
    content = make_changelog(10)
    _, entries = parse_changelog(content)
    new_entry = make_entry(99)
    entries = [new_entry] + entries
    entries = entries[:10]  # max=10, 11 → drop last
    assert len(entries) == 10
    assert "2026-01-99" in entries[0]  # newest kept
    assert "2026-01-10" not in entries[-1]  # oldest dropped


def test_max_one_keeps_only_newest():
    content = make_changelog(5)
    _, entries = parse_changelog(content)
    new_entry = make_entry(99)
    entries = [new_entry] + entries
    entries = entries[:1]  # max=1
    assert len(entries) == 1
    assert "2026-01-99" in entries[0]


# ── build_changelog ────────────────────────────────────────────────────────────


def test_build_roundtrip():
    content = make_changelog(3)
    header, entries = parse_changelog(content)
    rebuilt = build_changelog(header, entries)
    # Re-parse should yield same entries
    _, entries2 = parse_changelog(rebuilt)
    assert len(entries2) == 3


def test_first_run_creates_header():
    """Simulates first run: empty existing changelog."""
    new_entry = make_entry(1)
    header, entries = parse_changelog("")
    entries = [new_entry] + entries
    result = build_changelog(CHANGELOG_HEADER, entries)
    assert result.startswith("###### tags")
    assert "## 2026-01-01" in result
