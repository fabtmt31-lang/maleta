"""Version de demo jouable sans manette : une touche par action, clics
souris sur les tuiles/cartes/reponses (v1.2)."""

import os
import subprocess
import sys

from test_content_transfer import APP_DIR, make_client


def test_every_action_has_a_default_key(tmp_path):
    app, _ = make_client(tmp_path / "demo", demo=True)
    from managers import settings_manager

    with app.app_context():
        key_map = settings_manager.get_gamepad_key_map()
        assigned = {a for acts in key_map.values() for a in acts}
        assert {a["action"] for a in settings_manager.GAMEPAD_ACTIONS} <= assigned
        # Une action retiree retrouve sa touche au demarrage suivant.
        settings_manager.unassign_keyboard_key("answer_3")
        settings_manager.seed_demo_key_map()
        assert settings_manager.get_gamepad_key_map().get("3") == ["answer_3"]
        assert "?" not in settings_manager.build_kiosk_action_labels().values()


def test_mouse_pointer(tmp_path):
    app, client = make_client(tmp_path / "demo", demo=True)
    client.post("/admin/quiz/new", data={
        "question_fr": "Q ?", "choice_a": "a", "choice_b": "b", "choice_c": "c", "correct_choice": "a"})
    client.post("/admin/duel/new", data={
        "question_fr": "D ?", "choice_a": "a", "choice_b": "b", "correct_choice": "b"})
    controller = app.extensions["game_controller"]
    config = sys.modules["config"]
    config.ACTION_LOCKOUT_SECONDS = 0  # pas de verrou d'entree entre deux clics du test

    from managers import game_controller as gc

    controller.go_to_menu()
    quiz_index = [a["id"] for a in gc.MENU_ACTIVITIES].index("quiz_calandreta")
    assert client.post("/demo/pointer", json={"kind": "menu", "index": quiz_index}).status_code == 200
    assert controller.state == gc.STATE_QUIZ

    controller.go_to_menu()
    duel_index = [a["id"] for a in gc.MENU_ACTIVITIES].index("duel_occitan")
    client.post("/demo/pointer", json={"kind": "menu", "index": duel_index})
    assert controller.state == gc.STATE_DUEL
    client.post("/demo/pointer", json={"kind": "duel", "choice": "a"})
    client.post("/demo/pointer", json={"kind": "duel", "choice": "b"})
    assert controller.duel["answered_p1"] == "a"
    assert controller.duel["answered_p2"] == "b"
    controller.go_to_menu()


def test_pointer_route_is_demo_only(tmp_path):
    _, client = make_client(tmp_path / "pc", demo=False)
    assert client.post("/demo/pointer", json={"kind": "menu", "index": 0}).status_code == 404


def test_command_line_import(tmp_path):
    _, client = make_client(tmp_path / "demo", demo=True)
    client.post("/admin/villages/new", data={"name_fr": "Ville", "name_oc": "Vila"})
    export = tmp_path / "export.zip"
    export.write_bytes(client.get("/admin/transfer/export").data)

    env = dict(os.environ, MALETA_DATA_DIR=str(tmp_path / "pc"), MALETA_DEMO="0")
    os.makedirs(tmp_path / "pc", exist_ok=True)
    script = os.path.join(APP_DIR, "importer_contenu.py")
    out = subprocess.run([sys.executable, script, str(export)], env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "Vilatges (Memòria) : 1 ajoute(s)" in out.stdout
