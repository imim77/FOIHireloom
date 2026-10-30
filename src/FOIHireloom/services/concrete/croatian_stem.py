"""Light stemming of ASCII-folded Croatian query words.

Search terms match word prefixes, so cutting an ending off a query word lets
"njemacki" find "njemackog" and "kuharica" find titles written "KUHAR/ICA".
Only the query is stemmed; stored text is indexed whole. Sound changes such
as Rijeka/Rijeci are not undone.
"""

# Case endings, then the feminine -ica forms. -ka is left out: it would turn
# "osijeku" into "osije" and "vozacka" (licence) into "vozac" (driver).
ENDINGS = (
    "a", "e", "i", "o", "u", "eg", "em", "ih", "im", "og", "oj", "om", "ama", "ega", "emu", "ima", "oga", "ome",
    "omu", "evima", "ijama", "ovima", "ica", "ice", "ici", "icu", "icom", "icama",
)
# Shorter stems match unrelated words: "zadru" would become "zadr", as in "zadrzava".
MIN_STEM_LENGTH = 5
_LONGEST_FIRST = sorted(ENDINGS, key=len, reverse=True)


def stem(word: str) -> str:
    """Remove the longest known ending that leaves a stem of MIN_STEM_LENGTH letters."""
    if not word.isalpha():
        return word
    for ending in _LONGEST_FIRST:
        if word.endswith(ending) and len(word) - len(ending) >= MIN_STEM_LENGTH:
            return word[:-len(ending)]
    return word
