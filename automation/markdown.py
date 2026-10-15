"""Render untrusted values as Markdown text rather than markup."""

import html
import re


def markdown_text(value: str) -> str:
    value = html.escape(" ".join(value.split()), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|])", r"\\\1", value)
