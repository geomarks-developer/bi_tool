# db.py

def get_tables(conn, owner):

    cur = conn.cursor()

    cur.execute(
        """
        select table_name
        from all_tables
        where owner = :owner
        order by table_name
        """,
        owner=owner.upper()
    )

    return [r[0] for r in cur.fetchall()]


def get_columns(
    conn,
    owner,
    table_name
):

    cur = conn.cursor()

    cur.execute(
        """
        select column_name
        from all_tab_columns
        where owner = :owner
          and table_name = :table_name
        order by column_id
        """,
        owner=owner.upper(),
        table_name=table_name.upper()
    )

    return [r[0] for r in cur.fetchall()]

def get_table_relationships(conn, owner, table_name):
    sql = """
        SELECT
            fk.owner              AS fk_owner,
            fk.table_name         AS fk_table,
            fkc.column_name       AS fk_column,
            pk.owner              AS pk_owner,
            pk.table_name         AS pk_table,
            pkc.column_name       AS pk_column,
            fk.constraint_name    AS fk_name
        FROM all_constraints fk
        JOIN all_cons_columns fkc
            ON fk.owner = fkc.owner
           AND fk.constraint_name = fkc.constraint_name
        JOIN all_constraints pk
            ON fk.r_owner = pk.owner
           AND fk.r_constraint_name = pk.constraint_name
        JOIN all_cons_columns pkc
            ON pk.owner = pkc.owner
           AND pk.constraint_name = pkc.constraint_name
           AND fkc.position = pkc.position
        WHERE fk.constraint_type = 'R'
          AND (
                (fk.owner = :owner AND fk.table_name = :table_name)
                OR
                (pk.owner = :owner AND pk.table_name = :table_name)
              )
        ORDER BY
            fk.table_name,
            fk.constraint_name,
            fkc.position
    """

    cursor = conn.cursor()

    try:
        cursor.execute(
            sql,
            owner=owner.upper(),
            table_name=table_name.upper()
        )

        columns = [
            col[0].lower()
            for col in cursor.description
        ]

        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]

    finally:
        cursor.close()