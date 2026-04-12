# Counterparty Ontology

## Classes

- **LegalEntity** (abstract parent)
  - **Corporation**
  - **Individual**
  - **GovernmentBody**
  - **Fund**

## Properties

- **LegalEntity:** `name`, `jurisdiction`, `entityType`, `isActive`, `isSanctioned`
- **Corporation:** `incorporationDate`, `registrationNumber`, `industry`
- **Individual:** `nationality`, `dateOfBirth`, `politicallyExposed` (boolean)

## Relationships

- **OWNS** (from: LegalEntity, to: LegalEntity, properties: `ownershipPercentage`, `since`)
- **DIRECTOR_OF** (from: Individual, to: Corporation)
- **REGISTERED_IN** (from: Corporation, to: Jurisdiction)
- **TRADES_WITH** (from: LegalEntity, to: LegalEntity)

## Constraints

- `ownershipPercentage` must be between 0 and 100.
- Total ownership of a single entity cannot exceed 100%.
- A sanctioned entity’s subsidiaries (more than 50% owned) are also considered sanctioned (derived rule).