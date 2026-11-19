"""Jòcs amagats (v1.3) : mode jeu cache, aprene, centre de jòcs, manette, Wi-Fi."""

import io
import os
import stat
import sys
import time
import zipfile

from werkzeug.datastructures import FileStorage

from test_content_transfer import make_client

NES_ROM = b"NES\x1a" + bytes([1, 1, 0, 0]) + bytes(8) + bytes(16384) + bytes(8192)


def _mods():
    return sys.modules["managers.game_controller"], sys.modules["managers.hidden_games"]


# --- Mode jeu cache -------------------------------------------------------------

class Handler:
    def __init__(self):
        self.actions, self.stopped = [], 0

    def on_action(self, action):
        self.actions.append(action)

    def on_stopped(self):
        self.stopped += 1


def test_external_state_takes_over(tmp_path):
    app, client = make_client(tmp_path / "pc", demo=False)
    gc, _ = _mods()
    controller = app.extensions["game_controller"]
    sys.modules["config"].ACTION_LOCKOUT_SECONDS = 0
    handler = Handler()
    token = controller.start_external("aprene", "Competicion aprene", handler, step="internet")
    assert controller.get_state_payload()["state"] == "externe"

    controller.on_action("right")
    controller.on_action("start_idle")  # le raccourci diaporama n'agit plus
    assert controller.state == gc.STATE_EXTERNE and handler.actions == ["right", "start_idle"]
    controller.on_tag_scanned("UID-INCONNU")
    assert controller.state == gc.STATE_EXTERNE

    assert client.post("/externe/quitter").get_json() == {"ok": True}
    assert controller.state == gc.STATE_MENU and handler.stopped == 1
    assert controller.update_external(token, step="login") is False  # jeu termine : ignore


# --- aprene -----------------------------------------------------------------------

class FakeDriver:
    def __init__(self):
        self.calls = []

    def open(self, on_message):
        self.on_message = on_message
        self.calls.append("open")

    def add_page_script(self, source):
        self.script = source

    def navigate(self, url):
        self.calls.append(("navigate", url))

    def evaluate(self, expression):
        self.calls.append(("evaluate", expression))

    def close(self, return_url=None):
        self.calls.append(("close", return_url))


def _wait(predicate, seconds=3):
    end = time.time() + seconds
    while time.time() < end and not predicate():
        time.sleep(0.02)
    return predicate()


def _aprene_ready(tmp_path, monkeypatch, **settings):
    app, client = make_client(tmp_path / "pc", demo=False)
    gc, hg = _mods()
    sys.modules["config"].ACTION_LOCKOUT_SECONDS = 0
    with app.app_context():
        hg.set_aprene_settings(settings.get("url", "https://aprene.example/competicion"),
                               settings.get("login", "compet"), settings.get("password", "compet"), True)
    monkeypatch.setattr(hg, "check_aprene", lambda url, timeout=8: (None, None))
    driver = FakeDriver()
    app.extensions["browser_driver_factory"] = lambda: driver
    return app, client, gc, hg, driver


def test_aprene_session(tmp_path, monkeypatch):
    app, client, gc, hg, driver = _aprene_ready(tmp_path, monkeypatch)
    controller = app.extensions["game_controller"]
    hg.start_aprene(app)
    assert _wait(lambda: ("navigate", "https://aprene.example/connexion?next=/competicion") in driver.calls)
    assert '"login": "compet"' in driver.script and '"gamepad": true' in driver.script

    controller.on_action("right")
    assert ("evaluate", "window.__maleta && window.__maleta.key('next')") in driver.calls

    driver.on_message("quit")
    assert _wait(lambda: controller.state == gc.STATE_MENU)
    assert _wait(lambda: ("close", "http://127.0.0.1:5000/") in driver.calls)


def test_aprene_login_refused(tmp_path, monkeypatch):
    app, _, gc, hg, driver = _aprene_ready(tmp_path, monkeypatch)
    controller = app.extensions["game_controller"]
    hg.start_aprene(app)
    assert _wait(lambda: "open" in driver.calls)
    driver.on_message("login_failed")
    assert _wait(lambda: controller.state == gc.STATE_MENU)
    assert "connexion refusée" in controller.menu_notice


def test_aprene_offline_shows_error_then_menu(tmp_path, monkeypatch):
    app, _, gc, hg, driver = _aprene_ready(tmp_path, monkeypatch)
    monkeypatch.setattr(hg, "check_aprene", lambda url, timeout=8: ("internet", "Pas de connexion internet."))
    monkeypatch.setattr(hg, "ERROR_DISPLAY_SECONDS", 0.3)
    controller = app.extensions["game_controller"]
    hg.start_aprene(app)
    assert _wait(lambda: (controller.external_status() or {}).get("error") == "Pas de connexion internet.")
    assert "open" not in driver.calls
    assert _wait(lambda: controller.state == gc.STATE_MENU)


