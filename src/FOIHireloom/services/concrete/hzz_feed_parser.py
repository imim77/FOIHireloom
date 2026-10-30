import hashlib
import html
import re
from datetime import date, datetime

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

from FOIHireloom.dto.job import ParsedFeedDTO, ParsedJobDTO
from FOIHireloom.exceptions import HzzFeedParseError

LINK = re.compile(r"^https?://burzarada\.hzz\.hr/RadnoMjesto_Ispis\.aspx\?WebSifra=(\d+)$")
CANONICAL_URL = "https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra={}"
DESCRIPTION_PREFIX = "Opis posla:"
SUFFIX_START = ", Kategorija: "
SUFFIX_LABEL = re.compile(r", (Kategorija|Rok za prijavu|Mjesto rada|Općina|Županija): ")
DEADLINE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
BLOCK_TAG = re.compile(r"</?(?:p|br|li|ul|ol|div|h[1-6]|tr|table)\b[^>]*>", re.I)
TAG = re.compile(r"<[^>]*>")
DANGLING_TAG = re.compile(r"<[^>]*$")
NBSP = re.compile(r"&nbsp;", re.I)
# HZZ cuts descriptions at 512 characters before its last escaping pass.
TRUNCATION_LENGTH = 500
TITLE_LIMIT = 150


class HzzFeedParser:
    """Parse one HZZ RSS 2.0 feed into job DTOs without touching the network.

    Items without a WebSifra link or a DD.MM.YYYY pubDate are counted as
    invalid instead of failing the feed. Malformed or unsafe XML, a non-RSS
    document and duplicate WebSifra values raise HzzFeedParseError.
    """

    def parse(self, content: bytes) -> ParsedFeedDTO:
        try:
            root = fromstring(content, forbid_dtd=True)
        except (ParseError, DefusedXmlException) as error:
            raise HzzFeedParseError("HZZ feed is not well-formed, safe XML.") from error
        channel = root.find("channel")
        if root.tag != "rss" or channel is None:
            raise HzzFeedParseError("HZZ feed is not an RSS 2.0 document.")
        jobs: list[ParsedJobDTO] = []
        seen: set[str] = set()
        invalid = 0
        for item in channel.iter("item"):
            job = self._parse_item(item)
            if job is None:
                invalid += 1
                continue
            if job.source_job_id in seen:
                raise HzzFeedParseError(f"Duplicate WebSifra {job.source_job_id} in HZZ feed.")
            seen.add(job.source_job_id)
            jobs.append(job)
        return ParsedFeedDTO(jobs=tuple(jobs), invalid_items=invalid)

    def _parse_item(self, item) -> ParsedJobDTO | None:
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        match = LINK.match(link)
        if match is None:
            return None
        try:
            published_on = datetime.strptime(pub, "%d.%m.%Y").date()
        except ValueError:
            return None
        title = (item.findtext("title") or "").strip() or None
        raw = item.findtext("description") or ""
        body, fields, complete = self._split_suffix(raw.removeprefix(DESCRIPTION_PREFIX))
        deadline_on = self._deadline(fields.get("Rok za prijavu"))
        truncated = len(raw) >= TRUNCATION_LENGTH or bool(DANGLING_TAG.search(raw)) or not complete
        flags = [
            name for name, applies in (
                ("title_missing", title is None),
                ("title_truncated", title is not None and len(title) >= TITLE_LIMIT),
                ("description_truncated", truncated),
                ("deadline_unknown", deadline_on is None),
            ) if applies
        ]
        return ParsedJobDTO(
            source_job_id=match.group(1),
            canonical_url=CANONICAL_URL.format(match.group(1)),
            title=title,
            description_raw=raw,
            description_text=self._text(body),
            published_on=published_on,
            deadline_on=deadline_on,
            category=fields.get("Kategorija"),
            location_text=fields.get("Mjesto rada"),
            municipality=fields.get("Općina"),
            quality_flags=tuple(flags),
            content_hash=hashlib.sha256("\x1f".join((title or "", pub, raw)).encode()).hexdigest(),
        )

    @classmethod
    def _split_suffix(cls, description: str) -> tuple[str, dict[str, str], bool]:
        """Split ", Kategorija: …, Županija: …" off the description.

        Values are split on the known labels because categories contain
        commas. Truncation can cut the last value, so it is dropped unless it
        is the deadline, whose strict format exposes a cut. The flag says
        whether the suffix reached its final Županija label.
        """
        start = description.rfind(SUFFIX_START)
        if start < 0:
            return description, {}, False
        suffix = description[start:]
        labels = list(SUFFIX_LABEL.finditer(suffix))
        fields = {}
        for current, following in zip(labels, labels[1:] + [None]):
            if following is None and current.group(1) != "Rok za prijavu":
                continue
            value = cls._decode(suffix[current.end():following.start() if following else None]).strip()
            if value:
                fields[current.group(1)] = value
        return description[:start], fields, labels[-1].group(1) == "Županija"

    @staticmethod
    def _deadline(value: str | None) -> date | None:
        match = DEADLINE.fullmatch(value or "")
        if match is None:
            return None
        try:
            return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            return None

    @staticmethod
    def _decode(text: str) -> str:
        """Undo HZZ's repeated escaping, e.g. "&amp;amp;AMP;NBSP;"."""
        for _ in range(5):
            decoded = html.unescape(NBSP.sub(" ", text))
            if decoded == text:
                break
            text = decoded
        return text

    @classmethod
    def _text(cls, body: str) -> str | None:
        text = cls._decode(body)
        text = TAG.sub("", DANGLING_TAG.sub("", BLOCK_TAG.sub("\n", text)))
        lines = (" ".join(line.replace(" ", " ").split()) for line in text.splitlines())
        return "\n".join(line for line in lines if line) or None
