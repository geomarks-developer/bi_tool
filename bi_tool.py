# bi_tool.py
import streamlit as st
import pandas as pd
import oracledb

from charting import build_chart
from query_builder import build_select_sql
from db import get_tables, get_columns, get_table_relationships
from exports import (
    dataframe_to_csv,
    dataframe_to_excel,
    dataframe_to_pdf,
    chart_to_png,
)
from security import clean_sql, validate_sql
from saved_queries import (
    init_db,
    add_history,
    get_history,
    save_query,
    get_saved_queries,
)


# --------------------------------------------------
# INITIALIZE
# --------------------------------------------------
init_db()


# --------------------------------------------------
# DATABASE
# --------------------------------------------------
def get_connection():
    oracle_user = st.session_state.get(
        "oracle_user_input",
        ""
    ).strip()

    oracle_password = st.session_state.get(
        "oracle_password_input",
        ""
    )

    if not oracle_user or not oracle_password:
        raise ValueError(
            "Enter the Oracle user ID and password."
        )

    return oracledb.connect(
        user=oracle_user,
        password=oracle_password,
        dsn=st.secrets["oracle"]["dsn"],
    )

def run_query(sql):
    conn = None

    try:
        conn = get_connection()
        return pd.read_sql_query(sql, conn)
    finally:
        if conn is not None:
            conn.close()

def clear_sql_query():
    st.session_state["sql_text"] = ""
    st.session_state.pop("sql_df", None)


def clear_sql_results():
    st.session_state.pop("sql_df", None)


def clear_builder_state():
    st.session_state["builder_table"] = ""
    st.session_state["builder_columns"] = []
    st.session_state["builder_where_clause"] = ""
    st.session_state["builder_row_limit"] = 100
    st.session_state["builder_join_count"] = 0
    st.session_state["builder_filter_count"] = 1
    st.session_state["builder_sort_count"] = 1
    st.session_state["builder_aggregate_count"] = 1
    st.session_state["builder_use_aggregates"] = False
    for key in list(st.session_state.keys()):
        if key in {"generated_sql", "builder_df"} or key.startswith((
            "builder_join_relationship_",
            "builder_join_type_",
            "builder_join_columns_",
            "builder_filter_",
            "builder_sort_",
            "builder_aggregate_",
            "builder_group_by_",
            "builder_having_",
        )):
            st.session_state.pop(key, None)


def clear_builder_results():
    st.session_state.pop("builder_df", None)


def reset_dependent_builder_state():
    """Clear relationships, filters, grouping and sorting after table changes."""
    st.session_state["builder_join_count"] = 0
    st.session_state["builder_filter_count"] = 1
    st.session_state["builder_sort_count"] = 1
    st.session_state["builder_aggregate_count"] = 1
    st.session_state["builder_columns"] = []

    for key in list(st.session_state.keys()):
        if (
            key in {
                "generated_sql",
                "builder_df",
                "builder_group_by_columns",
                "builder_having_clause",
            }
            or key.startswith("builder_join_relationship_")
            or key.startswith("builder_join_type_")
            or key.startswith("builder_join_columns_")
            or key.startswith("builder_filter_")
            or key.startswith("builder_sort_")
            or key.startswith("builder_aggregate_")
        ):
            st.session_state.pop(key, None)


def reset_join_tail(changed_index):
    """Clear the changed join's dependent fields and all joins after it."""
    st.session_state.pop("generated_sql", None)
    st.session_state.pop("builder_df", None)

    for key in list(st.session_state.keys()):
        clear_key = False

        for prefix in (
            "builder_join_relationship_",
            "builder_join_type_",
            "builder_join_columns_",
        ):
            if key.startswith(prefix):
                suffix = key[len(prefix):]
                index_text = suffix.split("_", 1)[0]
                if index_text.isdigit():
                    key_index = int(index_text)
                    if prefix == "builder_join_relationship_":
                        clear_key = key_index > changed_index
                    else:
                        clear_key = key_index >= changed_index
                break

        if clear_key:
            st.session_state.pop(key, None)

    # The relationship at changed_index remains selected. Joins after it are
    # rebuilt from that selection during the next Streamlit rerun.
    st.session_state["builder_join_count"] = min(
        st.session_state.get("builder_join_count", 0),
        changed_index + 1,
    )

    # Criteria based on the old join chain are stale too.
    st.session_state["builder_filter_count"] = 1
    st.session_state["builder_sort_count"] = 1
    st.session_state["builder_aggregate_count"] = 1
    for key in list(st.session_state.keys()):
        if (
            key == "builder_group_by_columns"
            or key == "builder_having_clause"
            or key.startswith("builder_filter_")
            or key.startswith("builder_sort_")
            or key.startswith("builder_aggregate_")
        ):
            st.session_state.pop(key, None)

