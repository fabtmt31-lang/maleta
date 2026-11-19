"""Pilotage du navigateur de la borne pour les jeux caches en ligne (v1.3).

aprene interdit d'etre affiche dans une autre page (en-tete CSP
`frame-ancestors 'none'`) : pour la competition, le navigateur de la borne
quitte donc la page de la Maleta, va sur aprene, puis revient. Deux
"pilotes" font ce travail :

- CdpDriver (borne) : Chromium lance par .xinitrc avec son port de pilotage
  (--remote-debugging-port, sur 127.0.0.1 seulement, voir install.sh). On
  lui parle par le protocole DevTools (CDP) : aller sur une page, y ajouter
  un script, recevoir des messages de ce script.
- WebviewDriver (version demo) : la fenetre pywebview, fournie par
  desktop/maleta_desktop.py (app.extensions["browser_driver_factory"]).
  Sans canal de messages : le script renvoie la fenetre sur
  /externe/retour?message=... (voir blueprints/kiosk.py).

Les deux ajoutent sur chaque page d'aprene le meme script (PAGE_SCRIPT) :
connexion automatique, double Echap pour quitter, petit rappel en bas a
droite, et navigation a la manette (voir key()). Ce script parle a la borne
par une seule fonction, window.__maletaSend(message).
"""

import itertools
import json
import logging
import threading
import urllib.request

logger = logging.getLogger(__name__)


class DriverError(RuntimeError):
    """Pilotage du navigateur impossible (message affiche tel quel)."""


