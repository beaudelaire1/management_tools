# État des lieux vérifié — Modular Brix

Date de vérification : 2026-07-19.
Commit de référence : `b1a9006` (fusion de la PR #4, portail configurable par brique).

Ce document est un constat d'ingénierie : chaque affirmation de la section « Vérification » a été obtenue en
exécutant réellement la chaîne qualité de la CI (`.github/workflows/ci.yml`) sur un environnement propre
(Python 3.13, PostgreSQL 16.13, installation depuis `requirements.lock`), et non en lisant la documentation.

## 1. Résumé

Modular Brix est un socle Django modulaire (briques installables séparément) couvrant les fondations
transverses, le cycle commercial, la facturation/encaissement et le pilotage. Le projet est en pré-release :
les lots 0 à 3 du cahier des charges sont livrés, testés et durcis ; les lots opérations et comptabilité ne
sont pas commencés. Le dépôt est sain : aucune PR ouverte, aucune issue ouverte, arbre de travail propre,
et toutes les portes qualité passent depuis un environnement vierge.

## 2. Vérification reproduite (résultats mesurés)

| Étape (ordre CI) | Commande | Résultat |
| --- | --- | --- |
| Installation verrouillée | `pip install --no-deps -r requirements.lock` puis install editable | OK — Django 5.2.16 |
| Lint | `ruff check .` | OK — « All checks passed! » |
| Typage | `mypy src` | OK — 0 problème sur 129 fichiers |
| Scan sécurité | `bandit -r src -c pyproject.toml` | OK — 0 finding (toutes sévérités) |
| Audit dépendances | `pip-audit --skip-editable` | OK — aucune vulnérabilité connue |
| Complétude migrations | `manage.py makemigrations --check --dry-run` | OK — « No changes detected » |
| Migration base vierge | `manage.py migrate --noinput` sur PostgreSQL 16.13 | OK — toutes migrations appliquées |
| Check déploiement production | `manage.py check --deploy --fail-level WARNING` | OK — 0 issue |
| Tests + porte de couverture | `pytest -q` | OK — 109 tests passés en ~18 s, couverture 95,12 % (seuil 85 %) |
| Smoke test runtime | `runserver` puis sondes HTTP | OK — `GET /org/health/` → 200 « organizations-ok » ; `GET /app/` → 302 vers la page de connexion (portail protégé par authentification) |

Environnement de vérification : conteneur Linux, Python 3.13, PostgreSQL 16.13 local (base `app_test`),
réglages `example_project.config.settings.test` (production pour le check de déploiement).

## 3. Périmètre livré

- Fondations F01–F12 : organisations, comptes (sessions, MFA, verrouillage progressif), permissions
  deny-by-default avec périmètres de données et délégations datées, audit append-only verrouillé par trigger
  PostgreSQL, workflows idempotents, documents versionnés, notifications, configuration, données de
  référence, imports/exports, séquences transactionnelles, base UI.
- Cycle commercial G01–G05 : tiers avec fusion contrôlée, CRM, catalogue à tarification datée, devis
  versionnés à totaux figés, commandes et livraisons plafonnées.
- Finance C01–C03 : factures immuables à numérotation chronologique continue, avoirs plafonnés, paiements
  idempotents à allocation double-plafonnée, balance âgée, relances, litiges.
- Pilotage P01–P09 et P13 : indicateurs déterministes, tableaux de bord soumis aux permissions, objectifs,
  budgets figés à l'approbation, prévisions reproductibles, scénarios sans effet de bord, projections de
  trésorerie sourcées, marges et entonnoir réconciliés, rapports ; le pilotage ne modifie jamais les domaines.
- Portail `modular_brix.portal` : interface server-rendered authentifiée à `/app/`, bascule d'organisation,
  navigation soumise aux permissions, parcours devis → commande → facture → paiement, configurable par
  brique sans fork de templates (voir `portal_customization.md`).

Volumétrie : ~7 300 lignes sous `src/`, ~2 700 lignes de tests (15 modules), 3 ADR, traçabilité
spécification ↔ code maintenue dans `spec_traceability.md`.

## 4. Reste à faire

- Non commencé : opérations et effectifs (G06–G15, P10–P12) ; chaîne pré-comptable et comptable —
  dépenses, fournisseurs, banque, comptabilité générale et analytique, TVA, immobilisations, clôture,
  facturation électronique, FEC (C04–C15).
- Limites par brique (documentées dans chaque README) : signatures électroniques et antivirus (F06), listes de
  suppression (F07), champs personnalisés (F08), calendriers et jours fériés (F10), mappings et chiffrement des
  imports (F11), catalogue de partiels HTMX (F12). C01 (mentions obligatoires et PDF) a été complété depuis ce
  constat : snapshot complet figé à l'émission, détection des mentions manquantes, rendu PDF déterministe sans
  dépendance et téléchargement portail ; restent l'adresse acheteur sans modèle source côté G01 et le taux de
  pénalité fourni par l'appelant.
- Prérequis avant production : validation légale et par expert-comptable des exigences françaises
  (facturation, conservation, FEC) ; sauvegarde/restauration uniquement démontrée via
  `dumpdata`/`loaddata` sur le projet de référence.

## 5. Risques et points d'attention

- Aucune release taguée : le `CHANGELOG` est entièrement en « Unreleased » ; figer une version 0.x
  faciliterait l'installation par des projets clients.
- La couverture globale mesurée (95,12 %) est légèrement inférieure au chiffre historique du document de
  traçabilité (96,63 %) — normal après l'ajout du portail, et toujours largement au-dessus du seuil de 85 %.
- Les invariants financiers reposent sur des triggers PostgreSQL : toute cible de déploiement doit être
  PostgreSQL ; SQLite n'est utilisable pour aucun test d'intégration des invariants.

## 6. Prochaines étapes recommandées

1. ~~Basculer le changelog en versionné~~ — fait : section 0.1.0 datée du 2026-07-19 ; créer le tag `v0.1.0`
   sur `main` une fois la branche fusionnée.
2. ~~Compléter C01 (mentions obligatoires et PDF)~~ — fait : voir `tests/test_invoice_compliance.py` et le
   README de la brique billing pour les deux limites restantes (adresse acheteur, taux de pénalité).
3. Lot suivant au choix : opérations (G06+) ou chaîne pré-comptable (C04+), selon la priorité produit.
4. Compléter les limites restantes listées en section 4 brique par brique.
