#!/bin/zsh
# Dwuklik = jedno wyszukiwanie od razu (także poza godzinami z harmonogramu).
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Szukam… (to może potrwać kilka minut)"
"$DIR/uruchom.sh" --wymus
tail -n 6 "$DIR/cache/przebiegi.log"
echo "(To okno możesz zamknąć.)"