# Script ajoute sur chaque page d'aprene. __MALETA_CONFIG__ est remplace par
# un objet JSON {login, password, gamepad} (voir page_script()).
PAGE_SCRIPT = r"""
(function () {
  if (window.__maleta) return;
  const CFG = __MALETA_CONFIG__;
  // Vers la borne : canal du pilote Chromium (borne) ; sinon (demo) la page
  // part sur une adresse de la borne qui transmet le message -- la politique
  // de securite d'aprene (CSP) bloque les autres moyens (requetes, pont
  // pywebview), mais jamais une navigation.
  const send = (msg) => {
    if (window.maletaBridge) { window.maletaBridge(msg); return; }
    if (msg.indexOf("page:") === 0) return;  // simple information, inutile sans canal
    location.href = CFG.home + "externe/retour?message=" + encodeURIComponent(msg);
  };

  // --- Connexion automatique (page /connexion) -------------------------------
  function autoLogin() {
    if (location.pathname !== "/connexion") {
      sessionStorage.removeItem("maletaLoginTries");
      return;
    }
    const form = document.querySelector('form[action="/connexion"]');
    if (!form || !CFG.login) return;
    const tries = Number(sessionStorage.getItem("maletaLoginTries") || 0);
    if (tries >= 2) { send("login_failed"); return; }
    sessionStorage.setItem("maletaLoginTries", String(tries + 1));
    form.querySelector('[name="identifiant"]').value = CFG.login;
    form.querySelector('[name="mdp"]').value = CFG.password;
    const next = form.querySelector('[name="next"]');
    if (next && !next.value) next.value = "/competicion";
    form.submit();
  }

  // --- Habillage : rappel, bandeau de sortie, focus visible ------------------
  const style = document.createElement("style");
  style.textContent = `
    .maleta-hint { position: fixed; right: 16px; bottom: 12px; z-index: 2147483646;
      background: rgba(28,18,16,.78); color: #fff; border-radius: 999px; padding: 6px 14px;
      font: 600 13px/1.3 system-ui, sans-serif; pointer-events: none; }
    .maleta-quit { position: fixed; left: 0; right: 0; top: 0; z-index: 2147483647;
      background: #1C1210; color: #FFF4DC; padding: 18px 28px; display: flex; align-items: center;
      gap: 18px; font: 700 22px/1.3 system-ui, sans-serif; box-shadow: 0 6px 20px rgba(0,0,0,.4); }
    .maleta-quit kbd { background: #F6C22E; color: #1C1210; border-radius: 8px; padding: 4px 10px; font: inherit; }
    .maleta-quit small { font-weight: 500; opacity: .8; font-size: 18px; }
    ${CFG.gamepad ? `:focus-visible, .maleta-focus { outline: 4px solid #B3141C !important;
      box-shadow: 0 0 0 8px #F6C22E !important; outline-offset: 2px; }` : ""}`;

  function decorate() {
    document.head.appendChild(style);
    const hint = document.createElement("div");
    hint.className = "maleta-hint";
    hint.textContent = "Maleta · Échap ×2 : quitar" + (CFG.gamepad ? " · Manèta : ✥ causir, A validar" : "");
    document.body.appendChild(hint);
  }

  // --- Double Echap pour quitter ---------------------------------------------
  let banner = null;
  let bannerTimer = null;
  function hideBanner() {
    if (banner) banner.remove();
    banner = null;
    clearTimeout(bannerTimer);
  }
  async function quit() {
    hideBanner();
    try { await fetch("/deconnexion", { method: "POST", credentials: "same-origin" }); } catch (e) {}
    send("quit");
  }
  window.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") { if (banner) hideBanner(); return; }
    if (event.repeat) return;
    if (banner) { event.preventDefault(); event.stopImmediatePropagation(); quit(); return; }
    // 1er appui : on le laisse passer (il ferme aussi les fenetres d'aprene).
    banner = document.createElement("div");
    banner.className = "maleta-quit";
    banner.innerHTML = "<kbd>Échap</kbd><span>Quitar aprene e tornar a la Maleta ?</span>" +
      "<small>Torna quichar Échap per confirmar — tota autra tòca : contunhar</small>";
    document.body.appendChild(banner);
    bannerTimer = setTimeout(hideBanner, 5000);
  }, true);

  // --- Manette : deplacement entre les elements cliquables -------------------
  // Appele par la borne (manette de la borne convertie en "next"/"prev"/"ok").
  const FOCUSABLE = 'button:not([disabled]), a[href], input:not([type=hidden]):not([disabled]), ' +
    'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  function visible(el) {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
  }
  function key(kind) {
    if (!CFG.gamepad) return;
    const items = Array.from(document.querySelectorAll(FOCUSABLE)).filter(visible);
    if (!items.length) return;
    const current = document.activeElement;
    let index = items.indexOf(current);
    if (kind === "ok") {
      if (index >= 0) current.click(); else items[0].focus();
      return;
    }
    if (index < 0) index = kind === "next" ? -1 : 0;
    const target = items[(index + (kind === "next" ? 1 : -1) + items.length) % items.length];
    document.querySelectorAll(".maleta-focus").forEach((el) => el.classList.remove("maleta-focus"));
    target.classList.add("maleta-focus");
    target.focus({ focusVisible: true });
    target.scrollIntoView({ block: "nearest" });
  }

  window.__maleta = { key, quit };
  window.__maletaSend = send;
  const ready = () => { decorate(); autoLogin(); send("page:" + location.pathname); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ready);
  else ready();
})();
"""


def page_script(login, password, gamepad, home_url):
    """Script de page pret a injecter, en ASCII pur : les caracteres
    accentues sont ecrits en echappements \\uXXXX (pywebview sous Linux
    tronque les scripts non ASCII, il compte leur longueur en caracteres et
    non en octets)."""
    config = json.dumps({"login": login or "", "password": password or "", "gamepad": bool(gamepad),
                         "home": home_url if home_url.endswith("/") else home_url + "/"})
    return _ascii_js(PAGE_SCRIPT.replace("__MALETA_CONFIG__", config))


def _ascii_js(source):
    out = []
    for char in source:
        code = ord(char)
        if code < 128:
            out.append(char)
        elif code <= 0xFFFF:
            out.append("\\u%04x" % code)
        else:  # hors plan de base : paire de substitution
            code -= 0x10000
            out.append("\\u%04x\\u%04x" % (0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)))
    return "".join(out)


