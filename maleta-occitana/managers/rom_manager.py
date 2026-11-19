"""Centre de jòcs (v1.3) : bibliotheque des jeux et reglage de la manette.

Les fichiers de jeux (ROM) sont ajoutes par l'ecole depuis l'admin, sous sa
responsabilite : la Maleta n'en livre, n'en telecharge et n'en exporte
aucun (media/roms/ n'est pas dans les exports de contenu, voir
content_transfer.MEDIA_KINDS). Emulation : EmulatorJS, servi en local depuis
static/vendor/emulatorjs/ (voir packaging/fetch_emulatorjs.sh).
"""

import json
import os

import config
from db.database import get_db
from managers import settings_manager
from managers.upload_utils import safe_upload_name

SYSTEMS = {
    "nes": {"label": "NES", "core": "fceumm", "extensions": {"nes"}, "max_bytes": 1024 * 1024},
    "md": {"label": "Mega Drive", "core": "genesis_plus_gx", "extensions": {"md", "gen", "bin", "smd"},
           "max_bytes": 8 * 1024 * 1024},
}
COVER_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def system_for_extension(ext):
    for key, system in SYSTEMS.items():
        if ext in system["extensions"]:
            return key
    return None


# --- Bibliotheque ----------------------------------------------------------------

def list_roms(only_active=False):
    query = "SELECT * FROM roms"
    if only_active:
        query += " WHERE active = 1"
    return get_db().execute(query + " ORDER BY sort_order, id").fetchall()


def get_rom(rom_id):
    return get_db().execute("SELECT * FROM roms WHERE id = ?", (rom_id,)).fetchone()


def counts():
    """{"nes": n, "md": n} des jeux actifs."""
    rows = get_db().execute("SELECT system, COUNT(*) AS n FROM roms WHERE active = 1 GROUP BY system").fetchall()
    result = {key: 0 for key in SYSTEMS}
    result.update({row["system"]: row["n"] for row in rows})
    return result


def add_rom_upload(file_storage):
    """Enregistre un fichier de jeu envoye depuis l'admin. Console reconnue a
    l'extension, taille limitee. Renvoie l'id du jeu cree ; leve ValueError
    (message affichable) si le fichier est refuse."""
    name, ext = safe_upload_name(file_storage.filename)
    system = system_for_extension(ext)
    if system is None:
        raise ValueError(f"{file_storage.filename} : format non reconnu (NES : .nes ; Mega Drive : .md .gen .bin .smd)")
    data = file_storage.read(SYSTEMS[system]["max_bytes"] + 1)
    if len(data) > SYSTEMS[system]["max_bytes"]:
        limit = SYSTEMS[system]["max_bytes"] // (1024 * 1024)
        raise ValueError(f"{file_storage.filename} : fichier trop gros pour un jeu {SYSTEMS[system]['label']} (≤ {limit} Mo)")
    if not data:
        raise ValueError(f"{file_storage.filename} : fichier vide")
    os.makedirs(config.ROMS_DIR, exist_ok=True)
    filename = f"{os.urandom(4).hex()}_{name}"
    with open(os.path.join(config.ROMS_DIR, filename), "wb") as f:
        f.write(data)
    title = os.path.splitext(os.path.basename(file_storage.filename.replace("\\", "/")))[0]
    title = title.replace("_", " ").replace(".", " ").strip() or name
    db = get_db()
    max_order = db.execute("SELECT MAX(sort_order) AS m FROM roms").fetchone()["m"] or 0
    cur = db.execute(
        "INSERT INTO roms (title, system, filename, players, sort_order) VALUES (?, ?, ?, ?, ?)",
        (title, system, filename, "1-2", max_order + 1),
    )
    db.commit()
    return cur.lastrowid


def save_cover(file_storage):
    name, ext = safe_upload_name(file_storage.filename)
    if ext not in COVER_EXTENSIONS:
        raise ValueError("Jaquette : image .png, .jpg ou .webp attendue")
    os.makedirs(config.ROM_COVERS_DIR, exist_ok=True)
    filename = f"{os.urandom(4).hex()}_{name}"
    file_storage.save(os.path.join(config.ROM_COVERS_DIR, filename))
    return filename


