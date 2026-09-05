# Apply this tree onto `JustJakeOne/mtg-card-index`

This Cloud Agent cannot push the public index repo (GitHub 403). Copy these files onto that repo, push `main`, then run the two Actions once.

From PowerShell, with both repos as siblings:

```powershell
Copy-Item -Recurse -Force .\contrib\mtg-card-index\* ..\mtg-card-index\
cd ..\mtg-card-index
git add -A
git commit -m "Publish printings, tags, oracle text, Spellbook dump, and rules"
git push origin main
```

Then:

1. https://github.com/JustJakeOne/mtg-card-index/actions/workflows/refresh-card-index.yml → **Run workflow**
2. After that is green: https://github.com/JustJakeOne/mtg-card-index/actions/workflows/refresh-combos.yml → **Run workflow**

Confirm https://github.com/JustJakeOne/mtg-card-index/tree/data lists `printings.csv.gz`, `oracle_tags.csv.gz`, `game_changers.json`, `combos.jsonl`, `MagicCompRules.txt`, and a `cards.csv.gz` whose header includes `oracle_text`.

Then on the DeckForge machine:

```powershell
py -m deckforge data pull
```

That command only downloads `raw.githubusercontent.com/JustJakeOne/mtg-card-index/data/…`. It does not call Scryfall bulk or Spellbook `/variants/`.
