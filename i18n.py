import json
import re
from pathlib import Path

import bpy


_TRANSLATION_DOMAIN = __package__ or "UnrealBlenderIO"
_LOCALE_ALIASES = {
    "zh_HANS": "zh_HANS",
    "zh_CN": "zh_HANS",
    "en_US": "en_US",
    "en_GB": "en_US",
}
_TRANSLATIONS = {}


def _i18n_dir() -> Path:
    return Path(__file__).resolve().parent / "i18n"


def _extract_placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", text))


def _read_locale_file(locale_code: str) -> dict[str, str]:
    file_path = _i18n_dir() / f"{locale_code}.json"
    if not file_path.exists():
        raise RuntimeError(f"i18n 文件不存在: {file_path}")
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise RuntimeError(f"i18n 文件格式错误（应为对象）: {file_path}")
    return data


def _validate_translations(all_data: dict[str, dict[str, str]]) -> None:
    base_locale = "en_US"
    base_data = all_data[base_locale]
    base_keys = set(base_data.keys())

    for locale, locale_data in all_data.items():
        locale_keys = set(locale_data.keys())
        missing = sorted(base_keys - locale_keys)
        extra = sorted(locale_keys - base_keys)
        if missing or extra:
            raise RuntimeError(
                f"i18n key 不一致 ({locale})，缺失: {missing[:5]}，多余: {extra[:5]}"
            )

        for key in base_keys:
            base_vars = _extract_placeholders(base_data[key])
            locale_vars = _extract_placeholders(locale_data[key])
            if base_vars != locale_vars:
                raise RuntimeError(
                    f"i18n 占位符不一致 ({locale}, key={key})，"
                    f"en_US={sorted(base_vars)}，{locale}={sorted(locale_vars)}"
                )


def load_translations(force: bool = False) -> None:
    if _TRANSLATIONS and not force:
        return
    all_data = {
        "en_US": _read_locale_file("en_US"),
        "zh_HANS": _read_locale_file("zh_HANS"),
    }
    _validate_translations(all_data)
    _TRANSLATIONS.clear()
    _TRANSLATIONS.update(all_data)


def _normalize_locale(locale: str) -> str:
    if not locale:
        return "en_US"
    if locale in _LOCALE_ALIASES:
        return _LOCALE_ALIASES[locale]
    if locale.startswith("zh"):
        return "zh_HANS"
    if locale.startswith("en"):
        return "en_US"
    return "en_US"


def get_current_locale() -> str:
    locale = ""
    try:
        locale = bpy.context.preferences.view.language
    except Exception:
        locale = ""

    if not locale or locale == "DEFAULT":
        locale = getattr(bpy.app.translations, "locale", "en_US")

    return _normalize_locale(locale)


def msgid(key: str) -> str:
    load_translations()
    return _TRANSLATIONS["en_US"].get(key, key)


def tr(key: str, **kwargs) -> str:
    load_translations()
    locale = get_current_locale()
    base_text = _TRANSLATIONS["en_US"].get(key, key)
    text = _TRANSLATIONS.get(locale, _TRANSLATIONS["en_US"]).get(key, base_text)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def _build_blender_translation_table() -> dict[str, dict[tuple[str, str], str]]:
    load_translations()
    base_data = _TRANSLATIONS["en_US"]
    table = {}

    for locale in ("en_US", "zh_HANS"):
        locale_data = _TRANSLATIONS[locale]
        locale_map = {}
        for key, english_msg in base_data.items():
            locale_map[("*", english_msg)] = locale_data[key]
        table[locale] = locale_map

    table["zh_CN"] = dict(table["zh_HANS"])
    return table


def register_translations() -> None:
    table = _build_blender_translation_table()
    try:
        bpy.app.translations.unregister(_TRANSLATION_DOMAIN)
    except Exception:
        pass
    bpy.app.translations.register(_TRANSLATION_DOMAIN, table)


def unregister_translations() -> None:
    try:
        bpy.app.translations.unregister(_TRANSLATION_DOMAIN)
    except Exception:
        pass