def update_rom(rom_id, title, players, active, cover_filename=None, clear_cover=False):
    rom = get_rom(rom_id)
    if rom is None:
        raise ValueError("Jeu introuvable")
    cover = rom["cover_filename"]
    if cover_filename:
        _remove(config.ROM_COVERS_DIR, cover)
        cover = cover_filename
    elif clear_cover:
        _remove(config.ROM_COVERS_DIR, cover)
        cover = None
    db = get_db()
    db.execute(
        "UPDATE roms SET title = ?, players = ?, active = ?, cover_filename = ? WHERE id = ?",
        ((title or "").strip() or rom["title"], (players or "").strip() or None, 1 if active else 0, cover, rom_id),
    )
    db.commit()


def set_active(rom_id, active):
    db = get_db()
    db.execute("UPDATE roms SET active = ? WHERE id = ?", (1 if active else 0, rom_id))
    db.commit()


def delete_rom(rom_id):
    """Supprime le jeu ET ses fichiers (ROM, jaquette)."""
    rom = get_rom(rom_id)
    if rom is None:
        return
    _remove(config.ROMS_DIR, rom["filename"])
    _remove(config.ROM_COVERS_DIR, rom["cover_filename"])
    db = get_db()
    db.execute("DELETE FROM roms WHERE id = ?", (rom_id,))
    db.commit()


def _remove(directory, filename):
    if filename:
        try:
            os.remove(os.path.join(directory, os.path.basename(filename)))
        except FileNotFoundError:
            pass


# --- Reglage de la manette ---------------------------------------------------------
#
# EmulatorJS adresse les boutons par "emplacement" de la manette virtuelle
# libretro (RetroPad) : 0 = B, 1 = Y, 2 = Select, 3 = Start, 4-7 = haut, bas,
# gauche, droite, 8 = A, 9 = X, 10 = L, 11 = R. Chaque console y range ses
# propres boutons (ci-dessous). Pour chaque bouton : "pad" = nom du bouton de
# la manette tel que le navigateur le voit (BUTTON_1, DPAD_UP,
# LEFT_STICK_X:+1...), "key" = touche du clavier (noms EmulatorJS : "x",
# "enter", "up arrow"...). Echap est reserve a la sortie.

BUTTONS = {
    "nes": [
        ("up", "Haut", 4), ("down", "Bas", 5), ("left", "Gauche", 6), ("right", "Droite", 7),
        ("a", "A", 8), ("b", "B", 0), ("select", "Select", 2), ("start", "Start", 3),
    ],
    "md": [
        ("up", "Haut", 4), ("down", "Bas", 5), ("left", "Gauche", 6), ("right", "Droite", 7),
        ("a", "A", 1), ("b", "B", 0), ("c", "C", 8), ("start", "Start", 3),
        ("x", "X", 10), ("y", "Y", 9), ("z", "Z", 11), ("mode", "Mode", 2),
    ],
}
SIX_BUTTONS = {"x", "y", "z", "mode"}  # Mega Drive 6 boutons seulement

# Valeurs par defaut : celles d'EmulatorJS (manette « standard » du
# navigateur) ; clavier pour le joueur 1 seulement.
DEFAULT_PAD = {
    0: "BUTTON_2", 1: "BUTTON_4", 2: "SELECT", 3: "START", 4: "DPAD_UP", 5: "DPAD_DOWN",
    6: "DPAD_LEFT", 7: "DPAD_RIGHT", 8: "BUTTON_1", 9: "BUTTON_3", 10: "LEFT_TOP_SHOULDER",
    11: "RIGHT_TOP_SHOULDER",
}
DEFAULT_KEYS = {
    0: "x", 1: "s", 2: "v", 3: "enter", 4: "up arrow", 5: "down arrow", 6: "left arrow",
    7: "right arrow", 8: "z", 9: "a", 10: "q", 11: "e",
}
PLAYERS = (1, 2)
KEY_CONTROLS = "jocs_controls"
KEY_SIX_BUTTONS = "jocs_md_six_buttons"


def default_controls():
    controls = {}
    for system, buttons in BUTTONS.items():
        controls[system] = {}
        for player in PLAYERS:
            controls[system][str(player)] = {
                name: {"pad": DEFAULT_PAD[slot], "key": DEFAULT_KEYS[slot] if player == 1 else ""}
                for name, _, slot in buttons
            }
    return controls


