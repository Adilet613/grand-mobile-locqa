# Grand Mobile · Qazaq Loc QA (Decentrathon 6.0)

Автономный инструмент аудита и контроля качества казахской локализации для Flutter ARB-файлов мобильной игры Grand Mobile.

## Команда
- **Adilet Sungatuly** — Lead & Native Qazaq Reviewer

## Результаты аудита
- Проверено **5 479 строк** локализации игры.
- Обнаружено **145 дефектов** по всем 11 типам детекции.
- **100% исправлений (144 строки)** проверены носителем языка (`reviewed_by_human: true`).
- Решена проблема казахского сингармонизма аффиксов (`{name}-ға` / `-ге`).
- Сформирован утверждённый глоссарий игрового сленга (87 терминов: «варн», «мут», «ГК», «отбасы», «фракция»).

## Запуск инструмента
Исходный код CLI находится в папке `locqa_github_ready/`:
```bash
cd locqa_github_ready
python -m pip install .
locqa check --source intl_ru.arb --target intl_kk.arb --glossary glossary.csv --out report.json
