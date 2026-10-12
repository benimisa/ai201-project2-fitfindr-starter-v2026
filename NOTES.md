# Milestone 1 notes: the data and the starter

Working notes from reading `data/listings.json` and `data/wardrobe_schema.json`
before writing any tools. Commands were run with the project venv
(`.venv/Scripts/python`, Python 3.13).

## Listing fields

`data/listings.json` is a list of 40 listing dicts. Every record has the same
11 fields, in this order (from `python app.py fields`):

| field         | type          | example                                   |
|---------------|---------------|-------------------------------------------|
| `id`          | str           | `lst_001`                                 |
| `title`       | str           | `Vintage Levi's 501 Jeans — Medium Wash`  |
| `description` | str           | free text, a sentence or three            |
| `category`    | str           | `bottoms`                                 |
| `style_tags`  | list[str]     | `['vintage', 'classic', 'denim', 'streetwear']` |
| `size`        | str           | `W30 L30`                                 |
| `condition`   | str           | `good`                                    |
| `price`       | float         | `38.0`                                    |
| `colors`      | list[str]     | `['blue', 'indigo']`                      |
| `brand`       | str or null   | `Levi's`                                  |
| `platform`    | str           | `depop`                                   |

Things `search_listings` has to cope with:

- `size` is a free-form string with 22 distinct values. Clothing uses letters
  and ranges (`S`, `S/M`, `M/L`, `L/XL`, `XL (oversized)`, `XL (fits oversized)`),
  bottoms use waist sizes (`W27` to `W32`, and `W30 L30`), shoes use `US 7` to
  `US 9` including `US 8.5`, and some items are `One Size`,
  `One Size (adjustable)` or `One Size / Oversized`. A plain substring test is
  wrong: `"s" in "us 9"` and `"l" in "xl"` are both true.
- `category` is one of `tops`, `bottoms`, `outerwear`, `shoes`, `accessories`.
- `platform` is one of `depop`, `poshmark`, `thredUp`.
- `condition` is one of `excellent`, `good`, `fair`.
- `price` is always a float, from 12.0 to 75.0.
- `brand` is `null` for 32 of the 40 listings. Nothing can assume it is there.
- Keyword matching has three text sources: `title`, `description`, and
  `style_tags`. The example query "vintage graphic tee" matches `lst_002`
  (tags include `vintage` and `graphic tee`) and `lst_006` (title starts with
  `Graphic Tee`, tags include `graphic tee` and `vintage`).

## Wardrobe shape

`suggest_outfit` receives a wardrobe dict with one key, `items`, holding a
list of items. Each item has six fields (from `python app.py fields`):

| field        | type         | example                               |
|--------------|--------------|---------------------------------------|
| `id`         | str          | `w_001`                               |
| `name`       | str          | `Baggy straight-leg jeans, dark wash` |
| `category`   | str          | `bottoms`                             |
| `colors`     | list[str]    | `['dark blue', 'indigo']`             |
| `style_tags` | list[str]    | `['denim', 'streetwear', 'baggy']`    |
| `notes`      | str or null  | `High-waisted, sits above the hip`    |

- `get_example_wardrobe()` in `utils/data_loader.py` returns the schema's
  `example_wardrobe`: 10 items covering tops, bottoms, outerwear, shoes and
  accessories.
- `get_empty_wardrobe()` returns `{"items": []}`. The loader strips the
  schema's `_note` key, so an empty wardrobe is exactly a dict with an empty
  `items` list, not `None` and not a missing key. `suggest_outfit` has to
  check `wardrobe["items"]` for emptiness, not the wardrobe itself.

## Starter check

Nothing is built yet, so the agent should report that the loop is missing.
It does:

```
$ .venv/Scripts/python app.py ask 'vintage graphic tee under $30'

  The planning loop isn't built yet — see the TODO in agent.py.

0 model calls this session
```

Exit code 0, and no model call was made because all three tools in
`tools.py` are stubs. Single quotes around the query on purpose: in
PowerShell, double quotes would swallow `$30` as a variable.

`python app.py examples` lists five queries the data can match and one it
cannot (`designer ballgown size XXS under $5`), which is the empty-search
branch to test later.