def get_controls():
    """{system: {"1"|"2": {bouton: {"pad", "key"}}}}, valeurs par defaut
    completees pour tout bouton jamais regle."""
    controls = default_controls()
    try:
        stored = json.loads(settings_manager._get(KEY_CONTROLS, None) or "{}")
    except ValueError:
        stored = {}
    for system, players in stored.items():
        for player, buttons in (players or {}).items():
            for name, value in (buttons or {}).items():
                if system in controls and player in controls[system] and name in controls[system][player]:
                    controls[system][player][name].update(
                        {k: str(v) for k, v in (value or {}).items() if k in ("pad", "key")})
    return controls


def set_control(system, player, button, kind, value):
    """Regle un bouton (kind "pad" ou "key"). Valeur vide = aucun."""
    if system not in BUTTONS or int(player) not in PLAYERS or kind not in ("pad", "key"):
        raise ValueError("Réglage inconnu")
    if button not in {name for name, _, _ in BUTTONS[system]}:
        raise ValueError("Bouton inconnu")
    if kind == "key" and value == "escape":
        raise ValueError("Échap est réservé à la sortie du jeu")
    controls = get_controls()
    controls[system][str(player)][button][kind] = value or ""
    settings_manager._set(KEY_CONTROLS, json.dumps(controls))


def reset_controls():
    settings_manager._delete(KEY_CONTROLS)


def get_six_buttons():
    return settings_manager._get(KEY_SIX_BUTTONS, "0") == "1"


def set_six_buttons(enabled):
    settings_manager._set(KEY_SIX_BUTTONS, "1" if enabled else "0")


def emulatorjs_controls(system):
    """Format EJS_defaultControls : {joueur(0-3): {emplacement: {value, value2}}}."""
    controls = get_controls()[system]
    six = get_six_buttons()
    result = {0: {}, 1: {}, 2: {}, 3: {}}
    for player in PLAYERS:
        for name, _, slot in BUTTONS[system]:
            if system == "md" and name in SIX_BUTTONS and not six:
                continue
            value = controls[str(player)][name]
            result[player - 1][slot] = {"value": value["key"], "value2": value["pad"]}
    return result


class PadCapture:
    """Capture d'un bouton de manette pour le reglage de l'emulateur.

    L'admin peut etre ouverte sur un PC distant : la manette, elle, est
    branchee sur la borne. L'admin "arme" donc une capture (arm) ; le
    navigateur de la borne (ecran de la borne, ou la page admin si elle y est
    ouverte) lit la manette et envoie le premier bouton appuye (submit, voir
    static/js/pad-capture.js). Sans capture armee, submit ne fait rien."""

    TIMEOUT = 10

    def __init__(self, app):
        import threading
        self.app = app
        self._lock = threading.Lock()
        self._pending = None
        self._last = None

    def arm(self, system, player, button):
        if system not in BUTTONS or str(player) not in {str(p) for p in PLAYERS}:
            raise ValueError("Réglage inconnu")
        if button not in {name for name, _, _ in BUTTONS[system]}:
            raise ValueError("Bouton inconnu")
        import time
        with self._lock:
            self._pending = {"system": system, "player": str(player), "button": button,
                             "until": time.monotonic() + self.TIMEOUT}
            self._last = None

    def submit(self, label):
        """Bouton recu du navigateur de la borne. Renvoie True s'il a ete
        enregistre (une capture etait armee)."""
        import re
        import time
        if not isinstance(label, str) or not re.fullmatch(r"[A-Z0-9_]{2,30}(:[+-]1)?", label):
            return False
        with self._lock:
            pending = self._pending
            if pending is None or time.monotonic() > pending["until"]:
                self._pending = None
                return False
            self._pending = None
        with self.app.app_context():
            set_control(pending["system"], pending["player"], pending["button"], "pad", label)
        with self._lock:
            self._last = dict(pending, label=label)
        return True

    def cancel(self):
        with self._lock:
            self._pending = None

    def status(self):
        import time
        with self._lock:
            if self._pending and time.monotonic() <= self._pending["until"]:
                return {"waiting": True, "left": round(self._pending["until"] - time.monotonic())}
            self._pending = None
            return {"waiting": False, "last": self._last}
