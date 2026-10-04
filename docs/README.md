# Flight Price Tracker

Suivi quotidien et gratuit des prix de billets d'avion aller-retour (Barcelone et Marseille vers le Japon, mai 2027, dans l'exemple). Le projet envoie chaque matin un e-mail avec un conseil d'achat. Le guide utilisateur complet (secrets, configuration, limites) se trouve dans [`README.md`](../README.md).

## Stack

- **Langage** : Python 3.12, bibliothèque standard autant que possible : `csv`, `smtplib`, `urllib`, `statistics`.
- **Dépendances** :
  - `fast-flights` 3.1.0, plus `typing_extensions`, qu'il oublie de déclarer ;
  - `PyYAML` ;
  - `pytest`.
- **Automatisation** : GitHub Actions (dépôt public, minutes illimitées), avec un cron quotidien et un déclenchement manuel.
- **Stockage** : fichiers CSV commités par le workflow dans `data/`.

## Installation

```bash
cd flight-price-tracker
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Commandes

Ce projet n'a pas de `package.json` : on n'utilise ni `npm test` ni `npm run build`.

| Commande                                | Rôle                                                                                       |
| --------------------------------------- | ------------------------------------------------------------------------------------------ |
| `python -m pytest -q`                   | tests sur données simulées                                                                 |
| `python -m tracker --dry-run`           | relevé réel, e-mail écrit dans `out/email.html`, sans envoi ni écriture de l'historique    |
| `python -m tracker`                     | relevé, ajout à l'historique et envoi de l'e-mail                                          |
| `python -m tracker --config autre.yaml` | autre fichier de configuration                                                             |
| `python -m tracker.adhoc`               | recherche ponctuelle à partir des variables `SEARCH_*` (workflow « Recherche ponctuelle ») |
| `python -m tracker.diagnose`            | réponse brute de l'API Travelpayouts (nécessite `TRAVELPAYOUTS_TOKEN`)                     |

## Variables d'environnement

Ce sont des secrets GitHub en production. La liste se trouve aussi dans `.env.example`.

| Variable              | Rôle                                                                                         |
| --------------------- | -------------------------------------------------------------------------------------------- |
| `TRAVELPAYOUTS_TOKEN` | token gratuit de l'API Data Travelpayouts                                                    |
| `GMAIL_USER`          | compte Gmail expéditeur                                                                      |
| `GMAIL_APP_PASSWORD`  | mot de passe d'application Gmail                                                             |
| `MAIL_TO`             | destinataires, séparés par des virgules (donnée personnelle, donc jamais dans `config.yaml`) |
