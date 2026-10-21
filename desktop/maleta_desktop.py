"""La Maleta Occitana - version de demonstration (application de bureau).

Lance l'appli Flask/SocketIO en local (127.0.0.1, port libre choisi au
demarrage) puis l'affiche dans une simple fenetre (pywebview : WebView2 sous
Windows, WebKitGTK sous Linux). Aucun lecteur NFC ni manette necessaire :
- MALETA_DEMO=1 : clavier assigne par defaut, panneau "Pausar un objècte"
  (touche F2) a la place du lecteur NFC, bandeau DÉMO dans l'admin ;
- MALETA_HARDWARE=dev : lecteur NFC simule.

Les donnees (base + medias) vivent dans le dossier utilisateur, jamais a
cote du programme :
- Windows : %APPDATA%\\MaletaOccitanaDemo
- Linux   : ~/.local/share/maleta-occitana-demo
Le contenu saisi s'exporte depuis Admin > Exportar / Importar pour etre
reimplante dans la version standard (borne).

Usage depuis les sources :
    pip install -r desktop/requirements.txt
    python desktop/maleta_desktop.py
"""

import faulthandler
import logging
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.request
import webbrowser
from urllib.parse import parse_qs, urlparse

APP_TITLE = "La Maleta Occitana — démo"
HERE = os.path.dirname(os.path.abspath(__file__))


def _app_dir():
    """Dossier du code de l'appli (maleta-occitana/)."""
    if getattr(sys, "frozen", False):  # executable PyInstaller
        return os.path.join(sys._MEIPASS, "maleta-occitana")
    return os.environ.get("MALETA_APP_DIR") or os.path.join(os.path.dirname(HERE), "maleta-occitana")


def _data_dir():
    if os.environ.get("MALETA_DATA_DIR"):
        return os.environ["MALETA_DATA_DIR"]
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "MaletaOccitanaDemo")
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "maleta-occitana-demo")


def _icon_path():
    candidates = [
        os.path.join(getattr(sys, "_MEIPASS", HERE), "assets", "maleta-occitana.png"),
        os.path.join(HERE, "assets", "maleta-occitana.png"),
    ]
    return next((p for p in candidates if os.path.isfile(p)), None)


