# workflows (F05)

Configurable state machines with approvals.

- Depends on: organizations (F01).
- Models: `WorkflowDefinition` (versioned), `WorkflowState`, `WorkflowTransition`, `WorkflowInstance`, `ApprovalDecision`.
- Services: `apply_transition` — rejects illegal transitions, enforces requester/approver separation, idempotent via unique `(instance, idempotency_key)`; definitions with running instances are frozen.
- Not yet implemented: escalation rules, deadlines, definition version cloning.
