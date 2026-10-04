# Architecture de Flight Price Tracker

## Dossiers

```text
flight-price-tracker/
├── config.yaml              trajets, dates, filtres, seuils (aucun secret)
├── data/prices.csv          historique des relevés (ajout seul, commité par le workflow)
├── data/baseline.csv        prix de l'an dernier (Travelpayouts), récupérés une fois par recherche
├── tracker/
│   ├── __main__.py          orchestration : sources → stockage → analyse → expert → e-mail
│   ├── adhoc.py             recherche ponctuelle : formulaire GitHub (SEARCH_*) → config → run sans historique
│   ├── diagnose.py          réponse brute de l'API Travelpayouts, pour le débogage
│   ├── config.py            lecture et validation de config.yaml, filtres
│   ├── airports.py          villes/pays → codes IATA, règle « BCN ou France » au départ
│   ├── models.py            Quote, Leg, Context, paires de dates, assemblage des open-jaw
│   ├── sources/             une source = un module avec NAME et collect(search, ctx)
│   │   ├── travelpayouts.py
│   │   └── google_flights.py
│   ├── storage.py           lecture et écriture CSV
│   ├── analysis.py          meilleurs prix, comparaisons, tendance
│   ├── expert.py            recommandation ACHETER / ATTENDRE / SURVEILLER
│   └── report.py            e-mail HTML et envoi SMTP
├── tests/                   pytest, données simulées, aucun appel réseau
└── .github/workflows/
    ├── daily.yml            cron quotidien sur config.yaml, commit de l'historique
    └── search.yml           recherche ponctuelle, formulaire de 17 champs, sans commit
```

## Flux d'une exécution

1. `config.yaml` est validé. Une ville de départ hors France et hors Barcelone, ou une destination inconnue, arrête le programme avec un message clair.
2. Pour chaque recherche, les sources de `sources.SOURCES` passent dans l'ordre :
   - **Travelpayouts** fait environ 3 requêtes par couple de villes et par mois : allers-retours, puis allers simples dans les deux sens pour composer les open-jaw. Les séjours sont acceptés à ±2 jours de `stay_days` (`STAY_TOLERANCE_DAYS`), car le cache contient des séjours de toutes durées.
   - **Google Flights** planifie ses requêtes dans la limite du budget : d'abord les 20 combinaisons les moins chères de la veille et du jour, puis la moitié d'un échantillon d'allers-retours mélangé différemment chaque jour, puis les open-jaw de la meilleure paire de dates, puis le reste de l'échantillon.
   - Une exception dans une source est capturée et affichée dans « État des sources ».
3. On garde la moins chère par source et par combinaison, puis on l'ajoute à `data/prices.csv`. Le dry-run n'écrit rien.
4. `analysis` calcule les meilleurs prix (global, par ville, par date, par durée), les écarts vs veille, 7 jours et 30 jours, la moyenne mobile, le plus bas historique, le percentile et les alertes.
5. `expert` combine ces éléments en un score :
   - la fenêtre d'achat long-courrier (6 à 2 mois, ou 8 à 4 en haute saison : Golden Week, jours fériés français calculés depuis Pâques) ;
   - l'indicateur Google ;
   - le percentile ;
   - la tendance sur 7 jours et sur l'historique Google ;
   - les prix de l'an dernier ;
   - le seuil d'alerte.

   La confiance dépend du volume de données disponibles.

6. `report` produit le HTML, avec des styles en ligne et un graphique en barres HTML, car Gmail bloque le SVG. Il est envoyé par SMTP Gmail ; l'objet du mail porte le meilleur prix et la décision.

## Choix techniques

- **CSV plutôt que SQLite** : chaque commit quotidien n'ajoute que des lignes, donc git ne stocke que la différence, alors qu'une base SQLite serait réécrite entièrement à chaque commit. Le volume reste faible : quelques centaines de lignes par jour.
- **Lecture de la page Google par le projet** : fast-flights sert à construire l'URL. Son analyseur ignore les « meilleurs vols » (`payload[2]`, souvent les moins chers) et l'indicateur de prix (`payload[5]`).
- **Cookie `SOCS`** : sans lui, une IP européenne reçoit la page de consentement de Google au lieu des résultats.
- **Durée maximale filtrée après coup** : envoyée à Google, elle fait disparaître l'indicateur de prix.
- **Durée d'escale envoyée à Google et revérifiée** : le filtre `min/max_layover_minutes` garde l'indicateur de prix et s'applique aux deux trajets. Le détail des escales (`f[13]` : minutes, aéroport d'arrivée, aéroport de départ) permet de revérifier l'aller et de détecter un changement d'aéroport. Un vol avec escale(s) dont le détail manque est écarté. Pour la même raison, Travelpayouts écarte ses prix avec escale quand ces critères sont actifs.
- **Recherche ponctuelle sans historique** : `run(keep_history=False)` ne lit ni n'écrit `data/`, pour ne pas mélanger des recherches différentes dans les tendances. Les champs du formulaire passent par des variables d'environnement, jamais interpolés dans le script du workflow (risque d'injection), puis par la même validation que `config.yaml`.
- **Identifiants Gmail nettoyés** : espaces et retours à la ligne sont retirés du mot de passe d'application, car Google l'affiche en 4 groupes. Un refus d'authentification donne un message clair.
- **Open-jaw composés de deux allers simples** : Google charge les résultats multi-destinations en différé, ils ne sont donc pas dans la page.
- **Prix toujours par personne** : Google renvoie le total pour tous les passagers, Travelpayouts un prix par personne.
- **Sources injectables** (`fetch`, `get`, `sleep`, `sources`) : les tests tournent sans réseau et sans attente.

## Diagnostic Travelpayouts

`python -m tracker.diagnose`, ou le workflow lancé à la main avec `diagnostic` coché, affiche la réponse brute de l'API pour trois requêtes témoins, sans afficher le token. Vérifié le 3 octobre 2026 : les champs utilisés par le code correspondent à la réponse réelle. En revanche, `v2/prices/latest` ne renvoie rien pour l'an dernier, car le cache ne conserve les prix que 2 à 7 jours.
