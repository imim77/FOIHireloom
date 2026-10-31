from collections import Counter

from FOIHireloom.dto.job import ParsedJobDTO
from FOIHireloom.dto.source_feed import FeedCategoryMappingDTO


class FeedCategoryVerifier:
    """Find an occupation feed's HZZ category from its jobs' explicit categories.

    A mapping is confirmed only when at least min_examples jobs name the same
    category and none names another. Jobs without a category are no evidence
    either way.
    """

    def __init__(self, min_examples: int = 3) -> None:
        if min_examples < 1:
            raise ValueError("min_examples must be at least 1.")
        self._min_examples = min_examples

    def verify(self, jobs: tuple[ParsedJobDTO, ...]) -> FeedCategoryMappingDTO:
        counts = Counter(job.category for job in jobs if job.category)
        # Ties are contradicted anyway; the name only makes the choice repeatable.
        category, matching = min(counts.items(), key=lambda item: (-item[1], item[0]), default=(None, 0))
        contradicting = counts.total() - matching
        if contradicting:
            status = "contradicted"
        elif matching < self._min_examples:
            status = "too_few_examples"
        else:
            status = "confirmed"
        return FeedCategoryMappingDTO(
            category=category, status=status, matching_examples=matching, contradicting_examples=contradicting,
        )
