# mtg-card-index

Public Commander card data for [DeckForge](https://github.com/JustJakeOne/DeckForge). Clients **download** this branch; they do not re-ingest Scryfall bulk or paginate Spellbook.

Published on branch [`data`](https://github.com/JustJakeOne/mtg-card-index/tree/data):

| File | Job | Cadence |
|---|---|---|
| `cards.csv.gz` | Refresh card index | daily |
| `printings.csv.gz` | Refresh card index | daily |
| `oracle_tags.csv.gz` | Refresh card index | daily |
| `game_changers.json` | Refresh card index | daily |
| `combos.jsonl` | Refresh Spellbook combos | weekly |
| `MagicCompRules.txt` | Refresh Spellbook combos | weekly (no-op if unchanged) |
| `BUILD_INFO.txt` | both | merged stamps |

`cards.csv` is one row per oracle card, including `oracle_text`. Combos come from Commander Spellbook’s published dump (`json.commanderspellbook.com/variants.json.gz`), not from paginating `/variants/`.

Raw URLs: `https://raw.githubusercontent.com/JustJakeOne/mtg-card-index/data/<file>`
