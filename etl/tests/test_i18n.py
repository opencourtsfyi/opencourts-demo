"""
Tests for i18n.py internationalization module.
Verifies locale detection, context managers, catalog loading, path lookup, and translations.
"""

import json
from pathlib import Path
import pytest

import i18n
from i18n import (
    DEFAULT_LOCALE,
    ENV_LOCALE_KEY,
    FALLBACK_ENV_LOCALE_KEY,
    SYSTEM_LANG_KEY,
    _,
    _lookup_path,
    _resolve_locale_file,
    get_current_locale,
    load_catalog,
    set_locale,
    t,
    use_locale,
)

SAMPLE_FILENAME = "caseload_2024.pdf"
SAMPLE_ERROR_MESSAGE = "Connection reset"
EXPECTED_FALLBACK_KEY = "nonexistent.translation.key"


@pytest.fixture(autouse=True)
def reset_i18n_state(monkeypatch):
    """Ensure clean i18n global state and clean environment before and after every test."""
    set_locale(None)
    monkeypatch.delenv(ENV_LOCALE_KEY, raising=False)
    monkeypatch.delenv(FALLBACK_ENV_LOCALE_KEY, raising=False)
    monkeypatch.delenv(SYSTEM_LANG_KEY, raising=False)
    original_catalogs = i18n._catalogs.copy()
    yield
    set_locale(None)
    i18n._catalogs.clear()
    i18n._catalogs.update(original_catalogs)


class TestGetCurrentLocale:
    """Tests for get_current_locale detection logic and precedence."""

    def test_default_locale_when_no_env_or_override(self):
        assert get_current_locale() == DEFAULT_LOCALE

    def test_explicit_set_locale_takes_precedence(self, monkeypatch):
        monkeypatch.setenv(ENV_LOCALE_KEY, "es")
        set_locale("fr")
        assert get_current_locale() == "fr"

    def test_opencourts_env_locale(self, monkeypatch):
        monkeypatch.setenv(ENV_LOCALE_KEY, "es")
        assert get_current_locale() == "es"

    def test_fallback_env_locale(self, monkeypatch):
        monkeypatch.setenv(FALLBACK_ENV_LOCALE_KEY, "de")
        assert get_current_locale() == "de"

    def test_system_lang_with_charset(self, monkeypatch):
        monkeypatch.setenv(SYSTEM_LANG_KEY, "es_ES.UTF-8")
        assert get_current_locale() == "es"

    def test_system_lang_with_underscore_only(self, monkeypatch):
        monkeypatch.setenv(SYSTEM_LANG_KEY, "pt_BR")
        assert get_current_locale() == "pt"

    def test_precedence_chain(self, monkeypatch):
        # 1. System LANG lowest
        monkeypatch.setenv(SYSTEM_LANG_KEY, "de_DE.UTF-8")
        assert get_current_locale() == "de"

        # 2. LOCALE overrides LANG
        monkeypatch.setenv(FALLBACK_ENV_LOCALE_KEY, "it")
        assert get_current_locale() == "it"

        # 3. OPENCOURTS_LOCALE overrides LOCALE
        monkeypatch.setenv(ENV_LOCALE_KEY, "es")
        assert get_current_locale() == "es"

        # 4. set_locale overrides OPENCOURTS_LOCALE
        set_locale("fr")
        assert get_current_locale() == "fr"


class TestLocaleContextManager:
    """Tests for use_locale context manager."""

    def test_use_locale_switches_and_restores(self):
        set_locale("en")
        assert get_current_locale() == "en"

        with use_locale("es"):
            assert get_current_locale() == "es"

        assert get_current_locale() == "en"

    def test_use_locale_restores_on_exception(self):
        set_locale("en")

        with pytest.raises(RuntimeError):
            with use_locale("es"):
                assert get_current_locale() == "es"
                raise RuntimeError("Boom")

        assert get_current_locale() == "en"


