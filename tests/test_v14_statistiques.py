"""Statistiques d'utilisation (v1.4) : enregistrement par le moteur de la borne
et pages Admin > Estadísticas."""

import datetime
import io
import os
import sqlite3
import sys

from test_content_transfer import make_client


def _setup(tmp_path, demo=False):
    app, client = make_client(tmp_path / "pc", demo=demo)
    controller = app.extensions["game_controller"]
    # Pas de minuteurs reels pendant les tests : on fait avancer le jeu a la main.
    controller._start_epoch_timer = lambda *a, **k: None
    controller._reset_idle_timer = lambda *a, **k: None
    return app, client, controller, sys.modules["managers.stats_manager"]


def _add_quiz(client, n=3):
    for i in range(n):
        client.post("/admin/quiz/new", data={
            "question_fr": f"Question {i} ?", "choice_a": "a", "choice_b": "b", "choice_c": "c",
            "correct_choice": "a", "source": "test"})


def _rows(tmp_path, table):
    conn = sqlite3.connect(tmp_path / "pc" / "maleta.db")
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
    finally:
        conn.close()


def _play_quiz(controller, answers):
    controller.start_quiz()
    for choice in answers:
        controller._handle_quiz_answer(choice)
        controller._advance_quiz()


def test_quiz_finished_and_abandoned(tmp_path):
    app, client, controller, stats = _setup(tmp_path)
    _add_quiz(client)
    _play_quiz(controller, ["a", "b", "a"])            # finie : 2 / 3
    assert controller.state == "quiz_fin"
    controller.start_quiz()                              # rejouer = nouvelle partie
    controller._handle_quiz_answer("a")
    controller.go_to_menu()                              # quittee avant la fin
    controller.go_to_veille()

    sessions = _rows(tmp_path, "stats_sessions")
    assert [(s["activity"], s["outcome"], s["score"], s["total"]) for s in sessions] == [
        ("quiz_calandreta", "finie", 2, 3), ("quiz_calandreta", "abandon", None, None)]
    assert all(s["ended_at"] for s in sessions)
    answers = _rows(tmp_path, "stats_answers")
    assert [a["correct"] for a in answers] == [1, 0, 1, 1]
    assert answers[0]["label"].startswith("Question")
    visits = _rows(tmp_path, "stats_visits")
    assert len(visits) == 1 and visits[0]["ended_at"]


def test_descoberta_and_idle_time_not_counted(tmp_path):
    app, client, controller, stats = _setup(tmp_path)
    client.post("/admin/objects/new", data={"name_oc": "Fromatge", "name_fr": "Fromage", "category": "",
                                            "image": (io.BytesIO(b"\x89PNG"), "f.png")}, content_type="multipart/form-data")
    with app.app_context():
        from db.database import get_db
        db = get_db()
        db.execute("INSERT INTO tags (uid, object_id) VALUES ('UID1', 1)")
        db.commit()
    controller.on_tag_scanned("UID1")
    controller.on_tag_scanned("UID1")                    # reposer l'objet = nouvelle consultation
    # Mise en veille 5 minutes plus tard (inactivite) : seul le temps de
    # lecture compte, pas les 5 minutes.
    real_now = stats.now
    stats.now = lambda: real_now() + datetime.timedelta(minutes=5)
    try:
        controller.go_to_veille()
    finally:
        stats.now = real_now
    sessions = _rows(tmp_path, "stats_sessions")
    assert [(s["activity"], s["detail"], s["outcome"]) for s in sessions] == [
        ("descoberta", "Fromatge", None), ("descoberta", "Fromatge", None)]
    last = sessions[-1]
    seconds = (datetime.datetime.fromisoformat(last["ended_at"]) - datetime.datetime.fromisoformat(last["started_at"])).total_seconds()
    assert 0 < seconds <= 5 * 60 - 20 + 2


