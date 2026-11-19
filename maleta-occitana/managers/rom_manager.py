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
    "nes": {"label": "NES", "core": "fceumm", "extensions": {"nes"}, "max_bytes": 1024 * 1024,
            "libretro": "Nintendo - Nintendo Entertainment System"},
    "snes": {"label": "Super NES", "core": "snes9x", "extensions": {"sfc", "smc"}, "max_bytes": 8 * 1024 * 1024,
             "libretro": "Nintendo - Super Nintendo Entertainment System"},
    "md": {"label": "Mega Drive", "core": "genesis_plus_gx", "extensions": {"md", "gen", "bin", "smd"},
           "max_bytes": 8 * 1024 * 1024, "libretro": "Sega - Mega Drive - Genesis"},
    "a26": {"label": "Atari 2600", "core": "stella2014", "extensions": {"a26", "bin"}, "max_bytes": 512 * 1024,
            "libretro": "Atari - 2600"},
}
# v1.33 : l'extension .bin sert a la fois a l'Atari 2600 et a la Mega Drive.
# Les jeux Atari 2600 font au plus quelques dizaines de Ko, les jeux Mega
# Drive au moins 128 Ko : en dessous de ce seuil, un .bin est un jeu Atari
# 2600 (la console reste modifiable dans la bibliotheque).
A26_BIN_MAX_BYTES = 64 * 1024
COVER_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
FORMATS_HELP = "NES : .nes ; Super NES : .sfc .smc ; Mega Drive : .md .gen .bin .smd ; Atari 2600 : .a26 .bin"


def system_for_extension(ext, size=None):
    if ext == "bin":
        return "a26" if size is not None and size <= A26_BIN_MAX_BYTES else "md"
    for key, system in SYSTEMS.items():
        if ext in system["extensions"]:
            return key
    return None


def clean_title(filename):
    """Titre affiche tire du nom du fichier : "Super_Mario_Bros._3_(USA).nes"
    -> "Super Mario Bros. 3". Les mentions entre parentheses ou crochets
    (pays, version) sont retirees ; les points du titre sont gardes."""
    import re
    stem = os.path.splitext(os.path.basename((filename or "").replace("\\", "/")))[0]
    stem = stem.replace("_", " ")
    title = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", stem)
    title = re.sub(r"\s+", " ", title).strip(" -")
    return title or re.sub(r"\s+", " ", stem).strip() or "Jòc"


# --- Bibliotheque ----------------------------------------------------------------

def list_roms(only_active=False):
    query = "SELECT * FROM roms"
    if only_active:
        query += " WHERE active = 1"
    return get_db().execute(query + " ORDER BY sort_order, id").fetchall()


def get_rom(rom_id):
    return get_db().execute("SELECT * FROM roms WHERE id = ?", (rom_id,)).fetchone()


def counts():
    """{"nes": n, "snes": n, "md": n, "a26": n} des jeux actifs."""
    rows = get_db().execute("SELECT system, COUNT(*) AS n FROM roms WHERE active = 1 GROUP BY system").fetchall()
    result = {key: 0 for key in SYSTEMS}
    result.update({row["system"]: row["n"] for row in rows})
    return result