def _secret_key(data_dir):
    """Cle de session Flask propre a cette installation (gardee d'un
    lancement a l'autre, pour ne pas deconnecter l'admin a chaque fois)."""
    path = os.path.join(data_dir, ".secret_key")
    try:
        with open(path, "r", encoding="ascii") as f:
            key = f.read().strip()
            if key:
                return key
    except OSError:
        pass
    key = secrets.token_hex(32)
    with open(path, "w", encoding="ascii") as f:
        f.write(key)
    return key


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(url, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except Exception:
            time.sleep(0.2)
    return False


def _open_folder(path):
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - dossier local de l'appli
    else:
        subprocess.Popen(["xdg-open", path])


def main():
    data_dir = _data_dir()
    os.makedirs(data_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(os.path.join(data_dir, "maleta-demo.log"), encoding="utf-8")]
        + ([logging.StreamHandler()] if sys.stderr else []),
    )
    logger = logging.getLogger("maleta_desktop")
    # Plantage natif (ex. composant fenetre Windows) : trace dans un fichier,
    # sinon l'executable sans console disparait sans rien dire.
    global _crash_file
    _crash_file = open(os.path.join(data_dir, "maleta-demo-crash.log"), "w", encoding="utf-8")
    faulthandler.enable(_crash_file)
    sys.excepthook = lambda *exc: logger.critical("Erreur non geree", exc_info=exc)
    threading.excepthook = lambda a: logger.critical(
        "Erreur non geree (thread %s)", a.thread and a.thread.name,
        exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
    logger.info("Demarrage - Python %s - %s - frozen=%s", sys.version.split()[0], sys.platform,
                getattr(sys, "frozen", False))

    # Reglages lus par config.py : a definir AVANT tout import de l'appli.
    os.environ["MALETA_DEMO"] = "1"
    os.environ["MALETA_HARDWARE"] = "dev"
    os.environ["MALETA_DATA_DIR"] = data_dir
    os.environ.setdefault("MALETA_SECRET_KEY", _secret_key(data_dir))

    app_dir = _app_dir()
    lib_dir = os.environ.get("MALETA_LIB_DIR") or os.path.join(os.path.dirname(HERE), "lib")
    if os.path.isdir(lib_dir):
        sys.path.insert(0, lib_dir)  # dependances embarquees (paquet .deb)
    sys.path.insert(0, app_dir)

    import config
    from app import create_app

    app, socketio = create_app()
    logging.getLogger("werkzeug").setLevel(logging.WARNING)  # une ligne par requete sinon
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    logger.info("La Maleta Occitana %s (demo) - %s - donnees : %s", config.APP_VERSION, base_url, data_dir)

    def serve():
        socketio.run(app, host="127.0.0.1", port=port, debug=False,
                     use_reloader=False, log_output=False, allow_unsafe_werkzeug=True)

    threading.Thread(target=serve, name="maleta-server", daemon=True).start()
    if not _wait_ready(base_url + "/"):
        logger.error("Le serveur local n'a pas demarre")
        sys.exit(1)

    smoke = os.environ.get("MALETA_SMOKE_TEST")
    if smoke in ("1", "gui"):
        # Verification automatique des paquets construits (CI) : les pages
        # principales repondent ("1" s'arrete la, "gui" ouvre ensuite
        # vraiment la fenetre, voir plus bas).
        for path in ("/", "/admin/login", "/static/js/kiosk-demo.js", "/demo/objects",
                     "/socket.io/?EIO=4&transport=polling"):
            with urllib.request.urlopen(base_url + path, timeout=10) as resp:
                logger.info("smoke test %s -> %s", path, resp.status)
        import webview  # noqa: F401 - la fenetre doit au moins pouvoir s'importer
        if smoke == "1":
            logger.info("SMOKE TEST OK")
            return

    try:
        import webview
        from webview.menu import Menu, MenuAction, MenuSeparator
    except Exception:
        logger.exception("pywebview indisponible - ouverture dans le navigateur")
        if smoke:
            raise
        _show_error("La fenêtre de l'application n'a pas pu être chargée.", data_dir)
        _browser_fallback(base_url)
        return

    window_ref = {}

    class Api:
        """Fonctions appelables depuis les pages (window.pywebview.api)."""

        def save_export(self, url):
            # Boite "Enregistrer sous" native, puis export ecrit directement
            # (pas de telechargement navigateur, peu fiable dans une webview).
            from managers import content_transfer
            params = parse_qs(urlparse(url).query)
            include_media = params.get("media", ["1"])[0] == "1"
            include_settings = params.get("settings", ["1"])[0] == "1"
            with app.app_context():
                filename, payload = content_transfer.build_export(include_media, include_settings)
            window = window_ref["main"]
            result = window.create_file_dialog(
                webview.FileDialog.SAVE,
                directory=os.path.expanduser("~"),
                save_filename=filename,
                file_types=("Export Maleta (*.zip)",),
            )
            if not result:
                return None
            path = result if isinstance(result, str) else result[0]
            if not path.lower().endswith(".zip"):
                path += ".zip"
            with open(path, "wb") as f:
                f.write(payload)
            logger.info("Export enregistre : %s", path)
            return path

        def toggle_fullscreen(self):
            window_ref["main"].toggle_fullscreen()

    def T(title):
        return _MenuTitle(title) if sys.platform.startswith("linux") else title

    def go(path):
        return lambda: window_ref["main"].load_url(base_url + path)

    menu = [
        Menu(T("Maleta"), [
            MenuAction(T("Écran de la borne"), go("/")),
            MenuAction(T("Administration"), go("/admin/")),
            MenuAction(T("Exporter / importer le contenu"), go("/admin/transfer")),
            MenuSeparator(),
            MenuAction(T("Plein écran (F11)"), lambda: window_ref["main"].toggle_fullscreen()),
            MenuAction(T("Ouvrir le dossier des données"), lambda: _open_folder(data_dir)),
            MenuSeparator(),
            MenuAction(T("Quitter"), lambda: window_ref["main"].destroy()),
        ]),
        Menu(T("Aide"), [
            MenuAction(T("Commandes clavier"), lambda: window_ref["main"].evaluate_js(f"alert({_HELP_TEXT!r})")),
        ]),
    ]

    window = webview.create_window(
        APP_TITLE, base_url + "/", js_api=Api(),
        width=1280, height=760, min_size=(800, 500),
        text_select=True, background_color="#1C1210",
    )
    window_ref["main"] = window

    def on_loaded():
        # F11 = plein ecran, sur toutes les pages (kiosque comme admin).
        window.evaluate_js(
            "if(!window.__maletaF11){window.__maletaF11=true;"
            "window.addEventListener('keydown',function(e){if(e.key==='F11'){e.preventDefault();"
            "window.pywebview&&window.pywebview.api.toggle_fullscreen();}});}"
        )

    window.events.loaded += on_loaded
    webview.settings["ALLOW_DOWNLOADS"] = True

    page_loaded = threading.Event()
    window.events.loaded += page_loaded.set

    def watch_gui():
        # Fenetre ouverte mais page jamais chargee : le noter dans le journal
        # (et, en test automatique, refermer pour rendre la main).
        ok = page_loaded.wait(60)
        if ok:
            logger.info("Fenetre ouverte, page chargee")
            if smoke == "gui":
                title = window.evaluate_js("document.title")
                logger.info("SMOKE TEST GUI OK - titre : %s", title)
        else:
            logger.error("La page ne s'est pas chargee dans la fenetre apres 60 s")
        if smoke == "gui":
            gui_result["ok"] = ok
            window.destroy()

    gui_result = {"ok": False}
    # Diagnostic : MALETA_WEBVIEW_OPTS=nomenu,noicon,private desactive une option.
    opts = set(filter(None, os.environ.get("MALETA_WEBVIEW_OPTS", "").split(",")))
    start_kwargs = {"menu": menu, "private_mode": False,
                    "storage_path": os.path.join(data_dir, "webview"), "icon": _icon_path()}
    if "nomenu" in opts:
        start_kwargs.pop("menu")
    if "noicon" in opts:
        start_kwargs.pop("icon")
    if "private" in opts:
        start_kwargs.pop("storage_path")
        start_kwargs["private_mode"] = True
    logger.info("Ouverture de la fenetre (options : %s)", sorted(start_kwargs))
    try:
        webview.start(watch_gui, **start_kwargs)
        logger.info("Fenetre fermee (renderer : %s)", getattr(webview, "renderer", "?"))
    except Exception:
        logger.exception("Impossible d'ouvrir la fenetre - ouverture dans le navigateur")
        if smoke:
            raise
        _show_error("La fenêtre de l'application n'a pas pu s'ouvrir : la démo va "
                    "s'ouvrir dans le navigateur.", data_dir)
        _browser_fallback(base_url)
        return
    if smoke == "gui" and not gui_result["ok"]:
        raise RuntimeError("SMOKE TEST GUI : page non chargee")


def _show_error(message, data_dir):
    """Message visible meme sans console (executable Windows)."""
    detail = f"{message}\n\nDétails : {os.path.join(data_dir, 'maleta-demo.log')}"
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, detail, APP_TITLE, 0x30)
            return
        except Exception:
            pass
    print(detail, file=sys.stderr or sys.stdout)


