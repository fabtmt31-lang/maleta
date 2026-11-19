"""Jòcs amagats (jeux caches) -- v1.3.

Jeux absents du menu des visiteurs, lances uniquement depuis l'admin
(Admin > Jòcs amagats) : voir docs/cahier-des-charges-jocs-amagats.md a la
racine du depot.

- aprene : la competition en ligne d'aprene. Le navigateur de la borne y
  est envoye puis ramene (managers/browser_driver.py) ; connexion
  automatique, double Echap pour quitter, manette convertie en navigation.
- Centre de jòcs : emulateur NES / Mega Drive dans la page /jocs/ (borne
  seulement, voir blueprints/jocs.py et managers/rom_manager.py).

Pendant un jeu cache, la borne est dans l'etat STATE_EXTERNE du
GameController : ses actions habituelles sont ignorees.
"""

import logging
import socket
import threading
import urllib.error
import urllib.request
from urllib.parse import urlsplit

import config
from managers import settings_manager
from managers.browser_driver import CdpDriver, DriverError, page_script

logger = logging.getLogger(__name__)

# --- Reglages (table settings ; jamais exportes : content_transfer n'exporte
# que les reglages d'apparence, voir SETTINGS_KEYS) -----------------------------

KEY_APRENE_URL = "aprene_url"
KEY_APRENE_LOGIN = "aprene_login"
KEY_APRENE_PASSWORD = "aprene_password"
KEY_APRENE_GAMEPAD = "aprene_gamepad"
DEFAULT_APRENE_URL = "https://aprene.appsdoc.fr/competicion"

# Delai d'affichage d'une erreur (pas de reseau...) avant le retour au menu.
ERROR_DISPLAY_SECONDS = 10


def get_aprene_settings():
    return {
        "url": settings_manager._get(KEY_APRENE_URL, None) or DEFAULT_APRENE_URL,
        "login": settings_manager._get(KEY_APRENE_LOGIN, "") or "",
        "password": settings_manager._get(KEY_APRENE_PASSWORD, "") or "",
        "gamepad": settings_manager._get(KEY_APRENE_GAMEPAD, "1") == "1",
    }


def set_aprene_settings(url, login, password, gamepad):
    """`password` vide ou None : mot de passe inchange (il n'est jamais
    reaffiche dans le formulaire)."""
    url = (url or "").strip() or DEFAULT_APRENE_URL
    if not url.startswith(("https://", "http://")):
        raise ValueError("L'adresse d'aprene doit commencer par https://")
    settings_manager._set(KEY_APRENE_URL, url)
    settings_manager._set(KEY_APRENE_LOGIN, (login or "").strip())
    if password:
        settings_manager._set(KEY_APRENE_PASSWORD, password)
    settings_manager._set(KEY_APRENE_GAMEPAD, "1" if gamepad else "0")


# --- Verification de la connexion --------------------------------------------