def add_builder_join():
    st.session_state["builder_join_count"] = st.session_state.get("builder_join_count", 0) + 1
    st.session_state.pop("generated_sql", None)
    st.session_state.pop("builder_df", None)


def remove_builder_join():
    count = st.session_state.get("builder_join_count", 0)
    if count > 0:
        removed = count - 1
        for key in list(st.session_state.keys()):
            if key.startswith((
                f"builder_join_relationship_{removed}",
                f"builder_join_type_{removed}",
                f"builder_join_columns_{removed}_",
            )):
                st.session_state.pop(key, None)
        st.session_state["builder_join_count"] = count - 1
        st.session_state.pop("generated_sql", None)
        st.session_state.pop("builder_df", None)


def add_builder_filter():
    st.session_state["builder_filter_count"] = st.session_state.get("builder_filter_count", 1) + 1
    st.session_state.pop("generated_sql", None)


def remove_builder_filter():
    count = st.session_state.get("builder_filter_count", 1)
    if count > 1:
        removed = count - 1
        for key in list(st.session_state.keys()):
            if key.startswith(f"builder_filter_{removed}_"):
                st.session_state.pop(key, None)
        st.session_state["builder_filter_count"] = count - 1
        st.session_state.pop("generated_sql", None)


def add_builder_sort():
    st.session_state["builder_sort_count"] = (
        st.session_state.get("builder_sort_count", 1) + 1
    )
    st.session_state.pop("generated_sql", None)
    st.session_state.pop("builder_df", None)


def remove_builder_sort():
    count = st.session_state.get("builder_sort_count", 1)
    if count <= 1:
        return

    removed = count - 1
    for key in list(st.session_state.keys()):
        if key.startswith(f"builder_sort_{removed}_"):
            st.session_state.pop(key, None)

    st.session_state["builder_sort_count"] = count - 1
    st.session_state.pop("generated_sql", None)
    st.session_state.pop("builder_df", None)


def add_builder_aggregate():
    st.session_state["builder_aggregate_count"] = st.session_state.get("builder_aggregate_count", 1) + 1
    st.session_state.pop("generated_sql", None)


def remove_builder_aggregate():
    count = st.session_state.get("builder_aggregate_count", 1)
    if count > 1:
        removed = count - 1
        for key in list(st.session_state.keys()):
            if key.startswith(f"builder_aggregate_{removed}_"):
                st.session_state.pop(key, None)
        st.session_state["builder_aggregate_count"] = count - 1
        st.session_state.pop("generated_sql", None)


