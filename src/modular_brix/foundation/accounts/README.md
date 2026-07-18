# accounts (F02)

User identity and organization memberships.

- Depends on: organizations (F01).
- Models: `Membership` (unique user/organization), `Invitation` (token, expiry, revocation).
- Services: `invite_user`, `accept_invitation` (generic error message for unknown/expired/revoked tokens — anti-enumeration), `user_has_membership`.
- Not yet implemented: MFA, progressive lockout, session revocation, `UserProfile`, `SessionRecord`.
