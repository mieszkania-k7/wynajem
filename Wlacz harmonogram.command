#!/bin/zsh
# Dwuklik = włącza automatyczne wyszukiwanie na tym Macu (co 2 godziny, 7:00–23:00).
DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/pl.kinga.wynajem.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$DIR/cache"
chmod +x "$DIR/uruchom.sh"
sed "s#__KATALOG__#$DIR#g" "$DIR/harmonogram/pl.kinga.wynajem.plist" > "$PLIST"
launchctl bootout "gui/$(id -u)/pl.kinga.wynajem" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" "$PLIST" && echo "✅ Harmonogram włączony: wyszukiwanie o 7, 9, 11, …, 23." \
  || echo "❌ Nie udało się włączyć harmonogramu."
echo "(To okno możesz zamknąć.)"