def test_aprene_settings_password_hidden_and_not_exported(tmp_path, monkeypatch):
    app, client, *_ = _aprene_ready(tmp_path, monkeypatch, password="secret-compet")
    page = client.get("/admin/jocs").get_data(as_text=True)
    assert "secret-compet" not in page and "enregistré" in page
    archive = zipfile.ZipFile(io.BytesIO(client.get("/admin/transfer/export").data))
    assert b"secret-compet" not in archive.read("maleta-contenu.json")


def test_page_script_builds():
    from managers.browser_driver import page_script

    script = page_script("compet", 'mot"de"passe', False, "http://127.0.0.1:5000")
    assert '"password": "mot\\"de\\"passe"' in script and "__MALETA_CONFIG__" not in script


# --- Centre de jòcs -----------------------------------------------------------------

def _with_rom(tmp_path):
    app, client = make_client(tmp_path / "pc", demo=False)
    from managers import rom_manager
    with app.app_context():
        rom_id = rom_manager.add_rom_upload(FileStorage(io.BytesIO(NES_ROM), filename="Mon_Jeu.nes"))
    return app, client, rom_id, rom_manager


def test_jocs_pages_only_while_running(tmp_path):
    app, client, rom_id, _ = _with_rom(tmp_path)
    _, hg = _mods()
    assert client.get("/jocs/").status_code == 302
    assert client.get(f"/jocs/rom/{rom_id}").status_code == 404

    hg.start_jocs(app)
    page = client.get("/jocs/").get_data(as_text=True)
    assert "Mon Jeu" in page and f"/jocs/joc/{rom_id}" in page
    play = client.get(f"/jocs/joc/{rom_id}").get_data(as_text=True)
    assert 'EJS_core = "fceumm"' in play and "EJS_defaultControls" in play and "vendor/emulatorjs/data/" in play
    assert client.get(f"/jocs/rom/{rom_id}").data == NES_ROM
    app.extensions["game_controller"].stop_external()
    assert client.get("/jocs/").status_code == 302


def test_library_upload_rules(tmp_path):
    app, client, rom_id, rom_manager = _with_rom(tmp_path)
    page = client.post("/admin/jocs/bibliotheca", data={"files": [
        (io.BytesIO(b"x"), "photo.jpg"), (io.BytesIO(bytes(1024 * 1024 + 1)), "gros.nes"),
        (io.BytesIO(bytes(2000)), "sonic.md"),
    ]}, content_type="multipart/form-data", follow_redirects=True).get_data(as_text=True)
    assert "1 jeu(x) ajouté(s)" in page and "format non reconnu" in page and "trop gros" in page
    with app.app_context():
        assert rom_manager.counts() == {"nes": 1, "md": 1}
        files_before = set(os.listdir(tmp_path / "pc" / "media" / "roms"))
        rom_manager.delete_rom(rom_id)
        assert len(set(os.listdir(tmp_path / "pc" / "media" / "roms"))) == len(files_before) - 1
    # Les jeux ne sont jamais exportes.
    archive = zipfile.ZipFile(io.BytesIO(client.get("/admin/transfer/export").data))
    assert not any("rom" in name for name in archive.namelist())


def test_controls_and_pad_capture(tmp_path):
    app, client, _, rom_manager = _with_rom(tmp_path)
    with app.app_context():
        assert rom_manager.emulatorjs_controls("nes")[0][8] == {"value": "z", "value2": "BUTTON_1"}
        assert 9 not in rom_manager.emulatorjs_controls("md")[0]  # Y : 6 boutons desactive
    r = client.post("/admin/jocs/maneta/assignar", json={"system": "nes", "player": "1", "button": "a",
                                                          "kind": "key", "value": "escape"})
    assert r.status_code == 400  # Echap reserve a la sortie

    capture = app.extensions["pad_capture"]
    assert client.post("/externe/manette", json={"label": "BUTTON_7"}).get_json() == {"ok": False}
    assert client.post("/admin/jocs/maneta/escotar", json={"system": "md", "player": 2, "button": "c"}).get_json()["ok"]
    assert capture.status()["waiting"]
    assert client.post("/externe/manette", json={"label": "<script>"}).get_json() == {"ok": False}
    assert client.post("/externe/manette", json={"label": "LEFT_STICK_X:+1"}).get_json() == {"ok": True}
    with app.app_context():
        assert rom_manager.get_controls()["md"]["2"]["c"]["pad"] == "LEFT_STICK_X:+1"
    assert client.get("/admin/jocs/maneta").status_code == 200


