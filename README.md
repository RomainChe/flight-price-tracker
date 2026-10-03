# Flight Price Tracker

Suivi quotidien des prix de billets d'avion aller-retour, avec conseil d'achat, **100 % gratuit**.

Chaque matin, GitHub Actions :

1. relève les prix sur Google Flights et Aviasales / Travelpayouts ;
2. les ajoute à l'historique `data/prices.csv`, commité dans le dépôt ;
3. calcule la tendance (veille, 7 jours, 30 jours, moyenne mobile, plus bas historique, percentile) ;
4. donne une recommandation **ACHETER / ATTENDRE / SURVEILLER**, avec un niveau de confiance et une fenêtre d'achat estimée ;
5. t'envoie un récapitulatif HTML par e-mail.

Suivi configuré : voyage au Japon du 5 au 22 mai 2027, au départ de Barcelone, Paris, Marseille, Lyon, Nice ou Toulouse. Le projet compare tous les aéroports internationaux japonais, avec 2 escales au maximum, chacune de 3 à 6 h et sans changer d'aéroport.

Un second workflow, **Recherche ponctuelle**, lance une recherche unique sur n'importe quelle destination, avec des critères saisis dans un formulaire.

## Sources de prix

| Source | Coût | Ce qu'elle apporte |
| --- | --- | --- |
| Google Flights, via [fast-flights](https://github.com/AWeirdDev/fast-flights) | gratuit, sans clé | prix actuels, indicateur « bas / habituel / élevé », environ 60 jours d'historique par trajet |
| [Aviasales / Travelpayouts Data API](https://www.travelpayouts.com/) | token gratuit | tout un mois en une requête (prix du cache des recherches des utilisateurs), prix de l'an dernier |

Sources écartées :

- **Skyscanner** : API réservée aux partenaires.
- **Amadeus Self-Service** : fermé depuis juillet 2026.
- **SerpApi, Ignav…** : payants au-delà d'un quota.

Si une source tombe en panne, les autres continuent, et l'e-mail le signale dans « État des sources ».

## Installation locale

Il faut Python 3.12.

```bash
python -m venv .venv
source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q            # tests sur données simulées
python -m tracker --dry-run    # génère out/email.html sans l'envoyer
```

Le **dry-run** interroge les vraies sources mais n'envoie rien et ne touche pas à l'historique. Ouvre `out/email.html` dans un navigateur pour voir le résultat. Sans token Travelpayouts, cette source apparaît en échec et Google Flights fonctionne seul.

Pour un essai local avec les vrais identifiants, renseigne les variables de `.env.example` dans ton terminal. Le fichier `.env` est ignoré par git.

## Créer le token Travelpayouts (gratuit)

1. Crée un compte sur [travelpayouts.com](https://www.travelpayouts.com/).
2. Rejoins le programme **Aviasales**, sans frais.
3. Dans ton **Profil**, onglet **API token**, copie le token ([aide Travelpayouts](https://support.travelpayouts.com/hc/en-us/articles/13024069738386-Where-to-find-API-token)). N'utilise « Update token » que si le token a fuité : l'ancien cesse aussitôt de fonctionner.

## Créer le mot de passe d'application Gmail

1. Active la [validation en deux étapes](https://myaccount.google.com/signinoptions/twosv) de ton compte Google.
2. Va sur [Mots de passe des applications](https://myaccount.google.com/apppasswords), crée-en un nommé « Flight tracker », puis copie les 16 caractères.

Ce n'est pas ton mot de passe Gmail : il ne sert qu'à envoyer des e-mails, et tu peux le révoquer à tout moment.

## Configurer les secrets GitHub

Dans le dépôt : **Settings → Secrets and variables → Actions → New repository secret**.

| Secret | Valeur |
| --- | --- |
| `TRAVELPAYOUTS_TOKEN` | le token Travelpayouts |
| `GMAIL_USER` | l'adresse Gmail qui envoie |
| `GMAIL_APP_PASSWORD` | le mot de passe d'application |
| `MAIL_TO` | le ou les destinataires, séparés par des virgules |

Les destinataires sont dans un secret, et non dans `config.yaml`, parce que le dépôt est public.

## Changer de trajet ou de dates

Tout se règle dans [`config.yaml`](config.yaml), sans toucher au code.

- `origins` : villes ou codes IATA. Seuls Barcelone et les aéroports en France sont acceptés ; `Paris` donne CDG et ORY. Toute autre ville est refusée avec un message clair.
- `destination` : une ville (`Tokyo`), un pays (`Japon`) ou un code IATA. Pour un pays, tous ses aéroports internationaux sont essayés, y compris en open-jaw (par exemple arrivée à Tokyo, retour depuis Osaka). Le retour peut se faire vers n'importe quelle ville de départ. Pour un pays absent de la table, ajoute `destination_airports: [CODE, ...]`.
- `depart_from` / `depart_to`, plus `stay_days` (par exemple `[10, 14, 21]`) ou une `return_date` fixe.
- `passengers`, `cabin`, `currency`, `max_stops`, `max_duration_hours`, `checked_bag`, `excluded_airlines`, `alert_below`.
- `layover_hours: [3, 6]` : durée de chaque escale, en heures. `no_airport_change: true` : arrivée et départ de l'escale dans le même aéroport. Ces deux critères sont envoyés à Google, puis revérifiés sur l'aller. Les prix Travelpayouts avec escale sont alors écartés, car son cache ne détaille pas les escales.
- Pour suivre plusieurs recherches en parallèle, ajoute des entrées sous `searches`. Le budget Google se partage entre elles.

## Lancer manuellement

Deux workflows, dans l'onglet **Actions** :

- **Suivi quotidien (config.yaml)** : la recherche de `config.yaml`, lancée chaque matin, ou à la main avec **Run workflow**.
  - Coche « Générer l'e-mail sans l'envoyer » pour un dry-run : l'e-mail est alors téléchargeable dans les artefacts du run.
  - Coche « Afficher dans les logs la réponse brute de l'API Travelpayouts » pour un diagnostic. Le token n'est jamais affiché.
- **Recherche ponctuelle** : un formulaire où tu saisis la destination, les villes de départ, les dates (période de départ, plus une date de retour fixe ou des durées de séjour), les passagers, la classe, les escales (nombre, durée min et max, sans changement d'aéroport), le bagage en soute, la durée max, les compagnies exclues et le seuil d'alerte.
  - Le run envoie l'e-mail, sans toucher à l'historique ni à `config.yaml`.
  - La règle « départ de Barcelone ou de France » s'applique aussi.

Le cron tourne à 6 h UTC, soit 8 h à Paris l'été et 7 h l'hiver. GitHub n'exécute les crons que sur la **branche par défaut** du dépôt.

## Limites, en toute transparence

- **Google Flights n'a pas d'API officielle.** fast-flights lit la page publique, qui peut changer ou bloquer les requêtes. Le projet s'arrête alors proprement après 5 échecs de suite et l'e-mail le signale. Pour rester discret, il fait 150 requêtes par jour au maximum, avec 2 à 5 s de pause entre chaque.
- **Les open-jaw sont composés de deux allers simples**, soit deux billets séparés : Google ne fournit pas les résultats multi-destinations dans sa page, et Travelpayouts ne les a pas en cache. Un vrai billet open-jaw peut coûter moins cher.
- **Tout n'est pas interrogé chaque jour** : il y a plus de 2 000 combinaisons. Le projet re-vérifie d'abord les 20 moins chères de la veille, puis interroge un échantillon qui change chaque jour, si bien que toutes les dates finissent par être couvertes.
- **Pour un aller-retour Google**, la compagnie, les escales et la durée affichées sont celles de l'aller. Le critère de durée d'escale est envoyé à Google pour les deux trajets, mais seul l'aller peut être revérifié, notamment pour l'absence de changement d'aéroport.
- **Travelpayouts sert des prix en cache**, qui peuvent dater de quelques jours. Sa base ne couvre que la classe économique. Comme le cache contient des séjours de toutes durées, il accepte un écart de ±2 jours par rapport à `stay_days`, et l'e-mail affiche la durée réelle.
- **Historique de l'an dernier** : le projet le demande à Travelpayouts, depuis Barcelone, Paris et les villes de départ configurées. Je n'ai pas trouvé de jeu de données public et gratuit fiable pour l'Europe → Asie. Faute de données, l'e-mail le dit et la recommandation s'appuie sur les règles générales du secteur.
- **Les règles de la recommandation sont un barème simple** : achat long-courrier 6 à 2 mois avant le départ, 8 à 4 mois en haute saison (Golden Week, ponts français). Elles se basent aussi sur la position du prix et la tendance. La confiance augmente avec les jours d'historique accumulés.
