"""Tests for egon.config — ReportConfig and load_report_config."""



from egon.config import _DEFAULTS, ReportConfig, load_report_config


class TestReportConfigEnabled:
    def test_explicit_true(self):
        cfg = ReportConfig(analyses={"wordcloud": True})
        assert cfg.enabled("wordcloud") is True

    def test_explicit_false(self):
        cfg = ReportConfig(analyses={"wordcloud": False})
        assert cfg.enabled("wordcloud") is False

    def test_falls_back_to_default_true(self):
        cfg = ReportConfig(analyses={})
        assert cfg.enabled("sentiment") is True  # default True

    def test_falls_back_to_default_false(self):
        cfg = ReportConfig(analyses={})
        assert cfg.enabled("wordcloud") is False  # default False

    def test_unknown_key_returns_true(self):
        # Unknown keys not in _DEFAULTS fall back to True
        cfg = ReportConfig(analyses={})
        assert cfg.enabled("nonexistent_analysis") is True

    def test_override_beats_default(self):
        cfg = ReportConfig(analyses={"sentiment": False})
        assert cfg.enabled("sentiment") is False


class TestDefaults:
    def test_wordcloud_is_disabled_by_default(self):
        assert _DEFAULTS["wordcloud"] is False

    def test_standard_analyses_enabled_by_default(self):
        for key in ("word_count", "sentiment", "bigfive", "mbti", "weight", "sleep", "exercise"):
            assert _DEFAULTS[key] is True, f"Expected {key!r} to default to True"

    def test_all_defaults_are_bool(self):
        for key, val in _DEFAULTS.items():
            assert isinstance(val, bool), f"_DEFAULTS[{key!r}] is not bool"


class TestLoadReportConfig:
    def test_missing_file_returns_empty_config(self, tmp_path):
        cfg = load_report_config(tmp_path / "nonexistent.toml")
        assert isinstance(cfg, ReportConfig)
        assert cfg.analyses == {}

    def test_reads_analyses_section(self, tmp_path):
        toml = tmp_path / "egon.toml"
        toml.write_text(
            "[report.analyses]\nwordcloud = true\nsentiment = false\n",
            encoding="utf-8",
        )
        cfg = load_report_config(toml)
        assert cfg.enabled("wordcloud") is True
        assert cfg.enabled("sentiment") is False

    def test_unknown_keys_are_ignored(self, tmp_path):
        toml = tmp_path / "egon.toml"
        toml.write_text(
            "[report.analyses]\nfuture_feature = true\n",
            encoding="utf-8",
        )
        cfg = load_report_config(toml)
        assert cfg.analyses == {}  # unknown key filtered out

    def test_empty_analyses_section(self, tmp_path):
        toml = tmp_path / "egon.toml"
        toml.write_text("[report.analyses]\n", encoding="utf-8")
        cfg = load_report_config(toml)
        assert cfg.analyses == {}

    def test_missing_analyses_section(self, tmp_path):
        toml = tmp_path / "egon.toml"
        toml.write_text("[other_section]\nfoo = 1\n", encoding="utf-8")
        cfg = load_report_config(toml)
        assert cfg.analyses == {}

    def test_partial_override(self, tmp_path):
        toml = tmp_path / "egon.toml"
        toml.write_text(
            "[report.analyses]\nwordcloud = true\n",
            encoding="utf-8",
        )
        cfg = load_report_config(toml)
        # wordcloud overridden to True
        assert cfg.enabled("wordcloud") is True
        # sentiment not in file → default True
        assert cfg.enabled("sentiment") is True
