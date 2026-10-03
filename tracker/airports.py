"""Résolution des villes et pays en codes IATA.

# ponytail: table écrite à la main (France + BCN + une dizaine de pays) ;
# un pays absent se règle avec `destination_airports` dans config.yaml.
"""
import unicodedata

# Départs autorisés : Barcelone ou un aéroport en France.
FRANCE_AIRPORTS = {
    "CDG", "ORY", "BVA", "MRS", "NCE", "LYS", "TLS", "BOD", "NTE", "MPL", "LIL", "SXB", "BSL",
    "BIQ", "BES", "RNS", "AJA", "BIA", "PUF", "PGF", "FSC", "CFE", "LRH", "TLN", "GNB", "LDE",
}
ALLOWED_ORIGIN_AIRPORTS = FRANCE_AIRPORTS | {"BCN"}

CITIES = {
    # départs
    "paris": ["CDG", "ORY"], "par": ["CDG", "ORY"], "marseille": ["MRS"], "nice": ["NCE"],
    "lyon": ["LYS"], "toulouse": ["TLS"], "bordeaux": ["BOD"], "nantes": ["NTE"],
    "montpellier": ["MPL"], "lille": ["LIL"], "strasbourg": ["SXB"], "mulhouse": ["BSL"],
    "bale-mulhouse": ["BSL"], "biarritz": ["BIQ"], "brest": ["BES"], "rennes": ["RNS"],
    "ajaccio": ["AJA"], "bastia": ["BIA"], "pau": ["PUF"], "perpignan": ["PGF"],
    "clermont-ferrand": ["CFE"], "toulon": ["TLN"], "grenoble": ["GNB"],
    "barcelone": ["BCN"], "barcelona": ["BCN"],
    # destinations
    "tokyo": ["NRT", "HND"], "osaka": ["KIX"], "kyoto": ["KIX"], "nagoya": ["NGO"],
    "fukuoka": ["FUK"], "sapporo": ["CTS"], "okinawa": ["OKA"], "seoul": ["ICN"],
    "bangkok": ["BKK", "DMK"], "hanoi": ["HAN"], "ho chi minh": ["SGN"], "singapour": ["SIN"],
    "bali": ["DPS"], "montreal": ["YUL"], "toronto": ["YYZ"], "mexico": ["MEX"],
    "sydney": ["SYD"], "rio de janeiro": ["GIG"], "sao paulo": ["GRU"],
}

# Pays : (code ISO pour Travelpayouts, aéroports internationaux)
COUNTRIES = {
    "japon": ("JP", ["NRT", "HND", "KIX", "NGO", "FUK", "CTS", "OKA"]),
    "coree du sud": ("KR", ["ICN", "PUS"]),
    "thailande": ("TH", ["BKK", "DMK", "HKT", "CNX"]),
    "vietnam": ("VN", ["SGN", "HAN", "DAD"]),
    "indonesie": ("ID", ["CGK", "DPS"]),
    "singapour": ("SG", ["SIN"]),
    "canada": ("CA", ["YUL", "YYZ", "YVR"]),
    "mexique": ("MX", ["MEX", "CUN"]),
    "bresil": ("BR", ["GRU", "GIG"]),
    "australie": ("AU", ["SYD", "MEL", "BNE", "PER"]),
}

# Code ville utilisé par le cache Travelpayouts (par défaut : le code aéroport).
TP_CITY = {
    "CDG": "PAR", "ORY": "PAR", "BVA": "PAR", "BSL": "MLH", "NRT": "TYO", "HND": "TYO",
    "KIX": "OSA", "CTS": "SPK", "ICN": "SEL", "DMK": "BKK", "CGK": "JKT", "YUL": "YMQ",
    "YYZ": "YTO", "GIG": "RIO", "GRU": "SAO",
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return text.strip().lower()


def _known_code(code: str) -> bool:
    return code in ALLOWED_ORIGIN_AIRPORTS or any(code in a for a in CITIES.values()) or any(
        code in a for _, a in COUNTRIES.values())


def resolve_origin(name: str) -> list[str]:
    """Ville ou code IATA de départ -> aéroports. Refuse tout ce qui n'est ni en France ni à Barcelone."""
    key = _norm(name)
    airports = CITIES.get(key) or ([key.upper()] if len(key) == 3 else [])
    if not airports or not set(airports) <= ALLOWED_ORIGIN_AIRPORTS:
        raise ValueError(
            f"Ville de départ refusée : « {name} ». Seuls Barcelone (BCN) et les aéroports en France "
            f"sont autorisés ({', '.join(sorted(ALLOWED_ORIGIN_AIRPORTS))})."
        )
    return airports


def resolve_destination(name: str) -> tuple[list[str], str | None]:
    """Ville, pays ou code IATA de destination -> (aéroports, code pays éventuel)."""
    key = _norm(name)
    if key in COUNTRIES:
        country, airports = COUNTRIES[key]
        return list(airports), country
    if key in CITIES:
        return list(CITIES[key]), None
    if len(key) == 3 and _known_code(key.upper()):
        return [key.upper()], None
    raise ValueError(
        f"Destination inconnue : « {name} ». Ajoute `destination_airports: [CODE, ...]` à la recherche "
        f"dans config.yaml (pays connus : {', '.join(sorted(COUNTRIES))})."
    )


def tp_city(airport: str) -> str:
    return TP_CITY.get(airport, airport)