class CdpDriver:
    """Pilote Chromium par le protocole DevTools (port local de pilotage).

    Une session = une connexion websocket a l'onglet de la borne, gardee
    ouverte pendant tout le jeu cache : le script ajoute aux pages et le
    canal de messages (binding) n'existent que tant qu'elle est ouverte."""

    BINDING = "maletaBridge"

    def __init__(self, port=9222, host="127.0.0.1"):
        self.base = f"http://{host}:{port}"
        self._ws = None
        self._ids = itertools.count(1)
        self._pending = {}
        self._lock = threading.Lock()
        self._on_message = None
        self._reader = None
        self._closed = threading.Event()

    # -- Session ---------------------------------------------------------------

    def open(self, on_message):
        """Se connecte a l'onglet de la borne. on_message(str) recoit les
        messages du script de page ("quit", "login_failed", "page:/...") et
        "page_error" si une page ne se charge pas (reseau coupe...)."""
        try:
            with urllib.request.urlopen(self.base + "/json", timeout=3) as resp:
                targets = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise DriverError(
                "Pilotage du navigateur de la borne indisponible (Chromium doit être lancé avec "
                "--remote-debugging-port : relancer install.sh puis redémarrer la borne)."
            ) from exc
        pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
        if not pages:
            raise DriverError("Aucun onglet du navigateur de la borne n'est pilotable.")
        import simple_websocket  # dependance de Flask-SocketIO, deja installee

        self._ws = simple_websocket.Client.connect(pages[0]["webSocketDebuggerUrl"])
        self._on_message = on_message
        self._closed.clear()
        self._reader = threading.Thread(target=self._read_loop, name="cdp-reader", daemon=True)
        self._reader.start()
        self.call("Page.enable")
        self.call("Runtime.enable")
        self.call("Runtime.addBinding", {"name": self.BINDING})

    def add_page_script(self, source):
        """Script execute sur chaque nouvelle page tant que la session dure."""
        self.call("Page.addScriptToEvaluateOnNewDocument", {"source": source})

    def navigate(self, url):
        result = self.call("Page.navigate", {"url": url}, timeout=20)
        if result.get("errorText"):
            raise DriverError(f"Page impossible à charger ({result['errorText']}).")

    def evaluate(self, expression):
        try:
            self.call("Runtime.evaluate", {"expression": expression}, timeout=5)
        except DriverError:
            pass

    def close(self, return_url=None):
        """Fin de session : ramene le navigateur sur la borne puis se deconnecte."""
        if self._ws is None:
            return
        try:
            if return_url:
                self.call("Page.navigate", {"url": return_url}, timeout=10)
        except DriverError:
            logger.warning("Retour du navigateur sur la borne impossible")
        finally:
            self._closed.set()
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    # -- Protocole ---------------------------------------------------------------

    def call(self, method, params=None, timeout=10):
        if self._ws is None:
            raise DriverError("Session de pilotage fermée.")
        msg_id = next(self._ids)
        waiter = {"event": threading.Event(), "result": None}
        with self._lock:
            self._pending[msg_id] = waiter
        try:
            self._ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        except Exception as exc:
            raise DriverError(f"Navigateur de la borne injoignable ({exc}).") from exc
        if not waiter["event"].wait(timeout):
            with self._lock:
                self._pending.pop(msg_id, None)
            raise DriverError(f"Le navigateur ne répond pas ({method}).")
        result = waiter["result"] or {}
        if "error" in result:
            raise DriverError(f"{method} : {result['error'].get('message')}")
        return result.get("result", {})

    def _read_loop(self):
        while not self._closed.is_set():
            try:
                raw = self._ws.receive(timeout=1) if self._ws else None
            except Exception:
                if not self._closed.is_set():
                    self._emit("page_error")
                return
            if raw is None:
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if "id" in msg:
                with self._lock:
                    waiter = self._pending.pop(msg["id"], None)
                if waiter:
                    waiter["result"] = msg
                    waiter["event"].set()
                continue
            method = msg.get("method")
            params = msg.get("params", {})
            if method == "Runtime.bindingCalled" and params.get("name") == self.BINDING:
                self._emit(params.get("payload", ""))
            elif method == "Page.frameNavigated":
                frame = params.get("frame", {})
                if not frame.get("parentId") and frame.get("url", "").startswith("chrome-error:"):
                    self._emit("page_error")
            elif method == "Inspector.detached":
                self._emit("page_error")
                return

    def _emit(self, message):
        if self._on_message:
            threading.Thread(target=self._on_message, args=(message,), daemon=True).start()
