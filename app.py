import os
import streamlit as st
from neo4j import GraphDatabase

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    URI = st.secrets["NEO4J_URI"]
    USER = st.secrets["NEO4J_USER"]
    PASSWORD = st.secrets["NEO4J_PASSWORD"]
except Exception:
    URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    USER = os.getenv("NEO4J_USER", "neo4j")
    PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
    
@st.cache_resource
def get_driver():
    return GraphDatabase.driver(URI, auth=(USER, PASSWORD))


def run_query(query, params=None):
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, params or {})
        return [record.data() for record in result]


# ── Sidebar ──────────────────────────────────────────────
st.sidebar.title("KYC / AML Screening")
mode = st.sidebar.radio(
    "Select Mode",
    ["Entity Lookup", "Sanctions Scan", "Full Risk Report"],
)

# ── Helper: fetch all entity names for autocomplete ──────
@st.cache_data(ttl=300)
def all_entity_names():
    rows = run_query("MATCH (e:LegalEntity) RETURN e.name AS name ORDER BY e.name")
    return [r["name"] for r in rows]


# ═══════════════════════════════════════════════════════════
# MODE 1 — Entity Lookup
# ═══════════════════════════════════════════════════════════
if mode == "Entity Lookup":
    st.title("Entity Lookup")
    names = all_entity_names()
    selected = st.selectbox("Select an entity", [""] + names)

    if selected:
        # Basic properties
        props = run_query(
            "MATCH (e:LegalEntity {name: $name}) RETURN e AS entity",
            {"name": selected},
        )
        if props:
            entity = props[0]["entity"]
            st.subheader("Entity Properties")
            col1, col2, col3 = st.columns(3)
            col1.metric("Type", entity.get("entity_type", "—"))
            col2.metric("Jurisdiction", entity.get("jurisdiction", "—"))
            col3.metric(
                "Sanctioned",
                "YES" if entity.get("is_sanctioned") else "No",
            )

            if entity.get("entity_type") == "Individual":
                c1, c2 = st.columns(2)
                c1.metric("Date of Birth", entity.get("date_of_birth", "—"))
                c2.metric(
                    "Politically Exposed",
                    "YES" if entity.get("politically_exposed") else "No",
                )

            # Who they own
            st.subheader("Ownership — Outbound (entities this entity owns)")
            owns = run_query(
                """
                MATCH (e:LegalEntity {name: $name})-[r:OWNS]->(target)
                RETURN target.name AS entity, r.ownership_pct AS pct,
                       target.entity_type AS type, target.jurisdiction AS jurisdiction
                ORDER BY r.ownership_pct DESC
                """,
                {"name": selected},
            )
            if owns:
                st.dataframe(owns, use_container_width=True)
            else:
                st.info("This entity does not own any other entities.")

            # Who owns them
            st.subheader("Ownership — Inbound (entities that own this entity)")
            owned_by = run_query(
                """
                MATCH (owner)-[r:OWNS]->(e:LegalEntity {name: $name})
                RETURN owner.name AS entity, r.ownership_pct AS pct,
                       owner.entity_type AS type, owner.jurisdiction AS jurisdiction,
                       owner.is_sanctioned AS sanctioned
                ORDER BY r.ownership_pct DESC
                """,
                {"name": selected},
            )
            if owned_by:
                st.dataframe(owned_by, use_container_width=True)
            else:
                st.info("No entities own this entity.")

            # Directorships
            st.subheader("Directorships")
            directors = run_query(
                """
                MATCH (person:Individual)-[r:DIRECTOR_OF]->(e:LegalEntity {name: $name})
                RETURN person.name AS director, r.role AS role,
                       person.politically_exposed AS pep
                """,
                {"name": selected},
            )
            directs = run_query(
                """
                MATCH (e:LegalEntity {name: $name})-[r:DIRECTOR_OF]->(company)
                RETURN company.name AS company, r.role AS role
                """,
                {"name": selected},
            )
            if directors:
                st.write("**Directors of this entity:**")
                st.dataframe(directors, use_container_width=True)
            if directs:
                st.write("**This person is a director of:**")
                st.dataframe(directs, use_container_width=True)
            if not directors and not directs:
                st.info("No directorships found.")

            # Trades
            st.subheader("Trading Relationships")
            trades = run_query(
                """
                MATCH (e:LegalEntity {name: $name})-[r:TRADES_WITH]-(other)
                RETURN other.name AS counterparty, r.trade_type AS trade_type,
                       r.notional_amount AS notional, r.currency AS currency,
                       r.trade_date AS trade_date, other.is_sanctioned AS counterparty_sanctioned
                """,
                {"name": selected},
            )
            if trades:
                st.dataframe(trades, use_container_width=True)
            else:
                st.info("No trades found for this entity.")


