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
    app.extensions["cover_search"].http_get = _offline
    page = client.post("/admin/jocs/bibliotheca", data={"files": [
        (io.BytesIO(b"x"), "notes.txt"), (io.BytesIO(bytes(1024 * 1024 + 1)), "gros.nes"),
        (io.BytesIO(bytes(2000)), "sonic.md"),
    ]}, content_type="multipart/form-data", follow_redirects=True).get_data(as_text=True)
    assert "1 jeu(x) ajouté(s)" in page and "format non reconnu" in page and "trop gros" in page
    with app.app_context():
        assert rom_manager.counts() == {"nes": 1, "snes": 0, "md": 1, "a26": 0}
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


def test_diaporama_no_longer_on_gamepad(tmp_path):
    """v1.32 : plus d'action manette/clavier pour le diaporama ; l'icone du
    menu reste."""
    app, client = make_client(tmp_path / "pc", demo=False)
    gc, _ = _mods()
    from managers import settings_manager
    controller = app.extensions["game_controller"]
    sys.modules["config"].ACTION_LOCKOUT_SECONDS = 0
    with app.app_context():
        assert "start_idle" not in {a["action"] for a in settings_manager.GAMEPAD_ACTIONS}
        settings_manager.set_gamepad_key_map({"p": ["start_idle", "select"]})  # ancien reglage
        assert settings_manager.get_gamepad_key_map() == {"p": ["select"]}
    controller.go_to_menu()
    controller.on_action("start_idle")
    assert controller.state == gc.STATE_MENU
    client.post("/diaporama")
    assert controller.state == gc.STATE_VEILLE
    controller.go_to_menu()


def test_diagnostic_option(tmp_path):
    app, client, rom_id, rom_manager = _with_rom(tmp_path)
    _, hg = _mods()
    client.post("/admin/jocs/diagnostic", data={"diagnostic": "1"})
    hg.start_jocs(app)
    page = client.get(f"/jocs/joc/{rom_id}").get_data(as_text=True)
    assert 'EJS_defaultOptions = { fps: "show" }' in page and "jocsDiagnostic(false)" in page
    client.post("/admin/jocs/diagnostic", data={})
    assert "jocsDiagnostic(" not in client.get(f"/jocs/joc/{rom_id}").get_data(as_text=True)
    app.extensions["game_controller"].stop_external()


# --- v1.33 : emulateur sans mode debug, Super NES / Atari 2600, jaquettes ---------

def _offline(url, max_bytes):
    from managers.cover_lookup import CoverError
    raise CoverError("pas d'accès à Internet (vérifier le Wi-Fi dans l'admin)")


def test_emulator_without_debug_mode(tmp_path):
    app, client, rom_id, _ = _with_rom(tmp_path)
    _, hg = _mods()
    hg.start_jocs(app)
    play = client.get(f"/jocs/joc/{rom_id}").get_data(as_text=True)
    assert "EJS_DEBUG_XX =" not in play  # mode debug = emulateur verbeux et ralenti
    data = os.path.join(os.path.dirname(__file__), "..", "maleta-occitana", "static", "vendor", "emulatorjs", "data")
    for name in ("emulator.min.js", "emulator.min.css", "cores/snes9x-wasm.data", "cores/stella2014-wasm.data"):
        assert os.path.getsize(os.path.join(data, name)) > 10000, name
    app.extensions["game_controller"].stop_external()


