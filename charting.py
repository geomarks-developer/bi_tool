# charting.py

import plotly.express as px
import pandas as pd


def build_bar_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str | None = None
):
    """
    Create a Plotly bar chart.
    """

    if title is None:
        title = f"{y_col} by {x_col}"

    fig = px.bar(
        df,
        x=x_col,
        y=y_col,
        title=title
    )

    fig.update_layout(
        xaxis_title=x_col,
        yaxis_title=y_col
    )

    return fig


def build_line_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str | None = None
):
    """
    Create a Plotly line chart.
    """

    if title is None:
        title = f"{y_col} by {x_col}"

    fig = px.line(
        df,
        x=x_col,
        y=y_col,
        title=title
    )

    fig.update_layout(
        xaxis_title=x_col,
        yaxis_title=y_col
    )

    return fig


def build_scatter_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str | None = None
):
    """
    Create a Plotly scatter chart.
    """

    if title is None:
        title = f"{y_col} by {x_col}"

    fig = px.scatter(
        df,
        x=x_col,
        y=y_col,
        title=title
    )

    fig.update_layout(
        xaxis_title=x_col,
        yaxis_title=y_col
    )

    return fig


def build_pie_chart(
    df: pd.DataFrame,
    category_col: str,
    value_col: str,
    title: str | None = None
):
    """
    Create a Plotly pie chart.
    """

    if title is None:
        title = f"{value_col} by {category_col}"

    fig = px.pie(
        df,
        names=category_col,
        values=value_col,
        title=title
    )

    return fig


def build_histogram(
    df: pd.DataFrame,
    column: str,
    title: str | None = None
):
    """
    Create histogram for numeric columns.
    """

    if title is None:
        title = f"Distribution of {column}"

    fig = px.histogram(
        df,
        x=column,
        title=title
    )

    return fig


def build_box_plot(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str | None = None
):
    """
    Create a box plot.
    """

    if title is None:
        title = f"{y_col} by {x_col}"

    fig = px.box(
        df,
        x=x_col,
        y=y_col,
        title=title
    )

    return fig


def build_chart(
    chart_type: str,
    df: pd.DataFrame,
    x_col: str,
    y_col: str
):
    """
    Generic chart factory.
    """

    chart_type = chart_type.lower()

    if chart_type == "bar":
        return build_bar_chart(df, x_col, y_col)

    elif chart_type == "line":
        return build_line_chart(df, x_col, y_col)

    elif chart_type == "scatter":
        return build_scatter_chart(df, x_col, y_col)

    elif chart_type == "pie":
        return build_pie_chart(df, x_col, y_col)

    elif chart_type == "box":
        return build_box_plot(df, x_col, y_col)

    else:
        raise ValueError(
            f"Unsupported chart type: {chart_type}"
        )