def check_aprene(url, timeout=8):
    """Renvoie (etape_en_echec, message) ; (None, None) si aprene repond.
    Etapes : "internet" (adresse introuvable), "aprene" (le site ne repond
    pas correctement)."""
    parts = urlsplit(url)
    host = parts.hostname
    if not host:
        return "aprene", "Adresse d'aprene invalide (voir Admin > Jòcs amagats)."
    try:
        socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80))
    except OSError:
        return "internet", "Pas de connexion internet (adresse d'aprene introuvable)."
    health = f"{parts.scheme}://{parts.netloc}/healthz"
    try:
        with urllib.request.urlopen(health, timeout=timeout) as resp:
            if resp.status != 200:
                return "aprene", f"aprene ne répond pas correctement (code {resp.status})."
    except urllib.error.HTTPError as exc:
        return "aprene", f"aprene ne répond pas correctement (code {exc.code})."
    except (urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return "aprene", f"aprene ne répond pas ({reason})."
    return None, None


# --- Session aprene --------------------------------------------------------------

class ApreneSession:
    """Une competition aprene, du lancement au retour au menu."""

    # Manette de la borne -> navigation dans la page d'aprene (voir
    # PAGE_SCRIPT, window.__maleta.key) : croix = passer d'un element a
    # l'autre, A = valider. "back" (B) ne fait rien : pas de retour arriere
    # accidentel en pleine partie.
    ACTION_KEYS = {"left": "prev", "up": "prev", "right": "next", "down": "next", "select": "ok"}

    def __init__(self, app, controller, driver_factory, kiosk_url):
        self.app = app
        self.controller = controller
        self.driver_factory = driver_factory
        self.kiosk_url = kiosk_url
        self.driver = None
        self.token = None
        self.gamepad = False
        self._stopped = threading.Event()

    def start(self):
        self.token = self.controller.start_external("aprene", "Competicion aprene", self, step="internet")
        threading.Thread(target=self._run, name="aprene", daemon=True).start()
        return self.token

    def _run(self):
        with self.app.app_context():
            cfg = get_aprene_settings()
        self.gamepad = cfg["gamepad"]
        if not cfg["login"] or not cfg["password"]:
            return self._fail("login", "Identifiant ou mot de passe aprene manquant (Admin > Jòcs amagats).")

        failed_step, message = check_aprene(cfg["url"])
        if failed_step:
            return self._fail(failed_step, message)
        if self._stopped.is_set():
            return
        self.controller.update_external(self.token, step="login")

        parts = urlsplit(cfg["url"])
        origin = f"{parts.scheme}://{parts.netloc}"
        try:
            self.driver = self.driver_factory()
            self.driver.open(self._on_message)
            home = getattr(self.driver, "home_url", None) or self.kiosk_url
            self.driver.add_page_script(page_script(cfg["login"], cfg["password"], cfg["gamepad"], home))
            if self._stopped.is_set():
                return
            self.driver.navigate(f"{origin}/connexion?next={parts.path or '/competicion'}")
        except DriverError as exc:
            self._close_driver(navigate_back=False)
            return self._fail("login", str(exc))
        self.controller.update_external(self.token, step="playing")

    def _fail(self, step, message):
        logger.warning("aprene : %s", message)
        self.controller.update_external(self.token, step=step, error=message)
        self.controller.schedule_external_stop(self.token, ERROR_DISPLAY_SECONDS)

    def on_message(self, message):
        """Message du script de page recu par /externe/retour (demo)."""
        self._on_message(message)

    def _on_message(self, message):
        if message == "quit":
            self.controller.stop_external(self.token)
        elif message == "login_failed":
            self.controller.stop_external(
                self.token, notice="aprene : connexion refusée (identifiant ou mot de passe, Admin > Jòcs amagats).")
        elif message == "page_error":
            self.controller.stop_external(self.token, notice="aprene : la page ne s'est pas chargée (connexion perdue ?).")

    # Appeles par le GameController ------------------------------------------------

    def on_action(self, action):
        kind = self.ACTION_KEYS.get(action)
        if kind and self.gamepad and self.driver is not None:
            self.driver.evaluate(f"window.__maleta && window.__maleta.key('{kind}')")

    def on_stopped(self):
        self._stopped.set()
        # Hors du verrou du GameController : le retour du navigateur peut
        # prendre quelques secondes.
        threading.Thread(target=self._close_driver, name="aprene-stop", daemon=True).start()

    def _close_driver(self, navigate_back=True):
        driver, self.driver = self.driver, None
        if driver is not None:
            driver.close(return_url=self.kiosk_url if navigate_back else None)


class JocsHandler:
    """Centre de jòcs : la page /jocs/ lit elle-meme la manette (navigateur),
    la borne n'a rien a faire des actions ni a l'arret (la page revient sur
    l'accueil quand l'etat change, voir static/js/jocs.js)."""

    def on_action(self, action):
        pass

    def on_stopped(self):
        pass


def start_aprene(app):
    factory = app.extensions.get("browser_driver_factory") or (lambda: CdpDriver(config.BROWSER_DEBUG_PORT))
    session = ApreneSession(app, app.extensions["game_controller"], factory, config.KIOSK_URL)
    return session.start()


def start_jocs(app):
    return app.extensions["game_controller"].start_external("jocs", "Centre de jòcs", JocsHandler())
