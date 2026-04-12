"""
Load KYC CSVs into Neo4j: entities, ownership, directors, trades, sanctions metadata.
Requires Neo4j 5.x and environment variables NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

_BOOL_TRUE = frozenset({"true", "1", "yes", "t"})


def _parse_bool(value) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _BOOL_TRUE


def prepare_entity_rows(rows: list[dict]) -> list[dict]:
    """Normalize blanks and type-specific fields for the Cypher UNWIND payload."""
    out: list[dict] = []
    for raw in rows:
        r = {}
        for k, v in raw.items():
            if v is None or (isinstance(v, str) and not str(v).strip()):
                r[k] = None
            else:
                r[k] = v

        et = r.get("entity_type")
        r["is_active"] = _parse_bool(r["is_active"]) if r.get("is_active") is not None else True
        r["is_sanctioned"] = _parse_bool(r["is_sanctioned"]) if r.get("is_sanctioned") is not None else False

        if et == "Individual":
            r["politically_exposed"] = (
                _parse_bool(r.get("politically_exposed")) if r.get("politically_exposed") is not None else False
            )
        else:
            r["date_of_birth"] = None
            r["politically_exposed"] = None

        if et not in ("Corporation", "Fund"):
            r["incorporation_date"] = None
            r["registration_number"] = None

        out.append(r)
    return out


def get_driver():
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")
    return GraphDatabase.driver(uri, auth=(user, password))


def ensure_schema(tx):
    tx.run(
        """
        CREATE CONSTRAINT legal_entity_id IF NOT EXISTS
        FOR (e:LegalEntity) REQUIRE e.entity_id IS UNIQUE
        """
    )


def load_entities(tx, rows: list[dict]):
    rows = prepare_entity_rows(rows)
    tx.run(
        """
        UNWIND $rows AS row
        MERGE (e:LegalEntity {entity_id: row.entity_id})
        SET e.name = row.name,
            e.jurisdiction = row.jurisdiction,
            e.entity_type = row.entity_type,
            e.is_active = row.is_active,
            e.is_sanctioned = row.is_sanctioned,
            e.date_of_birth = CASE WHEN row.entity_type = 'Individual' THEN row.date_of_birth END,
            e.politically_exposed = CASE WHEN row.entity_type = 'Individual' THEN row.politically_exposed END,
            e.incorporation_date = CASE WHEN row.entity_type IN ['Corporation', 'Fund'] THEN row.incorporation_date END,
            e.registration_number = CASE WHEN row.entity_type IN ['Corporation', 'Fund'] THEN row.registration_number END
        WITH e, row
        FOREACH (_ IN CASE WHEN row.entity_type = 'Corporation' THEN [1] ELSE [] END | SET e:Corporation)
        FOREACH (_ IN CASE WHEN row.entity_type = 'Individual' THEN [1] ELSE [] END | SET e:Individual)
        FOREACH (_ IN CASE WHEN row.entity_type = 'Fund' THEN [1] ELSE [] END | SET e:Fund)
        FOREACH (_ IN CASE WHEN row.entity_type = 'GovernmentBody' THEN [1] ELSE [] END | SET e:GovernmentBody)
        WITH e, row
        FOREACH (_ IN CASE WHEN row.is_sanctioned = true THEN [1] ELSE [] END | SET e:sanctioned)
        """,
        rows=rows,
    )


def load_ownership(tx, rows: list[dict]):
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (owner:LegalEntity {entity_id: row.owner_id})
        MATCH (owned:LegalEntity {entity_id: row.owned_id})
        MERGE (owner)-[r:OWNS]->(owned)
        SET r.ownership_pct = toFloat(row.ownership_pct),
            r.effective_from = row.effective_from,
            r.source = row.source
        """,
        rows=rows,
    )


def load_sanctions(tx, rows: list[dict]):
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (e:LegalEntity {entity_id: row.sanctioned_id})
        SET e:sanctioned,
            e.sanctions_list = row.list_name,
            e.sanctions_listed_on = row.listed_on,
            e.sanctions_notes = row.notes
        """,
        rows=rows,
    )


def load_directors(tx, rows: list[dict]):
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (person:LegalEntity:Individual {entity_id: row.person_id})
        MATCH (company:LegalEntity:Corporation {entity_id: row.company_id})
        MERGE (person)-[r:DIRECTOR_OF]->(company)
        SET r.role = row.role,
            r.appointed_date = row.appointed_date
        """,
        rows=rows,
    )


def load_trades(tx, rows: list[dict]):
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (p1:LegalEntity {entity_id: row.party1_id})
        MATCH (p2:LegalEntity {entity_id: row.party2_id})
        MERGE (p1)-[r:TRADES_WITH]->(p2)
        SET r.trade_type = row.trade_type,
            r.trade_date = row.trade_date,
            r.notional_amount = toFloat(row.notional_amount),
            r.currency = row.currency
        """,
        rows=rows,
    )


def read_csv(name: str) -> list[dict]:
    path = DATA / name
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    entities = read_csv("entities.csv")
    ownership = read_csv("ownership.csv")
    directors = read_csv("directors.csv")
    trades = read_csv("trades.csv")
    sanctions = read_csv("sanctions_list.csv")

    driver = get_driver()
    with driver.session() as session:
        session.execute_write(ensure_schema)
        session.execute_write(load_entities, entities)
        session.execute_write(load_ownership, ownership)
        session.execute_write(load_directors, directors)
        session.execute_write(load_trades, trades)
        session.execute_write(load_sanctions, sanctions)
    driver.close()
    print(
        "Loaded LegalEntity nodes (with subtype labels), OWNS, DIRECTOR_OF, "
        "TRADES_WITH, and sanctions metadata into Neo4j."
    )


if __name__ == "__main__":
    main()
