#!/usr/bin/env bash
# Собирает папку для drag-and-drop на Netlify (без git, secrets, Python).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/netlify-upload}"
DESKTOP_COPY="${HOME}/Desktop/hupp-netlify"

rm -rf "$OUT"
mkdir -p "$OUT/assets" "$OUT/data/examples"

cp "$ROOT/index.html" "$OUT/"
cp "$ROOT/elixir.html" "$OUT/"
cp "$ROOT/assets/hupp-mascot.jpg" "$OUT/assets/"

# Данные Метрики + резервный стартовый Direct spend.
# Загруженный в Admin CSV хранится в браузере и общем JSONBin, поэтому виден всем.
cp "$ROOT/data/hupp-daily.csv" "$OUT/data/"
cp "$ROOT/data/hupp-start.csv" "$OUT/data/"
cp "$ROOT/data/hupp-meta.json" "$OUT/data/"
# cohort не используется в UI, но маленький — можно положить
cp "$ROOT/data/hupp-cohort.json" "$OUT/data/" 2>/dev/null || true
cp "$ROOT/data/examples/partners-m-2026-07-16.csv" "$OUT/data/examples/" 2>/dev/null || true

# Netlify config внутри upload-папки (publish = ".")
cat > "$OUT/netlify.toml" <<'EOF'
[build]
  publish = "."
  command = "echo ok"

[[redirects]]
  from = "/"
  to = "/elixir.html"
  status = 302

[[headers]]
  for = "/data/*"
  [headers.values]
    Cache-Control = "public, max-age=60, must-revalidate"

[[headers]]
  for = "/*.html"
  [headers.values]
    Cache-Control = "public, max-age=0, must-revalidate"
EOF

cat > "$OUT/КАК-ЗАЛИТЬ.txt" <<'EOF'
Hupp → Netlify (без Git)
========================

1. Открой https://app.netlify.com/
2. Sites → «Add new site» → «Deploy manually»
3. Перетащи ВСЮ эту папку (netlify-upload / hupp-netlify) в окно
4. Готово — откроется URL вида *.netlify.app

Обновить стату Метрики позже:
  - на Netlify сайт сам тянет свежий hupp-daily.csv из elixir-dashboard (GitHub, ~каждый час)
  - кнопка «Обновить» перечитывает Metrika + Direct CSV из облака
  - локально (localhost) читается папка data/

CSV Директа:
  - загружается через Admin;
  - сохраняется локально в браузере + в общем облачном хранилище;
  - на другом ПК/телефоне подтягивается автоматически;
  - новый CSV обновляет совпавшие даты и сохраняет spend прошлых дней.

Admin: пароль в elixir.html (ADMIN_PW) — смени перед публичным URL.
Секреты (токены) сюда НЕ кладутся и на Netlify не нужны.
EOF

# Копия на рабочий стол — только локально (на Netlify CI папки Desktop нет)
if [[ -d "${HOME}/Desktop" ]]; then
  rm -rf "$DESKTOP_COPY"
  cp -R "$OUT" "$DESKTOP_COPY"
  ZIP="${HOME}/Desktop/hupp-netlify.zip"
  rm -f "$ZIP"
  ( cd "$(dirname "$OUT")" && zip -r -q "$ZIP" "$(basename "$OUT")" )
  echo "OK: $DESKTOP_COPY"
  echo "OK: $ZIP"
fi

echo "OK: $OUT"
du -sh "$OUT"
