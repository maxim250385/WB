"""Сбор сводки конкурента + остатков; одна точка входа для main."""

import random
import time
from collections import defaultdict

from .sklad import WBParser
from .storage import (
    DEFAULT_DEST,
    empty_summary_row,
    find_nm_rank,
    load_search_queries,
    load_snapshot_for_article,
    new_session,
)


def _position_column_label(query):
    q = query.strip()
    short = q[:30] + ("…" if len(q) > 30 else "")
    return f"Позиция: {short}"


def collect_report(articles, data_dir):
    """
    Возвращает (summary_rows, stock_rows).
    summary_rows — по одной строке на артикул (цена, рейтинг, позиции в поиске, …).
    """
    session = new_session()
    queries = load_search_queries(data_dir)
    pos_labels = [_position_column_label(q) for q in queries]

    summary_rows = []
    for nm in articles:
        print(f"[*] Сводка по артикулу: {nm}")
        row, snap_err = load_snapshot_for_article(session, nm, dest=DEFAULT_DEST)
        if row is None:
            row = empty_summary_row(nm)
            if snap_err is not None:
                row["Название"] = f"(карточка не загружена: {snap_err})"

        for q, label in zip(queries, pos_labels):
            pos, rank_err = find_nm_rank(session, nm, q, DEFAULT_DEST)
            if rank_err is not None and rank_err != "bad_request":
                row[label] = "ошибка"
            elif rank_err == "bad_request":
                row[label] = "—"
            elif pos is not None:
                row[label] = pos
            else:
                row[label] = "—"
            time.sleep(random.uniform(0.4, 0.9))

        summary_rows.append(row)

    print("[*] Сбор остатков по регионам…")
    parser = WBParser(session=session)
    stock_rows = parser.get_stock_data(articles)

    total_col = "Всего шт (по остаткам)"
    sum_by_nm = defaultdict(int)
    for r in stock_rows:
        sum_by_nm[str(r.get("Артикул", "")).strip()] += int(r.get("Остаток") or 0)
    for row in summary_rows:
        row[total_col] = sum_by_nm.get(str(row.get("Артикул", "")).strip(), 0)

    return summary_rows, stock_rows
