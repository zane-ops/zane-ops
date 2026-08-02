# Caddy proxy logs & custom configuration — Implementation Plan

Branch: `feat/caddy-master-logs`. Issue: *[✨ feature] Caddy proxy logs & custom configuration*.

**What we want:** an instance-wide view of everything the ZaneOps proxy does — every HTTP request (services, ZaneOps itself, unmatched domains), Caddy's own application logs, the country each request came from, and a way to feed custom Caddyfile snippets to the proxy.

**Where it lives:** the `console` app (`/api/console/…`), the instance-owner surface, next to `SystemSettings`. Permission is `IsInstanceOwner`, like [system.py](../console/views/system.py).

**Not in scope:** GeoIP blocking, Frontend changes. Endpoints only.

---

## Ground rules

1. **Strict order.** Four phases, one finished before the next starts: master HTTP logs → GeoIP country → proxy app logs → custom Caddy config.
2. **Inside a phase: tests → models → endpoints.** Tests are written first and validated by hand before anything else is touched.
3. Nothing from a later phase gets written early, even when it is a two-line change.

---

## How things work today

| Piece                | Where                                                                     | What it does                                                                                                                            |
| -------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Log ingest           | [logs.py](../zane_api/views/logs.py) `LogIngestAPIView`                   | fluentd posts every container's logs here, tagged with `service_id`                                                                     |
| Proxy access logs    | same file                                                                 | logs tagged `zane.proxy` are parsed as JSON, and **dropped unless** they carry `zane_service_id` / `zane_stack_id` / `zane_registry_id` |
| HTTP logs storage    | `HttpLog` in [main.py](../zane_api/models/main.py)                        | Postgres, one row per request                                                                                                           |
| Runtime logs storage | [loki_client.py](../search/loki_client.py)                                | Loki, labelled by `service_id` / `deployment_id` / `source` / `level`                                                                   |
| Proxy config         | [proxy.py](../temporal/proxy.py), [bootstrap.py](../backend/bootstrap.py) | Caddy JSON driven through the admin API, persisted by `caddy run --resume`                                                              |
| Route markers        | [proxy.py](../temporal/proxy.py)                                          | `log_append` handlers stamp `zane_*` keys onto each access log                                                                          |

Two consequences that drive phase 1 and 3:

- Requests to the **ZaneOps dashboard/API** and to the **404 catch-all** carry no `zane_*` marker, so today they are thrown away.
- Caddy's **own** logs (cert issuance, config reloads, errors) also arrive tagged `zane.proxy`, fail the access-log shape, and are thrown away too.

---

## Phase 1 — Master HTTP logs

Show every HTTP request that went through the proxy, across all projects, including ZaneOps' own traffic.

### 1.1 Tests — ✅ done

[console/tests/proxy_logs.py](../console/tests/proxy_logs.py) — `ProxyHttpLogIngestViewTests`, `ProxyMasterHttpLogViewTests`.

### 1.2 Models — ✅ done

`HttpLog` in [main.py](../zane_api/models/main.py):

- `LogSource` choices — `SERVICE`, `COMPOSE_STACK`, `BUILD_REGISTRY`, `ZANE_OPS`, `UNKNOWN`
- `source` field, default `SERVICE`, indexed
- migrations `0343_httplog_request_country_code_httplog_source_and_more`, `0344_auto_20260802_1535` (backfills `COMPOSE_STACK` / `BUILD_REGISTRY` from the existing ids)

### 1.3 Proxy markers — ⬜ todo

- `ZaneProxyClient.ServiceType.ZANE_OPS = "zaneops"` in [proxy.py](../temporal/proxy.py)
- add the `log_append` handlers (`zane_service_type: zaneops`, `zane_request_id`) to the `api.zaneops.internal` / `front.zaneops.internal` routes in [bootstrap.py](../backend/bootstrap.py)

Without this, dashboard traffic still lands as `UNKNOWN`.

