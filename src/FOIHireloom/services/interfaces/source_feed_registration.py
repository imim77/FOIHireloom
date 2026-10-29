from abc import ABC, abstractmethod

from FOIHireloom.dto.source_feed import RegistrationPreviewDTO, RegistrationResultDTO


class SourceFeedRegistrationServiceInterface(ABC):
    """Register Croatian county job feeds published in a CKAN dataset."""

    @abstractmethod
    async def preview_sources(self, dataset_id: str) -> RegistrationPreviewDTO:
        """Fetch and validate the dataset's feeds without accessing the database.

        Raise CkanError for upstream failures and SourceFeedRegistrationError
        when the metadata is ambiguous.
        """

    @abstractmethod
    async def register_sources(self, dataset_id: str) -> RegistrationResultDTO:
        """Fetch and validate first, then register all counties and feeds atomically.

        Existing enabled flags and sync history are preserved; feeds missing
        from CKAN are neither deleted nor disabled. Raise CkanError for
        upstream failures and SourceFeedRegistrationError when the metadata is
        ambiguous or conflicts with stored data, in which case nothing is
        written.
        """
