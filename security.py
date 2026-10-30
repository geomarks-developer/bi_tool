# security.py

import re


FORBIDDEN_KEYWORDS = [
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "DROP",
    "TRUNCATE",
    "ALTER",
    "CREATE",
    "GRANT",
    "REVOKE",
    "EXECUTE",
    "EXEC",
    "CALL",
    "COMMIT",
    "ROLLBACK",
]

def contains_forbidden_keyword(sql: str) -> bool:

    sql_upper = sql.upper()

    for keyword in FORBIDDEN_KEYWORDS:

        if re.search(
            rf"\b{keyword}\b",
            sql_upper,
        ):
            return True

    return False

def normalize_sql(sql: str) -> str:
    """
    Remove leading/trailing whitespace.
    """

    return sql.strip()


def contains_forbidden_keyword(sql: str) -> bool:
    """
    Check for dangerous SQL keywords.
    """

    sql_upper = sql.upper()

    return any(
        keyword in sql_upper
        for keyword in FORBIDDEN_KEYWORDS
    )


def starts_with_allowed_statement(sql: str) -> bool:
    """
    Allow only SELECT or WITH statements.
    """

    sql = sql.strip().upper()

    return (
        sql.startswith("SELECT")
        or sql.startswith("WITH")
    )


def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Main validation routine.
    """

    if not sql.strip():
        return False, "SQL statement cannot be blank."

    if not starts_with_allowed_statement(sql):
        return (
            False,
            "Only SELECT and WITH statements are allowed."
        )

    if contains_forbidden_keyword(sql):
        return (
            False,
            "SQL contains prohibited commands."
        )

    return True, "Valid"


def limit_rows(sql: str, max_rows: int = 10000) -> str:
    """
    Optionally append a row limit if one is not present.

    Oracle-compatible via FETCH FIRST.
    """

    sql_upper = sql.upper()

    if "FETCH FIRST" in sql_upper:
        return sql

    return f"""
    SELECT *
    FROM (
        {sql}
    )
    FETCH FIRST {max_rows} ROWS ONLY
    """


def remove_sql_comments(sql: str) -> str:

    sql = re.sub(
        r'--.*?$',
        '',
        sql,
        flags=re.MULTILINE,
    )

    sql = re.sub(
        r'/\*.*?\*/',
        '',
        sql,
        flags=re.DOTALL,
    )

    return sql


def clean_sql(sql: str) -> str:
    """
    Full SQL cleanup pipeline.
    """

    sql = remove_sql_comments(sql)
    sql = normalize_sql(sql)

    return sql

