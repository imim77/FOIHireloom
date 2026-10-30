import html
import re

BLOCK_TAG = re.compile(r"</?(?:p|br|li|ul|ol|div|h[1-6]|tr|table)\b[^>]*>", re.I)
TAG = re.compile(r"<[^>]*>")
DANGLING_TAG = re.compile(r"<[^>]*$")
NBSP = re.compile(r"&nbsp;", re.I)


def decode_entities(text: str) -> str:
    """Undo HZZ's repeated escaping, e.g. "&amp;amp;AMP;NBSP;"."""
    for _ in range(5):
        decoded = html.unescape(NBSP.sub(" ", text))
        if decoded == text:
            break
        text = decoded
    return text


def html_to_text(markup: str) -> str | None:
    """Plain text of an HTML fragment; block elements start new lines.

    A tag cut off at the end is dropped. Entities left after the tags are
    removed are decoded once, so escaped markup stays text.
    """
    text = html.unescape(TAG.sub("", DANGLING_TAG.sub("", BLOCK_TAG.sub("\n", markup))))
    lines = (" ".join(line.replace("\xa0", " ").split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line) or None
