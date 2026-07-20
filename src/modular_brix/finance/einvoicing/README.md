# einvoicing (C14)

Electronic invoicing through pluggable platform adapters.

- Pre-validation reuses the C01 mandatory-mention check; the structured payload is frozen with its SHA-256 at preparation; transmission is idempotent per key (no double emission); provider status sync reports local/provider divergence; swapping the adapter never touches C01.
- Compliance note: the ordinary PDF sent by email is NOT the regulated electronic invoice. Production use requires an adapter for a plateforme agréée (the built-in `reference` adapter is for tests and local runs only) and directory/e-reporting flows remain to implement.
