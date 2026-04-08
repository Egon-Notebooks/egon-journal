"""Tests for egon.linker."""
from pathlib import Path

from egon.linker import index_graph, inject_wikilinks, load_topics


class TestLoadTopics:
    def test_loads_lines(self, tmp_path):
        f = tmp_path / "TOPICS.txt"
        f.write_text("Sleep and mental health\nUnderstanding anxiety\n")
        topics = load_topics(f)
        assert topics == ["Sleep and mental health", "Understanding anxiety"]

    def test_skips_blank_lines(self, tmp_path):
        f = tmp_path / "TOPICS.txt"
        f.write_text("Topic A\n\nTopic B\n  \nTopic C\n")
        topics = load_topics(f)
        assert topics == ["Topic A", "Topic B", "Topic C"]

    def test_returns_empty_list_if_file_missing(self, tmp_path):
        topics = load_topics(tmp_path / "nonexistent.txt")
        assert topics == []


class TestInjectWikilinks:
    def test_injects_link(self):
        body = "Rumination is a common pattern.\n"
        result = inject_wikilinks(body, ["Rumination"])
        assert "[[Rumination]]" in result

    def test_does_not_double_link(self):
        body = "[[Rumination]] is already linked.\n"
        result = inject_wikilinks(body, ["Rumination"])
        assert result.count("[[Rumination]]") == 1

    def test_only_first_occurrence_linked(self):
        body = "Rumination here. Rumination again.\n"
        result = inject_wikilinks(body, ["Rumination"])
        assert result.count("[[Rumination]]") == 1

    def test_longer_match_takes_priority(self):
        body = "Anxiety disorders are different from Anxiety.\n"
        result = inject_wikilinks(body, ["Anxiety", "Anxiety disorders"])
        # "Anxiety disorders" should be matched first (longer)
        assert "[[Anxiety disorders]]" in result

    def test_multiple_topics(self):
        body = "Sleep affects mood. Anxiety is common.\n"
        result = inject_wikilinks(body, ["Sleep", "Anxiety"])
        assert "[[Sleep]]" in result
        assert "[[Anxiety]]" in result

    def test_no_topics_returns_body_unchanged(self):
        body = "Some text.\n"
        assert inject_wikilinks(body, []) == body

    def test_topic_not_in_body_leaves_body_unchanged(self):
        body = "Nothing relevant here.\n"
        result = inject_wikilinks(body, ["Rumination"])
        assert "[[" not in result


class TestIndexGraph:
    def _make_node(self, path: Path, title: str, node_type: str = "article") -> None:
        path.write_text(
            f"---\ntitle: {title!r}\ndate: 2026-01-01\ntype: {node_type}\n"
            f"tags: []\negon_version: '1'\n---\n\nBody.\n",
            encoding="utf-8",
        )

    def test_returns_titles(self, tmp_path):
        self._make_node(tmp_path / "A.md", "Sleep and mental health")
        self._make_node(tmp_path / "B.md", "Understanding anxiety")
        titles = index_graph(tmp_path)
        assert "Sleep and mental health" in titles
        assert "Understanding anxiety" in titles

    def test_skips_files_without_frontmatter(self, tmp_path):
        (tmp_path / "plain.md").write_text("# Just a heading\nNo frontmatter.\n")
        titles = index_graph(tmp_path)
        assert titles == []

    def test_recurses_into_subdirectories(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        self._make_node(sub / "C.md", "Building a daily routine")
        titles = index_graph(tmp_path)
        assert "Building a daily routine" in titles

    def test_returns_empty_for_empty_dir(self, tmp_path):
        assert index_graph(tmp_path) == []
