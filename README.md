# Практическая работа №3 — Аналитика данных и low-code технология

**Студент:** Архангельский Данила Андреевич  
**Группа:** ИСТ-05

## Состав проекта
- `report.md` — подробная структура практической работы и описание трёх модулей Loginom.
- `reflection3.md` — рефлексия.
- `analysis.py` — расчётные проверки по CSV-экспорту из Loginom.
- `requirements.txt` — зависимости.
- `data/README.md` — описание ожидаемых входных данных.

## Запуск вспомогательных расчётов
```bash
python3 -m pip install -r requirements.txt
python3 analysis.py data/transactions.csv
```

Для сравнения ABC-XYZ-сегментов полного периода и последних шести месяцев:
```bash
python3 analysis.py data/transactions.csv --segments-all data/abcxyz_all.csv --segments-6m data/abcxyz_6m.csv
```

## Ограничения
Исходный `transactions_diy.lgd`, результаты индивидуальной попытки Onlinetestpad и готовый Loginom-пакет `.lgp` в переданных материалах отсутствовали. Числовые ответы, которые нельзя вывести из методички, не выдумывались. Сценарии Loginom подробно описаны в `report.md`.