# --------------------------------------------------
# SHARED RESULTS DISPLAY
# --------------------------------------------------
def display_results(df, key_prefix):
    st.subheader("Results")
    st.caption(f"{len(df):,} rows x {len(df.columns):,} columns")

    st.dataframe(
        df,
        use_container_width=True,
        height=450,
    )

    st.subheader("Exports")

    csv_data = dataframe_to_csv(df)
    excel_data = dataframe_to_excel(df)
    pdf_data = dataframe_to_pdf(df)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.download_button(
            label="Export CSV",
            data=csv_data,
            file_name="results.csv",
            mime="text/csv",
            key=f"{key_prefix}_export_csv",
        )

    with col2:
        st.download_button(
            label="Export Excel",
            data=excel_data,
            file_name="results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}_export_excel",
        )

    with col3:
        st.download_button(
            label="Export PDF",
            data=pdf_data,
            file_name="results.pdf",
            mime="application/pdf",
            key=f"{key_prefix}_export_pdf",
        )

    numeric_columns = (
        df.select_dtypes(include=["number"])
        .columns
        .tolist()
    )

    if not numeric_columns:
        st.info(
            "No numeric columns found. "
            "Charting requires at least one numeric column."
        )
        return

    st.subheader("Chart Builder")

    col1, col2 = st.columns(2)

    with col1:
        x_column = st.selectbox(
            "X Axis",
            df.columns.tolist(),
            key=f"{key_prefix}_x_column",
        )

    with col2:
        y_column = st.selectbox(
            "Y Axis",
            numeric_columns,
            key=f"{key_prefix}_y_column",
        )

    chart_type = st.selectbox(
        "Chart Type",
        ["Bar", "Line", "Scatter", "Pie", "Box"],
        key=f"{key_prefix}_chart_type",
    )

    try:
        fig = build_chart(
            chart_type=chart_type,
            df=df,
            x_col=x_column,
            y_col=y_column,
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            key=f"{key_prefix}_chart",
        )

        png_data = chart_to_png(fig)

        st.download_button(
            label="Export Chart PNG",
            data=png_data,
            file_name="chart.png",
            mime="image/png",
            key=f"{key_prefix}_export_chart_png",
        )

    except Exception as exc:
        st.warning(f"Chart generation failed: {exc}")


# --------------------------------------------------
# PAGE SETTINGS
# --------------------------------------------------
st.title("Oracle BI Tool")


# --------------------------------------------------
# ORACLE LOGIN
# --------------------------------------------------
st.sidebar.header("Oracle Login")

default_oracle_user = st.secrets["oracle"].get(
    "user",
    ""
)

st.sidebar.text_input(
    "User ID",
    value=default_oracle_user,
    key="oracle_user_input",
)

st.sidebar.text_input(
    "Password",
    type="password",
    key="oracle_password_input",
)

if st.sidebar.button(
    "Test Connection",
    key="test_oracle_connection",
):
    conn = None

    try:
        conn = get_connection()

        st.session_state["oracle_authenticated"] = True

        st.sidebar.success(
            "Connection successful."
        )

    except Exception as exc:
        st.session_state["oracle_authenticated"] = False
        st.sidebar.error(str(exc))

    finally:
        if conn is not None:
            conn.close()


if (
    not st.session_state.get("oracle_user_input")
    or not st.session_state.get("oracle_password_input")
):
    st.info(
        "Enter your Oracle password in the sidebar."
    )
    st.stop()

# --------------------------------------------------
# DEFAULT SQL
# --------------------------------------------------
default_sql = """
select *
from your_table
fetch first 100 rows only
"""

if "sql_text" not in st.session_state:
    st.session_state["sql_text"] = default_sql


# --------------------------------------------------
# SIDEBAR SAVED QUERIES AND HISTORY
# --------------------------------------------------
st.sidebar.header("Saved Queries")

saved_queries = get_saved_queries()
saved_dict = {row[1]: row[2] for row in saved_queries}

selected_query = st.sidebar.selectbox(
    "Load Saved Query",
    [""] + list(saved_dict.keys()),
    key="saved_query_selector",
)

if selected_query:
    selected_sql = saved_dict[selected_query]

    if st.session_state.get("loaded_saved_query") != selected_query:
        st.session_state["sql_text"] = selected_sql
        st.session_state["loaded_saved_query"] = selected_query
        st.rerun()

st.sidebar.divider()
st.sidebar.header("Recent Query History")

history = get_history(10)
for row in history:
    st.sidebar.caption(row[2])


# --------------------------------------------------
# MAIN TABS
# --------------------------------------------------
tab_sql, tab_builder = st.tabs(
    ["SQL Editor", "Visual Builder"]
)