class TestResolveLocaleFile:
    """Tests for _resolve_locale_file path resolution and fallbacks."""

    def test_resolve_exact_match(self):
        resolved = _resolve_locale_file("en")
        assert resolved is not None
        assert resolved.name == "en.json"

    def test_resolve_underscore_normalization(self):
        resolved = _resolve_locale_file("es_ES")
        assert resolved is not None
        assert resolved.name == "es.json"

    def test_resolve_hyphen_normalization(self):
        resolved = _resolve_locale_file("es-MX")
        assert resolved is not None
        assert resolved.name == "es.json"

    def test_resolve_fallback_to_default_locale(self):
        resolved = _resolve_locale_file("nonexistent_lang")
        assert resolved is not None
        assert resolved.name == f"{DEFAULT_LOCALE}.json"

    def test_resolve_returns_none_if_directory_has_no_default(self, monkeypatch, tmp_path):
        monkeypatch.setattr(i18n, "LOCALES_DIRECTORY", tmp_path)
        resolved = _resolve_locale_file("unknown")
        assert resolved is None


class TestLoadCatalog:
    """Tests for load_catalog reading and caching."""

    def test_load_catalog_success(self):
        catalog = load_catalog("en")
        assert "downloader" in catalog
        assert "orchestrator" in catalog

    def test_load_catalog_caches_result(self, monkeypatch):
        first_call = load_catalog("en")
        # Overwrite file resolution to return empty to verify cache is hit
        monkeypatch.setattr(i18n, "_resolve_locale_file", lambda loc: None)
        second_call = load_catalog("en")
        assert first_call is second_call

    def test_load_catalog_returns_empty_when_no_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(i18n, "LOCALES_DIRECTORY", tmp_path)
        i18n._catalogs.clear()
        catalog = load_catalog("nonexistent")
        assert catalog == {}


class TestLookupPath:
    """Tests for _lookup_path dot notation and boundary conditions."""

    def test_direct_key_lookup(self):
        data = {"hello": "world"}
        assert _lookup_path(data, "hello") == "world"

    def test_nested_dot_notation(self):
        data = {"downloader": {"status": {"success": "Done"}}}
        assert _lookup_path(data, "downloader.status.success") == "Done"

    def test_missing_nested_key_returns_none(self):
        data = {"downloader": {"status": "ok"}}
        assert _lookup_path(data, "downloader.status.missing") is None

    def test_missing_root_key_returns_none(self):
        data = {"downloader": "ok"}
        assert _lookup_path(data, "orchestrator.status") is None

    def test_non_string_leaf_returns_none(self):
        data = {"downloader": {"items": ["a", "b"]}}
        assert _lookup_path(data, "downloader.items") is None


class TestTranslateFunction:
    """Tests for t() and gettext alias _()."""

    def test_translate_in_default_locale(self):
        msg = t("downloader.log_attempt_download", filename=SAMPLE_FILENAME)
        assert msg == f"Attempting to download: {SAMPLE_FILENAME}"

    def test_translate_with_explicit_locale_param(self):
        msg_en = t("downloader.cli_description", locale="en")
        msg_es = t("downloader.cli_description", locale="es")
        assert msg_en == "Download SC Probate court reports."
        assert msg_es == "Descargar informes de los tribunales de sucesiones de SC."

    def test_translate_with_use_locale_context(self):
        with use_locale("es"):
            msg = t("downloader.cli_description")
            assert msg == "Descargar informes de los tribunales de sucesiones de SC."

    def test_translate_kwargs_formatting(self):
        msg = t(
            "downloader.log_failed_download_error",
            locale="en",
            filename=SAMPLE_FILENAME,
            error=SAMPLE_ERROR_MESSAGE,
        )
        assert msg == f"❌ Failed to download {SAMPLE_FILENAME}: {SAMPLE_ERROR_MESSAGE}"

    def test_translate_fallback_to_default_locale(self, monkeypatch):
        # Create a catalog with a key missing in 'es' but present in 'en'
        custom_es = {"downloader": {}}
        i18n._catalogs["custom_es"] = custom_es

        with use_locale("custom_es"):
            # Should fall back to 'en' translation
            msg = t("downloader.cli_description")
            assert msg == "Download SC Probate court reports."

    def test_translate_missing_key_returns_key_verbatim(self):
        assert t(EXPECTED_FALLBACK_KEY) == EXPECTED_FALLBACK_KEY

    def test_gettext_alias_matches_t(self):
        assert _("downloader.cli_description") == t("downloader.cli_description")