# ═══════════════════════════════════════════════════════════
# MODE 2 — Sanctions Scan
# ═══════════════════════════════════════════════════════════
elif mode == "Sanctions Scan":
    st.title("Sanctions Exposure Scan")
    st.write("All entities with direct or indirect sanctions exposure via ownership chains.")

    rows = run_query(
        """
        MATCH path = (s:LegalEntity {is_sanctioned: true})-[:OWNS*1..5]->(target)
        WHERE s <> target
        WITH s, target, path,
             reduce(pct = 1.0, r IN relationships(path) | pct * r.ownership_pct / 100.0) AS eff
        WHERE eff > 0.05
        RETURN s.name AS sanctioned_source,
               target.name AS exposed_entity,
               round(eff * 10000) / 100.0 AS effective_pct,
               length(path) AS chain_depth,
               [n IN nodes(path) | n.name] AS chain,
               CASE
                 WHEN eff >= 0.25 THEN 'HIGH'
                 WHEN eff >= 0.10 THEN 'MEDIUM'
                 ELSE 'LOW'
               END AS risk_level
        ORDER BY eff DESC
        """
    )

    if rows:
        # Summary metrics
        high = sum(1 for r in rows if r["risk_level"] == "HIGH")
        medium = sum(1 for r in rows if r["risk_level"] == "MEDIUM")
        low = sum(1 for r in rows if r["risk_level"] == "LOW")

        col1, col2, col3 = st.columns(3)
        col1.metric("HIGH RISK", high)
        col2.metric("MEDIUM RISK", medium)
        col3.metric("LOW RISK", low)

        st.divider()

        # Display each risk row with color coding
        for row in rows:
            chain_str = " → ".join(row["chain"])
            level = row["risk_level"]

            if level == "HIGH":
                st.markdown(
                    f'🔴 **HIGH RISK** — {row["exposed_entity"]} '
                    f'({row["effective_pct"]:.1f}% via {row["sanctioned_source"]})'
                )
            elif level == "MEDIUM":
                st.markdown(
                    f'🟡 **MEDIUM RISK** — {row["exposed_entity"]} '
                    f'({row["effective_pct"]:.1f}% via {row["sanctioned_source"]})'
                )
            else:
                st.markdown(
                    f'⚪ **LOW RISK** — {row["exposed_entity"]} '
                    f'({row["effective_pct"]:.1f}% via {row["sanctioned_source"]})'
                )
            st.caption(f"Chain: {chain_str} | Depth: {row['chain_depth']}")
    else:
        st.success("No sanctions exposure found in the graph.")


