"""Text helpers shared by the readers: home-path shortening and length caps."""

import re


# An absolute home path: at the start of the text, after a character that cannot be part
# of a path, or after "file://". Repository paths (src/home/x.py) and web addresses
# (example.com/home/x) do not match.
_HOME = re.compile(r"""(?:(?:(?<![\w./~-])|(?<=file://))(?:/Users/|/home/)|(?<!\w)[A-Za-z]:\\Users\\)[^/\\\s"'<>:;,)]+""")

ERROR_CHARS = 2000    # copied error text: exception messages, failure reasons, log lines
OUTPUT_CHARS = 20000  # a copied patch


def redact(text: str) -> str:
    """Replace absolute home-directory prefixes with "~". Everything else is kept verbatim."""
    return _HOME.sub("~", text)


def clip(text: str, limit: int) -> str:
    """The first `limit` characters, with a note saying how many were left out."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n[{len(text) - limit} more characters not copied]"
