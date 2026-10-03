"""E-mail HTML quotidien (styles en ligne, lisible sur mobile) et envoi par SMTP Gmail."""
import smtplib
from datetime import date
from email.message import EmailMessage
from html import escape

from .expert import MONTHS

COLORS = {"ACHETER": "#1b5e20", "ATTENDRE": "#0d47a1", "SURVEILLER": "#8a4b00"}
CARD = "background:#ffffff;border:1px solid #dde3ea;border-radius:8px;padding:14px;margin:0 0 14px"
MUTED = "color:#555b66;font-size:13px"


def fr_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{'1er' if d.day == 1 else d.day} {MONTHS[d.month - 1]}"


def euros(value) -> str:
    return f"{value:,.0f} €".replace(",", " ")


def _links(q) -> str:
    links = [u for u in q.link.split(" | ") if u]
    if len(links) == 2:
        labels = [f"Voir l'aller {q.origin}–{q.dest}", f"Voir le retour {q.return_from}–{q.return_to}"]
    else:
        labels = [f"Voir l'offre {q.origin}–{q.dest} du {fr_date(q.depart_date)}"]
    return " · ".join(f'<a href="{escape(u)}" style="color:#0b57d0">{escape(t)}</a>' for u, t in zip(links, labels))


def _offer(q) -> str:
    stops = "direct" if q.stops == 0 else f"{q.stops} escale(s) à l'aller" if q.stops is not None else "escales non précisées"
    hours = f", {q.duration_min // 60} h {q.duration_min % 60:02d} à l'aller" if q.duration_min else ""
    route = f"{q.origin} → {q.dest} · retour {q.return_from} → {q.return_to}"
    return (
        f'<div style="border-top:1px solid #eef1f4;padding:10px 0">'
        f'<div style="font-size:18px;font-weight:bold">{euros(q.price)} <span style="{MUTED};font-weight:normal">/ pers.</span></div>'
        f"<div>{escape(route)}</div>"
        f'<div style="{MUTED}">{fr_date(q.depart_date)} → {fr_date(q.return_date)} ({q.stay_days} j) · '
        f"{escape(q.airlines or 'compagnie non précisée')} · {stops}{hours}</div>"
        + (f'<div style="{MUTED}">Escales {escape(q.layovers)}</div>' if q.layovers else "")
        + f'<div style="{MUTED}">{escape(q.kind)} · {escape(q.source)}</div>'
        f'<div style="font-size:14px;margin-top:4px">{_links(q)}</div></div>'
    )


def _bars(points: list[tuple[str, float]], title: str) -> str:
    if len(points) < 2:
        return ""
    high = max(p for _, p in points)  # barres depuis zéro : pas d'écart visuel exagéré
    rows = []
    for day, price in points:
        width = 100 * price / high
        rows.append(
            f'<tr><td style="{MUTED};white-space:nowrap;padding-right:6px">{fr_date(day)}</td>'
            f'<td style="width:100%"><div style="background:#5b8def;height:10px;width:{width:.0f}%"></div></td>'
            f'<td style="font-size:13px;padding-left:6px;white-space:nowrap">{euros(price)}</td></tr>'
        )
    return (f'<h3 style="font-size:15px;margin:12px 0 6px">{escape(title)}</h3>'
            f'<table role="presentation" style="width:100%;border-collapse:collapse">{"".join(rows)}</table>')


def criteria(search) -> str:
    if search.depart_from == search.depart_to:
        dates = f"départ le {fr_date(search.depart_from.isoformat())}"
    else:
        dates = f"départ du {fr_date(search.depart_from.isoformat())} au {fr_date(search.depart_to.isoformat())}"
    dates += (f", retour le {fr_date(search.return_date.isoformat())}" if search.return_date
              else f", séjour de {', '.join(map(str, search.stay_days))} jours")
    parts = [dates, f"{search.passengers} passager(s), {search.cabin}"]
    if search.max_stops is not None:
        parts.append("vol direct" if search.max_stops == 0 else f"{search.max_stops} escale(s) max")
    if search.layover_hours:
        parts.append(f"escales de {search.layover_hours[0]:g} à {search.layover_hours[1]:g} h")
    if search.no_airport_change:
        parts.append("sans changement d'aéroport")
    if search.max_duration_hours:
        parts.append(f"{search.max_duration_hours:g} h de trajet max")
    if search.checked_bag:
        parts.append("bagage en soute inclus (Google)")
    if search.excluded_airlines:
        parts.append(f"sans {', '.join(search.excluded_airlines)}")
    return " · ".join(parts)


