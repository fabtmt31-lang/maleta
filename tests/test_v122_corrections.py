"""Corrections v1.22 : import "Remplacer", inactivite Memòria, lecteur NFC
branche apres le demarrage, cle de session par installation."""

import importlib
import os
import sys
import threading
import time

from test_content_transfer import count, make_client
from test_csv_import import USER_EXPORT, import_files

QUIZ_1 = "question;reponse_a;reponse_b;reponse_c;bonne_reponse\nQ1 ?;a;b;c;A\n".encode()
QUIZ_2 = "question;reponse_a;reponse_b;reponse_c;bonne_reponse\nQ2 ?;a;b;c;B\n".encode()


def with_user_export(tmp_path):
    app, client = make_client(tmp_path / "pc", demo=False)
    with open(USER_EXPORT, "rb") as f:
        import_files(client, [("export.zip", f.read())])
    return app, client


# --- 1 et 2 : mode "Remplacer" ----------------------------------------------

def test_replace_with_csv_only_touches_its_section(tmp_path):
    app, client = with_user_export(tmp_path)
    before = {t: count(app, t) for t in ("objects", "vertadier_words", "duel_questions", "villages", "media_items")}

    page = import_files(client, [("quiz-a.csv", QUIZ_1), ("quiz-b.csv", QUIZ_2)], mode="replace").get_data(as_text=True)

    assert count(app, "quiz_questions") == 2  # les deux fichiers s'additionnent
    assert {t: count(app, t) for t in before} == before  # le reste est intact
    backups = os.listdir(tmp_path / "pc" / "sauvegardes")
    assert len(backups) == 1 and backups[0].startswith("maleta-sauvegarde-")
    assert "Supprimés" in page and "maleta-sauvegarde-" in page


def test_replace_with_unreadable_file_erases_nothing(tmp_path):
    app, client = with_user_export(tmp_path)
    quiz_before = count(app, "quiz_questions")
    import_files(client, [("quiz.csv", QUIZ_1), ("autre.csv", b"x;y\n1;2\n")], mode="replace")
    assert count(app, "quiz_questions") == quiz_before
    assert not os.path.exists(tmp_path / "pc" / "sauvegardes")


def test_backups_are_limited(tmp_path):
    app, _ = make_client(tmp_path / "pc", demo=False)
    from managers import content_transfer

    backup_dir = tmp_path / "pc" / "sauvegardes"
    backup_dir.mkdir()
    for i in range(12):
        (backup_dir / f"maleta-sauvegarde-20260101-0000{i:02d}.zip").write_bytes(b"")
    with app.app_context():
        content_transfer.create_backup()
    assert len(os.listdir(backup_dir)) == content_transfer.BACKUP_KEEP


# --- 4 : inactivite Memòria ---------------------------------------------------

def _memoria_ready(tmp_path):
    app, client = make_client(tmp_path / "pc", demo=False)
    for i in range(6):
        client.post("/admin/objects/new", data={"name_oc": f"oc{i}", "name_fr": f"fr{i}", "category": ""})
    config = sys.modules["config"]
    config.ACTION_LOCKOUT_SECONDS = 0
    return app, config, app.extensions["game_controller"], sys.modules["managers.game_controller"]


def test_memoria_returns_to_menu_when_abandoned(tmp_path):
    _, config, controller, gc = _memoria_ready(tmp_path)
    config.MEMORIA_CHOICE_IDLE_SECONDS = 0.3
    config.MEMORIA_IDLE_SECONDS = 0.3

    controller._open_memoria_choice("memoria")
    assert controller.state == gc.STATE_MEMORIA_CHOICE
    time.sleep(0.6)
    assert controller.state == gc.STATE_MENU

    controller._open_memoria_choice("memoria")
    controller.on_action("select")
    assert controller.state == gc.STATE_MEMORIA
    time.sleep(0.6)
    assert controller.state == gc.STATE_MENU


def test_memoria_stays_while_playing(tmp_path):
    _, config, controller, gc = _memoria_ready(tmp_path)
    config.MEMORIA_IDLE_SECONDS = 0.5
    controller._open_memoria_choice("memoria")
    controller.on_action("select")
    for _ in range(4):  # une action toutes les 0,25 s pendant 1 s
        time.sleep(0.25)
        controller.on_action("right")
    assert controller.state == gc.STATE_MEMORIA
    controller.go_to_menu()


# --- 5 : lecteur NFC branche apres le demarrage -------------------------------

def test_nfc_reader_plugged_in_later(tmp_path):
    make_client(tmp_path / "pc", demo=False)
    from managers.tag_reader import OmnikeyTagReader

    plugged = []
    monitors = []

    class FakeMonitor:
        def __init__(self):
            monitors.append(self)

        def addObserver(self, observer):
            self.observer = observer

        def deleteObserver(self, observer):
            pass

    reader = OmnikeyTagReader()
    reader.WATCH_SECONDS = 0.05
    reader._pcsc = (FakeMonitor, object, lambda data: "", lambda: list(plugged))
    threading.Thread(target=reader._watch, daemon=True).start()

    time.sleep(0.2)
    assert reader.status()["connected"] is False and not monitors
    plugged.append("HID Global OMNIKEY 5422")
    time.sleep(0.2)
    assert reader.status()["connected"] is True
    assert "OMNIKEY" in reader.status()["message"]
    assert len(monitors) == 1  # surveillance des tags activee une seule fois
    reader.stop()


def test_dashboard_shows_reader_state(tmp_path):
    _, client = make_client(tmp_path / "pc", demo=False)
    assert "Lector NFC" in client.get("/admin/").get_data(as_text=True)


# --- 7 : cle de session propre a chaque installation --------------------------

def _load_config(data_dir):
    os.environ["MALETA_DATA_DIR"] = str(data_dir)
    os.environ.pop("MALETA_SECRET_KEY", None)
    sys.modules.pop("config", None)
    return importlib.import_module("config")


def test_secret_key_per_installation(tmp_path):
    key_a = _load_config(tmp_path / "a").SECRET_KEY
    assert key_a != "dev-secret-a-changer" and len(key_a) == 64
    assert _load_config(tmp_path / "a").SECRET_KEY == key_a  # reutilisee au redemarrage
    assert _load_config(tmp_path / "b").SECRET_KEY != key_a  # differente ailleurs
    assert oct(os.stat(tmp_path / "a" / ".secret_key").st_mode & 0o777) == "0o600"
    sys.modules.pop("config", None)