# ═══════════════════════════════════════════════════════════
# MODE 3 — Full Risk Report
# ═══════════════════════════════════════════════════════════
elif mode == "Full Risk Report":
    st.title("Full Risk Report")
    names = all_entity_names()
    selected = st.selectbox("Select an entity for risk assessment", [""] + names)

    if selected:
        # 1. Direct sanctions status
        st.subheader("1. Direct Sanctions Status")
        direct = run_query(
            "MATCH (e:LegalEntity {name: $name}) RETURN e.is_sanctioned AS sanctioned",
            {"name": selected},
        )
        if direct and direct[0]["sanctioned"]:
            st.error("⛔ This entity is DIRECTLY SANCTIONED.")
        else:
            st.success("✅ This entity is not directly sanctioned.")

        # 2. Indirect sanctions exposure
        st.subheader("2. Indirect Sanctions Exposure")
        indirect = run_query(
            """
            MATCH path = (s:LegalEntity {is_sanctioned: true})-[:OWNS*1..5]->(target:LegalEntity {name: $name})
            WITH s, target, path,
                 reduce(pct = 1.0, r IN relationships(path) | pct * r.ownership_pct / 100.0) AS eff
            RETURN s.name AS sanctioned_source,
                   round(eff * 10000) / 100.0 AS effective_pct,
                   length(path) AS chain_depth,
                   [n IN nodes(path) | n.name] AS chain,
                   CASE
                     WHEN eff >= 0.25 THEN 'HIGH'
                     WHEN eff >= 0.10 THEN 'MEDIUM'
                     ELSE 'LOW'
                   END AS risk_level
            ORDER BY eff DESC
            """,
            {"name": selected},
        )
        if indirect:
            for row in indirect:
                chain_str = " → ".join(row["chain"])
                level = row["risk_level"]
                icon = "🔴" if level == "HIGH" else ("🟡" if level == "MEDIUM" else "⚪")
                st.markdown(
                    f'{icon} **{level}** — {row["effective_pct"]:.1f}% effective ownership '
                    f'by **{row["sanctioned_source"]}**'
                )
                st.caption(f"Chain: {chain_str}")
        else:
            st.success("No indirect sanctions exposure found.")

        # 3. PEP connections
        st.subheader("3. Politically Exposed Persons (PEPs)")
        peps = run_query(
            """
            MATCH (pep:Individual {politically_exposed: true})-[r:DIRECTOR_OF]->(e:LegalEntity {name: $name})
            RETURN pep.name AS pep_name, r.role AS role
            """,
            {"name": selected},
        )
        # Also check if the entity itself is a PEP
        self_pep = run_query(
            """
            MATCH (e:LegalEntity {name: $name})
            WHERE e.politically_exposed = true
            RETURN e.name AS name
            """,
            {"name": selected},
        )
        if self_pep:
            st.warning(f"⚠️ **{selected}** is themselves a Politically Exposed Person.")
        if peps:
            for p in peps:
                st.warning(f"⚠️ PEP Director: **{p['pep_name']}** (role: {p['role']})")
        if not peps and not self_pep:
            st.success("No PEP connections found.")

        # 4. Risky trades
        st.subheader("4. Trades with Sanctions-Exposed Counterparties")
        risky_trades = run_query(
            """
            MATCH (e:LegalEntity {name: $name})-[t:TRADES_WITH]-(counterparty)
            WHERE counterparty.is_sanctioned = true
               OR EXISTS {
                    MATCH (s:LegalEntity {is_sanctioned: true})-[:OWNS*1..4]->(counterparty)
                  }
            RETURN counterparty.name AS counterparty,
                   counterparty.is_sanctioned AS directly_sanctioned,
                   t.trade_type AS trade_type,
                   t.notional_amount AS notional,
                   t.currency AS currency,
                   t.trade_date AS trade_date
            """,
            {"name": selected},
        )
        if risky_trades:
            st.dataframe(risky_trades, use_container_width=True)
        else:
            st.success("No trades with sanctions-exposed counterparties found.")

        # 5. Overall risk summary
        st.divider()
        st.subheader("Overall Risk Assessment")
        is_sanctioned = direct and direct[0]["sanctioned"]
        has_indirect = len(indirect) > 0 if indirect else False
        has_high = any(r["risk_level"] == "HIGH" for r in indirect) if indirect else False
        has_pep = len(peps) > 0 if peps else False
        has_risky_trades = len(risky_trades) > 0 if risky_trades else False

        if is_sanctioned:
            st.error("🚫 **BLOCKED** — Entity is directly sanctioned. No trading permitted.")
        elif has_high and has_pep:
            st.error(
                "🔴 **CRITICAL RISK** — High sanctions exposure AND PEP involvement. "
                "Escalate to compliance immediately."
            )
        elif has_high:
            st.warning("🔴 **HIGH RISK** — Significant indirect sanctions exposure detected.")
        elif has_indirect and has_pep:
            st.warning(
                "🟡 **ELEVATED RISK** — Medium sanctions exposure with PEP connections."
            )
        elif has_indirect:
            st.info("🟡 **MEDIUM RISK** — Some indirect sanctions exposure exists.")
        elif has_pep:
            st.info("⚠️ **MONITOR** — PEP connections detected, but no sanctions exposure.")
        elif has_risky_trades:
            st.info("⚠️ **MONITOR** — Trading with sanctions-exposed counterparties.")
        else:
            st.success("✅ **LOW RISK** — No sanctions exposure, PEP connections, or risky trades detected.")