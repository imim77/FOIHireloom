import re

# Searchable text with Croatian letters folded to ASCII, so "cistacica" finds
# "ČISTAČICA". "/" and "." become spaces: the parser would otherwise read
# "KUHAR/KUHARICA" as a file path and "68.STRUČNI" as a host name. Queries
# must apply the same translate(); unaccent() is not immutable and cannot be
# used in a generated column.
SEARCH_FOLD_FROM, SEARCH_FOLD_TO = "ČĆŽŠĐčćžšđ/.", "CCZSDcczsd  "
SEARCH_FOLD = str.maketrans(SEARCH_FOLD_FROM, SEARCH_FOLD_TO)
SEARCH_TERM = re.compile(r"[^\W_]+")
