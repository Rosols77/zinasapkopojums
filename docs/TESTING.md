# Testēšanas vide (datu plūsmas novērošana)

Šī vide ir paredzēta, lai testos redzētu:
1. **no kurienes nāk informācija** (`source`),
2. **cik ilgā laikā tā pienāk** (`latency_ms`),
3. statusu un lēno notikumu statistiku,
4. datu kvalitātes problēmas (`quality`),
5. drošības testu rezultātus (`security`),
6. detalizētu JSON atskaiti ar visiem notikumiem.

## 1) Palaišana

### Cross-platform (ieteicams)

```bash
python3 run_observability_demo.py
```

Windows PowerShell:

```powershell
py .\run_observability_demo.py
```

## 2) Kur redzēt rezultātu

Pēc palaišanas tiek izveidots fails:

- `artifacts/latest_report.json`

Tajā ir:
- `sources` (avotu sadalījums),
- `latency` (vidējais/min/max un lēnie notikumi),
- `per_source_latency` (statistika pa avotiem),
- `quality` (kvalitātes indikatori),
- `security` (drošības pārbaudes),
- `status` sadalījums,
- `events` ar katra ieraksta laikiem.

## 3) Drošības testi (ja mēģina apiet un tikt klāt parolēm)

Šajā vidē tiek veikti 5 aizsardzības testi:

### A) Path traversal pārbaude
- Sistēma mēģina atrisināt ceļu `../users_secure.key` no `artifacts` mapes.
- Pareizs rezultāts: `security.path_traversal_blocked = true`.

### B) Sensitīvu lauku meklēšana reportā
- Tiek pārmeklēts reporta saturs uz atslēgvārdiem: `password`, `token`, `secret`, `api_key`, `private_key`.
- Pareizs rezultāts: `security.sensitive_keys_found_count = 0`.

### C) Brute-force lockout simulācija
- Simulēti 5 neveiksmīgi mēģinājumi un 6. mēģinājums ar pareizu paroli lockout periodā.
- Pareizs rezultāts:
  - `security.bruteforce_simulation.lockout_triggered = true`
  - `security.bruteforce_simulation.bypass_possible = false`

### D) IP-based rate limiting simulācija
- Simulēti 7 mēģinājumi no viena IP un 1 mēģinājums no cita IP.
- Pareizs rezultāts:
  - `security.ip_rate_limit_simulation.primary_blocked = true`
  - `security.ip_rate_limit_simulation.secondary_allowed = true`

### E) Cooldown recovery simulācija
- Pēc lockout tiek pārbaudīts mēģinājums lockout laikā un pēc lockout beigām.
- Pareizs rezultāts:
  - `security.cooldown_recovery_simulation.during_lockout_allowed = false`
  - `security.cooldown_recovery_simulation.after_cooldown_allowed = true`

## 4) Ko papildus vari testēt (kas var noiet greizi)

### A) Lēni ienākoši notikumi
- Maini `slow_threshold_ms` parametrā `build_report(...)` un pārbaudi `latency.slow_count`.

### B) Nepareizi laiki
- Izveido notikumu, kur `received_at < sent_at`, un pārbaudi `quality.negative_latency_count`.

### C) Nākotnes timestamp
- Izveido notikumu ar `sent_at > now` un pārbaudi `quality.future_sent_count`.

### D) Pārāk liels payload
- Pievieno notikumu ar `payload_size > 900` un pārbaudi `quality.oversized_payload_count`.

### E) Avotu salīdzināšana
- Salīdzini `per_source_latency` starp `rss` un `api`, lai redzētu kurš avots piegādā lēnāk.

### F) Sensitīvu atslēgu noplūde nested struktūrās
- Pārbaudi, ka atslēgas kā `meta.credentials.password` tiek noķertas ar sensitive-key detectoru.

## 5) Testu komandas

```bash
make test-local
make test-script
make test-observability
make test-all
```

## 6) Testu saturs

- `tests/test_smoke.py` — pamatpārbaude (`README.md` eksistence)
- `tests/test_project_structure.py` — būtisko failu esamība
- `tests/test_observability.py` — validē avotus, latentumu, quality, security, IP rate limit, cooldown recovery un sensitive-key scenārijus

## 7) CI

GitHub Actions workflow:
- `.github/workflows/tests.yml`

Tas palaiž unit testus uz `push` un `pull_request`.
