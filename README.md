# Firn

Firn is a multilingual webshop for alpine equipment: eight products, three Swiss
target locales (`de-CH`, `fr-CH`, `it-CH`), and English as the source. Every
visible string carries a verification state, so the shopfront itself shows which
translations are machine output, which are pending with a human verifier, and
which have landed.

**This is a workshop demo, not production code.** It was built for the session
*Human Expertise as a Tool Call: Giving Your Agent a Professional Verifier Over
MCP* — the point is the workflow, not the shop. Two deliberate simplifications
follow from that: `/admin/analytics` is unauthenticated by design (it is a
localhost demo; there is no user model anywhere in the app), and nothing in this
repository should ever face the internet.

## Quickstart

```bash
make install   # uv sync (or pip install -r requirements.txt)
make seed      # deterministic 30-day analytics + placeholder product imagery
make run       # uvicorn on port 8000, with live reload
make translate # machine-translate the whole shop via the Supertext API (needs a key, below)
```

Then open <http://localhost:8000>. Append a locale prefix for a translated view
(<http://localhost:8000/de-CH>, `/fr-CH`, `/it-CH`). The site reloads itself
within three seconds of a catalogue file changing — no restart needed.

`make reset` returns the repo to its pre-demo state: locale catalogues emptied,
verification ledger cleared, analytics reseeded.

`make check` runs ruff and the tests. The route tests record real page views in
`data/analytics.sqlite`, which shifts the numbers on the dashboard and in
anything the agent reads from it; run `make seed` afterwards to restore the
deterministic 30 days.

## The state model

Every string is resolved at render time from the English source plus the
locale entry. Eight states can come out:

| State | Meaning | Marker |
|---|---|---|
| `source` | English source on the English site | — |
| `source_locked` | `translatable: false` — shown as-is everywhere | 🔒 |
| `fallback` | No entry in this locale's catalogue, so English shows | EN |
| `withheld` | `policy: human_only` and not yet verified — English shows, on purpose | EN |
| `stale` | The English source changed since this translation was made | ! |
| `machine` | Machine translation, never reviewed | MT |
| `pending` | Submitted to the human verifier, awaiting the result | ⏱ |
| `verified` | The verifier's text has landed | ✓ |

Only `machine`, `pending` and `verified` are ever *stored* in a locale file;
`stale`, `withheld` and `fallback` are derived at render time.

### The trust overlay

Append `?trust=1` to any URL (e.g. <http://localhost:8000/fr-CH?trust=1>) and
every string renders with its state marker attached — the audience can see the
whole surface, not just the polished parts.

## The agent's playground

If you are running Claude Code (or any agent) against this repo, these are the
files it reads and writes:

- `content/source.en.json` — the English source plus each string's `class`,
  `surfaces`, `translatable` and optional `policy`.
- `locales/{de-CH,fr-CH,it-CH}.json` — translations with their state.
- `data/verification_ledger.json` — verification orders and spend against the
  CHF 100 budget.
- `data/analytics.sqlite` — 30 days of shaped traffic (schema and example
  queries in `data/SCHEMA.md`; the dashboard lives at `/admin/analytics`).

`CLAUDE.md` is the agent's operating manual for this workflow.

## Machine translation: `make translate`

`scripts/translate.py` sends all 180 translatable strings to the Supertext
public API (`POST /v1/translate/ai/text`, batched to the endpoint's 10,000-char
limit, five requests in flight) and writes them to the locale files as
`state: "machine"`. Each locale goes out as one burst of five requests and lands
in about 20 seconds; the whole shop takes about a minute and costs about CHF 2. `make quote` prices it without translating.

It needs an API key from the Supertext cockpit:

```bash
echo 'SUPERTEXT_API_KEY=<token>' > .env    # gitignored; or export it
```

It never overwrites a `pending` or `verified` entry, so re-running it after a
verification has landed is safe.

## Pointing it at the Supertext MCP

The shop deliberately ships no MCP server of its own. The agent is the
integration layer: it reads the files above, calls the Supertext tools
(`preview_verification`, `confirm_verification`, `get_verification_result`),
and writes the results back.

To enable that, connect the Supertext MCP server to your agent client by
following the steps at <https://www.supertext.com/en/mcp>, and authorise the
account the verification spend should land on. Once the connector is live, the
workflow in `CLAUDE.md` works end-to-end: price a string, approve the spend,
submit, poll, land the verified text.

## License

MIT — see `LICENSE`. The bundled webfonts are not covered by it: IBM Plex and
Chivo are under the SIL Open Font License 1.1, with their license texts next to
the font files in `app/static/fonts/`.