def section(search, a: dict, advice: dict) -> str:
    title = f"{search.name} : {', '.join(search.origins)} → {search.destination}"
    if not a.get("best"):
        return f'<div style="{CARD}"><h2 style="font-size:18px;margin:0">{escape(title)}</h2><p>Aucun prix trouvé aujourd\'hui.</p></div>'
    best = a["best"]
    alerts = "".join(
        f'<p style="background:#fff4e5;border-left:4px solid #b26a00;padding:8px;margin:8px 0"><strong>Alerte :</strong> {escape(t)}</p>'
        for t in a["alerts"])
    color = COLORS[advice["decision"]]
    reasons = "".join(f"<li>{escape(r)}</li>" for r in advice["reasons"])
    limits = "".join(f"<li>{escape(r)}</li>" for r in advice["limits"])

    changes = " · ".join(
        f"vs {label} : {c[2]} {c[0]:+} € ({c[1]:+} %)" if c else f"vs {label} : pas encore de relevé"
        for label, c in a["changes"].items())
    stats = [f"Moyenne mobile 7 j : {euros(a['moving_avg_7'])}", f"Plus bas historique : {euros(a['historical_min'])}"]
    if a["percentile"] is not None:
        stats.append(f"Percentile du prix du jour : {a['percentile']}e")
    if a["google"]:
        g = a["google"]
        stats.append(f"Google : prix {g.price_level} (fourchette habituelle {g.typical_low:.0f}–{euros(g.typical_high)})")

    cities = "".join(f"<li>{escape(c)} : {euros(q.price)} ({q.origin} → {q.dest})</li>" for c, q in a["by_city"].items())
    comparison = "".join(f"<li>{escape(t)}</li>" for t in a["city_comparison"])
    stays = " · ".join(f"{days} j : {euros(q.price)}" for days, q in a["by_stay"].items())
    dates = " · ".join(f"{fr_date(d)} {euros(q.price)}" for d, q in a["by_depart_date"].items())

    chart = _bars(a["series"][-30:][::-2][::-1], "Évolution du meilleur prix (nos relevés, un jour sur deux)")
    if not chart and a["google"] and a["google"].history:
        g = a["google"]
        chart = _bars(g.history[-30:][::-2][::-1], f"Évolution selon Google ({g.origin} → {g.dest}, {fr_date(g.depart_date)})")

    return f"""
<div style="{CARD}">
  <h2 style="font-size:18px;margin:0 0 6px">{escape(title)}</h2>
  <p style="{MUTED};margin:0 0 6px">{escape(criteria(search))}</p>
  {alerts}
  <p style="margin:6px 0"><span style="background:{color};color:#fff;padding:4px 10px;border-radius:4px;font-weight:bold">{advice['decision']}</span>
  <span style="{MUTED}"> confiance {escape(advice['confidence'])}</span></p>
  <p style="margin:6px 0"><strong>Fenêtre d'achat estimée :</strong> {escape(advice['window'])}</p>
  <ul style="margin:6px 0;padding-left:20px">{reasons}</ul>
  {f'<p style="{MUTED};margin:6px 0">Limites :</p><ul style="{MUTED};margin:0;padding-left:20px">{limits}</ul>' if limits else ''}
</div>
<div style="{CARD}">
  <h3 style="font-size:15px;margin:0 0 6px">Meilleur prix du jour : {euros(best.price)} / pers.</h3>
  <p style="margin:4px 0">{escape(changes)}</p>
  <p style="{MUTED};margin:4px 0">{escape(' · '.join(stats))}</p>
  {chart}
</div>
<div style="{CARD}">
  <h3 style="font-size:15px;margin:0">Top 5 des offres</h3>
  {''.join(_offer(q) for q in a['top'])}
</div>
<div style="{CARD}">
  <h3 style="font-size:15px;margin:0 0 6px">Villes de départ</h3>
  <ul style="margin:0;padding-left:20px">{cities}{comparison}</ul>
  <h3 style="font-size:15px;margin:12px 0 6px">Par durée de séjour</h3>
  <p style="margin:0">{escape(stays)}</p>
  <h3 style="font-size:15px;margin:12px 0 6px">Par date de départ</h3>
  <p style="{MUTED};margin:0">{escape(dates)}</p>
</div>"""


def build_email(run_date: str, sections: list[str], statuses: list[tuple[str, bool, str]]) -> str:
    status = "".join(
        f"<li>{'✅' if ok else '❌'} {escape(name)} : {escape(note)}</li>" for name, ok, note in statuses)
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Suivi des prix des vols</title></head>
<body style="margin:0;background:#f3f5f8;font-family:Arial,Helvetica,sans-serif;color:#1d2330;line-height:1.4">
<div style="max-width:640px;margin:0 auto;padding:16px">
<h1 style="font-size:20px;margin:0 0 12px">Suivi des prix des vols, {fr_date(run_date)} {run_date[:4]}</h1>
{''.join(sections)}
<div style="{CARD}"><h3 style="font-size:15px;margin:0 0 6px">État des sources</h3><ul style="margin:0;padding-left:20px;font-size:14px">{status}</ul>
<p style="{MUTED}">Prix par personne, issus de caches et de pages publiques : à confirmer sur le site avant de réserver.</p></div>
</div></body></html>"""


def send_email(html: str, subject: str, user: str, password: str, recipients: list[str]):
    # Google affiche le mot de passe d'application en 4 groupes : espaces et retours à la ligne retirés.
    user, password = user.strip(), "".join(password.split())
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, ", ".join(recipients)
    msg.set_content("Ce récapitulatif est au format HTML.")
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        try:
            smtp.login(user, password)
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPServerDisconnected) as e:
            raise SystemExit(
                f"Gmail a refusé la connexion ({type(e).__name__}) : vérifie que GMAIL_USER est l'adresse du compte "
                "qui a créé le mot de passe d'application, et que GMAIL_APP_PASSWORD contient ses 16 lettres."
            ) from e
        smtp.send_message(msg)
