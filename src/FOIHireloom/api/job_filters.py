from typing import Annotated

from pydantic import Field

from FOIHireloom.dto.job_conditions import Contract, EducationLevel, EmploymentTag
from FOIHireloom.dto.job_search import MAX_EXPERIENCE_MONTHS, MAX_QUERY_LENGTH

CATEGORY_DESCRIPTION = (
    "Exact category name from list_categories; letter case is ignored. A job's category is stated in its "
    "description or filled in from an HZZ occupation feed verified on its jobs. Jobs without one do not match, "
    "so also use query when every job of an occupation matters."
)
# The condition filters, shared by the tools that choose jobs as search_jobs does.
MaxExperienceMonths = Annotated[int | None, Field(
    ge=0, le=MAX_EXPERIENCE_MONTHS,
    description="Most experience in months the job may ask for; 0 finds jobs that need none ('Nije važno') and "
                "trainee ads.",
)]
ContractFilter = Annotated[Contract | None, Field(
    description="'permanent' (na neodređeno), 'fixed_term' (na određeno) or 'other' (other forms of work).",
)]
FullTime = Annotated[bool | None, Field(
    description="true for full-time jobs, false for part-time ones (under 40 hours a week).",
)]
Education = Annotated[EducationLevel | None, Field(
    description="The user's education level; finds jobs that accept it: 'primary_lower' (lower primary grades), "
                "'primary' (primary school), 'secondary_3' (3-year secondary school), 'secondary_4' (4-year "
                "secondary school), 'college' (viša or bachelor's) or 'university' (faculty, master's or doctorate).",
)]
Accommodation = Annotated[bool | None, Field(
    description="true for jobs offering accommodation (shared, single or family), false for jobs offering none.",
)]
EmploymentTags = Annotated[tuple[EmploymentTag, ...] | None, Field(
    description="Tags the job must all have: 'new_position', 'vacancy', 'replacement', 'increased_workload', "
                "'seasonal', 'reappointment', 'trainee', 'retirees' (pensioners may apply) or 'disability' "
                "(people with disabilities may apply).",
)]
Place = Annotated[str | None, Field(
    max_length=MAX_QUERY_LENGTH,
    description="Place of work in the nominative, e.g. 'Rijeka', not 'Rijeci'. Its words must appear as whole "
                "words in the job page's place of work or the feed's municipality, ignoring case and diacritics, "
                "so 'Varazdin' finds 'VARAŽDIN', 'Pula' finds 'PULA-POLA' and 'Zagreb' finds 'ZAGREB-DUBRAVA'.",
)]
