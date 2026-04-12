"""
Reusable Cypher snippets for KYC graph analysis.
Run individual queries via Neo4j Browser or wrap with the driver in a small CLI.

Each catalog entry is (name, description, cypher).
"""

from __future__ import annotations

# --- Legacy / general analysis ---

BENEFICIAL_OWNERSHIP_CHAIN = """
MATCH path = (owner:LegalEntity)-[:OWNS*1..6]->(target:LegalEntity {entity_id: $target_id})
RETURN path,
       reduce(p = 1.0, r IN relationships(path) | p * (r.ownership_pct / 100.0)) AS effective_pct
ORDER BY effective_pct DESC
"""

LIST_SANCTIONED = """
MATCH (e:LegalEntity)
WHERE coalesce(e.is_sanctioned, false) = true OR e:sanctioned
RETURN e.entity_id AS id, e.name AS name, e.sanctions_list AS list_name
ORDER BY e.name
"""

COMPANIES_OWNED_BY_PERSON = """
MATCH (p:LegalEntity:Individual {entity_id: $person_id})-[:OWNS]->(c:LegalEntity)
WHERE c:Corporation OR c:Fund
RETURN c.entity_id, c.name, c.jurisdiction
"""

DIRECT_STAKE_ABOVE = """
MATCH (owner:LegalEntity:Individual)-[r:OWNS]->(company:LegalEntity)
WHERE company:Corporation OR company:Fund
  AND r.ownership_pct >= $min_pct
RETURN owner.entity_id, owner.name, company.entity_id, company.name, r.ownership_pct
ORDER BY r.ownership_pct DESC
"""

# --- KYC risk queries ---

PEP_DIRECTORS = """
MATCH (p:LegalEntity:Individual)-[d:DIRECTOR_OF]->(c:LegalEntity:Corporation)
WHERE coalesce(p.politically_exposed, false) = true
RETURN c.entity_id AS company_id,
       c.name AS company_name,
       p.entity_id AS director_id,
       p.name AS director_name,
       d.role AS role,
       d.appointed_date AS appointed_date
ORDER BY c.name, p.name
"""

PEP_AND_SANCTIONS = """
MATCH (p:LegalEntity:Individual)-[:DIRECTOR_OF]->(c:LegalEntity:Corporation)
WHERE coalesce(p.politically_exposed, false) = true
MATCH path = (s:LegalEntity)-[:OWNS*1..5]->(c)
WHERE coalesce(s.is_sanctioned, false) = true OR s:sanctioned
WITH c, p, s, path,
     {
       sanctioned_source: s.name,
       effective_ownership: reduce(pct = 1.0, r IN relationships(path) | pct * r.ownership_pct / 100.0),
       chain_depth: length(path),
       name_chain: [n IN nodes(path) | n.name]
     } AS exposure_row
WITH c, p, collect(exposure_row) AS exposures
RETURN c.entity_id AS company_id,
       c.name AS company_name,
       p.name AS pep_director,
       exposures
ORDER BY c.name
"""

TRADE_RISK = """
MATCH (a:LegalEntity)-[t:TRADES_WITH]->(b:LegalEntity)
WHERE (coalesce(a.is_sanctioned, false) = true OR a:sanctioned
       OR EXISTS {
         MATCH (s:LegalEntity)-[:OWNS*1..5]->(a)
         WHERE coalesce(s.is_sanctioned, false) = true OR s:sanctioned
       })
   OR (coalesce(b.is_sanctioned, false) = true OR b:sanctioned
       OR EXISTS {
         MATCH (s:LegalEntity)-[:OWNS*1..5]->(b)
         WHERE coalesce(s.is_sanctioned, false) = true OR s:sanctioned
       })
RETURN a.entity_id AS party1_id,
       a.name AS party1_name,
       b.entity_id AS party2_id,
       b.name AS party2_name,
       t.trade_type AS trade_type,
       t.trade_date AS trade_date,
       t.notional_amount AS notional_amount,
       t.currency AS currency
ORDER BY t.trade_date DESC
"""

