# This file contains CSV-based calculations for practical work 3.
# Source data must be exported from Loginom with columns:
# Клиент, Товар, Дата продажи, Кол-во, Сумма
import argparse
from pathlib import Path
import pandas as pd

TX_COLS = ['Клиент', 'Товар', 'Дата продажи', 'Кол-во', 'Сумма']
SEG_COLS = ['Товар', 'Группа ABC', 'Группа XYZ']

def main():
    p = argparse.ArgumentParser(description='Calculations for Loginom practical work 3')
    p.add_argument('csv', help='CSV export of transactions')
    p.add_argument('--encoding', default='utf-8-sig')
    p.add_argument('--sep', default=',')
    p.add_argument('--segments-all', help='ABC-XYZ export for full period')
    p.add_argument('--segments-6m', help='ABC-XYZ export for latest six months')
    a = p.parse_args()
    df = pd.read_csv(a.csv, encoding=a.encoding, sep=a.sep)
    missing = [x for x in TX_COLS if x not in df.columns]
    if missing:
        raise SystemExit(f'Missing columns: {missing}; available: {list(df.columns)}')
    df['Дата продажи'] = pd.to_datetime(df['Дата продажи'], errors='coerce', dayfirst=True)
    for col in ['Кол-во', 'Сумма']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=TX_COLS).copy()
    df['День визита'] = df['Дата продажи'].dt.date
    customers = df.groupby('Клиент').agg(Расходы=('Сумма', 'sum'), Визиты=('День визита', 'nunique'))
    one_visit_ids = customers.index[customers['Визиты'] == 1]
    one_visit_checks = df.loc[df['Клиент'].isin(one_visit_ids), 'Сумма']
    print('Клиентов с расходами <= 100 руб.:', int((customers['Расходы'] <= 100).sum()))
    print('Средний чек клиентов-одновизитников:', round(one_visit_checks.mean()) if len(one_visit_checks) else 'нет данных')
    print('Средние суммарные расходы одного одновизитника:', round(customers.loc[one_visit_ids, 'Расходы'].mean()) if len(one_visit_ids) else 'нет данных')
    print('Клиентов с более чем 50 визитами:', int((customers['Визиты'] > 50).sum()))
    positive = df[df['Кол-во'] > 0].copy()
    positive['Цена'] = positive['Сумма'] / positive['Кол-во']
    means = positive.groupby('Товар')['Цена'].mean()
    print('Товаров со средней простой ценой <= 10 руб.:', int((means <= 10).sum()))
    weighted = positive.groupby('Товар').apply(lambda g: (g['Цена'] * g['Кол-во']).sum() / g['Кол-во'].sum())
    pd.DataFrame({'Простая средняя цена': means, 'Средневзвешенная цена': weighted}).to_csv(Path(a.csv).with_name('price_summary.csv'), encoding='utf-8-sig')
    print('Транзакций с нулевым количеством:', int((df['Кол-во'] == 0).sum()))
    if bool(a.segments_all) != bool(a.segments_6m):
        raise SystemExit('Для сегментов нужно передать оба файла --segments-all и --segments-6m')
    if a.segments_all:
        full = pd.read_csv(a.segments_all, encoding=a.encoding, sep=a.sep)[SEG_COLS].drop_duplicates('Товар').copy()
        six = pd.read_csv(a.segments_6m, encoding=a.encoding, sep=a.sep)[SEG_COLS].drop_duplicates('Товар').copy()
        full['Сегмент полный период'] = full['Группа ABC'].astype(str) + '-' + full['Группа XYZ'].astype(str)
        six['Сегмент последние 6м'] = six['Группа ABC'].astype(str) + '-' + six['Группа XYZ'].astype(str)
        both = full[['Товар', 'Сегмент полный период']].merge(six[['Товар', 'Сегмент последние 6м']], on='Товар', how='inner')
        changed = both[both['Сегмент полный период'] != both['Сегмент последние 6м']]
        out = Path(a.csv).with_name('changed_abc_xyz_segments.csv')
        changed.to_csv(out, index=False, encoding='utf-8-sig')
        print('Общих товаров в двух периодах:', len(both))
        print('Товаров с изменившимся сегментом:', len(changed))
        print('Список изменений:', out)

if __name__ == '__main__':
    main()
