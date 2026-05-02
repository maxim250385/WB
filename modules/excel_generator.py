import os
import pandas as pd


def _style_sheet(writer, sheet_name, df, zero_value_col_idx=None):
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]

    header_fmt = workbook.add_format({
        "bold": True,
        "bg_color": "#1F4E78",
        "font_color": "white",
        "border": 1,
        "align": "center",
        "valign": "vcenter",
    })
    cell_fmt = workbook.add_format({"border": 1, "align": "center"})
    red_fmt = workbook.add_format({"bg_color": "#FFC7CE", "font_color": "#9C0006"})

    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, header_fmt)

    if len(df.columns) == 0:
        return

    for i, col in enumerate(df.columns):
        if len(df) > 0:
            try:
                m = max(int(df[col].astype(str).str.len().max()), len(str(col))) + 3
            except ValueError:
                m = len(str(col)) + 3
        else:
            m = len(str(col)) + 3
        worksheet.set_column(i, i, min(m, 60), cell_fmt)

    if zero_value_col_idx is not None and len(df) > 0:
        worksheet.conditional_format(1, zero_value_col_idx, len(df), zero_value_col_idx, {
            "type": "cell",
            "criteria": "==",
            "value": 0,
            "format": red_fmt,
        })


def _write_summary_wb_links(writer, sheet_name, df):
    """Колонка «Ссылка» — кликабельная гиперссылка (после to_excel и стилей)."""
    if df is None or len(df) == 0 or "Ссылка" not in df.columns:
        return
    worksheet = writer.sheets[sheet_name]
    workbook = writer.book
    col_idx = list(df.columns).index("Ссылка")
    link_fmt = workbook.add_format({
        "font_color": "#0563C1",
        "underline": 1,
        "border": 1,
        "align": "center",
    })
    for i in range(len(df)):
        url = df["Ссылка"].iloc[i]
        if pd.isna(url):
            continue
        url = str(url).strip()
        if not url.startswith("http"):
            continue
        worksheet.write_url(i + 1, col_idx, url, string="Карточка", cell_format=link_fmt)


def save_competitor_excel(summary_rows, stock_rows, file_path):
    """
    Два листа: «Сводка» (цена, рейтинг, позиции в поиске, …), «Остатки» (как раньше).
    """
    try:
        folder = os.path.dirname(file_path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)

        df_sum = pd.DataFrame(summary_rows)
        df_stock = pd.DataFrame(stock_rows)

        writer = pd.ExcelWriter(file_path, engine="xlsxwriter")
        df_sum.to_excel(writer, sheet_name="Сводка", index=False)
        df_stock.to_excel(writer, sheet_name="Остатки", index=False)

        _style_sheet(writer, "Сводка", df_sum, zero_value_col_idx=None)
        _write_summary_wb_links(writer, "Сводка", df_sum)
        stock_zero_idx = (
            list(df_stock.columns).index("Остаток")
            if stock_rows and "Остаток" in df_stock.columns
            else None
        )
        _style_sheet(writer, "Остатки", df_stock, zero_value_col_idx=stock_zero_idx)

        writer.close()
        print(f"[💎] Отчет успешно создан: {file_path}")
        return file_path

    except Exception as e:
        print(f"[❌] Ошибка при генерации Excel: {e}")
        return None
