# kyc-ontology

A graph-based KYC/AML screening tool built with Neo4j.

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
- Streamlit (interactive UI)
- Cypher (graph query language)
- Domain ontology modeled after FIBO (Financial Industry Business Ontology) principles


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

- `data/` — CSV inputs:
  - `entities.csv` — Legal entities (corporations, individuals, funds, government bodies) with properties
  - `ownership.csv` — Ownership relationships with percentage stakes
  - `sanctions_list.csv` — Sanctioned entity flags
  - `directors.csv` — Directorships linking individuals to corporations
  - `trades.csv` — Trading relationships between entities
- `scripts/` — `load_data.py`, `queries.py`, `sanctions_check.py`
- `ontology/schema.md` — Domain ontology definition (classes, properties, relationships, constraints)
- `app.py` — Streamlit UI for interactive risk screening

## Setup

1. Python 3.9+ required.
2. Install dependencies: 
  ```
  pip install -r requirements.txt

  ```
3. Create a free Neo4j Aura instance at [neo4j.com/cloud/aura-free](https://neo4j.com/cloud/aura-free).
4. Create a `.env` file in the project root with your credentials: 
  ```
  NEO4J_URI=neo4j+s://your-instance-id.databases.neo4j.ioNEO4J_USER=neo4jNEO4J_PASSWORD=your_password_here

  ```

## Load Data

From the repo root:

```
python3 scripts/load_data.py

```

## Run Sanctions Screening

```
python3 scripts/sanctions_check.py

```

## Run Streamlit UI

```
python3 -m streamlit run app.py

```

## Sample Output

```
[HIGH RISK]
  Sanctioned source:  Neva Logistics OOO
  Exposed entity:     Harbour Ring Capital Pte Ltd
  Effective ownership: 80.0000%
  Chain depth:        1
  Full chain (names): Neva Logistics OOO → Harbour Ring Capital Pte Ltd

[HIGH RISK]
  Sanctioned source:  Mirage Crescent Fund SPC
  Exposed entity:     Camden Gate Properties Ltd
  Effective ownership: 70.0000%
  Chain depth:        1
  Full chain (names): Mirage Crescent Fund SPC → Camden Gate Properties Ltd

[MEDIUM RISK]
  Sanctioned source:  Mirage Crescent Fund SPC
  Exposed entity:     Shinjuku Consumer Brands KK
  Effective ownership: 21.0000%
  Chain depth:        3
  Full chain (names): Mirage Crescent Fund SPC → Camden Gate Properties Ltd → Kyoto Precision Components KK → Shinjuku Consumer Brands KK

```

## Disclaimer

Sample data and logic are for **demonstration only**, not for production compliance decisions.