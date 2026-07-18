# References validation log

Consultation date: 2026-07-18

## R-001

- Source: Django Software Foundation, Supported versions policy
- URL: https://www.djangoproject.com/download/#supported-versions
- Classification: technical best practice
- Verified statement: Django 5.2 is listed as LTS and remains in extended support until April 2028.
- Testable rule: dependency constraint must pin Django to >=5.2,<5.3 for this lot.
- Evidence: dependency is pinned in pyproject.toml.

## R-002

- Source: CNIL, Guide de la securite des donnees personnelles
- URL: https://www.cnil.fr/fr/guide-de-la-securite-des-donnees-personnelles
- Classification: security recommendation
- Verified statement: authentication, authorization, operations traceability, backup, and continuity are explicit baseline controls.
- Testable rule: foundation architecture must include dedicated modules for auth/accounts, permissions, audit, and provide migration-backed persistence.
- Evidence: foundation apps created and organization persistence tested.

## R-003

- Source: OWASP ASVS project page
- URL: https://owasp.org/www-project-application-security-verification-standard/
- Classification: applicable standard
- Verified statement: latest stable ASVS is 5.0.0.
- Testable rule: future security backlog requirements should be tagged with ASVS IDs in v5.0.0 format.
- Evidence: initial backlog rule documented in this file.

## References not verified in this increment

- RGPD art. 25 and 32: NON VERIFIED
- NIST SP 800-218 (SSDF): NON VERIFIED
- ANSSI recommendations: NON VERIFIED
- BOFiP FEC and French accounting legal references: NON VERIFIED