def add_rom_upload(file_storage):
    """Enregistre un fichier de jeu envoye depuis l'admin. Console reconnue a
    l'extension (et a la taille pour .bin), taille limitee. Renvoie l'id du
    jeu cree ; leve ValueError (message affichable) si le fichier est refuse."""
    name, ext = safe_upload_name(file_storage.filename)
    if system_for_extension(ext) is None:
        raise ValueError(f"{file_storage.filename} : format non reconnu ({FORMATS_HELP})")
    data = file_storage.read(max(s["max_bytes"] for s in SYSTEMS.values()) + 1)
    system = system_for_extension(ext, len(data))
    if len(data) > SYSTEMS[system]["max_bytes"]:
        limit = SYSTEMS[system]["max_bytes"] / (1024 * 1024)
        limit = f"{limit:g} Mo" if limit >= 1 else f"{SYSTEMS[system]['max_bytes'] // 1024} Ko"
        raise ValueError(f"{file_storage.filename} : fichier trop gros pour un jeu {SYSTEMS[system]['label']} (≤ {limit})")
    if not data:
        raise ValueError(f"{file_storage.filename} : fichier vide")
    os.makedirs(config.ROMS_DIR, exist_ok=True)
    filename = f"{os.urandom(4).hex()}_{name}"
    with open(os.path.join(config.ROMS_DIR, filename), "wb") as f:
        f.write(data)
    title = clean_title(file_storage.filename)
    db = get_db()
    max_order = db.execute("SELECT MAX(sort_order) AS m FROM roms").fetchone()["m"] or 0
    cur = db.execute(
        "INSERT INTO roms (title, system, filename, players, sort_order) VALUES (?, ?, ?, ?, ?)",
        (title, system, filename, "1-2", max_order + 1),
    )
    db.commit()
    return cur.lastrowid


def set_cover(rom_id, cover_filename):
    """Associe une jaquette deja enregistree (save_cover / recherche
    automatique) a un jeu, en supprimant l'ancienne."""
    rom = get_rom(rom_id)
    if rom is None:
        _remove(config.ROM_COVERS_DIR, cover_filename)
        return
    if rom["cover_filename"] and rom["cover_filename"] != cover_filename:
        _remove(config.ROM_COVERS_DIR, rom["cover_filename"])
    db = get_db()
    db.execute("UPDATE roms SET cover_filename = ? WHERE id = ?", (cover_filename, rom_id))
    db.commit()


def save_cover(file_storage):
    name, ext = safe_upload_name(file_storage.filename)
    if ext not in COVER_EXTENSIONS:
        raise ValueError("Jaquette : image .png, .jpg ou .webp attendue")
    os.makedirs(config.ROM_COVERS_DIR, exist_ok=True)
    filename = f"{os.urandom(4).hex()}_{name}"
    file_storage.save(os.path.join(config.ROM_COVERS_DIR, filename))
    return filename


def save_cover_bytes(data, ext):
    os.makedirs(config.ROM_COVERS_DIR, exist_ok=True)
    filename = f"{os.urandom(4).hex()}_jaquette.{ext}"
    with open(os.path.join(config.ROM_COVERS_DIR, filename), "wb") as f:
        f.write(data)
    return filename


def is_cover_file(filename):
    return safe_upload_name(filename)[1] in COVER_EXTENSIONS


def match_cover_upload(file_storage, rom_ids):
    """v1.33 : image envoyee avec les jeux, nommee comme l'un d'eux
    ("Sonic.md" + "Sonic.png") -> jaquette de ce jeu. Cherche parmi rom_ids
    (jeux envoyes en meme temps) puis parmi tous les jeux sans jaquette.
    Renvoie le titre du jeu, ou None si aucun ne correspond."""
    from managers.cover_lookup import normalize
    wanted = normalize(clean_title(file_storage.filename))
    roms = list_roms()
    candidates = [r for r in roms if r["id"] in rom_ids] + [r for r in roms if r["id"] not in rom_ids and not r["cover_filename"]]
    for rom in candidates:
        if wanted and normalize(rom["title"]) == wanted:
            set_cover(rom["id"], save_cover(file_storage))
            return rom["title"]
    return None