# --------------------------------------------------
# SQL EDITOR TAB
# --------------------------------------------------
with tab_sql:
    sql = st.text_area(
        "SQL Query",
        key="sql_text",
        height=250,
    )

    st.subheader("Save Query")

    save_col, button_col = st.columns([4, 1])

    with save_col:
        save_name = st.text_input(
            "Query Name",
            key="sql_save_name",
        )

    with button_col:
        st.write("")
        st.write("")

        if st.button(
            "Save Query",
            key="sql_save_query",
        ):
            if save_name.strip():
                save_query(save_name.strip(), sql)
                st.success("Query saved.")
            else:
                st.warning("Enter a query name before saving.")

    run_col, clear_query_col, clear_results_col = st.columns(3)

    with run_col:
        run_sql_query = st.button(
            "Run Query",
            type="primary",
            key="sql_run_query",
            use_container_width=True,
        )

    with clear_query_col:
        st.button(
            "Clear Query",
            key="sql_clear_query",
            on_click=clear_sql_query,
            use_container_width=True,
        )

    with clear_results_col:
        st.button(
            "Clear Results",
            key="sql_clear_results",
            on_click=clear_sql_results,
            use_container_width=True,
        )

    if run_sql_query:
        try:
            cleaned_sql = clean_sql(sql)
            valid, message = validate_sql(cleaned_sql)

            if not valid:
                st.error(message)
            else:
                add_history(cleaned_sql)

                with st.spinner("Executing query..."):
                    sql_df = run_query(cleaned_sql)

                st.session_state["sql_df"] = sql_df

                st.success(
                    f"Returned {len(sql_df):,} rows and "
                    f"{len(sql_df.columns):,} columns."
                )

        except Exception as exc:
            st.error(str(exc))

        if "sql_df" in st.session_state:
            display_results(
                st.session_state["sql_df"],
                key_prefix="sql",
            )


