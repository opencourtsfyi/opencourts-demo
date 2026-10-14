"""
Internationalization (i18n) support for OpenCourts ETL pipeline.
Loads localized user-facing strings from UTF-8 JSON locale catalogs.
"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
from typing import Any, Generator

DEFAULT_LOCALE = "en"
ENV_LOCALE_KEY = "OPENCOURTS_LOCALE"
FALLBACK_ENV_LOCALE_KEY = "LOCALE"
SYSTEM_LANG_KEY = "LANG"

LOCALE_EXT = ".json"
SEPARATOR_UNDERSCORE = "_"
SEPARATOR_HYPHEN = "-"
SEPARATOR_DOT = "."

LOCALES_DIRECTORY = Path(__file__).resolve().parent / "locales"

_catalogs: dict[str, dict[str, Any]] = {}
_current_locale: str | None = None


def get_current_locale() -> str:
    """Returns the currently active locale code."""
    if _current_locale:
        return _current_locale
    env_locale = os.environ.get(ENV_LOCALE_KEY) or os.environ.get(FALLBACK_ENV_LOCALE_KEY)
    if env_locale:
        return env_locale
    system_lang = os.environ.get(SYSTEM_LANG_KEY, "")
    if system_lang:
        lang_code = system_lang.split(SEPARATOR_DOT)[0].split(SEPARATOR_UNDERSCORE)[0]
        if lang_code:
            return lang_code
    return DEFAULT_LOCALE


def set_locale(locale: str | None) -> None:
    """Sets the active locale code globally for the process."""
    global _current_locale
    _current_locale = locale


@contextmanager
def use_locale(locale: str) -> Generator[None, None, None]:
    """Context manager for temporarily overriding the active locale."""
    global _current_locale
    previous = _current_locale
    _current_locale = locale
    try:
        yield
    finally:
        _current_locale = previous


def _resolve_locale_file(locale: str) -> Path | None:
    """Finds the appropriate JSON locale file, checking exact then base language."""
    direct_file = LOCALES_DIRECTORY / f"{locale}{LOCALE_EXT}"
    if direct_file.is_file():
        return direct_file

    # Normalize e.g. en_US or en-US to base language 'en'
    if SEPARATOR_UNDERSCORE in locale:
        base_locale = locale.split(SEPARATOR_UNDERSCORE)[0]
        base_file = LOCALES_DIRECTORY / f"{base_locale}{LOCALE_EXT}"
        if base_file.is_file():
            return base_file

    if SEPARATOR_HYPHEN in locale:
        base_locale = locale.split(SEPARATOR_HYPHEN)[0]
        base_file = LOCALES_DIRECTORY / f"{base_locale}{LOCALE_EXT}"
        if base_file.is_file():
            return base_file

    # Fall back to default locale
    fallback_file = LOCALES_DIRECTORY / f"{DEFAULT_LOCALE}{LOCALE_EXT}"
    if fallback_file.is_file():
        return fallback_file

    return None


def load_catalog(locale: str) -> dict[str, Any]:
    """Loads and caches the translation dictionary for the given locale."""
    if locale in _catalogs:
        return _catalogs[locale]

    target_file = _resolve_locale_file(locale)
    if target_file and target_file.is_file():
        with open(target_file, mode="r", encoding="utf-8") as f:
            catalog = json.load(f)
            _catalogs[locale] = catalog
            return catalog

    return {}


def _lookup_path(data: dict[str, Any], key: str) -> str | None:
    """Looks up a nested translation using dot notation or exact key match."""
    if key in data and isinstance(data[key], str):
        return data[key]

    parts = key.split(SEPARATOR_DOT)
    node: Any = data
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node if isinstance(node, str) else None


def t(key: str, locale: str | None = None, **kwargs: Any) -> str:
    """Translates a message key into the active or specified locale.

    Args:
        key: Dot-separated translation key (e.g. 'downloader.log_attempt_download').
        locale: Optional locale override (e.g. 'es'). Defaults to active locale.
        **kwargs: Format values to interpolate into the translated string template.

    Returns:
        Formatted translated string, or key if no translation was found.
    """
    active_locale = locale or get_current_locale()
    catalog = load_catalog(active_locale)
    template = _lookup_path(catalog, key)

    if template is None and active_locale != DEFAULT_LOCALE:
        fallback_catalog = load_catalog(DEFAULT_LOCALE)
        template = _lookup_path(fallback_catalog, key)

    if template is None:
        template = key

    if kwargs:
        return template.format(**kwargs)
    return template


# Common alias for standard gettext convention
_ = t

