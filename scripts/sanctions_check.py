"""
Flag downstream exposure from sanctioned LegalEntities via OWNS chains.
Effective stake is the product of edge ownership_pct values along each path.
Uses the same Neo4j env vars as load_data.py.
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import os

from neo4j import GraphDatabase

# Sanctioned source (property and/or label); graph uses lowercase :sanctioned from load_data.
SANCTIONS_EXPOSURE_PATHS = """
MATCH path = (s:LegalEntity)-[:OWNS*1..5]->(target:LegalEntity)
WHERE coalesce(s.is_sanctioned, false) = true OR s:sanctioned
WITH path, s, target,
     reduce(pct = 1.0, r IN relationships(path) | pct * r.ownership_pct / 100.0) AS effective_ownership
WHERE effective_ownership > 0.0
RETURN s.name AS sanctioned_entity,
       target.name AS exposed_entity,
       effective_ownership,
       length(path) AS chain_depth,
       [n IN nodes(path) | n.name] AS chain
ORDER BY effective_ownership DESC
"""


def get_driver():
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")
    return GraphDatabase.driver(uri, auth=(user, password))


def risk_tier(effective_ownership: float) -> str:
    if effective_ownership > 0.25:
        return "HIGH RISK"
    if 0.10 <= effective_ownership <= 0.25:
        return "MEDIUM RISK"
    return "LOW RISK"


def main():
    driver = get_driver()
    with driver.session() as session:
        rows = session.run(SANCTIONS_EXPOSURE_PATHS).data()
    driver.close()

    if not rows:
        print("No sanctioned-source ownership chains found (or graph empty).")
        return

    print(
        "Sanctioned entity → downstream OWNS exposure "
        "(effective % = product of ownership_pct along path, ordered by stake):\n"
    )
    for r in rows:
        eff = float(r["effective_ownership"])
        eff_pct = eff * 100.0
        tier = risk_tier(eff)
        chain = r.get("chain") or []
        chain_str = " → ".join(chain)

        print(f"  [{tier}]")
        print(f"    Sanctioned source:  {r.get('sanctioned_entity')}")
        print(f"    Exposed entity:     {r.get('exposed_entity')}")
        print(f"    Effective ownership: {eff_pct:.4f}% (fraction {eff:.6f})")
        print(f"    Chain depth:        {r.get('chain_depth')}")
        print(f"    Full chain (names): {chain_str}")
        print()


if __name__ == "__main__":
    main()