def test_snes_and_atari_2600(tmp_path):
    app, client, rom_id, rom_manager = _with_rom(tmp_path)
    app.extensions["cover_search"].http_get = _offline
    client.post("/admin/jocs/bibliotheca", data={"files": [
        (io.BytesIO(bytes(4096)), "Pitfall!.bin"), (io.BytesIO(bytes(256 * 1024)), "Sonic_(Europe).bin"),
        (io.BytesIO(bytes(512 * 1024)), "Super_Mario_World_(France).sfc"), (io.BytesIO(bytes(4096)), "Combat.a26"),
    ]}, content_type="multipart/form-data")
    with app.app_context():
        roms = {r["title"]: r for r in rom_manager.list_roms()}
        assert {t: r["system"] for t, r in roms.items()} == {
            "Mon Jeu": "nes", "Pitfall!": "a26", "Sonic": "md", "Super Mario World": "snes", "Combat": "a26"}
        assert rom_manager.emulatorjs_controls("a26")[0][0] == {"value": "x", "value2": "BUTTON_2"}
        assert rom_manager.emulatorjs_controls("snes")[0][9]["value2"] == "BUTTON_3"
    # Console modifiable (ex. .bin mal reconnu)
    sonic = roms["Sonic"]["id"]
    client.post(f"/admin/jocs/bibliotheca/{sonic}", data={"title": "Sonic", "players": "1", "active": "1", "system": "a26"})
    with app.app_context():
        assert rom_manager.get_rom(sonic)["system"] == "a26"
    hg = _mods()[1]
    hg.start_jocs(app)
    assert 'EJS_core = "stella2014"' in client.get(f"/jocs/joc/{sonic}").get_data(as_text=True)
    # v1.36 : console annoncee a EmulatorJS (sinon Mega Drive = Master System, Start supprime)
    client.post(f"/admin/jocs/bibliotheca/{sonic}", data={"title": "Sonic", "players": "1", "active": "1", "system": "md"})
    play = client.get(f"/jocs/joc/{sonic}").get_data(as_text=True)
    assert 'EJS_controlScheme = "segaMD"' in play and f"jocsPartida(" in play and f", {sonic});" in play
    snes = roms["Super Mario World"]["id"]
    assert 'EJS_core = "snes9x"' in client.get(f"/jocs/joc/{snes}").get_data(as_text=True)
    app.extensions["game_controller"].stop_external()
    page = client.get("/admin/jocs/maneta?console=a26").get_data(as_text=True)
    assert "Super NES" in page and "Atari 2600" in page and "Reset" in page and "Tir (Fire)" in page
    assert "Select</strong>" in page and "Mode</strong>" not in page  # une seule console affichee


def test_cover_matching():
    from managers import cover_lookup as cl
    from managers.rom_manager import clean_title
    assert clean_title("Super_Mario_Bros._3_(USA)_[!].nes") == "Super Mario Bros. 3"
    names = ["Super Mario Bros. 3 (USA)", "Super Mario Bros. 3 (Europe)", "Super Mario Bros. 3 (USA) (Beta)",
             "Legend of Zelda, The (USA)", "Sonic The Hedgehog 2 (World)", "Pac-Man (Japan)"]
    assert cl.best_match("Super Mario Bros. 3", names) == "Super Mario Bros. 3 (Europe)"
    assert cl.best_match("The Legend of Zelda", names) == "Legend of Zelda, The (USA)"
    assert cl.best_match("Sonic the Hedgehog 2", names) == "Sonic The Hedgehog 2 (World)"
    assert cl.best_match("PacMan", names) == cl.best_match("Pac Man", names) == "Pac-Man (Japan)"
    assert cl.best_match("Tetris", names) is None
    page = ('<a href="?C=N;O=D">Name</a><a href="/Nintendo/">Parent</a>'
            '<a href="Super%20Mario%20Bros.%203%20%28USA%29.png">x</a><a href="Kirby%27s%20Adventure%20(USA).png">y</a>')
    assert cl.parse_index(page) == ["Super Mario Bros. 3 (USA)", "Kirby's Adventure (USA)"]


def test_cover_search_and_companion_images(tmp_path):
    app, client, rom_id, rom_manager = _with_rom(tmp_path)
    png = b"\x89PNG\r\n\x1a\n" + bytes(100)
    calls = []

    def fake_get(url, max_bytes):
        calls.append(url)
        if url.endswith("/Named_Boxarts/"):
            return b'<a href="Mon%20Jeu%20(France).png">a</a><a href="Autre%20Jeu%20(USA).png">b</a>'
        return png

    search = app.extensions["cover_search"]
    search.http_get = fake_get
    # Image jointe du meme nom que le jeu -> jaquette ; sinon refusee.
    page = client.post("/admin/jocs/bibliotheca", data={"files": [
        (io.BytesIO(NES_ROM), "Autre_Jeu.nes"), (io.BytesIO(png), "Autre Jeu.png"), (io.BytesIO(png), "Inconnu.png"),
    ]}, content_type="multipart/form-data", follow_redirects=True).get_data(as_text=True)
    assert "1 jaquette(s) associée(s)" in page and "Inconnu.png : aucun jeu du même nom" in page
    search.wait(5)
    assert not any("Autre" in url for url in calls)  # deja une jaquette : pas de recherche
    # Recherche des jaquettes manquantes
    client.post("/admin/jocs/bibliotheca/jaquettes")
    search.wait(5)
    assert search.status() == {"running": False, "found": ["Mon Jeu"], "missing": [], "error": None}
    assert calls[-1].endswith("/Named_Boxarts/Mon%20Jeu%20%28France%29.png")
    with app.app_context():
        assert all(r["cover_filename"] for r in rom_manager.list_roms())
    _mods()[1].start_jocs(app)
    centre = client.get("/jocs/").get_data(as_text=True)
    assert centre.count("has-cover") == 2 and "/jocs/jaquette/" in centre
    app.extensions["game_controller"].stop_external()
    # Sans reseau : message clair, rien de casse.
    with app.app_context():
        rom_manager.update_rom(rom_id, "Mon Jeu", "1", True, clear_cover=True)
    search.http_get = _offline
    os.remove(os.path.join(str(tmp_path / "pc"), "media", "roms", ".index-jaquettes", "libretro-nes.txt"))
    client.post("/admin/jocs/bibliotheca/jaquettes")
    search.wait(5)
    assert "Internet" in search.status()["error"]
    assert "Internet" in client.get("/admin/jocs/bibliotheca").get_data(as_text=True)


