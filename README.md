# job-scraper

A personal job offer aggregator that fetches listings from job APIs, filters them based on profile criteria, and saves results to JSON.

## Stack

- **Python 3.13+** managed with [uv](https://docs.astral.sh/uv/)
- **FranceTravail API** (Pôle Emploi) — OAuth2 REST API for French job listings
- **Playwright** *(planned)* — for scraping sites without a public API (e.g. LinkedIn)

## Project structure

```
job-scraper/
├── main.py                  # CLI entry point
├── config.py                # Settings loaded from .env
├── models.py                # JobOffer dataclass
├── pipeline.py              # Orchestrates fetch → deduplicate → filter → store
├── filters.py               # Filtering logic (contract type, salary, experience)
├── sources/
│   ├── base.py              # Abstract JobSource
│   └── france_travail.py    # FranceTravail API client
└── storage/
    └── json_writer.py       # Writes results/jobs_<timestamp>.json
```

## Setup

1. **Install dependencies**
   ```bash
   uv sync
   ```

2. **Configure credentials**
   ```bash
   cp .env.example .env
   ```
   Fill in your FranceTravail API credentials. Register at [francetravail.io/data/api/offres-demploi](https://francetravail.io/data/api/offres-demploi).

## Usage

```bash
# Run with defaults from .env
uv run main.py

# Custom search
uv run main.py --keywords "ingénieur télécom" "satellite" --location 31 --max-results 100

# Filter to a specific source
uv run main.py --sources france_travail
```

### CLI options

| Option | Default | Description |
|---|---|---|
| `--keywords` | from `.env` | One or more keyword searches (run separately, results merged) |
| `--location` | from `.env` | Department code (`75` = Paris, `69` = Lyon, `31` = Toulouse) |
| `--sources` | all | Which sources to query |
| `--max-results` | from `.env` | Max results per source per keyword (hard cap: 150) |

Results are saved to `results/jobs_<timestamp>.json`.

## Configuration (`.env`)

| Variable | Description |
|---|---|
| `FRANCE_TRAVAIL_CLIENT_ID` | API client ID *(required)* |
| `FRANCE_TRAVAIL_CLIENT_SECRET` | API client secret *(required)* |
| `DEFAULT_KEYWORDS` | Comma-separated list of keyword searches |
| `DEFAULT_LOCATION` | Department code (e.g. `75` for Paris) |
| `DEFAULT_MAX_RESULTS` | Max results per keyword per source |
| `SALARY_MIN` | Minimum annual salary in € (default: `40000`) |
| `REQUIRE_SALARY` | If `true`, drop offers with no salary info (default: `false`) |

## Filters applied

- **Contract type**: keeps CDI and freelance (`Profession libérale`); keeps VIE/VIA only for Japan, USA, Switzerland; excludes CDD, interim, alternance
- **Salary**: drops offers with a known salary below `SALARY_MIN`; if `REQUIRE_SALARY=true`, also drops offers with no salary info
- **Experience**: drops offers requiring more than 2 years of experience, or where experience is unspecified but mandatory (*Expérience exigée*)
