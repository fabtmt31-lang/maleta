"""Import CSV (v1.21) : contenu ecrit dans un tableur, sans l'appli."""

import io
import os
import zipfile

from test_content_transfer import APP_DIR, count, make_client

ROOT = os.path.dirname(APP_DIR)
USER_EXPORT = os.path.join(ROOT, "tests", "fixtures", "maleta-contenu-demo.zip")


def import_files(client, files, **form):
    data = {"bundle": [(io.BytesIO(raw), name) for name, raw in files], "mode": "merge", "tags": "1"}
    for name in ("objects", "vertadier_words", "duel_questions", "quiz_questions", "villages", "media_items"):
        data[f"section_{name}"] = "1"
    data.update(form)
    return client.post("/admin/transfer/import", data=data, content_type="multipart/form-data")


def test_csv_written_by_hand(tmp_path):
    app, client = make_client(tmp_path / "pc", demo=False)
    quiz = (
        "question;reponse_a;reponse_b;reponse_c;bonne_reponse;explication;source;actif\n"
        "Q1 ?;a;b;c;B;;IEO;\n"
        "Q2 ?;a;b;c;réponse C;;;oui\n"
        "Q3 ?;a;;c;A;;;\n"          # reponse_b manquante -> ignoree
        "Q4 ?;a;b;c;D;;;\n"         # bonne reponse invalide -> ignoree
    ).encode("utf-8")
    # Excel sous Windows : virgules, cp1252, en-tetes accentues ; type par les colonnes.
    ven = "Mot français,Vient de l'occitan,Explication\nCassoulet,oui,x\nOrdinateur,non,\n".encode("cp1252")
    villages = "nom_francais;nom_occitan\nAlbi;Albi\nBéziers;Besièrs\n".encode("utf-8")
    resp = import_files(client, [("quiz.csv", quiz), ("liste.csv", ven), ("vilatges.csv", villages)])
    page = resp.get_data(as_text=True)
    assert count(app, "quiz_questions") == 2
    assert count(app, "vertadier_words") == 2
    assert count(app, "villages") == 2
    assert "ligne 4 ignorée" in page and "ligne 5 ignorée" in page

    from db.database import get_db
    with app.app_context():
        rows = get_db().execute("SELECT word_fr, is_occitan FROM vertadier_words ORDER BY id").fetchall()
        assert [tuple(r) for r in rows] == [("Cassoulet", 1), ("Ordinateur", 0)]
        assert get_db().execute("SELECT correct_choice FROM quiz_questions ORDER BY id").fetchall()[1][0] == "c"


def test_unknown_csv_type_is_reported(tmp_path):
    app, client = make_client(tmp_path / "pc", demo=False)
    resp = import_files(client, [("liste.csv", b"colonne1;colonne2\nx;y\n")])
    assert "type de contenu non reconnu" in resp.get_data(as_text=True)
    # Type choisi a la main : colonnes obligatoires verifiees.
    resp = import_files(client, [("liste.csv", b"colonne1;colonne2\nx;y\n")], csv_type="quiz_questions")
    assert "colonne(s) obligatoire(s) absente(s)" in resp.get_data(as_text=True)


def test_exported_csv_reimports(tmp_path):
    _, demo = make_client(tmp_path / "demo", demo=True)
    demo.post("/admin/duel/new", data={"question_fr": "D ?", "choice_a": "a", "choice_b": "b", "correct_choice": "b"})
    demo.post("/admin/vertadier/new", data={"word_fr": "Mot", "is_occitan": "on"})
    archive = zipfile.ZipFile(io.BytesIO(demo.get("/admin/transfer/export").data))
    assert archive.read("tableur/duel_questions.csv").decode("utf-8-sig").startswith("question;reponse_a")

    app, client = make_client(tmp_path / "pc", demo=False)
    import_files(client, [(name.split("/")[-1], archive.read(name)) for name in archive.namelist()
                          if name.startswith("tableur/")])
    assert count(app, "duel_questions") == 1
    assert count(app, "vertadier_words") == 1


def test_user_export_tableur_old_headers(tmp_path):
    """CSV d'un export v1.2 (en-tetes techniques) : toujours importables."""
    archive = zipfile.ZipFile(USER_EXPORT)
    app, client = make_client(tmp_path / "pc", demo=False)
    import_files(client, [(name.split("/")[-1], archive.read(name)) for name in archive.namelist()
                          if name.startswith("tableur/")])
    data = __import__("json").loads(archive.read("maleta-contenu.json"))
    assert count(app, "quiz_questions") == len(data["quiz_questions"])
    assert count(app, "objects") == len(data["objects"])  # sans images : a ajouter dans l'admin


def test_templates_in_repo_are_up_to_date(tmp_path):
    make_client(tmp_path / "pc", demo=False)
    from managers import content_transfer

    for name, content in content_transfer.csv_template_files().items():
        with open(os.path.join(ROOT, "docs", "modeles-csv", name), encoding="utf-8", newline="") as f:
            assert f.read() == content, f"docs/modeles-csv/{name} : relancer importer_contenu.py --modeles"