# --- v1.34 : vitesse calee sur l'image, console au choix, combinaison de sortie ---

def test_audio_sync_setting(tmp_path):
    app, client, rom_id, rom_manager = _with_rom(tmp_path)
    _mods()[1].start_jocs(app)
    play = client.get(f"/jocs/joc/{rom_id}").get_data(as_text=True)
    assert 'jocsRetroarchConfig("audio_sync = false\\n")' in play
    client.post("/admin/jocs/son", data={"audio_sync": "1"})
    play = client.get(f"/jocs/joc/{rom_id}").get_data(as_text=True)
    assert 'jocsRetroarchConfig("audio_sync = true\\n")' in play
    assert "Caler la vitesse des jeux sur le son" in client.get("/admin/jocs").get_data(as_text=True)
    app.extensions["game_controller"].stop_external()


def test_quit_combo(tmp_path):
    app, client, rom_id, rom_manager = _with_rom(tmp_path)
    with app.app_context():
        assert rom_manager.get_quit_combo() == {"buttons": ["SELECT", "START"], "hold": 1.0}
    page = client.get("/admin/jocs/maneta").get_data(as_text=True)
    assert "Quitter un jeu à la manette" in page and "Select + Start" in page and 'name="console"' in page
    _mods()[1].start_jocs(app)
    play = client.get(f"/jocs/joc/{rom_id}").get_data(as_text=True)
    assert f'jocsPartida({{"buttons": ["SELECT", "START"], "hold": 1.0}}, {rom_id})' in play and "Select + Start" in play

    # Capture sur la borne : un seul bouton refuse, puis L + R + Start
    capture = app.extensions["pad_capture"]
    assert client.post("/admin/jocs/maneta/sortida", json={"action": "capture"}).get_json()["ok"]
    assert client.post("/externe/manette", json={"label": "BUTTON_1"}).get_json() == {"ok": False}  # mode combinaison
    assert client.post("/externe/manette", json={"labels": ["START"]}).get_json() == {"ok": False}
    assert "2 à 4 boutons" in capture.status()["last"]["error"]
    client.post("/admin/jocs/maneta/sortida", json={"action": "capture"})
    assert client.post("/externe/manette", json={"labels": ["LEFT_TOP_SHOULDER", "RIGHT_TOP_SHOULDER", "START"]}).get_json() == {"ok": True}
    assert client.post("/externe/manette", json={"labels": ["SELECT", "START"]}).get_json() == {"ok": False}  # plus armee
    client.post("/admin/jocs/maneta/sortida", data={"hold": "2", "console": "snes"})
    with app.app_context():
        assert rom_manager.get_quit_combo() == {"buttons": ["LEFT_TOP_SHOULDER", "RIGHT_TOP_SHOULDER", "START"], "hold": 2.0}
        assert rom_manager.quit_combo_label() == "L + R + Start"
    assert client.post("/admin/jocs/maneta/sortida", json={"labels": ["<x>", "START"]}).status_code == 200  # ignore
    client.post("/admin/jocs/maneta/sortida", json={"action": "clear"})
    play = client.get(f"/jocs/joc/{rom_id}").get_data(as_text=True)
    assert '"buttons": []' in play
    client.post("/admin/jocs/maneta/sortida", json={"action": "default"})
    with app.app_context():
        assert rom_manager.get_quit_combo()["buttons"] == ["SELECT", "START"]
    app.extensions["game_controller"].stop_external()
