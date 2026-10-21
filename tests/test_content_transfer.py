"""Export du contenu depuis la demo puis reimport dans une installation
standard (v1.2). Chaque installation a sa propre base temporaire."""

import io
import json
import os
import sys
import zipfile

import pytest

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "maleta-occitana")
APP_MODULES = ("config", "app", "managers", "blueprints", "db")


def make_client(data_dir, demo):
    """Nouvelle instance de l'appli (config relue) sur data_dir, admin connecte."""
    os.environ["MALETA_DATA_DIR"] = str(data_dir)
    os.environ["MALETA_DEMO"] = "1" if demo else "0"
    os.environ["MALETA_HARDWARE"] = "dev"
    for name in list(sys.modules):
        if name.split(".")[0] in APP_MODULES:
            del sys.modules[name]
    if APP_DIR not in sys.path:
        sys.path.insert(0, APP_DIR)
    import app as app_module

    app, _ = app_module.create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    with client.session_transaction() as session:
        session["admin_logged_in"] = True
    return app, client


def count(app, table):
    from db.database import get_db

    with app.app_context():
        return get_db().execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


ALL_SECTIONS = {f"section_{name}": "1" for name in (
    "objects", "vertadier_words", "duel_questions", "quiz_questions", "villages", "media_items")}


@pytest.fixture
def export_zip(tmp_path):
    app, client = make_client(tmp_path / "demo", demo=True)
    client.post("/admin/objects/new", data={
        "name_oc": "Fromatge", "name_fr": "Fromage", "category": "",
        "image": (io.BytesIO(b"\x89PNG-test"), "fromatge.png"),
    }, content_type="multipart/form-data")
    client.post("/admin/quiz/new", data={
        "question_fr": "Question ?", "choice_a": "a", "choice_b": "b", "choice_c": "c",
        "correct_choice": "b", "source": "test"})
    client.post("/admin/villages/new", data={"name_fr": "Ville", "name_oc": "Vila"})

    # La demo donne un tag simule a chaque objet, et le kiosque peut le "poser".
    assert client.get("/demo/objects").get_json()["objects"][0]["name_oc"] == "Fromatge"
    assert client.post("/demo/place/1").get_json() == {"ok": True}

    resp = client.get("/admin/transfer/export?media=1&settings=1")
    assert resp.status_code == 200
    return resp.data


def test_export_contents(export_zip):
    archive = zipfile.ZipFile(io.BytesIO(export_zip))
    names = archive.namelist()
    assert "maleta-contenu.json" in names
    assert "tableur/quiz_questions.csv" in names
    assert any(n.startswith("media/objects/images/") for n in names)
    data = json.loads(archive.read("maleta-contenu.json"))
    assert data["source"] == "demo"
    assert data["objects"][0]["tags"] == []  # tags simules jamais exportes
    assert data["quiz_questions"][0]["correct_choice"] == "b"


def test_import_into_standard(tmp_path, export_zip):
    app, client = make_client(tmp_path / "pc", demo=False)
    assert client.get("/demo/objects").status_code == 404  # demo seulement

    def do_import(mode="merge"):
        return client.post("/admin/transfer/import", data={
            "bundle": (io.BytesIO(export_zip), "export.zip"), "mode": mode, "tags": "1", **ALL_SECTIONS,
        }, content_type="multipart/form-data")

    assert do_import().status_code == 200
    assert count(app, "objects") == 1
    assert count(app, "quiz_questions") == 1
    assert count(app, "villages") == 1
    assert count(app, "tags") == 0
    images = os.listdir(tmp_path / "pc" / "media" / "objects" / "images")
    assert len(images) == 1

    do_import()  # doublons ignores
    assert count(app, "objects") == 1

    do_import("replace")
    assert count(app, "objects") == 1
    assert len(os.listdir(tmp_path / "pc" / "media" / "objects" / "images")) == 1


def test_rejects_unknown_file(tmp_path):
    _, client = make_client(tmp_path / "pc", demo=False)
    resp = client.post("/admin/transfer/import", data={
        "bundle": (io.BytesIO(b"pas un zip"), "x.zip"), **ALL_SECTIONS,
    }, content_type="multipart/form-data", follow_redirects=True)
    assert "illisible" in resp.get_data(as_text=True)
