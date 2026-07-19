from collections.abc import Mapping


def ensure_idempotent_replay(
    *,
    replay_payload: Mapping[str, object],
    stored_payload: Mapping[str, object],
    resource_name: str,
) -> None:
    """Reject a reused key when any material payload field changed.

    Field names are reported for diagnostics, but values are intentionally omitted
    because notification bodies and provider references may contain sensitive data.
    """
    fields = set(replay_payload) | set(stored_payload)
    mismatched_fields = sorted(
        field for field in fields if replay_payload.get(field) != stored_payload.get(field)
    )
    if mismatched_fields:
        joined_fields = ", ".join(mismatched_fields)
        raise ValueError(
            f"An idempotency key cannot be reused with a different {resource_name} payload "
            f"(fields: {joined_fields})."
        )
