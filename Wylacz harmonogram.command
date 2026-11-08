#!/bin/zsh
# Dwuklik = wyłącza automatyczne wyszukiwanie na tym Macu.
launchctl bootout "gui/$(id -u)/pl.kinga.wynajem" 2>/dev/null
rm -f "$HOME/Library/LaunchAgents/pl.kinga.wynajem.plist"
echo "✅ Harmonogram wyłączony. (To okno możesz zamknąć.)"
