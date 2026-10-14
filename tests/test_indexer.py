"""Tests for the indexer module."""

import pytest

from obsidian_rag.indexer import chunk_markdown, parse_frontmatter


class TestParseFrontmatter:
    def test_no_frontmatter(self):
        content = "# Hello\n\nThis is content."
        frontmatter, body = parse_frontmatter(content)
        assert frontmatter == {}
        assert body == content

    def test_with_frontmatter(self):
        content = """---
title: Test Note
tags:
  - test
  - example
---

# Hello

This is content."""
        frontmatter, body = parse_frontmatter(content)
        assert frontmatter["title"] == "Test Note"
        assert frontmatter["tags"] == ["test", "example"]
        assert body.startswith("# Hello")

    def test_invalid_yaml(self):
        content = """---
invalid: yaml: content
---

Content here."""
        frontmatter, body = parse_frontmatter(content)
        assert frontmatter == {}


class TestChunkMarkdown:
    def test_single_chunk_no_headings(self):
        """Short content without headings becomes one chunk."""
        content = "This is a simple note without headings."
        chunks = chunk_markdown(content, "test.md")
        assert len(chunks) == 1
        assert "simple note" in chunks[0].content

    def test_splits_on_headings(self):
        """Content with headings gets split at heading boundaries when large enough."""
        # Each section needs enough content to exceed chunk_size when combined
        section_text = "This is filler content for the section. " * 50
        content = f"""## First Section

{section_text}

## Second Section

{section_text}"""
        chunks = chunk_markdown(content, "test.md")
        assert len(chunks) >= 2

    def test_preserves_file_path(self):
        content = "## Test\n\nContent here that is long enough."
        chunks = chunk_markdown(content, "notes/test.md")
        assert all(c.file_path == "notes/test.md" for c in chunks)

    def test_extracts_frontmatter(self):
        """Frontmatter is parsed and stored in metadata, not in chunk content."""
        content = """---
tags:
  - project
---

## Section

Actual content here."""
        chunks = chunk_markdown(content, "test.md")
        assert len(chunks) >= 1
        # Frontmatter should not appear in chunk content
        assert "---" not in chunks[0].content or "tags" not in chunks[0].content

    def test_assigns_type_metadata(self):
        """Chunks get type metadata based on file path."""
        daily = chunk_markdown("Some content here.", "Daily Notes/2026-01-01.md")
        note = chunk_markdown("Some content here.", "Projects/foo.md")
        assert daily[0].metadata["type"] == "daily"
        assert note[0].metadata["type"] == "note"

    def test_empty_content_returns_empty(self):
        """Empty or whitespace-only content returns no chunks."""
        assert chunk_markdown("", "test.md") == []
        assert chunk_markdown("   \n\n  ", "test.md") == []


class TestExcalidrawDrawingData:
    BLOB = "N4KAkARALgngDgUwgLgAQQQDwMYEMA2AlgCYBOuA7hADTgQBuCpAzoQPYB" * 40

    def _note(self, fence: str = "compressed-json") -> str:
        return (
            "---\nexcalidraw-plugin: parsed\ntags: [excalidraw]\n---\n"
            "==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠==\n\n"
            "# Excalidraw Data\n\n## Text Elements\n"
            "Persona ^4w3FVofx\n\nPivot Framework ^4wPlPKKv\n\n"
            f"%%\n## Drawing\n```{fence}\n{self.BLOB}\n\n{self.BLOB}\n```\n%%\n"
        )

    def test_compressed_drawing_removed_text_kept(self):
        chunks = chunk_markdown(self._note(), "Excalidraw/d.excalidraw.md")
        text = "\n".join(c.content for c in chunks)
        assert self.BLOB[:40] not in text
        assert "Persona" in text and "Pivot Framework" in text

    def test_uncompressed_json_drawing_removed(self):
        chunks = chunk_markdown(self._note("json"), "Excalidraw/d.excalidraw.md")
        assert self.BLOB[:40] not in "\n".join(c.content for c in chunks)

    def test_banner_and_block_ids_removed(self):
        text = "\n".join(c.content for c in chunk_markdown(self._note(), "d.md"))
        assert "EXCALIDRAW VIEW" not in text
        assert "^4w3FVofx" not in text

    def test_regular_note_json_and_block_ids_untouched(self):
        content = (
            "# Config\n\nSee this paragraph for the setup details. ^setup1\n\n"
            '```json\n{"key": "value", "enabled": true, "retries": 3}\n```\n'
        )
        text = "\n".join(c.content for c in chunk_markdown(content, "Notes/config.md"))
        assert '"key": "value"' in text
        assert "^setup1" in text

    def test_compressed_json_removed_even_without_excalidraw_frontmatter(self):
        content = f"# Embedded\n\nA sketch of the triage flow.\n\n```compressed-json\n{self.BLOB}\n```\n"
        text = "\n".join(c.content for c in chunk_markdown(content, "Notes/n.md"))
        assert self.BLOB[:40] not in text
        assert "triage flow" in text
