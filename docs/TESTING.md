# Testēšanas vide

Šajā projektā ir izveidota minimāla testēšanas vide ar Python standarta `unittest` (bez ārējām atkarībām).

## Ātra palaišana

No projekta saknes mapes:

```bash
make test-local
```

## Windows (PowerShell) instrukcija

Ja izmanto Windows PowerShell, **nav jāpalaiž `bash`**.

1. Atver PowerShell.
2. Pārej uz projekta mapi:
   ```powershell
   cd C:\celš\uz\ZinuApkopotajs
   ```
3. Palaid testus:
   ```powershell
   py -m unittest discover -s tests -p "test_*.py" -v
   ```
   (alternatīva: `python -m unittest discover -s tests -p "test_*.py" -v`)

## Linux / macOS instrukcija

No projekta mapes:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

## Docker palaišana

Prasības:
- uzinstalēts Docker ar `docker compose`.

Palaide:

```bash
make test-docker
```

Vai ekvivalenti:

```bash
docker compose -f docker-compose.test.yml run --rm tests
```

## Piekļuve testēšanas videi Docker konteinerā

Testēšanas vide ir pieejama caur servisu `tests` failā `docker-compose.test.yml`.

```bash
docker compose -f docker-compose.test.yml run --rm tests sh
```

No turienes:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

## Biežākās kļūdas

- `bash is not recognized` (Windows): nelieto `bash`, izmanto tieši PowerShell komandas augstāk.
- `ImportError: Start directory is not importable: 'tests'`: pārliecinies, ka komandu palaid no projekta saknes mapes.
