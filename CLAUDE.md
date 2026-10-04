# Flight Price Tracker

Suivi quotidien et gratuit des prix de vols aller-retour (voyage au Japon en mai 2027), avec une recommandation ACHETER / ATTENDRE / SURVEILLER envoyée chaque matin par e-mail. Tout tourne sur GitHub Actions (dépôt public).

## Stack

- Python 3.12, bibliothèque standard autant que possible (`csv`, `smtplib`, `urllib`, `statistics`).
- `fast-flights` 3.1.0 (+ `typing_extensions`, non déclaré par lui), `PyYAML`, `pytest`. Environnement `.venv`, pip.
- Sources : Google Flights (via fast-flights) et l'API Data Travelpayouts. Historique en CSV commité.

## Commandes

| Commande | Rôle |
| --- | --- |
| `python -m pytest -q` | Tests sur données simulées, sans réseau |
| `python -m tracker --dry-run` | Relevé réel, e-mail écrit dans `out/email.html`, sans envoi ni écriture de l'historique |
| `python -m tracker` | Relevé, ajout à l'historique et envoi de l'e-mail |
| `python -m tracker.adhoc` | Recherche ponctuelle à partir des variables `SEARCH_*` |
| `python -m tracker.diagnose` | Réponse brute de Travelpayouts (nécessite `TRAVELPAYOUTS_TOKEN`) |

Pas de `package.json` : ni `npm test` ni `npm run build`. Terminé = `python -m pytest -q` passe.

Déploiement : aucun. Les workflows `.github/workflows/daily.yml` (cron quotidien) et `search.yml` (recherche ponctuelle) tournent sur `main`. Ne lance jamais un workflow sans mon accord : il envoie un e-mail.

## Dossiers

```text
config.yaml        trajets, dates, filtres, seuils (aucun secret)
data/              prices.csv (historique) et baseline.csv (prix de l'an dernier)
tracker/           orchestration (__main__), config, airports, models, storage, analysis, expert, report
tracker/sources/   une source = un module avec NAME et collect(search, ctx)
tests/             pytest, sources injectées, aucun appel réseau
docs/              doc technique
```

## Règles critiques

- `data/*.csv` est écrit et commité par le workflow quotidien : ne le modifie pas à la main.
- Dépôt public : aucun secret ni donnée personnelle dans `config.yaml`. Les destinataires sont dans le secret `MAIL_TO`.
- Secrets GitHub (listés dans `.env.example`) : `TRAVELPAYOUTS_TOKEN`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `MAIL_TO`.
- Les tests ne font aucun appel réseau : passe par les dépendances injectables (`fetch`, `get`, `sleep`, `sources`).
- Recherche ponctuelle : les champs du formulaire passent par des variables d'environnement, jamais interpolés dans le script du workflow (risque d'injection).
- Pour piloter le suivi en langage naturel (villes, dates, seuil, dry-run…), utilise la skill `flight-tracker`.

## Où c'est

- `docs/README.md` : stack, installation, commandes, variables d'environnement.
- `docs/architecture.md` : dossiers, flux d'une exécution, choix techniques, diagnostic Travelpayouts.
- `README.md` : guide utilisateur (secrets, configuration, limites).
- `.claude/skills/nouvelle-source/` : procédure pour ajouter une source de prix.
