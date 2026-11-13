#!/usr/bin/env python3
"""Calculations for practical work 3 from a Loginom CSV export.

Accepted source columns (English): trDte, bcode, clientID, item, itemGroup,
quantity, amount. Russian column names are also supported.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

ALIASES = {
    "Клиент": {"клиент", "client", "clientid", "customer", "customerid"},
    "Товар": {"товар", "item", "product", "productid", "sku"},
    "Дата продажи": {"дата продажи", "trdte", "trdate", "date", "saledate"},
    "Кол-во": {"кол-во", "количество", "quantity", "qty"},
    "Сумма": {"сумма", "amount", "sales", "revenue"},
    "Код чека": {"код чека", "bcode", "billcode", "receipt", "receiptid"},
}
SEGMENT_ALIASES = {
    "Товар": {"товар", "item", "product", "sku"},
    "Группа ABC": {"группа abc", "abc_group", "abc", "abcgroup"},
    "Группа XYZ": {"группа xyz", "xyz_group", "xyz", "xyzgroup"},
}
REQUIRED = ["Клиент", "Товар", "Дата продажи", "Кол-во", "Сумма"]


def normalize_columns(frame: pd.DataFrame, aliases: dict[str, set[str]]) -> pd.DataFrame:
    lookup = {str(c).strip().casefold(): c for c in frame.columns}
    rename = {}
    for canonical, candidates in aliases.items():
        for candidate in candidates:
            original = lookup.get(candidate.casefold())
            if original is not None:
                rename[original] = canonical
                break
    return frame.rename(columns=rename)


def read_csv(path: str, encoding: str, sep: str) -> pd.DataFrame:
    return pd.read_csv(path, encoding=encoding, sep=sep)


def calculate_transactions(path: str, encoding: str, sep: str) -> dict:
    df = normalize_columns(read_csv(path, encoding, sep), ALIASES)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing required columns {missing}. Available: {list(df.columns)}")
    df["Дата продажи"] = pd.to_datetime(df["Дата продажи"], errors="coerce", dayfirst=True)
    for col in ["Кол-во", "Сумма"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    raw_rows = len(df)
    df = df.dropna(subset=REQUIRED).copy()
    df["День визита"] = df["Дата продажи"].dt.date

    clients = df.groupby("Клиент", dropna=False).agg(
        Расходы=("Сумма", "sum"),
        Количество=("Кол-во", "sum"),
        Визиты=("День визита", "nunique"),
    )
    one_visit = clients[clients["Визиты"] == 1]

    zero_qty = int((df["Кол-во"] == 0).sum())
    negative_qty = int((df["Кол-во"] < 0).sum())
    valid = df[df["Кол-во"] > 0].copy()
    valid["Цена"] = (valid["Сумма"] / valid["Кол-во"]).round(2)
    simple_mean = valid.groupby("Товар")["Цена"].mean()
    weighted = (
        (valid.assign(Взвешенная_стоимость=valid["Цена"] * valid["Кол-во"])
         .groupby("Товар")["Взвешенная_стоимость"].sum())
        / valid.groupby("Товар")["Кол-во"].sum()
    )
    prices = pd.DataFrame({
        "Простая средняя цена": simple_mean,
        "Средневзвешенная цена": weighted,
    }).sort_index()

    metrics = {
        "rows": len(df),
        "dropped_incomplete_rows": raw_rows - len(df),
        "clients_spend_le_100": int((clients["Расходы"] <= 100).sum()),
        "one_visit_clients": int(len(one_visit)),
        "one_visit_mean_spend": float(one_visit["Расходы"].mean()) if len(one_visit) else float("nan"),
        "clients_visits_gt_50": int((clients["Визиты"] > 50).sum()),
        "zero_quantity_rows": zero_qty,
        "negative_quantity_rows": negative_qty,
        "products_simple_mean_le_10": int((simple_mean <= 10).sum()),
    }
    out_dir = Path(path).resolve().parent
    clients.to_csv(out_dir / "client_statistics.csv", encoding="utf-8-sig")
    prices.to_csv(out_dir / "price_summary.csv", encoding="utf-8-sig")
    return {"metrics": metrics, "clients": clients, "prices": prices}


def compare_segments(path_full: str, path_recent: str, encoding: str, sep: str, output_dir: Path) -> dict:
    full = normalize_columns(read_csv(path_full, encoding, sep), SEGMENT_ALIASES)
    recent = normalize_columns(read_csv(path_recent, encoding, sep), SEGMENT_ALIASES)
    needed = ["Товар", "Группа ABC", "Группа XYZ"]
    for label, frame in [("full period", full), ("last six months", recent)]:
        missing = [c for c in needed if c not in frame.columns]
        if missing:
            raise SystemExit(f"Missing fields in {label} segment export: {missing}")

    full = full[needed].drop_duplicates("Товар").copy()
    recent = recent[needed].drop_duplicates("Товар").copy()
    full["Сегмент за весь период"] = full["Группа ABC"].astype(str).str.strip() + full["Группа XYZ"].astype(str).str.strip()
    recent["Сегмент за 6 месяцев"] = recent["Группа ABC"].astype(str).str.strip() + recent["Группа XYZ"].astype(str).str.strip()
    both = full[["Товар", "Сегмент за весь период"]].merge(
        recent[["Товар", "Сегмент за 6 месяцев"]], on="Товар", how="inner", validate="one_to_one"
    )
    changed = both[both["Сегмент за весь период"] != both["Сегмент за 6 месяцев"]].sort_values("Товар")
    output = output_dir / "changed_abc_xyz_segments.csv"
    changed.to_csv(output, index=False, encoding="utf-8-sig")
    return {"common_products": len(both), "changed_products": len(changed), "file": output}


def main() -> None:
    parser = argparse.ArgumentParser(description="Practical work 3 calculations")
    parser.add_argument("csv", help="Loginom CSV export of transaction rows")
    parser.add_argument("--encoding", default="utf-8-sig")
    parser.add_argument("--sep", default=",")
    parser.add_argument("--segments-all", help="ABC-XYZ export for the full period")
    parser.add_argument("--segments-6m", help="ABC-XYZ export for the latest six months")
    args = parser.parse_args()

    result = calculate_transactions(args.csv, args.encoding, args.sep)
    metrics = result["metrics"]
    print("ПРОВЕРКА ДАННЫХ")
    print(f"Строк после очистки: {metrics['rows']:,}".replace(",", " "))
    print(f"Строк с нулевым количеством: {metrics['zero_quantity_rows']}")
    print(f"Строк с отрицательным количеством: {metrics['negative_quantity_rows']}")
    print("\nИНДИВИДУАЛЬНЫЕ РАСЧЁТЫ")
    print(f"1. Клиентов с расходами <= 100 руб.: {metrics['clients_spend_le_100']}")
    value = metrics["one_visit_mean_spend"]
    print(f"2. Средние суммарные расходы одновизитника: {value:.2f} руб. (ответ: {round(value)})")
    print(f"   Одновизитных клиентов: {metrics['one_visit_clients']}")
    print(f"3. Клиентов с более чем 50 визитами: {metrics['clients_visits_gt_50']}")
    print(f"4. Товаров со средней простой ценой <= 10 руб.: {metrics['products_simple_mean_le_10']}")
    print("Сводки сохранены: client_statistics.csv, price_summary.csv")

    if bool(args.segments_all) != bool(args.segments_6m):
        raise SystemExit("For task 5 pass both --segments-all and --segments-6m.")
    if args.segments_all:
        comparison = compare_segments(args.segments_all, args.segments_6m, args.encoding, args.sep,
                                      Path(args.csv).resolve().parent)
        print(f"5. Общих товаров в двух периодах: {comparison['common_products']}")
        print(f"   Товаров с изменившимся ABC-XYZ-сегментом: {comparison['changed_products']}")
        print(f"   Перечень: {comparison['file']}")


if __name__ == "__main__":
    main()
