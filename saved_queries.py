# saved_queries.py

import sqlite3
from datetime import datetime

DB_FILE = "bi_tool.db"


def init_db():

    conn = sqlite3.connect(DB_FILE)

    conn.execute("""
        create table if not exists query_history (
            id integer primary key autoincrement,
            query_text text,
            run_ts text
        )
    """)

    conn.execute("""
        create table if not exists saved_queries (
            id integer primary key autoincrement,
            query_name text,
            query_text text,
            created_ts text
        )
    """)

    conn.commit()
    conn.close()


def add_history(sql):

    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        """
        insert into query_history
        (query_text, run_ts)
        values (?,?)
        """,
        (
            sql,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )

    conn.commit()
    conn.close()


def get_history(limit=20):

    conn = sqlite3.connect(DB_FILE)

    rows = conn.execute(
        """
        select id,
               query_text,
               run_ts
        from query_history
        order by id desc
        limit ?
        """,
        (limit,),
    ).fetchall()

    conn.close()

    return rows


def save_query(name, sql):

    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        """
        insert into saved_queries
        (query_name,
         query_text,
         created_ts)
        values (?,?,?)
        """,
        (
            name,
            sql,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )

    conn.commit()
    conn.close()


def get_saved_queries():

    conn = sqlite3.connect(DB_FILE)

    rows = conn.execute(
        """
        select id,
               query_name,
               query_text
        from saved_queries
        order by query_name
        """
    ).fetchall()

    conn.close()

    return rows


def delete_saved_query(query_id):

    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        """
        delete from saved_queries
        where id = ?
        """,
        (query_id,),
    )

    conn.commit()
    conn.close()