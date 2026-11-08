#!/bin/zsh
# Jedno wyszukiwanie na Macu + wysłanie wyników na GitHuba (żeby strona się odświeżyła).
# Uruchamiane automatycznie przez harmonogram macOS (launchd) albo ręcznie.
cd "$(dirname "$0")" || exit 1
mkdir -p cache
LOG=cache/przebiegi.log
{
  echo "=== $(date '+%Y-%m-%d %H:%M') ==="
  # aktualne dane z GitHuba (gdyby coś zmieniło się w chmurze)
  if git remote get-url origin >/dev/null 2>&1; then git pull --rebase --autostash -q || true; fi
  "$HOME/.local/bin/uv" run --quiet wynajem szukaj "$@"
  if git remote get-url origin >/dev/null 2>&1; then
    git add data docs
    if ! git diff --cached --quiet; then
      git commit -q -m "Wyszukiwanie $(date '+%Y-%m-%d %H:%M')"
      git push -q || echo "Nie udało się wysłać na GitHuba (brak internetu?)"
    fi
  fi
} >> "$LOG" 2>&1
# log nie rośnie w nieskończoność
tail -n 3000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