def test_recover_after_power_cut(tmp_path):
    app, client, controller, stats = _setup(tmp_path)
    _add_quiz(client)
    controller.start_quiz()                              # coupure de courant ici
    stats.StatsRecorder(app)                             # redemarrage
    session = _rows(tmp_path, "stats_sessions")[0]
    assert session["outcome"] == "abandon" and session["ended_at"] == session["last_seen"]
    assert _rows(tmp_path, "stats_visits")[0]["ended_at"]


def test_retro_games_and_aprene(tmp_path):
    app, client, controller, stats = _setup(tmp_path)
    from werkzeug.datastructures import FileStorage
    rom_manager = sys.modules["managers.rom_manager"]
    with app.app_context():
        rom_id = rom_manager.add_rom_upload(FileStorage(io.BytesIO(b"NES\x1a" + bytes(40000)), filename="Super_Mario_Bros._3.nes"))
    sys.modules["managers.hidden_games"].start_jocs(app)
    client.get(f"/jocs/joc/{rom_id}")
    client.get(f"/jocs/joc/{rom_id}")                    # rechargement : meme partie
    client.get("/jocs/")
    controller.stop_external()
    sessions = _rows(tmp_path, "stats_sessions")
    assert [(s["activity"], s["detail"], s["outcome"]) for s in sessions] == [("jocs", "Super Mario Bros. 3 (NES)", None)]
    assert sessions[0]["ended_at"]


def test_pages_and_csv(tmp_path):
    app, client, controller, stats = _setup(tmp_path)
    page = client.get("/admin/estadisticas").get_data(as_text=True)
    assert "Estadísticas" in page and "Pas encore" in page
    _add_quiz(client)
    _play_quiz(controller, ["a", "a", "a"])
    controller.go_to_veille()

    page = client.get("/admin/estadisticas?periode=jorn").get_data(as_text=True)
    assert "Quiz Calandreta" in page and "100 % de bonnes réponses" in page and "<svg" in page
    assert "Heure par heure" in page and "jour de la semaine et par heure" in page
    today = datetime.date.today().isoformat()
    page = client.get(f"/admin/estadisticas/jorn?data={today}").get_data(as_text=True)
    assert "Frise de la journée" in page and "finie" in page and "3 / 3" in page
    page = client.get("/admin/estadisticas/joc/quiz_calandreta?periode=30").get_data(as_text=True)
    assert "Questions les plus ratées" in page and "Répartition" in page
    assert client.get("/admin/estadisticas/joc/inconnu").status_code == 404
    dash = client.get("/admin/").get_data(as_text=True)
    assert "Aujourd'hui sur la borne" in dash or "Aujourd&#39;hui sur la borne" in dash

    csv_text = client.get("/admin/estadisticas/export.csv?periode=tot").get_data(as_text=True)
    lines = csv_text.lstrip("﻿").splitlines()
    assert lines[0].startswith("date;debut;fin;duree_secondes;jeu") and "Quiz Calandreta" in lines[1] and ";finie;3;3" in lines[1]

    # Effacement : sauvegarde CSV puis tables vides
    page = client.post("/admin/estadisticas/esfacar", follow_redirects=True).get_data(as_text=True)
    assert "maleta-statistiques-" in page
    assert _rows(tmp_path, "stats_sessions") == [] and _rows(tmp_path, "stats_answers") == []
    assert any(n.startswith("maleta-statistiques-") for n in os.listdir(tmp_path / "pc" / "sauvegardes"))


def test_purge_keeps_daily_totals(tmp_path):
    app, client, controller, stats = _setup(tmp_path)
    conn = sqlite3.connect(tmp_path / "pc" / "maleta.db")
    conn.execute("INSERT INTO stats_sessions (activity, started_at, ended_at, last_seen, outcome) VALUES "
                 "('quiz_calandreta', '2020-01-06 10:00:00', '2020-01-06 10:05:00', '2020-01-06 10:05:00', 'finie')")
    conn.execute("INSERT INTO stats_visits (started_at, ended_at, last_seen) VALUES "
                 "('2020-01-06 09:58:00', '2020-01-06 10:06:00', '2020-01-06 10:06:00')")
    conn.commit()
    conn.close()
    stats.purge()
    assert _rows(tmp_path, "stats_sessions") == []
    daily = {r["activity"]: r for r in _rows(tmp_path, "stats_daily")}
    assert daily["quiz_calandreta"]["finished"] == 1 and daily["quiz_calandreta"]["seconds"] == 300
    assert daily["_visites"]["sessions"] == 1
    start, end, _ = stats.period("tot")
    kpis = stats.overview(start, end)["kpis"]
    assert kpis["games"] == 1 and kpis["visits"] == 1 and kpis["finished"] == 1


