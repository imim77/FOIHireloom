"""Skill patterns shared by PostgreSQL extraction and portable regex checks.

Keep punctuation: the text search fold discards dots needed by .NET. New
patterns require a migration because jobs.skills is a generated column.
"""

SKILL_FOLD_FROM = "ČĆŽŠĐčćžšđ"
SKILL_FOLD_TO = "CCZSDcczsd"
URL_PATTERN = r"(https?://|www[.])[^\s<>]+"

SKILL_PATTERNS = {
    "csharp": r"(^|[^a-z0-9])(c#|c sharp)([^a-z0-9]|$)",
    "dotnet": r"(^|[^a-z0-9])(asp[.]net|[.]net)([^a-z0-9]|$)",
    "python": r"(^|[^a-z0-9])python([^a-z0-9]|$)",
    "java": r"(^|[^a-z0-9])java([^a-z0-9]|$)",
    "javascript": r"(^|[^a-z0-9])(javascript|typescript)([^a-z0-9]|$)",
    "sql": r"(^|[^a-z0-9])sql([^a-z0-9]|$)",
    "php": r"(^|[^a-z0-9])php([^a-z0-9]|$)",
    "excel": r"(^|[^a-z0-9])excel(a|u|om)?([^a-z0-9]|$)",
    "autocad": r"(^|[^a-z0-9])autocad(a|u|om)?([^a-z0-9]|$)",
    "plc": r"(^|[^a-z0-9])plc([^a-z0-9]|$)",
}
