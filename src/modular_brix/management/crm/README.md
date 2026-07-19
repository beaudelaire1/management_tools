# crm (G02)

Prospection cycle: leads and opportunities.

- Depends on: parties (G01).
- Models: `Lead`, `Opportunity` (stage, probability, loss reason).
- Services: `convert_lead_to_opportunity` (party reuse — no duplication, idempotent, history preserved), `lose_opportunity` (reason required), `win_opportunity`.
- Not yet implemented: `Pipeline`/`PipelineStage` versioning, `Interaction`, `FollowUp`, kanban UI.