### 1.4 Ingest — ⬜ todo

In `LogIngestAPIView`, for `tag.service_id == zane.proxy`:

| Log shape                                         | Result                                               |
| ------------------------------------------------- | ---------------------------------------------------- |
| `logger == "http.log.access"` + `zane_service_id` | `HttpLog(source=SERVICE)` — unchanged                |
| … + `zane_stack_id` / `zane_registry_id`          | `COMPOSE_STACK` / `BUILD_REGISTRY` — unchanged       |
| … + `zane_service_type == "zaneops"`              | `HttpLog(source=ZANE_OPS)`, no service/deployment id |
| … + `zane_service_type == "zaneops"`, static asset path | dropped                                        |
| … + no `zane_*` marker at all                     | `HttpLog(source=UNKNOWN)`                            |

**Dashboard traffic:** both the API and the frontend are logged, under the same `ZANE_OPS` source — `request_path` already tells them apart, no need for two sources.

Static assets are dropped at ingest, with a hardcoded prefix list in [logs.py](../zane_api/views/logs.py):

```python
ZANE_OPS_IGNORED_PATH_PREFIXES = ("/assets/", "/fonts/", "/logo/")
```

(matches `frontend/build/client`, plus `/robots.txt` is harmless enough to keep). One dashboard page load is a document plus a dozen hashed bundles — storing those would drown real traffic in Postgres and make `http_log_retention_days` decide what you can still see. Doing it at ingest rather than with a Caddy path matcher keeps [bootstrap.py](../backend/bootstrap.py) simple and lets the list change without a proxy reload.

### 1.5 Endpoints — ⬜ todo

New `console/views/proxy.py`, all `IsInstanceOwner`, wired in [console/urls.py](../console/urls.py):

| Name                             | Route                               | What                                        |
| -------------------------------- | ----------------------------------- | ------------------------------------------- |
| `console:proxy.http_logs`        | `GET /api/console/proxy/http-logs/` | cursor-paginated list, no service scoping   |
| `console:proxy.http_logs.single` | `GET …/http-logs/<request_uuid>/`   | one log, any source                         |
| `console:proxy.http_logs.fields` | `GET …/http-logs/fields/`           | autocomplete, `service_id` **not** required |

Filters: everything `DeploymentHttpLogsFilterSet` already supports (`time`, `status` incl. `4xx`, `request_method`, `request_host`, `request_path`, `request_ip`, `request_user_agent`, `request_query`, `service_id`, `stack_id`, `deployment_id`) **plus `source`** (repeatable).

Reuse `HttpLogSerializer` + `DeploymentHttpLogsPagination`; add `source` to the serializer fields.

---

## Phase 2 — GeoIP country

Resolve the country of `request_ip` at ingest time, so it can be filtered and displayed.

### 2.1 Tests

`ProxyHttpLogGeoIPTests` in [console/tests/proxy_logs.py](../console/tests/proxy_logs.py) — already written, currently red. It patches `zane_api.geoip.Reader` with a fake and calls `get_geoip_reader.cache_clear()`.

### 2.2 Models — ✅ done

`HttpLog.request_country_code`, `CharField(max_length=2, null=True)`, indexed (migration 0343).

### 2.3 The lookup

- add `geoip2` to [pyproject.toml](../pyproject.toml), `uv lock`
- new setting `MAXMIND_DB_PATH`, default `None` — GeoIP is **opt-in**, no download logic, the operator mounts their own `GeoLite2-Country.mmdb`
- new `zane_api/geoip.py`:
  - `Reader` imported at module level (so tests can patch it)
  - `get_geoip_reader()` — `functools.cache`d, returns `None` when the setting is unset or the file is missing
  - `lookup_country_code(ip) -> str | None` — swallows `AddressNotFoundError` and `ValueError`

### 2.4 Ingest

Fill `request_country_code` in `_build_http_log`. Must never make ingest fail: no DB configured, unknown IP, private IP → `None`.

