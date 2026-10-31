"""Report rendering (JSON / text / Markdown / HTML)."""

from typing import Dict

from ..models import AnalysisResult
from .html import to_html
from .render import to_json, to_markdown, to_text

__all__ = ["render", "to_json", "to_text", "to_markdown", "to_html", "FORMATS"]

FORMATS = ("json", "text", "markdown", "html")


def render(result: AnalysisResult, fmt: str = "text", lang: str = "en") -> str:
    fmt = (fmt or "text").lower()
    if fmt == "json":
        return to_json(result)
    if fmt == "markdown" or fmt == "md":
        return to_markdown(result, lang=lang)
    if fmt == "html":
        return to_html(result, lang=lang)
    return to_text(result, lang=lang)
