from collections.abc import Sequence
from datetime import date

from FOIHireloom.db.models import Job
from FOIHireloom.dto.job_comparison import JobComparisonInputDTO
from FOIHireloom.dto.job_conditions import JobConditionsDTO, RawJobConditionsDTO
from FOIHireloom.dto.job_search import JobCardDTO, JobCountyDTO, JobDetailsDTO, JobListingDTO, JobSummaryDTO


class JobPresenter:
    """JobPresenter projects stored feed and page values into job results.

    A page read once keeps refining the feed when a later fetch fails.
    Missing values stay unknown and resolved quality flags are removed.
    """

    def summary[T: JobSummaryDTO](
        self, job: Job, today: date, county: JobCountyDTO | None, title_match: bool | None,
        dto: type[T] = JobSummaryDTO,
    ) -> T:
        return dto.model_validate(job).model_copy(
            update={**self._page_fields(job, today), **self._county_fields(county), "title_match": title_match}
        )

    def card(self, job: Job, today: date, county: JobCountyDTO | None, title_match: bool | None) -> JobCardDTO:
        return self.summary(job, today, county, title_match, JobCardDTO).model_copy(update={
            "workers_needed": job.page_workers_needed,
            "employment_type": job.page_employment_type,
            "working_hours": job.page_working_hours,
            "education": job.page_education,
            "experience": job.page_experience,
            "accommodation": job.page_accommodation,
            "conditions": self._stored_conditions(job),
        })

    @staticmethod
    def _stored_conditions(job: Job) -> JobConditionsDTO | None:
        """The normalised conditions stored with the job page; None while no page has been read.

        A page read once keeps its conditions when a later fetch fails, and the
        search filters still use them, so this goes by page_fetched_at, not page_status.
        """
        if job.page_fetched_at is None:
            return None
        return JobConditionsDTO(**{
            name: getattr(job, "conditions_unrecognised" if name == "unrecognised" else name)
            for name in JobConditionsDTO.model_fields
        })

    @staticmethod
    def _page_fields(job: Job, today: date) -> dict[str, object]:
        """Values the job page refines once read; page columns stay None until then.

        Quality flags for a weakness the page made up for are dropped.
        """
        deadline = job.page_valid_until or job.deadline_on
        resolved = {
            "title_missing": bool(job.page_title), "title_truncated": bool(job.page_title),
            "description_truncated": bool(job.page_description_text), "deadline_unknown": deadline is not None,
        }
        return {
            "title": job.page_title or job.title,
            "deadline_on": deadline,
            "deadline_source": "job_page" if job.page_valid_until else "feed" if job.deadline_on else None,
            "deadline_passed": None if deadline is None else deadline < today,
            "work_place": job.page_work_place,
            "employer_name": job.page_employer_name,
            "quality_flags": tuple(flag for flag in job.quality_flags if not resolved.get(flag)),
            "details_status": job.page_status,
        }

    def comparison_input(self, job: Job, today: date, county: JobCountyDTO | None) -> JobComparisonInputDTO:
        """A job's summary, stored conditions and, once its page is read, the page's condition text."""
        conditions = self._stored_conditions(job)
        page = None if conditions is None else RawJobConditionsDTO(**{
            name: getattr(job, f"page_{name}") for name in RawJobConditionsDTO.model_fields
        })
        return JobComparisonInputDTO(summary=self.summary(job, today, county, None), conditions=conditions, page=page)

    def details(
        self, job: Job, today: date, county: JobCountyDTO | None, listings: Sequence[JobListingDTO],
    ) -> JobDetailsDTO:
        return JobDetailsDTO.model_validate(job).model_copy(update={
            **self._county_fields(county),
            **self._page_fields(job, today),
            "description_text": job.page_description_text or job.description_text,
            "description_source": "job_page" if job.page_description_text else "feed" if job.description_text else None,
            "valid_from": job.page_valid_from,
            "workers_needed": job.page_workers_needed,
            "employment_type": job.page_employment_type,
            "working_hours": job.page_working_hours,
            "work_schedule": job.page_work_schedule,
            "accommodation": job.page_accommodation,
            "transport_allowance": job.page_transport_allowance,
            "education": job.page_education,
            "experience": job.page_experience,
            "details_checked_at": job.page_checked_at,
            "listings": tuple(listings),
        })

    @staticmethod
    def _county_fields(county: JobCountyDTO | None) -> dict[str, str | None]:
        if county is None:
            return {"county_code": None, "county_name": None}
        return {"county_code": county.county_code, "county_name": county.county_name}
