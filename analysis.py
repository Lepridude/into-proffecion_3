#!/usr/bin/env python3
"""Расчёты практической работы №3 по CSV-экспорту из Loginom.

Поддерживаются русские поля и стандартные имена набора:
trDte, bcode, clientID, item, itemGroup, quantity, amount.

Запуск:
    python analysis.py data/transactions.csv

Сравнение ABC-XYZ сегментов (оба экспорта должны быть получены штатным
компонентом Loginom Silver Kit):
    python analysis.py data/transactions.csv \
      --segments-all data/abcxyz_all.csv --segments-6m data/abcxyz_6m.csv
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
    "Группа товара": {"группа товара", "itemgroup", "productgroup", "category"},
}
REQUIRED = ["Клиент", "Товар", "Дата продажи", "Кол-во", "Сумма"]
SEGMENT_ALIASES = {
    "Товар": {"товар", "item", "product", "sku"},
    "Группа ABC": {"группа abc", "abc_group", "abc", "abcgroup"},
    "Группа XYZ": {"группа xyz", "xyz_group", "xyz", "xyzgroup"},
}


def normalize_columns(frame: pd.DataFrame, aliases: dict[str, set[str]]) -> pd.DataFrame:
    """Переименовать столбцы независимо от регистра и языка исходного набора."""
    lookup = {str(col).strip().casefold(): col for col in frame.columns}
    rename: dict[str, str] = {}
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
    missing = [col for col in REQUIRED if col not in df.columns]
    if missing:
        raise SystemExit(
            f"Не найдены обязательные поля {missing}. Доступны: {list(df.columns)}. "
            "Поддерживаются русские имена и trDte/clientID/item/quantity/amount."
        )

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
    # Исключаем только нулевое количество — именно это требует методичка.
    valid = df[df["Кол-во"] != 0].copy()
    # Методичка предписывает округлить цену каждой транзакции до 2 знаков.
    valid["Цена"] = (valid["Сумма"] / valid["Кол-во"]).round(2)
    simple_mean = valid.groupby("Товар")["Цена"].mean()
    weighted_cost = (valid["Цена"] * valid["Кол-во"]).groupby(valid["Товар"]).sum()
    total_quantity = valid.groupby("Товар")["Кол-во"].sum()
    weighted_denominator = total_quantity.where(total_quantity.ne(0))
    weighted_mean = weighted_cost.div(weighted_denominator)
    prices = pd.DataFrame({
        "Простая средняя цена": simple_mean,
        "Средневзвешенная цена": weighted_mean,
    }).sort_index()

    return {
        "transactions": df,
        "clients": clients,
        "prices": prices,
        "metrics": {
            "rows": len(df),
            "dropped_incomplete_rows": raw_rows - len(df),
            "clients_spend_le_100": int((clients["Расходы"] <= 100).sum()),
            "one_visit_clients": int(len(one_visit)),
            "one_visit_mean_spend": float(one_visit["Расходы"].mean()) if len(one_visit) else float("nan"),
            "clients_visits_gt_50": int((clients["Визиты"] > 50).sum()),
            "zero_quantity_rows": zero_qty,
            "negative_quantity_rows": negative_qty,
            "products_simple_mean_le_10": int((simple_mean <= 10).sum()),
            "simple_mean_price_products": int(len(simple_mean)),
        },
    }


def compare_segments(path_full: str, path_recent: str, encoding: str, sep: str, output_dir: Path) -> dict:
    full = normalize_columns(read_csv(path_full, encoding, sep), SEGMENT_ALIASES)
    recent = normalize_columns(read_csv(path_recent, encoding, sep), SEGMENT_ALIASES)
    required = ["Товар", "Группа ABC", "Группа XYZ"]
    for label, frame in [("полный период", full), ("последние 6 месяцев", recent)]:
        missing = [col for col in required if col not in frame.columns]
        if missing:
            raise SystemExit(f"В выгрузке сегментов ({label}) отсутствуют поля {missing}")
        if frame[required].isna().any().any():
            raise SystemExit(f"В выгрузке сегментов ({label}) есть пустые значения")
        if frame["Товар"].duplicated().any():
            duplicate_items = frame.loc[frame["Товар"].duplicated(), "Товар"].astype(str).head(5).tolist()
            raise SystemExit(
                f"В выгрузке сегментов ({label}) несколько строк на один товар: {duplicate_items}"
            )

    full = full[required].copy()
    recent = recent[required].copy()
    full["Сегмент за весь период"] = (
        full["Группа ABC"].astype(str).str.strip() + full["Группа XYZ"].astype(str).str.strip()
    )
    recent["Сегмент за 6 месяцев"] = (
        recent["Группа ABC"].astype(str).str.strip() + recent["Группа XYZ"].astype(str).str.strip()
    )
    common = full[["Товар", "Сегмент за весь период"]].merge(
        recent[["Товар", "Сегмент за 6 месяцев"]],
        on="Товар", how="inner", validate="one_to_one"
    )
    changed = common[
        common["Сегмент за весь период"] != common["Сегмент за 6 месяцев"]
    ].sort_values("Товар")
    out_path = output_dir / "changed_abc_xyz_segments.csv"
    changed.to_csv(out_path, index=False, encoding="utf-8-sig")
    return {"common_products": len(common), "changed_products": len(changed), "file": out_path}


def main() -> None:
    parser = argparse.ArgumentParser(description="Расчёты практической работы №3 по CSV-экспорту Loginom")
    parser.add_argument("csv", help="CSV-экспорт транзакций")
    parser.add_argument("--encoding", default="utf-8-sig")
    parser.add_argument("--sep", default=",")
    parser.add_argument("--segments-all", help="ABC-XYZ выгрузка полного периода")
    parser.add_argument("--segments-6m", help="ABC-XYZ выгрузка последних шести месяцев")
    args = parser.parse_args()

    result = calculate_transactions(args.csv, args.encoding, args.sep)
    m = result["metrics"]
    output_dir = Path(args.csv).resolve().parent
    result["clients"].to_csv(output_dir / "client_statistics.csv", encoding="utf-8-sig")
    result["prices"].to_csv(output_dir / "price_summary.csv", encoding="utf-8-sig")

    print("ПРОВЕРКА ДАННЫХ")
    print(f"Строк транзакций после очистки: {m['rows']:,}".replace(",", " "))
    print(f"Строк с нулевым количеством: {m['zero_quantity_rows']}")
    print(f"Строк с отрицательным количеством: {m['negative_quantity_rows']}")
    print("\nИНДИВИДУАЛЬНЫЕ РАСЧЁТЫ")
    print(f"1. Клиентов с расходами <= 100 руб.: {m['clients_spend_le_100']}")
    val = m["one_visit_mean_spend"]
    print(f"2. Средние суммарные расходы одного одновизитника: {val:.2f} руб. (округлённый ответ: {round(val)})")
    print(f"   Одновизитных клиентов: {m['one_visit_clients']}")
    print(f"3. Клиентов с более чем 50 визитами: {m['clients_visits_gt_50']}")
    print(f"4. Товаров со средней простой ценой <= 10 руб.: {m['products_simple_mean_le_10']}")
    print("Сохранены client_statistics.csv и price_summary.csv")

    if bool(args.segments_all) != bool(args.segments_6m):
        raise SystemExit("Для задания 5 передайте оба файла --segments-all и --segments-6m.")
    if args.segments_all:
        cmp = compare_segments(args.segments_all, args.segments_6m, args.encoding, args.sep, output_dir)
        print(f"5. Общих товаров в двух периодах: {cmp['common_products']}")
        print(f"   Товаров с изменившимся ABC-XYZ-сегментом: {cmp['changed_products']}")
        print(f"   Перечень: {cmp['file']}")


if __name__ == "__main__":
    main()