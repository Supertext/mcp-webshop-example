# Analytics schema

`data/analytics.sqlite`, 30 days ending today. Query it directly:

    sqlite3 data/analytics.sqlite "SELECT ..."

## events

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | Primary key |
| `ts` | TEXT | ISO-8601 UTC |
| `session_id` | TEXT | Groups events into a visit |
| `locale` | TEXT | The **visitor's** language preference from Accept-Language: `en`, `de-CH`, `fr-CH`, `it-CH`. The site was English-only for this whole period, so this is demand, not what was served. |
| `path` | TEXT | e.g. `/`, `/p/arv-tx3`, `/c/climbing`, `/legal/shipping` |
| `event_type` | TEXT | `page_view`, `add_to_cart`, `begin_checkout`, `purchase` |
| `sku` | TEXT | Set on `add_to_cart` and `purchase` only. |
| `revenue_chf` | REAL | Set on `purchase` only |
| `referrer` | TEXT | `organic`, `direct`, `paid`, `social` |
| `device` | TEXT | `mobile`, `desktop` |

## Example queries

Top pages by views:

    SELECT path, COUNT(*) AS views
    FROM events WHERE event_type = 'page_view'
    GROUP BY path ORDER BY views DESC LIMIT 15;

Revenue by product:

    SELECT sku, COUNT(*) AS orders, SUM(revenue_chf) AS revenue
    FROM events WHERE event_type = 'purchase'
    GROUP BY sku ORDER BY revenue DESC;

Conversion funnel by visitor locale:

    SELECT locale,
      COUNT(DISTINCT session_id) AS sessions,
      COUNT(DISTINCT CASE WHEN event_type='begin_checkout' THEN session_id END) AS checkouts,
      COUNT(DISTINCT CASE WHEN event_type='purchase' THEN session_id END) AS buyers
    FROM events GROUP BY locale ORDER BY sessions DESC;
