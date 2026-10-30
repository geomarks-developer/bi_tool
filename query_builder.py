# query_builder.py

def build_select_sql(
    tables,
    columns,
    joins=None,
    filters=None,
):

    sql = "select\n"

    sql += ",\n".join(columns)

    sql += "\nfrom "

    sql += tables[0]

    if joins:

        for join in joins:

            sql += f"""
    {join['join_type']} join {join['table']}
        on {join['left_col']} = {join['right_col']}
"""

    if filters:

        sql += "\nwhere\n"

        sql += "\n and ".join(filters)

    return sql