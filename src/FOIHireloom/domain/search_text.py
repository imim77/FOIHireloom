import re

SEARCH_FOLD_FROM, SEARCH_FOLD_TO = "ČĆŽŠĐčćžšđ/.", "CCZSDcczsd  "
SEARCH_FOLD = str.maketrans(SEARCH_FOLD_FROM, SEARCH_FOLD_TO)
SEARCH_TERM = re.compile(r"[^\W_]+")
