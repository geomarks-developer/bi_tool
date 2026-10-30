from io import BytesIO

import pandas as pd
import plotly.graph_objects as go

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
)


def dataframe_to_csv(df):
    return df.to_csv(index=False).encode("utf-8")


def dataframe_to_excel(df):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(
            writer,
            sheet_name="Results",
            index=False,
        )

    output.seek(0)

    return output.getvalue()


def dataframe_to_pdf(df, max_rows=100):

    output = BytesIO()

    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(letter),
    )

    pdf_df = df.head(max_rows)

    data = [pdf_df.columns.tolist()]

    for row in pdf_df.values.tolist():
        data.append(
            [str(value) for value in row]
        )

    table = Table(data)

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.lightgrey],
                ),
            ]
        )
    )

    doc.build([table])

    output.seek(0)

    return output.getvalue()


def chart_to_png(
    fig,
    width=1600,
    height=900,
    scale=2,
):
    return fig.to_image(
        format="png",
        width=width,
        height=height,
        scale=scale,
    )