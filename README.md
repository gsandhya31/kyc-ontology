# kyc-ontology

Small prototype for loading KYC-style **entities**, **ownership**, and **sanctions** data into **Neo4j** and running exploratory queries.


## What This Project Does

Financial institutions must screen counterparties for sanctions exposure and politically exposed persons (PEPs) before trading. This is typically done manually — analysts trace ownership chains across spreadsheets and multiple systems.

This project replaces that manual process with a graph-based approach:

- Models legal entities (corporations, individuals, funds, government bodies) and their ownership relationships as a knowledge graph in Neo4j
- Computes effective ownership through multi-hop chains (e.g., Entity A owns 60% of B, B owns 50% of C → A effectively owns 30% of C)
- Flags entities exceeding sanctions exposure thresholds (>25% = HIGH RISK, 10-25% = MEDIUM RISK)
- Identifies companies with PEP directors who also have indirect sanctions exposure
- Surfaces trade-level risk — finds trades where either counterparty has sanctions connections

## Why a Graph?

Ownership structures are inherently graph-shaped — chains, cycles, diamond patterns. Relational databases struggle with variable-depth traversals ("find all entities within 5 hops of a sanctioned entity"). Neo4j handles this natively.

## Built With

- Neo4j Aura (graph database)
- Python 3 (data loading, analysis scripts)
- Cypher (graph query language)
- Domain ontology modeled after FIBO (Financial Industry Business Ontology) principles

  
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
