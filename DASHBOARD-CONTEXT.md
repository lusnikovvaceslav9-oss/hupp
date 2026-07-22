# Hupp — контекст дашборда

Форк логики из `Desktop/дашборд` (elixir-dashboard / Planto auto-feed) под веб-проект **Hupp**.

## Отличия от Planto

| | Planto | Hupp |
|---|---|---|
| Трафик | Direct | Direct |
| Продукт | App (AppMetrica) | Web (Metrika) |
| Конверсии | trial_started + RuStore bills | цели Метрики |
| Оплаты | Supabase | нет (пока) |

## Маппинг колонок

CSV специально совместим с Planto-парсером в `elixir.html`:

- `installs` = визиты Метрики  
- `trials` = достигает цели 1  
- `fb` = достигает цели 2 (если задана)  
- `sold` = 0  

Лейблы в UI: Visits / Goals / Goal 2.

## Файлы

- `scripts/hupp-feed/` — фид
- `config/hupp.json` — anchor, counter, goals, пути
- `data/hupp-*.csv/json` — выход фида
- `elixir.html` — UI

Не коммитить `secrets.env`.