def update_rom(rom_id, title, players, active, cover_filename=None, clear_cover=False, system=None):
    rom = get_rom(rom_id)
    if rom is None:
        raise ValueError("Jeu introuvable")
    if system and system not in SYSTEMS:
        raise ValueError("Console inconnue")
    cover = rom["cover_filename"]
    if cover_filename:
        _remove(config.ROM_COVERS_DIR, cover)
        cover = cover_filename
    elif clear_cover:
        _remove(config.ROM_COVERS_DIR, cover)
        cover = None
    db = get_db()
    db.execute(
        "UPDATE roms SET title = ?, players = ?, active = ?, cover_filename = ?, system = ? WHERE id = ?",
        ((title or "").strip() or rom["title"], (players or "").strip() or None, 1 if active else 0, cover,
         system or rom["system"], rom_id),
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
    "snes": [
        ("up", "Haut", 4), ("down", "Bas", 5), ("left", "Gauche", 6), ("right", "Droite", 7),
        ("a", "A", 8), ("b", "B", 0), ("x", "X", 9), ("y", "Y", 1),
        ("l", "L", 10), ("r", "R", 11), ("select", "Select", 2), ("start", "Start", 3),
    ],
    "md": [
        ("up", "Haut", 4), ("down", "Bas", 5), ("left", "Gauche", 6), ("right", "Droite", 7),
        ("a", "A", 1), ("b", "B", 0), ("c", "C", 8), ("start", "Start", 3),
        ("x", "X", 10), ("y", "Y", 9), ("z", "Z", 11), ("mode", "Mode", 2),
    ],
    "a26": [
        ("up", "Haut", 4), ("down", "Bas", 5), ("left", "Gauche", 6), ("right", "Droite", 7),
        ("fire", "Tir (Fire)", 0), ("select", "Select", 2), ("reset", "Reset (démarrer)", 3),
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


KEY_DIAGNOSTIC = "jocs_diagnostic"


def get_diagnostic():
    """v1.31 : affiche pendant la partie les images par seconde et la carte
    graphique utilisee par le navigateur (recherche de la cause d'un jeu
    saccade ou en retard)."""
    return settings_manager._get(KEY_DIAGNOSTIC, "0") == "1"


def set_diagnostic(enabled):
    settings_manager._set(KEY_DIAGNOSTIC, "1" if enabled else "0")


KEY_AUDIO_SYNC = "jocs_audio_sync"


def get_audio_sync():
    """v1.34 : vitesse du jeu calee sur la sortie son (reglage d'origine de
    RetroArch) ou sur l'image (par defaut). Calee sur le son, le jeu ralentit
    des que le tampon audio est plein si la sortie son du navigateur consomme
    un peu moins vite que prevu : 60 images/s au lancement, puis ~45 quelques
    secondes plus tard (constate sur la borne, NES comme Mega Drive)."""
    return settings_manager._get(KEY_AUDIO_SYNC, "0") == "1"


def set_audio_sync(enabled):
    settings_manager._set(KEY_AUDIO_SYNC, "1" if enabled else "0")


def retroarch_extra_config():
    """Lignes ajoutees au retroarch.cfg ecrit par EmulatorJS."""
    return "audio_sync = %s\n" % ("true" if get_audio_sync() else "false")


# v1.34 : combinaison de boutons de manette pour quitter un jeu (retour au
# centre de jòcs), en plus d'Echap au clavier. Noms des boutons au format
# d'EmulatorJS (SELECT, START, BUTTON_1...), toutes manettes confondues.
KEY_QUIT_COMBO = "jocs_quit_combo"
DEFAULT_QUIT_COMBO = {"buttons": ["SELECT", "START"], "hold": 1.0}
QUIT_HOLDS = (0, 1, 2, 3)
PAD_BUTTON_LABELS = {
    "BUTTON_1": "A / Croix (1)", "BUTTON_2": "B / Rond (2)", "BUTTON_3": "X / Carré (3)",
    "BUTTON_4": "Y / Triangle (4)", "LEFT_TOP_SHOULDER": "L", "RIGHT_TOP_SHOULDER": "R",
    "LEFT_BOTTOM_SHOULDER": "L2", "RIGHT_BOTTOM_SHOULDER": "R2", "SELECT": "Select", "START": "Start",
    "LEFT_STICK": "L3", "RIGHT_STICK": "R3", "DPAD_UP": "Haut", "DPAD_DOWN": "Bas",
    "DPAD_LEFT": "Gauche", "DPAD_RIGHT": "Droite",
}
_COMBO_RE = r"[A-Z0-9_]{2,30}"


def get_quit_combo():
    try:
        value = json.loads(settings_manager._get(KEY_QUIT_COMBO, None) or "null")
    except ValueError:
        value = None
    if not isinstance(value, dict):
        return dict(DEFAULT_QUIT_COMBO)
    import re
    buttons = [b for b in value.get("buttons") or [] if isinstance(b, str) and re.fullmatch(_COMBO_RE, b)]
    try:
        hold = float(value.get("hold", DEFAULT_QUIT_COMBO["hold"]))
    except (TypeError, ValueError):
        hold = DEFAULT_QUIT_COMBO["hold"]
    return {"buttons": buttons[:4], "hold": hold if hold in QUIT_HOLDS else DEFAULT_QUIT_COMBO["hold"]}


def set_quit_combo(buttons=None, hold=None):
    """buttons : liste de 2 a 4 boutons, [] = pas de combinaison (Echap
    seulement) ; hold : secondes a maintenir (0 = immediat)."""
    import re
    combo = get_quit_combo()
    if buttons is not None:
        buttons = list(dict.fromkeys(buttons))
        if buttons and not (2 <= len(buttons) <= 4 and all(isinstance(b, str) and re.fullmatch(_COMBO_RE, b) for b in buttons)):
            raise ValueError("Combinaison : 2 à 4 boutons appuyés ensemble")
        combo["buttons"] = buttons
    if hold is not None:
        hold = float(hold)
        if hold not in QUIT_HOLDS:
            raise ValueError("Durée inconnue")
        combo["hold"] = hold
    settings_manager._set(KEY_QUIT_COMBO, json.dumps(combo))


def quit_combo_label(combo=None):
    combo = combo or get_quit_combo()
    return " + ".join(PAD_BUTTON_LABELS.get(b, b) for b in combo["buttons"])


KEY_COVERS_AUTO = "jocs_covers_auto"


def get_covers_auto():
    """v1.33 : recherche automatique de la jaquette a l'ajout d'un jeu."""
    return settings_manager._get(KEY_COVERS_AUTO, "1") == "1"


def set_covers_auto(enabled):
    settings_manager._set(KEY_COVERS_AUTO, "1" if enabled else "0")


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

    def arm_combo(self):
        """v1.34 : capture de la combinaison de sortie (plusieurs boutons
        appuyes ensemble, envoyes au relachement)."""
        import time
        with self._lock:
            self._pending = {"combo": True, "until": time.monotonic() + self.TIMEOUT}
            self._last = None

    def armed_kind(self):
        with self._lock:
            return "combo" if self._pending and self._pending.get("combo") else "button"

    def submit_combo(self, labels):
        import time
        if not isinstance(labels, list):
            return False
        with self._lock:
            pending = self._pending
            if pending is None or not pending.get("combo") or time.monotonic() > pending["until"]:
                return False
        try:
            with self.app.app_context():
                set_quit_combo(buttons=labels)
        except ValueError as exc:
            with self._lock:
                self._pending = None
                self._last = {"combo": True, "error": str(exc)}
            return False
        with self._lock:
            self._pending = None
            self._last = {"combo": True, "labels": labels}
        return True

    def submit(self, label):
        """Bouton recu du navigateur de la borne. Renvoie True s'il a ete
        enregistre (une capture etait armee)."""
        import re
        import time
        if not isinstance(label, str) or not re.fullmatch(r"[A-Z0-9_]{2,30}(:[+-]1)?", label):
            return False
        with self._lock:
            pending = self._pending
            if pending is None or pending.get("combo") or time.monotonic() > pending["until"]:
                if pending is not None and not pending.get("combo"):
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
