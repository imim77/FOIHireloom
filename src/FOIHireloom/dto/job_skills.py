from typing import Literal

# Skill codes are checked against the extraction catalog in the tests.
type Skill = Literal[
    "csharp", "dotnet", "python", "java", "javascript", "sql", "php", "excel", "autocad", "plc",
]
