# kyc-ontology

Small prototype for loading KYC-style **entities**, **ownership**, and **sanctions** data into **Neo4j** and running exploratory queries.

## Layout

- `data/` — CSV inputs (`entities.csv`, `ownership.csv`, `sanctions_list.csv`)
- `scripts/` — `load_data.py`, `queries.py`, `sanctions_check.py`
- `ontology/schema.md` — graph model description

## Setup

1. Python 3.10+ recommended.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run Neo4j locally (or point env vars to your instance).

4. Set credentials (defaults shown):

   - `NEO4J_URI` — default `bolt://localhost:7687`
   - `NEO4J_USER` — default `neo4j`
   - `NEO4J_PASSWORD` — default `password`

## Load data

From the repo root:

```bash
python scripts/load_data.py
```

## Queries

- Open `scripts/queries.py` for Cypher templates (beneficial chains, sanctioned list, etc.).
- Run sanctions path scan:

```bash
python scripts/sanctions_check.py
```

## Disclaimer

Sample data and logic are for **demonstration only**, not for production compliance decisions.
