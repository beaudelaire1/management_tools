# accounts (F02)

User identity and organization memberships.

- Depends on: organizations (F01).
- Models: `Membership`, `Invitation`, `UserProfile`, `SessionRecord`, `AuthenticationFactor`, `AccessRestriction`.
- Services: `invite_user`, `accept_invitation` (anti-enumeration), `user_has_membership`, `record_session`, `revoke_all_sessions`, `register_failed_authentication` (progressive lockout), `is_account_locked`.
- Not yet implemented: MFA challenge flow (factor storage only), password recovery flow.
