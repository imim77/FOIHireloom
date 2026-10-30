import re
from datetime import date

from FOIHireloom.dto.hzz_job_page import ParsedJobPageDTO
from FOIHireloom.exceptions import HzzJobPageParseError, HzzJobPageUnavailableError

from .hzz_text import html_to_text

CONTENT_START = 'id="ctl00_MainContent_pnlAjaxBlock"'
ERROR_FORM = 'action="./ErrorPage.aspx'
TITLE = re.compile(r"<h3>(.*?)</h3>", re.S)
LIST_ITEM = re.compile(r"<li>(.*?)</li>", re.S)
DESCRIPTION = re.compile(
    r'id="ctl00_MainContent_lblOstaleInformacijeText">.*?</label>(.*?)<hr class="FieldDivider"\s*/>', re.S
)
PAGE_DATE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\.?")


class HzzJobPageParser:
    """Read an HZZ job page by the ASP.NET element IDs of its fields.

    Raise HzzJobPageUnavailableError for HZZ's error page and
    HzzJobPageParseError for a page without the job content block or without
    both the place of work and the closing date, which every job page shows.
    """

    def parse(self, content: bytes) -> ParsedJobPageDTO:
        try:
            page = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise HzzJobPageParseError("HZZ job page is not UTF-8.") from error
        if ERROR_FORM in page:
            raise HzzJobPageUnavailableError("HZZ showed its error page instead of the job.")
        start = page.find(CONTENT_START)
        if start < 0:
            raise HzzJobPageParseError("HZZ job page has no job content block.")
        page = page[start:]
        work_place, valid_until = self._field(page, "MjestoRada"), self._date(self._field(page, "VrijediDo"))
        if work_place is None and valid_until is None:
            raise HzzJobPageParseError("HZZ job page has neither a place of work nor a closing date.")
        title = TITLE.search(page)
        description = DESCRIPTION.search(page)
        workers = self._field(page, "BrojRadnika")
        return ParsedJobPageDTO(
            title=self._line(title.group(1)) if title else None,
            work_place=work_place,
            workers_needed=int(workers) if workers and workers.isdigit() else None,
            employment_type=self._field(page, "VrstaZaposlenja"),
            working_hours=self._field(page, "RadnoVrijeme"),
            work_schedule=self._field(page, "NacinRada"),
            accommodation=self._field(page, "Smjestaj"),
            transport_allowance=self._field(page, "Naknada"),
            valid_from=self._date(self._field(page, "VrijediOd")),
            valid_until=valid_until,
            education=self._field(page, "RazinaObrazovanja"),
            experience=self._field(page, "RadnoIskustvo"),
            description_text=html_to_text(description.group(1)) if description else None,
            employer_name=self._field(page, "NazivPoslodavca"),
        )

    @classmethod
    def _field(cls, page: str, key: str) -> str | None:
        """A field's value: a span with lbl<key>, or a list with bul<key> when it has several values."""
        span = re.search(rf'<span id="ctl00_MainContent_lbl{key}">(.*?)</span>', page, re.S)
        if span is not None:
            return cls._line(span.group(1))
        items = re.search(rf'<ul id="ctl00_MainContent_bul{key}">(.*?)</ul>', page, re.S)
        if items is None:
            return None
        values = [cls._line(item) for item in LIST_ITEM.findall(items.group(1))]
        return "; ".join(value for value in values if value) or None

    @staticmethod
    def _line(markup: str) -> str | None:
        text = html_to_text(markup)
        return " ".join(text.split()) if text else None

    @staticmethod
    def _date(value: str | None) -> date | None:
        match = PAGE_DATE.fullmatch(value or "")
        if match is None:
            return None
        try:
            return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            return None
