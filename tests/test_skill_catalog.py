import importlib.util
import re
import unittest
from pathlib import Path
from typing import get_args

from FOIHireloom.db.models.job import Job, SKILLS_DOCUMENT
from FOIHireloom.domain.skill_catalog import SKILL_FOLD_FROM, SKILL_FOLD_TO, SKILL_PATTERNS, URL_PATTERN
from FOIHireloom.dto.job_skills import Skill


# The same examples are exercised in PostgreSQL during migration verification.
SKILL_EXAMPLES = (
    ("JUNIOR C# .NET WEB PROGRAMER", {"csharp", "dotnet"}),
    ("C Sharp, ASP.NET i Python", {"csharp", "dotnet", "python"}),
    ("Java / JavaScript / TypeScript", {"java", "javascript"}),
    ("SQL, PHP, Excel, AutoCAD i PLC", {"sql", "php", "excel", "autocad", "plc"}),
    ("https://example.com/index.php?python=1 www.excel.hr/autocad", set()),
    ("internet javni c javascript", {"javascript"}),
    ("excellent javac mysql plcs", set()),
    ("https://example.com/index.php\nPython i PHP", {"python", "php"}),
    ("Poznavanje Excela, rad u Excelu i AutoCADom", {"excel", "autocad"}),
    ("", set()),
)


class SkillCatalogTests(unittest.TestCase):
    def test_patterns_match_skills_without_substrings_or_urls(self) -> None:
        for text, expected in SKILL_EXAMPLES:
            with self.subTest(text=text):
                folded = text.translate(str.maketrans(SKILL_FOLD_FROM, SKILL_FOLD_TO)).lower()
                document = re.sub(URL_PATTERN, " ", folded)
                actual = {code for code, pattern in SKILL_PATTERNS.items() if re.search(pattern, document)}
                self.assertEqual(actual, expected)

    def test_schema_codes_match_the_catalog(self) -> None:
        self.assertEqual(set(get_args(Skill.__value__)), set(SKILL_PATTERNS))

    def test_migration_keeps_a_frozen_copy_of_the_expression(self) -> None:
        path = Path(__file__).resolve().parents[1] / (
            "src/FOIHireloom/db/alembic/versions/f3b5d7e9a1c2_add_job_skills.py"
        )
        spec = importlib.util.spec_from_file_location("skill_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        # The later naming migration changes identifiers, not extraction rules.
        names = {column.key: column.name for column in Job.__table__.columns}
        translated = re.sub(
            r"'(?:[^']|'')*'|\b[a-z_]+\b",
            lambda match: names.get(match[0], match[0]) if not match[0].startswith("'") else match[0],
            migration.SKILLS_DOCUMENT,
        )
        self.assertEqual(translated, SKILLS_DOCUMENT)