def test_split_by_hour():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "maleta-occitana"))
    from managers import stats_manager as sm
    row = {"started_at": "2026-11-24 09:50:00", "ended_at": "2026-11-24 10:20:00"}
    assert [(h.hour, s) for h, s in sm._split_by_hour(row)] == [(9, 600), (10, 1200)]
    assert sm.format_duration(59) == "59 s" and sm.format_duration(600) == "10 min" and sm.format_duration(4000) == "1 h 06"


# --- v1.41 : le Duèl utilise les questions du Quiz ----------------------------------

def test_duel_question_from_quiz():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "maleta-occitana"))
    import random
    from managers.game_controller import duel_question_from_quiz
    question = {"id": 7, "question_fr": "Q ?", "choice_a": "bon", "choice_b": "faux 1", "choice_c": "faux 2",
                "correct_choice": "a", "explanation": "car"}
    rng = random.Random(1)
    seen_wrong, seen_position = set(), set()
    for _ in range(60):
        duel = duel_question_from_quiz(question, rng)
        pair = [duel["choice_a"], duel["choice_b"]]
        assert duel[f"choice_{duel['correct_choice']}"] == "bon" and "bon" in pair and len(set(pair)) == 2
        seen_wrong.add(next(c for c in pair if c != "bon"))
        seen_position.add(duel["correct_choice"])
        assert duel["id"] == 7 and duel["explanation"] == "car"
    assert seen_wrong == {"faux 1", "faux 2"} and seen_position == {"a", "b"}


def test_duel_plays_quiz_questions_and_ignores_old_duel_content(tmp_path):
    app, client, controller, stats = _setup(tmp_path)
    controller.start_duel()
    assert controller.state == "menu" and "Quiz Calandreta" in controller.menu_notice  # pas de question
    _add_quiz(client)
    controller.start_duel()
    assert controller.state == "duel" and len(controller.duel["questions"]) == 3
    assert all(q["question_fr"].startswith("Question") for q in controller.duel["questions"])
    controller.go_to_menu()
    # Anciennes pages du Duèl -> liste du Quiz ; plus d'entree Duèl dans le menu admin
    page = client.get("/admin/duel/new", follow_redirects=True).get_data(as_text=True)
    assert "Le Duèl Occitan utilise désormais les questions du Quiz Calandreta" in page
    assert "Quiz &amp; Duèl" in page and 'href="/admin/duel"' not in page

    # Import : un ancien export ou un duel.csv ne provoque pas d'erreur, juste un avertissement.
    import json, zipfile
    old = {"format": "maleta-occitana-contenu", "format_version": 1, "source": "demo",
           "duel_questions": [{"question_fr": "D ?", "choice_a": "a", "choice_b": "b", "correct_choice": "a"}],
           "quiz_questions": [{"question_fr": "Nouvelle ?", "choice_a": "a", "choice_b": "b", "choice_c": "c",
                               "correct_choice": "c"}]}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("maleta-contenu.json", json.dumps(old))
    page = client.post("/admin/transfer/import", data={
        "bundle": [(io.BytesIO(buf.getvalue()), "ancien.zip"),
                   (io.BytesIO("question;reponse_a;reponse_b;bonne_reponse\nD ?;a;b;A\n".encode()), "duel.csv")],
        "mode": "merge", "section_quiz_questions": "1", "section_duel_questions": "1"},
        content_type="multipart/form-data", follow_redirects=True).get_data(as_text=True)
    assert "questions ignorées" in page and "Erreur" not in page
    with app.app_context():
        assert len(sys.modules["managers.quiz_manager"].list_questions()) == 4
