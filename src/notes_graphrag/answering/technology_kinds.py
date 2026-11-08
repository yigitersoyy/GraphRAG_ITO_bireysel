"""Small category catalogue used for validation only, never to supply note facts.

Examples of primary category definitions: ruby-lang.org, typescriptlang.org,
postgresql.org and sqlite.org. Unknown or mixed names remain unclassified.
"""

import re
from typing import Literal

LANGUAGES = frozenset(
    {
        "python",
        "ruby",
        "rust",
        "javascript",
        "typescript",
        "java",
        "kotlin",
        "swift",
        "lua",
        "scala",
        "dart",
        "elixir",
        "haskell",
        "julia",
        "perl",
        "php",
        "c++",
        "c#",
    }
)
DATABASES = frozenset(
    {
        "neo4j",
        "postgresql",
        "postgres",
        "mysql",
        "mariadb",
        "sqlite",
        "mongodb",
        "redis",
        "duckdb",
        "arangodb",
        "cockroachdb",
        "cassandra",
        "influxdb",
        "dynamodb",
        "tidb",
    }
)


def known_technology_kind(text: str) -> Literal["PROGRAMMING_LANGUAGE", "DATABASE"] | None:
    def contains(names: frozenset[str]) -> bool:
        for name in names:
            for match in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.I):
                if not re.search(r"\b(?:project|proje)\s+$", text[: match.start()], re.I):
                    return True
        return False

    languages, databases = contains(LANGUAGES), contains(DATABASES)
    if languages == databases:
        return None
    return "PROGRAMMING_LANGUAGE" if languages else "DATABASE"
