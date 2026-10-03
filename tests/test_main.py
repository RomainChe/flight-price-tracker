from datetime import date
from types import SimpleNamespace

import pytest
from conftest import quote

from tracker.__main__ import run
from tracker.storage import load_quotes

CONFIG = """
searches:
  - name: Japon
    origins: [Barcelone, Marseille]
    destination: Japon
    depart_from: 2027-05-01
    depart_to: 2027-05-03
    stay_days: [10]
    alert_below: 700
"""


def source(name, prices=None, error=None):
    def collect(search, ctx):
        if error:
            raise RuntimeError(error)
        return [quote(p, ctx.run_date, origin=o, source=name, link="https://example.test/<x>")
                for p, o in zip(prices, ["BCN", "MRS"])], "ok"
    return SimpleNamespace(NAME=name, collect=collect)


@pytest.fixture
def setup(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(CONFIG, encoding="utf-8")
    sources = [source("Panne", error="HTTP 503"), source("Fake", [680, 900])]
    kwargs = dict(sources=sources, data_dir=tmp_path / "data", out_file=tmp_path / "out" / "email.html",
                  fetch_baseline=lambda s, t: [])
    return cfg, tmp_path, kwargs


def test_dry_run_writes_email_without_touching_history(setup):
    cfg, tmp, kw = setup
    html = run(cfg, dry_run=True, env={}, today=date(2027, 1, 10), **kw)
    assert (tmp / "out" / "email.html").read_text(encoding="utf-8") == html
    assert not (tmp / "data").exists()
    assert "680 €" in html and "Alerte" in html
    assert "❌ Panne : HTTP 503" in html and "✅ Fake" in html
    assert "&lt;x&gt;" in html  # données externes échappées


def test_real_run_appends_history_and_requires_mail_secrets(setup):
    cfg, tmp, kw = setup
    with pytest.raises(SystemExit, match="GMAIL_USER"):
        run(cfg, dry_run=False, env={}, today=date(2027, 1, 10), **kw)
    saved = load_quotes(tmp / "data" / "prices.csv")
    assert sorted(q.price for q in saved) == [680, 900]

    with pytest.raises(SystemExit):
        run(cfg, dry_run=False, env={}, today=date(2027, 1, 11), **kw)
    assert len(load_quotes(tmp / "data" / "prices.csv")) == 4


def test_invalid_config_raises_value_error(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(CONFIG.replace("Barcelone", "Madrid"), encoding="utf-8")
    with pytest.raises(ValueError, match="Madrid"):
        run(cfg, dry_run=True, env={}, data_dir=tmp_path, out_file=tmp_path / "e.html")


def test_one_off_search_neither_reads_nor_writes_history(setup, monkeypatch):
    cfg, tmp, kw = setup
    sent = []
    monkeypatch.setattr("tracker.report.send_email", lambda html, subject, *a: sent.append(subject))
    env = {"GMAIL_USER": "u", "GMAIL_APP_PASSWORD": "p", "MAIL_TO": "a@x.fr"}
    run(cfg, dry_run=False, env=env, today=date(2027, 1, 10), keep_history=False, **kw)
    assert not (tmp / "data").exists()
    assert sent and "680" in sent[0]
