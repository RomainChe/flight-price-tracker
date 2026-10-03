"""Point d'entrée : python -m tracker [--dry-run] [--config config.yaml]"""
import argparse
import os
import sys
from datetime import date
from pathlib import Path

from . import analysis, expert, report, storage
from .config import load_config
from .models import Context, keep_cheapest
from .sources import SOURCES, travelpayouts

ROOT = Path(__file__).resolve().parents[1]


def run(config_path, dry_run: bool, env=os.environ, today: date | None = None, sources=SOURCES,
        data_dir: Path = ROOT / "data", out_file: Path = ROOT / "out" / "email.html", fetch_baseline=travelpayouts.baseline,
        keep_history: bool = True):
    """keep_history=False : recherche ponctuelle, l'historique n'est ni lu ni modifié."""
    cfg = load_config(config_path)
    store = keep_history and not dry_run
    run_date = (today or date.today()).isoformat()
    quotes_path, baseline_path = data_dir / "prices.csv", data_dir / "baseline.csv"
    history = storage.load_quotes(quotes_path) if keep_history else []
    baseline = storage.load_baseline(baseline_path) if keep_history else []
    token = env.get("TRAVELPAYOUTS_TOKEN", "")
    budget = max(1, cfg.google_max_requests // len(cfg.searches))
    several = len(cfg.searches) > 1

    sections, statuses, subject = [], [], cfg.email_subject
    for search in cfg.searches:
        mine = [q for q in history if q.search == search.name and q.run_date < run_date]
        last_day = max((q.run_date for q in mine), default=None)
        ctx = Context(run_date, previous=[q for q in mine if q.run_date == last_day], google_budget=budget,
                      google_pause=cfg.google_pause_seconds, token=token)
        for source in sources:
            label = f"{source.NAME} ({search.name})" if several else source.NAME
            try:
                quotes, note = source.collect(search, ctx)
                statuses.append((label, True, f"{len(quotes)} prix · {note}"))
            except Exception as e:  # une source en panne n'arrête pas les autres
                quotes = []
                statuses.append((label, False, str(e)))
            ctx.quotes_so_far += quotes
        today_quotes = keep_cheapest(ctx.quotes_so_far)

        search_baseline = [r for r in baseline if r["search"] == search.name]
        if not search_baseline and token:
            try:
                search_baseline = fetch_baseline(search, token)
                statuses.append((f"Historique de l'an dernier ({search.name})", True, f"{len(search_baseline)} prix récupérés"))
                if store:
                    storage.append_baseline(baseline_path, search_baseline)
            except Exception as e:
                statuses.append((f"Historique de l'an dernier ({search.name})", False, str(e)))

        if store:
            storage.append_quotes(quotes_path, today_quotes)
        a = analysis.analyze(search, today_quotes, mine + today_quotes, run_date)
        advice = expert.recommend(search, a, search_baseline, date.fromisoformat(run_date))
        sections.append(report.section(search, a, advice))
        if a["best"] and search is cfg.searches[0]:
            subject += f" : {a['best'].price:.0f} € · {advice['decision']}"
            if a["alerts"]:
                subject = "🔔 " + subject

    html = report.build_email(run_date, sections, statuses)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(html, encoding="utf-8")
    if dry_run:
        print(f"Dry-run : e-mail généré dans {out_file} (non envoyé, historique non modifié).")
        return html

    user, password, to = env.get("GMAIL_USER"), env.get("GMAIL_APP_PASSWORD"), env.get("MAIL_TO", "")
    recipients = [r.strip() for r in to.split(",") if r.strip()]
    if not (user and password and recipients):
        sys.exit("Secrets GMAIL_USER, GMAIL_APP_PASSWORD et MAIL_TO requis pour envoyer l'e-mail (ou --dry-run).")
    report.send_email(html, subject, user, password, recipients)
    print(f"E-mail envoyé à {len(recipients)} destinataire(s).")
    return html


def main():
    parser = argparse.ArgumentParser(description="Suivi quotidien des prix de billets d'avion.")
    parser.add_argument("--config", default=ROOT / "config.yaml", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="génère out/email.html sans l'envoyer ni toucher à l'historique")
    args = parser.parse_args()
    try:
        run(args.config, args.dry_run)
    except ValueError as e:  # erreur de configuration : message clair, sans trace
        sys.exit(f"Configuration invalide : {e}")


if __name__ == "__main__":
    main()