class _MenuTitle(str):
    """Titre de menu pour GTK : pywebview fabrique le nom interne de l'action
    a partir du titre (f-string), et GTK refuse accents et parentheses dans
    ce nom (plantage au demarrage). Le libelle affiche reste le titre
    d'origine ; seul le nom interne est ramene a de l'ASCII."""

    def __format__(self, spec):
        ascii_title = unicodedata.normalize("NFKD", str(self)).encode("ascii", "ignore").decode()
        return re.sub(r"[^A-Za-z0-9]+", "-", ascii_title).strip("-")


_HELP_TEXT = (
    "La Maleta Occitana — version démo (clavier + souris, aucune manette)\n\n"
    "CLAVIER\n"
    "Flèches : se déplacer   ·   Entrée : valider   ·   Échap : retour au menu\n"
    "1 / 2 / 3 : réponses (Ven de l'occitan ?, Quiz)\n"
    "Duèl : S / D (joueur 1, réponses A / B), K / L (joueur 2)\n"
    "P : diaporama   ·   F2 : poser un objet (NFC simulé)\n"
    "F11 : plein écran   ·   Ctrl+Alt+A : administration (code 1234)\n\n"
    "SOURIS\n"
    "Clic sur une tuile, une carte ou une réponse : la choisir\n"
    "Duèl : 1er clic = joueur 1, 2e clic = joueur 2\n"
    "Clic droit : retour au menu   ·   bouton NFC en bas à gauche : poser un objet\n\n"
    "Touches modifiables dans Administration > Configuracion."
)


def _browser_fallback(base_url):
    """Sans fenetre integree (ex. WebKitGTK absent) : navigateur par defaut,
    le serveur tourne jusqu'a la fermeture du programme."""
    webbrowser.open(base_url + "/")
    print(f"La Maleta Occitana (démo) : {base_url}/  —  Ctrl+C pour quitter.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


_crash_file = None


if __name__ == "__main__":
    if os.environ.get("MALETA_SMOKE_TEST") in ("1", "gui"):
        # Jamais de boite d'erreur bloquante en CI (executable Windows sans
        # console) : code de sortie seulement, detail dans maleta-demo.log.
        try:
            main()
        except BaseException:
            logging.getLogger("maleta_desktop").exception("SMOKE TEST FAILED")
            logging.shutdown()
            os._exit(1)
        logging.shutdown()
        os._exit(0)
    try:
        main()
    except Exception:
        logging.getLogger("maleta_desktop").exception("Erreur au demarrage")
        _show_error("La Maleta Occitana (démo) n'a pas pu démarrer.", _data_dir())
        sys.exit(1)
