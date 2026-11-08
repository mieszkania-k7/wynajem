#!/bin/zsh
# Dwuklik = włącza automatyczne wyszukiwanie na tym Macu (3 razy dziennie: 8:05, 15:05, 20:05).
DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/pl.kinga.wynajem.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$DIR/cache"
chmod +x "$DIR/uruchom.sh"
sed "s#__KATALOG__#$DIR#g" "$DIR/harmonogram/pl.kinga.wynajem.plist" > "$PLIST"
launchctl bootout "gui/$(id -u)/pl.kinga.wynajem" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" "$PLIST" && echo "✅ Harmonogram włączony: wyszukiwanie o 8:05, 15:05 i 20:05." \
  || echo "❌ Nie udało się włączyć harmonogramu."
echo "(To okno możesz zamknąć.)"