# --------------------------------------------------
# VISUAL BUILDER TAB
# --------------------------------------------------
with tab_builder:
    st.subheader("Visual Query Builder")

    owner = st.text_input(
        "Schema",
        value="IQMS",
        key="builder_schema",
    ).strip().upper()

    try:
        conn = get_connection()

        try:
            tables = get_tables(conn, owner)
        finally:
            conn.close()

        selected_table = st.selectbox(
            "Table",
            [""] + tables,
            key="builder_table",
            placeholder="Choose a table",
            on_change=reset_dependent_builder_state,
        )

        if selected_table:
            conn = get_connection()

            try:
                columns = get_columns(
                    conn,
                    owner,
                    selected_table,
                )

                relationships = get_table_relationships(
                    conn,
                    owner,
                    selected_table,
                )

            finally:
                conn.close()

            st.markdown("### Primary Table Columns")

            selected_columns = st.multiselect(
                "Columns",
                columns,
                key="builder_columns",
            )

            st.markdown("### Dynamic Join Builder")

            if "builder_join_count" not in st.session_state:
                st.session_state["builder_join_count"] = 0

            join_count = st.session_state["builder_join_count"]
            if join_count == 0:
                st.info(
                    "No joins configured. Click Add Another Join to add one."
                )

            current_source_table = selected_table
            joined_tables = {selected_table.upper()}
            joins_to_generate = []
            joined_column_groups = []
            join_chain_valid = True

            for join_index in range(join_count):
                join_number = join_index + 1
                st.markdown(f"#### Join {join_number}")

                conn = get_connection()
                try:
                    available_relationships = get_table_relationships(
                        conn, owner, current_source_table
                    )
                finally:
                    conn.close()

                relationship_options = {}
                for relationship in available_relationships:
                    target_table = (
                        relationship["pk_table"]
                        if current_source_table.upper()
                        == relationship["fk_table"].upper()
                        else relationship["fk_table"]
                    )
                    if target_table.upper() in joined_tables:
                        continue
                    label = (
                        f"{relationship['fk_table']}.{relationship['fk_column']} -> "
                        f"{relationship['pk_table']}.{relationship['pk_column']}"
                    )
                    relationship_options[label] = relationship

                if not relationship_options:
                    st.info(
                        f"No unused relationships were found from "
                        f"{owner}.{current_source_table}."
                    )
                    join_chain_valid = False
                    break

                selected_label = st.selectbox(
                    f"Join {join_number} Relationship",
                    list(relationship_options.keys()),
                    key=f"builder_join_relationship_{join_index}",
                    on_change=reset_join_tail,
                    args=(join_index,),
                )
                relationship = relationship_options[selected_label]
                fk_table = relationship["fk_table"]
                fk_column = relationship["fk_column"]
                pk_table = relationship["pk_table"]
                pk_column = relationship["pk_column"]
                target_table = (
                    pk_table
                    if current_source_table.upper() == fk_table.upper()
                    else fk_table
                )
                join_type = st.selectbox(
                    f"Join {join_number} Type",
                    ["LEFT JOIN", "INNER JOIN"],
                    key=f"builder_join_type_{join_index}",
                )
                st.caption(
                    f"{owner}.{current_source_table} to {owner}.{target_table}"
                )
                st.code(
                    f"{fk_table}.{fk_column} = {pk_table}.{pk_column}",
                    language="sql",
                )

                conn = get_connection()
                try:
                    target_columns = get_columns(conn, owner, target_table)
                finally:
                    conn.close()
                selected_join_columns = st.multiselect(
                    f"Columns from {target_table}",
                    target_columns,
                    key=f"builder_join_columns_{join_index}_{target_table}",
                )
                joins_to_generate.append({
                    "join_type": join_type,
                    "table": target_table,
                    "fk_table": fk_table,
                    "fk_column": fk_column,
                    "pk_table": pk_table,
                    "pk_column": pk_column,
                })
                joined_column_groups.append((target_table, selected_join_columns))
                joined_tables.add(target_table.upper())
                current_source_table = target_table

            add_col, remove_col, summary_col = st.columns([1, 1, 3])
            with add_col:
                st.button(
                    "Add Another Join",
                    key="builder_add_join",
                    on_click=add_builder_join,
                    disabled=not join_chain_valid,
                    use_container_width=True,
                )
            with remove_col:
                st.button(
                    "Remove Last Join",
                    key="builder_remove_join",
                    on_click=remove_builder_join,
                    disabled=join_count <= 0,
                    use_container_width=True,
                )
            with summary_col:
                st.caption(
                    f"Configured joins: {len(joins_to_generate)} | "
                    f"Tables: {1 + len(joins_to_generate)}"
                )

            if len(joins_to_generate) >= 2:
                st.warning(
                    "Multiple one-to-many joins can multiply rows. "
                    "Review the generated SQL and result counts."
                )

            st.divider()
            st.markdown("### WHERE Clause Builder")

            filter_columns = [
                f"{selected_table}.{column}" for column in columns
            ]
            for table_name, _ in joined_column_groups:
                conn = get_connection()
                try:
                    extra_columns = get_columns(conn, owner, table_name)
                finally:
                    conn.close()
                filter_columns.extend(
                    f"{table_name}.{column}" for column in extra_columns
                )
            filter_columns = list(dict.fromkeys(filter_columns))

            if "builder_filter_count" not in st.session_state:
                st.session_state["builder_filter_count"] = 1

            filter_count = st.session_state["builder_filter_count"]
            filter_conditions = []
            filters_valid = True
            filter_operators = [
                "=", "<>", ">", ">=", "<", "<=",
                "LIKE", "NOT LIKE", "IN", "NOT IN",
                "BETWEEN", "IS NULL", "IS NOT NULL",
            ]

            for filter_index in range(filter_count):
                logic_box, column_box, operator_box, value_box = st.columns(
                    [0.8, 2.4, 1.3, 2.5]
                )
                with logic_box:
                    if filter_index == 0:
                        st.markdown("**WHERE**")
                        logic = ""
                    else:
                        logic = st.selectbox(
                            "Logic", ["AND", "OR"],
                            key=f"builder_filter_{filter_index}_logic",
                            label_visibility="collapsed",
                        )
                with column_box:
                    filter_column = st.selectbox(
                        "Column", filter_columns,
                        key=f"builder_filter_{filter_index}_column",
                        label_visibility="collapsed",
                    )
                with operator_box:
                    operator = st.selectbox(
                        "Operator", filter_operators,
                        key=f"builder_filter_{filter_index}_operator",
                        label_visibility="collapsed",
                    )
                with value_box:
                    if operator in {"IS NULL", "IS NOT NULL"}:
                        st.caption("No value required")
                        value1 = value2 = ""
                    elif operator == "BETWEEN":
                        left_value, right_value = st.columns(2)
                        with left_value:
                            value1 = st.text_input(
                                "From", key=f"builder_filter_{filter_index}_value1",
                                label_visibility="collapsed",
                            )
                        with right_value:
                            value2 = st.text_input(
                                "To", key=f"builder_filter_{filter_index}_value2",
                                label_visibility="collapsed",
                            )
                    else:
                        value1 = st.text_input(
                            "Value", key=f"builder_filter_{filter_index}_value1",
                            placeholder="SQL value, e.g. 'ACTIVE' or 100",
                            label_visibility="collapsed",
                        )
                        value2 = ""

                prefix = "" if filter_index == 0 else f"{logic} "
                if operator in {"IS NULL", "IS NOT NULL"}:
                    filter_conditions.append(f"{prefix}{filter_column} {operator}")
                elif operator == "BETWEEN":
                    if value1.strip() and value2.strip():
                        filter_conditions.append(
                            f"{prefix}{filter_column} BETWEEN {value1.strip()} AND {value2.strip()}"
                        )
                    elif value1.strip() or value2.strip():
                        # Only a half-completed BETWEEN filter is invalid.
                        filters_valid = False
                    # If both BETWEEN values are blank, ignore the row.
                elif value1.strip():
                    if operator in {"IN", "NOT IN"}:
                        filter_conditions.append(
                            f"{prefix}{filter_column} {operator} ({value1.strip()})"
                        )
                    else:
                        filter_conditions.append(
                            f"{prefix}{filter_column} {operator} {value1.strip()}"
                        )
                # A blank ordinary filter row is optional and ignored.

            filter_add_col, filter_remove_col, manual_col = st.columns([1, 1, 2])
            with filter_add_col:
                st.button(
                    "Add Filter", on_click=add_builder_filter,
                    key="builder_add_filter", use_container_width=True,
                )
            with filter_remove_col:
                st.button(
                    "Remove Filter", on_click=remove_builder_filter,
                    key="builder_remove_filter", disabled=filter_count <= 1,
                    use_container_width=True,
                )
            with manual_col:
                use_manual_where = st.checkbox(
                    "Use advanced manual WHERE instead",
                    key="builder_use_manual_where",
                )

            manual_where = ""
            if use_manual_where:
                manual_where = st.text_area(
                    "Advanced WHERE Clause", key="builder_where_clause",
                    placeholder=f"{selected_table}.STATUS = 'A'",
                )
            elif filter_conditions:
                st.code("WHERE " + "\n".join(filter_conditions), language="sql")

            st.markdown("### Aggregates and GROUP BY")
            use_aggregates = st.checkbox(
                "Enable aggregate query",
                key="builder_use_aggregates",
            )
            group_by_columns = []
            aggregate_expressions = []
            aggregate_aliases = []
            having_clause = ""

            if use_aggregates:
                group_by_columns = st.multiselect(
                    "GROUP BY Columns",
                    filter_columns,
                    key="builder_group_by_columns",
                )
                if "builder_aggregate_count" not in st.session_state:
                    st.session_state["builder_aggregate_count"] = 1
                aggregate_count = st.session_state["builder_aggregate_count"]

                for aggregate_index in range(aggregate_count):
                    function_col, column_col, distinct_col, alias_col = st.columns([1, 2.5, 1, 1.5])
                    with function_col:
                        aggregate_function = st.selectbox(
                            "Function", ["COUNT", "SUM", "AVG", "MIN", "MAX"],
                            key=f"builder_aggregate_{aggregate_index}_function",
                            label_visibility="collapsed",
                        )
                    aggregate_column_options = filter_columns.copy()
                    if aggregate_function == "COUNT":
                        aggregate_column_options = ["*"] + aggregate_column_options
                    with column_col:
                        aggregate_column = st.selectbox(
                            "Column", aggregate_column_options,
                            key=f"builder_aggregate_{aggregate_index}_column",
                            label_visibility="collapsed",
                        )
                    with distinct_col:
                        aggregate_distinct = st.checkbox(
                            "DISTINCT",
                            key=f"builder_aggregate_{aggregate_index}_distinct",
                            disabled=aggregate_column == "*",
                        )
                    with alias_col:
                        aggregate_alias = st.text_input(
                            "Alias",
                            key=f"builder_aggregate_{aggregate_index}_alias",
                            placeholder="Alias",
                            label_visibility="collapsed",
                        ).strip()

                    distinct_sql = "DISTINCT " if aggregate_distinct and aggregate_column != "*" else ""
                    aggregate_expression = f"{aggregate_function}({distinct_sql}{aggregate_column})"
                    if aggregate_alias:
                        aggregate_expression += f" AS {aggregate_alias}"
                        aggregate_aliases.append(aggregate_alias)
                    aggregate_expressions.append(aggregate_expression)

                aggregate_add_col, aggregate_remove_col = st.columns(2)
                with aggregate_add_col:
                    st.button(
                        "Add Aggregate", on_click=add_builder_aggregate,
                        key="builder_add_aggregate", use_container_width=True,
                    )
                with aggregate_remove_col:
                    st.button(
                        "Remove Aggregate", on_click=remove_builder_aggregate,
                        key="builder_remove_aggregate", disabled=aggregate_count <= 1,
                        use_container_width=True,
                    )

                having_clause = st.text_input(
                    "Optional HAVING Clause",
                    key="builder_having_clause",
                    placeholder="SUM(TABLE.AMOUNT) > 1000",
                )
                st.code(
                    "SELECT " + ",\n       ".join(group_by_columns + aggregate_expressions),
                    language="sql",
                )

            st.markdown("### Sorting")

            sort_columns = filter_columns.copy()
            if use_aggregates:
                sort_columns = list(dict.fromkeys(
                    group_by_columns + aggregate_aliases + aggregate_expressions
                ))
            if "builder_sort_count" not in st.session_state:
                st.session_state["builder_sort_count"] = 1

            sort_count = st.session_state["builder_sort_count"]
            sort_expressions = []

            for sort_index in range(sort_count):
                sort_column_box, direction_box, nulls_box = st.columns(
                    [3, 1.2, 1.5]
                )

                with sort_column_box:
                    sort_column = st.selectbox(
                        "Sort Column",
                        [""] + sort_columns,
                        key=f"builder_sort_{sort_index}_column",
                        placeholder="Choose a sort column",
                        label_visibility="collapsed",
                    )

                with direction_box:
                    sort_direction = st.selectbox(
                        "Direction",
                        ["ASC", "DESC"],
                        key=f"builder_sort_{sort_index}_direction",
                        label_visibility="collapsed",
                    )

                with nulls_box:
                    null_order = st.selectbox(
                        "Null Ordering",
                        ["DEFAULT", "NULLS FIRST", "NULLS LAST"],
                        key=f"builder_sort_{sort_index}_nulls",
                        label_visibility="collapsed",
                    )

                if sort_column:
                    sort_expression = (
                        f"{sort_column} {sort_direction}"
                    )
                    if null_order != "DEFAULT":
                        sort_expression += f" {null_order}"
                    sort_expressions.append(sort_expression)

            sort_add_col, sort_remove_col, sort_preview_col = st.columns(
                [1, 1, 2]
            )

            with sort_add_col:
                st.button(
                    "Add Sort",
                    on_click=add_builder_sort,
                    key="builder_add_sort",
                    use_container_width=True,
                )

            with sort_remove_col:
                st.button(
                    "Remove Sort",
                    on_click=remove_builder_sort,
                    key="builder_remove_sort",
                    disabled=sort_count <= 1,
                    use_container_width=True,
                )

            with sort_preview_col:
                if sort_expressions:
                    st.caption(
                        "ORDER BY " + ", ".join(sort_expressions)
                    )
                else:
                    st.caption("No sorting selected")

            row_limit = st.number_input(
                "Row Limit", min_value=1, max_value=100000,
                value=100, key="builder_row_limit",
            )

            if st.button("Generate SQL", key="builder_generate"):
                if use_aggregates:
                    selected_output_columns = group_by_columns + aggregate_expressions
                else:
                    selected_output_columns = [
                        f"{selected_table}.{column}" for column in selected_columns
                    ]
                    for table_name, join_columns in joined_column_groups:
                        selected_output_columns.extend(
                            f"{table_name}.{column}" for column in join_columns
                        )
                if not selected_output_columns:
                    st.warning("Select at least one output column.")
                elif not join_chain_valid:
                    st.warning("Remove the incomplete last join before generating SQL.")
                else:
                    sql_parts = [
                        "SELECT",
                        "    " + ",\n    ".join(selected_output_columns),
                        f"FROM {owner}.{selected_table}",
                    ]
                    for join_info in joins_to_generate:
                        sql_parts.extend([
                            f"{join_info['join_type']} {owner}.{join_info['table']}",
                            (
                                f"    ON {join_info['fk_table']}.{join_info['fk_column']} = "
                                f"{join_info['pk_table']}.{join_info['pk_column']}"
                            ),
                        ])
                    if use_manual_where:
                        if manual_where.strip():
                            sql_parts.append(f"WHERE {manual_where.strip()}")
                    else:
                        if not filters_valid:
                            st.warning("Complete all filter values before generating SQL.")
                            st.stop()
                        if filter_conditions:
                            sql_parts.append("WHERE " + "\n".join(filter_conditions))
                    if use_aggregates and group_by_columns:
                        sql_parts.append("GROUP BY " + ", ".join(group_by_columns))
                    if use_aggregates and having_clause.strip():
                        sql_parts.append(f"HAVING {having_clause.strip()}")
                    if sort_expressions:
                        sql_parts.append(
                            "ORDER BY " + ", ".join(sort_expressions)
                        )

                    sql_parts.append(f"FETCH FIRST {row_limit} ROWS ONLY")
                    st.session_state["generated_sql"] = "\n".join(sql_parts)
                    st.session_state.pop("builder_df", None)

            if "generated_sql" in st.session_state:
                st.subheader("Generated SQL")

                st.code(
                    st.session_state["generated_sql"],
                    language="sql",
                )

                copy_col, run_col, clear_builder_col, clear_results_col = st.columns(4)

                with copy_col:
                    if st.button(
                        "Copy to SQL Editor",
                        key="builder_copy_to_editor",
                        use_container_width=True,
                    ):
                        st.session_state["sql_text"] = st.session_state[
                            "generated_sql"
                        ]
                        st.success(
                            "Generated SQL copied to the SQL Editor."
                        )

                with run_col:
                    run_generated = st.button(
                        "Run Generated SQL",
                        type="primary",
                        key="run_generated_sql",
                        use_container_width=True,
                    )

                with clear_builder_col:
                    st.button(
                        "Clear Builder",
                        key="builder_clear",
                        on_click=clear_builder_state,
                        use_container_width=True,
                    )

                with clear_results_col:
                    st.button(
                        "Clear Results",
                        key="builder_clear_results",
                        on_click=clear_builder_results,
                        use_container_width=True,
                    )

                if run_generated:
                    try:
                        generated_sql = st.session_state["generated_sql"]
                        cleaned_sql = clean_sql(generated_sql)
                        valid, message = validate_sql(cleaned_sql)

                        if not valid:
                            st.error(message)
                        else:
                            add_history(cleaned_sql)

                            with st.spinner("Executing query..."):
                                builder_df = run_query(cleaned_sql)

                            st.session_state["builder_df"] = builder_df
                            st.success(
                                f"Returned {len(builder_df):,} rows and "
                                f"{len(builder_df.columns):,} columns."
                            )

                    except Exception as exc:
                        st.error(str(exc))

            if "builder_df" in st.session_state:
                display_results(
                    st.session_state["builder_df"],
                    key_prefix="builder",
                )

    except Exception as exc:
        st.error(f"Metadata Error: {exc}")


# --------------------------------------------------
# QUERY HISTORY DETAIL
# --------------------------------------------------
with st.expander("Query History"):
    history = get_history(25)

    if not history:
        st.info("No history available.")

    for row in history:
        st.caption(row[2])
        st.code(row[1], language="sql")


# --------------------------------------------------
# FOOTER
# --------------------------------------------------
st.divider()
st.caption("Oracle BI Tool | Streamlit + Oracle + Plotly")
