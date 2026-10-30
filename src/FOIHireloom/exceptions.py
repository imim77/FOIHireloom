class FOIHireloomException(Exception):
    """Base application error carrying a stable, machine-readable code."""

    code = "error"

    def __init__(self, details: str, code: str | None = None) -> None:
        self.details = details
        if code is not None:
            self.code = code
        super().__init__(details)


class NotFoundError(FOIHireloomException):
    code = "not_found"

    def __init__(self, resource_type: str, resource_id: str) -> None:
        super().__init__(f"{resource_type.capitalize()} {resource_id} not found.")


class PersistenceError(FOIHireloomException):
    """The database rejected or could not complete a Unit of Work."""

    code = "persistence_error"


class ConflictError(PersistenceError):
    """A write violated a database constraint; the transaction was rolled back."""

    code = "conflict"


class InvalidJobSearchError(FOIHireloomException):
    """The search filters or cursor cannot be used as given."""

    code = "invalid_job_search"


class SourceFeedRegistrationError(FOIHireloomException):
    """The metadata cannot be registered without ambiguity or conflicting data."""

    code = "source_feed_registration"


class CkanError(FOIHireloomException, RuntimeError):
    """A CKAN request could not supply valid dataset resources."""

    code = "ckan_error"


class CkanTransportError(CkanError):
    """The HTTP request failed, including timeouts."""


class CkanHttpError(CkanError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"CKAN returned HTTP {status_code}.")


class CkanApiError(CkanError):
    """CKAN returned success=false, even if HTTP succeeded."""


class CkanResponseError(CkanError):
    """The response is not a valid package_show response."""


class HzzFeedError(FOIHireloomException, RuntimeError):
    """An HZZ RSS feed could not be downloaded or read."""

    code = "hzz_feed_error"


class HzzFeedTransportError(HzzFeedError):
    """The HTTP request failed, including timeouts."""


class HzzFeedHttpError(HzzFeedError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"HZZ feed returned HTTP {status_code}.")


class HzzFeedTooLargeError(HzzFeedError):
    """The decoded response exceeded the configured size limit."""


class HzzFeedParseError(HzzFeedError):
    """The response is not a well-formed, safe RSS 2.0 document."""


class HzzJobPageError(FOIHireloomException, RuntimeError):
    """An HZZ job detail page could not be downloaded or read."""

    code = "hzz_job_page_error"


class HzzJobPageTransportError(HzzJobPageError):
    """The HTTP request failed, including timeouts."""


class HzzJobPageHttpError(HzzJobPageError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"HZZ job page returned HTTP {status_code}.")


class HzzJobPageTooLargeError(HzzJobPageError):
    """The decoded response exceeded the configured size limit."""


class HzzJobPageUnavailableError(HzzJobPageError):
    """HZZ redirected to its error page instead of the job, e.g. for a withdrawn job.

    This is not evidence that the job is closed.
    """


class HzzJobPageParseError(HzzJobPageError):
    """The page does not have the expected job page structure."""
