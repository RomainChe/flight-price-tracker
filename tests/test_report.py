import smtplib
from datetime import date

import pytest

from tracker import report


class FakeSMTP:
    def __init__(self, *_, fail=None, **__):
        self.fail, self.logins, self.sent = fail, [], []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def login(self, user, password):
        if self.fail:
            raise self.fail
        self.logins.append((user, password))

    def send_message(self, msg):
        self.sent.append(msg)


def test_send_email_cleans_app_password(monkeypatch):
    smtp = FakeSMTP()
    monkeypatch.setattr(smtplib, "SMTP_SSL", lambda *a, **k: smtp)
    report.send_email("<p>ok</p>", "Sujet", " moi@gmail.com\n", "abcd efgh ijkl mnop\n", ["a@x.fr", "b@x.fr"])
    assert smtp.logins == [("moi@gmail.com", "abcdefghijklmnop")]
    assert smtp.sent[0]["To"] == "a@x.fr, b@x.fr"


def test_send_email_explains_auth_failure(monkeypatch):
    smtp = FakeSMTP(fail=smtplib.SMTPServerDisconnected("Connection unexpectedly closed"))
    monkeypatch.setattr(smtplib, "SMTP_SSL", lambda *a, **k: smtp)
    with pytest.raises(SystemExit, match="16 lettres"):
        report.send_email("<p>ok</p>", "Sujet", "moi@gmail.com", "x", ["a@x.fr"])


def test_criteria_summarises_search(make_search):
    s = make_search(depart_to="2027-05-01", return_date="2027-05-22", stay_days=[], max_stops=2,
                    layover_hours=[3, 6], no_airport_change=True, checked_bag=True)
    assert report.criteria(s) == ("départ le 1er mai, retour le 22 mai · 1 passager(s), economy · 2 escale(s) max · "
                                  "escales de 3 à 6 h · sans changement d'aéroport · bagage en soute inclus (Google)")
    assert "séjour de 10 jours" in report.criteria(make_search())
    assert report.fr_date(date(2027, 5, 5).isoformat()) == "5 mai"
