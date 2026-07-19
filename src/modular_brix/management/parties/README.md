# parties (G01)

Common registry of persons and organizations (customers, suppliers, partners).

- Depends on: organizations (F01).
- Models: `Party` (normalized name, merge trail via `merged_into`), `PartyRole` (multi-role without duplication), `PartyIdentifier`.
- Services: `create_party`, `find_duplicate_parties` (accent/case-insensitive), `add_party_role`, `merge_parties` (controlled merge, history preserved, re-merge blocked).
- Not yet implemented: `PartyAddress`, `ContactPoint`, `Relationship`, `PartyTag`, import wizard.