FULL_RISK_REPORT = """
MATCH (e:LegalEntity {entity_id: $entity_id})
CALL {
  WITH e
  OPTIONAL MATCH path = (s:LegalEntity)-[:OWNS*1..5]->(e)
  WHERE coalesce(s.is_sanctioned, false) = true OR s:sanctioned
  WITH collect(
    CASE
      WHEN path IS NULL THEN null
      ELSE {
        sanctioned_source: s.name,
        effective_ownership: reduce(pct = 1.0, r IN relationships(path) | pct * r.ownership_pct / 100.0),
        chain_depth: length(path),
        name_chain: [n IN nodes(path) | n.name]
      }
    END
  ) AS raw_ind
  RETURN [x IN raw_ind WHERE x IS NOT NULL] AS indirect_exposure
}
WITH e, indirect_exposure
CALL {
  WITH e
  OPTIONAL MATCH (p:LegalEntity:Individual)-[d:DIRECTOR_OF]->(corp:LegalEntity:Corporation)
  WHERE corp.entity_id = e.entity_id AND coalesce(p.politically_exposed, false) = true
  WITH collect(
    CASE
      WHEN p IS NULL THEN null
      ELSE {name: p.name, role: d.role, appointed: d.appointed_date}
    END
  ) AS raw_pep
  RETURN [x IN raw_pep WHERE x IS NOT NULL] AS pep_directors
}
WITH e, indirect_exposure, pep_directors
CALL {
  WITH e
  OPTIONAL MATCH (e)-[tOut:TRADES_WITH]->(o:LegalEntity)
  WITH collect(
    CASE
      WHEN tOut IS NULL THEN null
      WHEN (coalesce(e.is_sanctioned, false) = true OR e:sanctioned
            OR EXISTS {
              MATCH (s:LegalEntity)-[:OWNS*1..5]->(e)
              WHERE coalesce(s.is_sanctioned, false) = true OR s:sanctioned
            }
            OR coalesce(o.is_sanctioned, false) = true OR o:sanctioned
            OR EXISTS {
              MATCH (s:LegalEntity)-[:OWNS*1..5]->(o)
              WHERE coalesce(s.is_sanctioned, false) = true OR s:sanctioned
            })
      THEN {
        direction: 'OUT',
        counterparty_id: o.entity_id,
        counterparty_name: o.name,
        trade_type: tOut.trade_type,
        trade_date: tOut.trade_date,
        notional_amount: tOut.notional_amount,
        currency: tOut.currency
      }
      ELSE null
    END
  ) AS raw_out
  RETURN [x IN raw_out WHERE x IS NOT NULL] AS risky_trades_out
}
WITH e, indirect_exposure, pep_directors, risky_trades_out
CALL {
  WITH e
  OPTIONAL MATCH (oIn:LegalEntity)-[tIn:TRADES_WITH]->(e)
  WITH collect(
    CASE
      WHEN tIn IS NULL THEN null
      WHEN (coalesce(e.is_sanctioned, false) = true OR e:sanctioned
            OR EXISTS {
              MATCH (s:LegalEntity)-[:OWNS*1..5]->(e)
              WHERE coalesce(s.is_sanctioned, false) = true OR s:sanctioned
            }
            OR coalesce(oIn.is_sanctioned, false) = true OR oIn:sanctioned
            OR EXISTS {
              MATCH (s:LegalEntity)-[:OWNS*1..5]->(oIn)
              WHERE coalesce(s.is_sanctioned, false) = true OR s:sanctioned
            })
      THEN {
        direction: 'IN',
        counterparty_id: oIn.entity_id,
        counterparty_name: oIn.name,
        trade_type: tIn.trade_type,
        trade_date: tIn.trade_date,
        notional_amount: tIn.notional_amount,
        currency: tIn.currency
      }
      ELSE null
    END
  ) AS raw_in
  RETURN [x IN raw_in WHERE x IS NOT NULL] AS risky_trades_in
}
WITH e, indirect_exposure, pep_directors, risky_trades_out, risky_trades_in
RETURN e.entity_id AS entity_id,
       e.name AS entity_name,
       e.entity_type AS entity_type,
       (coalesce(e.is_sanctioned, false) OR e:sanctioned) AS direct_sanctions,
       e.sanctions_list AS sanctions_list,
       e.sanctions_listed_on AS sanctions_listed_on,
       indirect_exposure,
       pep_directors,
       risky_trades_out + risky_trades_in AS risky_trades
"""


QUERY_CATALOG: list[tuple[str, str, str]] = [
    (
        "beneficial_ownership_chain",
        "Variable-length OWNS paths to a target entity with effective stake (product of edge %).",
        BENEFICIAL_OWNERSHIP_CHAIN,
    ),
    (
        "list_sanctioned",
        "All LegalEntities flagged as sanctioned (property and/or :sanctioned label).",
        LIST_SANCTIONED,
    ),
    (
        "companies_owned_by_person",
        "Corporations and funds one hop downstream of an Individual via OWNS.",
        COMPANIES_OWNED_BY_PERSON,
    ),
    (
        "direct_stake_above",
        "Individuals with direct OWNS to a corporation/fund above a minimum ownership_pct.",
        DIRECT_STAKE_ABOVE,
    ),
    (
        "pep_directors",
        "Corporations that have at least one director Individual with politically_exposed = true.",
        PEP_DIRECTORS,
    ),
    (
        "pep_and_sanctions",
        "Corporations with a PEP director AND at least one sanctioned-source OWNS chain into the company (with effective %).",
        PEP_AND_SANCTIONS,
    ),
    (
        "trade_risk",
        "TRADES_WITH rows where either party is sanctioned or downstream of a sanctioned owner (OWNS*1..5).",
        TRADE_RISK,
    ),
    (
        "full_risk_report",
        "Main KYC query for $entity_id: direct sanctions flags, indirect sanctioned ownership chains, PEP directors (when entity is a corporation), and risky trades (OUT + IN).",
        FULL_RISK_REPORT,
    ),
]

QUERIES: dict[str, str] = {name: cypher for name, _desc, cypher in QUERY_CATALOG}

QUERY_DESCRIPTIONS: dict[str, str] = {name: desc for name, desc, _cypher in QUERY_CATALOG}


def print_catalog() -> None:
    print("Available Cypher queries (name → description → query):\n")
    for name, description, cypher in QUERY_CATALOG:
        print(f"## {name}")
        print(description)
        print()
        print(cypher.strip())
        print()


if __name__ == "__main__":
    print_catalog()