### 2.5 Endpoint

Expose `request_country_code` in `HttpLogSerializer` and make it filterable on the phase 1 endpoints.

---

## Phase 3 — Proxy application logs

Caddy's own logs: certificate issuance, config reloads, upstream errors.

### 3.1 Tests

`ProxyApplicationLogIngestViewTests`, `ProxyApplicationLogViewTests` in [console/tests/proxy_logs.py](../console/tests/proxy_logs.py) — already written, currently red.

### 3.2 Models

No Postgres model — these go to Loki like other runtime logs.

- `RuntimeLogSource.PROXY` in [search/dtos.py](../search/dtos.py)
- add it to the `source` choices of `RuntimeLogsQuerySerializer` and `RuntimeLogSerializer` in [search/serializers.py](../search/serializers.py)

### 3.3 Ingest

For `tag.service_id == zane.proxy`, anything that is **not** an access log becomes a `RuntimeLogDto`:

- `service_id = "zane.proxy"`, `source = PROXY`
- level from Caddy's own `level` key: `warn|error|fatal|panic` → `ERROR`, everything else → `INFO`
- lines that are not JSON (Caddy's startup output) → `INFO`, stored raw
- `content` = the raw line, `content_text` = `escape_ansi(line)`

### 3.4 Endpoint

`console:proxy.logs` → `GET /api/console/proxy/logs/`, `IsInstanceOwner`. Wraps `LokiSearchClient.search()` with `source` forced to `PROXY`; accepts `query`, `level`, `time_before`/`time_after`, `per_page`, `cursor`. Returns the usual `RuntimeLogsSearchSerializer` shape.

---

## Phase 4 — Custom Caddy config

Let the instance owner add Caddyfile snippets to the proxy.

> Deliberately deferred until phases 1–3 are done — see commit `faf4d9d4`, which removed the model again.

### 4.1 Tests

[console/tests/proxy_configs.py](../console/tests/proxy_configs.py) — already written.

⚠️ **Blocker to handle first:** that file is imported by [console/tests/\_\_init\_\_.py](../console/tests/__init__.py) and imports `CustomProxyConfig`, which no longer exists — the whole suite fails to import. Comment the import out until this phase starts.

### 4.2 Models

`CustomProxyConfig` in [console/models.py](../console/models.py): `id` (`prx_cfg_`), unique `slug`, `contents` (the Caddyfile), `enabled`, timestamps, and `caddy_route_id` → `zane-custom-config-<id>`.

### 4.3 Validation & applying

- validate by `POST`ing the snippet to `{CADDY_PROXY_ADMIN_HOST}/adapt` with `Content-Type: text/caddyfile`; a non-2xx answer becomes a 400 on the `contents` field, carrying Caddy's own message
- take the adapted `apps.http.servers.*.routes` and install them as **one** route `@id = zane-custom-config-<id>`, wrapping them in a `subroute` handler, inserted into `zane-url-root` **before** the ZaneOps and service routes
- disable/delete → `DELETE /id/<route id>` on the admin API

### 4.4 Endpoints

| Name                            | Route | Methods                           |
| ------------------------------- | ----- | --------------------------------- |
| `console:proxy.configs.list`    | `GET  | POST /api/console/proxy/configs/` | list (unpaginated), create |
| `console:proxy.configs.details` | `GET  | PATCH                             | DELETE …/configs/<slug>/`  | read, update, toggle `enabled`, delete |

Duplicate slug → 409 (`ResourceConflict`). Invalid Caddyfile → 400, and the stored config is left untouched.

---

## Cross-cutting, once the four phases are green

- regenerate the OpenAPI schema + frontend client (`pnpm gen:api`)
- `HttpLog` retention already exists (`SystemSettings.http_log_retention_days`) — check the cleanup workflow still makes sense now that ZaneOps' own traffic is stored, since it is a much higher volume
