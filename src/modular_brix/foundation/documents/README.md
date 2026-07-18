# documents (F06)

Versioned documents attached to business objects.

- Depends on: organizations (F01).
- Models: `DocumentCategory`, `Document` (regulatory flag, revocable access), `DocumentVersion` (sha256 digest, append-only history, explicit current marker).
- Services: `add_document_version` — regulatory documents cannot be replaced silently (`allow_regulatory_replacement=True` required and audited by the caller); `revoke_document_access`.
- Not yet implemented: antivirus scanning, type/size validation, signature requests, retention rules.
