from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import Field

from FOIHireloom.dto.job_comparison import (
    MAX_COMPARED_JOBS,
    MIN_COMPARED_JOBS,
    JobComparisonConditionsDTO,
    JobComparisonDTO,
    JobComparisonViewDTO,
)

from .apps import job_comparison
from .apps.views import JOB_COMPARISON
from .job_filters import Accommodation, ContractFilter, Education, FullTime, MaxExperienceMonths
from .job_tools import JobId, JobToolGroup
from .tool_provider import DATA_ONLY, tool_arguments

ComparedJobIds = Annotated[list[JobId], Field(
    min_length=MIN_COMPARED_JOBS, max_length=MAX_COMPARED_JOBS,
    description="ids of the 2 or 3 jobs to compare, each once, from earlier search_jobs or show_jobs results, in the "
                "order to show them.",
)]
UserExperience = Annotated[MaxExperienceMonths, Field(
    description="The user's experience in months. A job meets it when it asks for at most that; with 0 only jobs "
                "that need none ('Nije važno') and trainee ads do.",
)]
UserContract = Annotated[ContractFilter, Field(
    description="The contract the user wants: 'permanent' (na neodređeno), 'fixed_term' (na određeno) or 'other' "
                "(other forms of work).",
)]
UserFullTime = Annotated[FullTime, Field(
    description="true when the user wants a full-time job, false when they want a part-time one (under 40 hours a "
                "week).",
)]
UserEducation = Annotated[Education, Field(
    description="The user's education level; a job meets it when it accepts that level: 'primary_lower' (lower "
                "primary grades), 'primary' (primary school), 'secondary_3' (3-year secondary school), 'secondary_4' "
                "(4-year secondary school), 'college' (viša or bachelor's) or 'university' (faculty, master's or "
                "doctorate).",
)]
UserAccommodation = Annotated[Accommodation, Field(
    description="true when the user needs accommodation, met by jobs offering any (shared, single or family); false "
                "when the user wants a job that offers none.",
)]


class JobComparisonTools(JobToolGroup):
    """JobComparisonTools compare 2 or 3 selected job ads against the conditions the user states."""

    def register(self, server: FastMCP) -> None:
        self._add_tool(server, self.compare_jobs, app=DATA_ONLY)
        self._add_tool(server, self.show_job_comparison, app=JOB_COMPARISON.app_config)

    async def compare_jobs(
        self,
        ctx: Context,
        job_ids: ComparedJobIds,
        max_experience_months: UserExperience = None,
        contract: UserContract = None,
        full_time: UserFullTime = None,
        education: UserEducation = None,
        accommodation: UserAccommodation = None,
    ) -> JobComparisonDTO:
        """App-only data comparison endpoint. For a user's selected ads use show_job_comparison.

        show_job_comparison returns the same comparison with an automatic table;
        use it for "Usporedi prvi i treći oglas" without requiring a format request.
        This endpoint remains callable for app workflows that consume raw rows.
        Compare 2 or 3 distinct known IDs in the user's order. Conditions must be
        stated by the user, never guessed or inferred. Report unknown as unknown;
        a match describes the advertisement, never that the employer will accept the user.
        Market-wide accommodation counts belong to show_accommodation_comparison.
        """
        conditions = JobComparisonConditionsDTO(**tool_arguments(locals(), "job_ids"))
        return await self._compare(ctx, job_ids, conditions)

    async def show_job_comparison(
        self,
        ctx: Context,
        job_ids: ComparedJobIds,
        max_experience_months: UserExperience = None,
        contract: UserContract = None,
        full_time: UserFullTime = None,
        education: UserEducation = None,
        accommodation: UserAccommodation = None,
    ) -> JobComparisonViewDTO:
        """Compare 2 or 3 specific job advertisements selected by the user against their stated conditions.

        DEFAULT for "Usporedi prvi i treći oglas", "Koji je od ova dva posla
        prikladniji za mene?" and "Compare these jobs". Call directly with their
        known job_ids in selection order. The user does not need to ask for a
        table, cards or any display format. Automatically presents a side-by-side
        comparison and also returns the data. If the selected ads cannot be
        identified from the conversation, ask which ads to compare; never invent IDs.

        On MCP Apps hosts, the app is the detailed comparison. After success,
        write only 1-3 short sentences about the key difference for the user's
        stated priorities, any urgent deadline or material unknown. Do not
        reproduce the comparison as a Markdown table, bullet list or field-by-field
        text. Provide a full text comparison only if explicitly requested or the
        host cannot render MCP Apps. If the tool fails, explain the error.

        Pass only the user's stated conditions, never guessed or inferred ones.
        Returns rows for experience, education, contract, working time,
        accommodation and deadline, with evidence and per-condition verdicts.
        Report 'unknown' as unknown; a match describes what the ad states,
        never that the employer will accept the user. Expired or unread ads may
        still be compared. Use canonical_url for full advertisements or applications.

        Do not select a few ads to answer an aggregate question. Accommodation
        counts or shares belong to show_accommodation_comparison; comparing
        counties belongs to show_county_comparison; finding new jobs to show_jobs.
        """
        conditions = JobComparisonConditionsDTO(**tool_arguments(locals(), "job_ids"))
        return job_comparison.job_comparison(await self._compare(ctx, job_ids, conditions))

    async def _compare(
        self, ctx: Context, job_ids: list[int], conditions: JobComparisonConditionsDTO,
    ) -> JobComparisonDTO:
        stated = conditions if conditions.model_dump(exclude_none=True) else None
        return await self._call(self._service(ctx).compare_jobs(job_ids, stated))