def test_demo_has_aprene_only(tmp_path):
    _, client = make_client(tmp_path / "demo", demo=True)
    page = client.get("/admin/jocs").get_data(as_text=True)
    assert "aprene" in page and "Centre de jòcs" not in page and "Wi-Fi" not in page
    assert client.get("/admin/jocs/bibliotheca").status_code == 302
    assert client.get("/admin/wifi").status_code == 302


# --- Wi-Fi ---------------------------------------------------------------------------

FAKE_NMCLI = r"""#!/bin/sh
echo "$@" >> "$NMCLI_LOG"
case "$*" in
  *"device status"*) echo "eth0:ethernet:connected:Filaire"; echo "wlan0:wifi:connected:Calandreta-Wifi" ;;
  *"IP4.ADDRESS"*) echo "192.168.1.42/24" ;;
  *"connection show"*) echo "Calandreta-Wifi:802-11-wireless"; echo "Filaire:802-3-ethernet" ;;
  *"wifi list"*) printf '%s\n' "*:Calandreta-Wifi:80:WPA2" " :Salon\\:Expo:55:WPA2" " ::40:WPA2" " :Calandreta-Wifi:30:WPA2" ;;
  *"wifi connect"*) [ "$5" = "password" ] && [ "$6" = "faux" ] && { echo "Error: Secrets were required." >&2; exit 4; } ; exit 0 ;;
  *) exit 0 ;;
esac
"""


def test_wifi_admin(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    nmcli = bin_dir / "nmcli"
    nmcli.write_text(FAKE_NMCLI)
    nmcli.chmod(nmcli.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("NMCLI_LOG", str(tmp_path / "nmcli.log"))
    _, client = make_client(tmp_path / "pc", demo=False)

    page = client.get("/admin/wifi").get_data(as_text=True)
    assert "192.168.1.42" in page and "Salon:Expo" in page and "connecté" in page
    assert page.count("Calandreta-Wifi") >= 2

    page = client.post("/admin/wifi/connectar", data={"ssid": "Salon:Expo", "password": "faux"},
                       follow_redirects=True).get_data(as_text=True)
    assert "impossible" in page and "Secrets were required" in page
    client.post("/admin/wifi/connectar", data={"ssid": "Salon:Expo", "password": "bon"})
    log = (tmp_path / "nmcli.log").read_text()
    assert "device wifi connect Salon:Expo password bon" in log


def test_wifi_without_networkmanager(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))  # nmcli introuvable
    _, client = make_client(tmp_path / "pc", demo=False)
    assert "pas installé sur la borne" in client.get("/admin/wifi").get_data(as_text=True)


def test_demo_return_route(tmp_path, monkeypatch):
    """Demo : la page d'aprene renvoie la fenetre sur /externe/retour."""
    app, client, gc, hg, driver = _aprene_ready(tmp_path, monkeypatch)
    controller = app.extensions["game_controller"]
    assert client.get("/externe/retour?message=quit").status_code == 302  # hors jeu cache : sans effet
    hg.start_aprene(app)
    assert _wait(lambda: "open" in driver.calls)
    assert '"home": "http://127.0.0.1:5000/"' in driver.script
    client.get("/externe/retour?message=autre-chose")
    assert controller.state == gc.STATE_EXTERNE
    client.get("/externe/retour?message=quit")
    assert _wait(lambda: controller.state == gc.STATE_MENU)


def test_login_counter_is_per_launch():
    """v1.31 : chaque lancement a son propre identifiant -- un compteur de
    tentatives reste d'un lancement precedent (onglet jamais ferme) ne bloque
    plus la connexion."""
    from managers.browser_driver import page_script

    first = page_script("compet", "compet", True, "http://127.0.0.1:5000")
    second = page_script("compet", "compet", True, "http://127.0.0.1:5000")
    assert '"session": "' in first and first != second
    assert 'sessionStorage.getItem("maletaLoginSession") !== CFG.session' in first


def test_check_aprene_messages(monkeypatch):
    import socket
    import urllib.error
    from managers import hidden_games

    def unreachable(*args, **kwargs):
        raise urllib.error.URLError(socket.gaierror(-2, "Name or service not known"))

    monkeypatch.setattr(hidden_games.urllib.request, "urlopen", unreachable)
    assert hidden_games.check_aprene("https://aprene.example/competicion")[0] == "internet"

    def refused(*args, **kwargs):
        raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

    monkeypatch.setattr(hidden_games.urllib.request, "urlopen", refused)
    assert hidden_games.check_aprene("https://aprene.example/competicion")[0] == "aprene"
