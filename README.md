# Hupp Dashboard

Аналог elixir-дашборда под проект **Hupp**. Автофид: **Yandex Direct + Yandex Metrika**.

## Воронка Метрики → колонки UI

| Событие | Goal ID | UI / CSV | Смысл |
|---|---|---|---|
| Visits | — | Visits → `installs` | визиты |
| reach_pay | 584550528 | Reach pay → `trials` | клик «Получить/Оплатить», скролл к форме |
| view_pay | 584550529 | View pay → `fb` | карточка оплаты на экране |
| pay_submit | 584550530 | Pay submit → `sold` | нажал «Оплатить» → ушёл на ЮKassa |
| purchase | 584550531 | Purchase → `purchase` | успешная оплата, экран выдачи (**цель для рекламы**) |
| contact_info | 584588133 | Contact info → `contact_info` | заполнил контакты |
| form_submit | 584588134 | Form submit → `form_submit` | отправки форм |
| contact_sent | 584588135 | Contact sent → `contact_sent` | отправил контакты |

Счётчик: `110726695` (в `config/hupp.json`).

## Стартовый пример CSV

При первом открытии подставляется [`data/hupp-start.csv`](data/hupp-start.csv) — **только spend/clicks/impressions** из отчёта Директа `partners-m` за 16.07.2026.

**Конверсии и визиты всегда из Яндекс Метрики** (`data/hupp-daily.csv`). Колонка «Конверсии» в CSV Директа игнорируется.

Оригинал отчёта: [`data/examples/partners-m-2026-07-16.csv`](data/examples/partners-m-2026-07-16.csv).

## Безопасность секретов

- Токены только в локальном `secrets.env` (chmod 600) или GitHub Actions Secrets.
- `secrets.env` в `.gitignore` (`*.env`) — **не коммитить**.
- В репо лежит только `secrets.env.example` без значений.
- Не вставлять OAuth в `config/`, `elixir.html`, README, Issues.

```bash
cp secrets.env.example secrets.env
# впиши METRIKA_OAUTH_TOKEN / DIRECT_* локально
chmod 600 secrets.env
```

Токен Метрики должен иметь доступ к API счётчика (oauth.yandex.ru → права `metrika:read` / доступ к приложению со счётчиком). Если API отвечает `403 access_denied` — перевыпусти токен с нужными правами.

## Прогон

```bash
pip install -r scripts/hupp-feed/requirements.txt
python scripts/hupp-feed/__main__.py --work-dir .
python -m http.server 8081 --bind 127.0.0.1
# → http://127.0.0.1:8081/elixir.html
```

## Деплой на Netlify (Git — рекомендуется)

Репозиторий: **https://github.com/lusnikovvaceslav9-oss/hupp**

Netlify при push в `main` сам собирает сайт (`bash scripts/pack-netlify.sh` → `netlify-upload/`).

### Привязать к **существующему** сайту (домен не меняется)

Если сайт уже есть (например `dapper-sorbet-b8c44b.netlify.app`):

1. https://app.netlify.com/ → открой **этот** сайт (не «Add new site»)
2. **Site configuration** → **Build & deploy** → **Continuous deployment**
3. **Link repository** → GitHub → `lusnikovvaceslav9-oss/hupp`
4. Branch: `main` · Build command: `bash scripts/pack-netlify.sh` · Publish: `netlify-upload`
5. **Deploy site**

URL и custom domain остаются прежними — меняется только источник деплоя.

### Ручной деплой (без Git)

- **Рабочий стол:** `hupp-netlify/` или `hupp-netlify.zip`
- В проекте: `netlify-upload/` (пересобрать: `scripts/pack-netlify.sh`)

1. https://app.netlify.com/ → **Add new site** → **Deploy manually**
2. Перетащи папку `hupp-netlify` (или zip)

Внутри только статика: `elixir.html`, `data/`, `assets/`. Секреты и Python-feed не нужны.  
Admin-пароль: `ADMIN_PW` в `elixir.html` — смени перед публичным URL.

## Деплой (GitHub Pages)

Не обязателен, если льёшь на Netlify. Для Pages: workflow `pages.yml`, без `secrets.env` в репо.

## Автообновление

`.github/workflows/hupp-feed.yml` — каждый час. В Actions Secrets добавь ключи из `secrets.env.example`.
