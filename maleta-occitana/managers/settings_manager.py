"""Réglages généraux modifiables depuis l'admin (v0.2, section "Configuration").

Table cle/valeur simple (`settings`, voir db/schema.sql) : chaque reglage a
une cle connue et une valeur par defaut utilisee tant que rien n'a ete
enregistre en base (donc une base toute neuve se comporte exactement comme
avant la v0.2, sans configuration prealable requise).

Regroupe ici plutot que disperse dans blueprints/admin.py : c'est le SEUL
endroit qui connait a la fois les cles utilisees et leurs valeurs par
defaut -- le reste du code (blueprints, game_controller, input_bus, les
templates) passe toujours par les fonctions de ce module, jamais par des
requetes SQL directes sur `settings`.
"""

import json
import os

from managers.upload_utils import safe_upload_name

from db.database import get_db
import config

# --- PIN admin --------------------------------------------------------------

KEY_ADMIN_PIN = "admin_pin"


def get_admin_pin():
    return _get(KEY_ADMIN_PIN, config.ADMIN_PIN)


def set_admin_pin(new_pin):
    _set(KEY_ADMIN_PIN, new_pin)


def reset_admin_pin():
    """Efface le PIN enregistre en base : au prochain acces, get_admin_pin()
    retombe sur config.ADMIN_PIN (variable d'environnement MALETA_ADMIN_PIN).
    Utilise au demarrage si MALETA_RESET_ADMIN_PIN=1 (voir run_pc.py) --
    filet de securite en cas de PIN oublie apres un changement depuis l'admin."""
    _delete(KEY_ADMIN_PIN)


# --- Modele d'interface (v1.1) -------------------------------------------------
#
# v1.1 (demande par Fabien, maquettes « La Maleta Occitana — 3 directions ») :
# les 4 palettes de couleur des versions precedentes sont remplacees par
# 3 MODELES complets -- chacun change les couleurs ET les polices, les formes,
# la mise en page et les decorations de TOUS les ecrans de la borne, ainsi
# que l'apparence de l'admin. "senhal" est le modele par defaut (premier des
# maquettes). La cle de reglage reste "theme" en base : une ancienne valeur
# (palette "occitan", "miegjorn"...) n'est plus reconnue et retombe donc
# simplement sur le modele par defaut, sans migration a faire.
# CSS correspondants : static/css/kiosk-<cle>.css et static/css/admin.css
# (bloc [data-template=<cle>]).

KEY_THEME = "theme"
DEFAULT_THEME = "senhal"

TEMPLATES = {
    "senhal": {
        "label": "Senhal",
        "description": "Jaune et rouge de la crotz occitana, gros caractères et contours noirs — très lisible de loin.",
        "swatches": ["#F5C518", "#B3141C", "#1C1210", "#FFF4DC"],
    },
    "mercat": {
        "label": "Mercat",
        "description": "Ambiance marché du Sud : terre cuite, olive et soleil, formes arrondies.",
        "swatches": ["#FBF3E4", "#B4472A", "#55612A", "#F2B33D"],
    },
    "nuech": {
        "label": "Nuèch",
        "description": "Bleu nuit étoilé et or, typographie à empattements — plus calme, pour une salle sombre.",
        "swatches": ["#10172E", "#E8B54A", "#F0745A", "#F4EDE0"],
    },
}
# Compatibilite : l'ancien nom (THEMES) reste disponible pour le code ou les
# scripts qui y feraient encore reference.
THEMES = TEMPLATES


def get_theme():
    """Cle du modele d'interface actif (toujours une cle valide de TEMPLATES)."""
    theme = _get(KEY_THEME, DEFAULT_THEME)
    return theme if theme in TEMPLATES else DEFAULT_THEME


def set_theme(theme_key):
    if theme_key not in TEMPLATES:
        raise ValueError(f"modele inconnu : {theme_key!r} (choix possibles : {sorted(TEMPLATES)})")
    _set(KEY_THEME, theme_key)


get_template = get_theme
set_template = set_theme


# --- Logo / croix personnalises -----------------------------------------------

KEY_LOGO_FILENAME = "logo_filename"
KEY_CROTZ_FILENAME = "crotz_filename"


def get_branding():
    """Utilise par le kiosque (ecran titre) a chaque chargement de page."""
    return {
        "theme": get_theme(),
        "logo_filename": _get(KEY_LOGO_FILENAME, None),
        "crotz_filename": _get(KEY_CROTZ_FILENAME, None),
    }


def set_logo_filename(filename):
    _set(KEY_LOGO_FILENAME, filename)


def set_crotz_filename(filename):
    _set(KEY_CROTZ_FILENAME, filename)


def save_branding_upload(file_storage):
    """Enregistre un logo/une image de croix uploade et renvoie son nom de
    fichier. Meme principe que object_manager._save_upload, dossier a part
    (config.BRANDING_DIR)."""
    if file_storage is None or file_storage.filename == "":
        return None
    # v0.72 (revue de code) : meme correctif que object_manager._save_upload.
    # v1.03 : voir managers/upload_utils.py (extension traitee a part)
    filename, ext = safe_upload_name(file_storage.filename)
    if ext not in config.ALLOWED_BRANDING_EXTENSIONS:
        raise ValueError(
            f"extension .{ext} non autorisee (autorise : {sorted(config.ALLOWED_BRANDING_EXTENSIONS)})"
        )
    os.makedirs(config.BRANDING_DIR, exist_ok=True)
    safe_name = f"{os.urandom(4).hex()}_{filename}"
    file_storage.save(os.path.join(config.BRANDING_DIR, safe_name))
    return safe_name


# --- Textes du kiosque personnalisables (v0.10) --------------------------------
#
# v0.10 (16/09/2026, demande par Fabien) : "peut être voir si on peut pas
# avoir [...] la possibilité de changer le texte, les infos ou directives
# afin qu'une école puisse mieux adapter pour elle". Premiere passe
# volontairement RESTREINTE aux quelques textes les plus visibles de l'ecran
# d'accueil/menu (plutot que TOUT rendre editable d'un coup, ce qui
# multiplierait les endroits ou une saisie malheureuse pourrait casser
# l'affichage) -- a completer si Fabien signale d'autres textes a rendre
# editables. Meme principe que le branding (theme/logo/croix) juste au-dessus :
# une valeur par defaut identique au texte actuel (donc une base neuve, ou
# une ecole qui ne personnalise rien, affiche EXACTEMENT comme avant cette
# version), une surcharge par cle stockee en JSON dans `settings`.
KEY_KIOSK_TEXTS = "kiosk_texts"

DEFAULT_KIOSK_TEXTS = {
    "brand_name": "La Maleta Occitana",
    "attract_title": "Pausa un objècte",
    "attract_subtitle": "sus la Maleta !",
    "attract_hint": (
        "Pose un objet du quotidien sur la valise pour découvrir son nom en "
        "occitan, ou appuie sur un bouton pour choisir un jeu."
    ),
    "menu_title": "Tria un jòc",
    "nfc_banner_oc": "Pausa un objècte sus la maleta",
    "nfc_banner_fr": (
        "Pose un objet du quotidien pour entendre son nom en occitan — sans "
        "rien choisir."
    ),
}

# Libelles (cote admin uniquement) decrivant chaque champ, pour le formulaire
# de Configuration -- pas de texte occitan/francais invente ici, uniquement
# une description NEUTRE en francais de ce que le champ affiche et ou.
KIOSK_TEXT_FIELDS = [
    {"key": "brand_name", "label": "Nom de la borne (écran d'accueil et menu)", "multiline": False},
    {"key": "attract_title", "label": "Titre principal, écran d'accueil", "multiline": False},
    {"key": "attract_subtitle", "label": "Sous-titre, écran d'accueil", "multiline": False},
    {"key": "attract_hint", "label": "Phrase d'explication, écran d'accueil", "multiline": True},
    {"key": "menu_title", "label": "Titre du menu de jeux", "multiline": False},
    {"key": "nfc_banner_oc", "label": "Bandeau « pose un objet », ligne occitane (menu)", "multiline": False},
    {"key": "nfc_banner_fr", "label": "Bandeau « pose un objet », ligne française (menu)", "multiline": True},
]


def get_kiosk_texts():
    """Renvoie DEFAULT_KIOSK_TEXTS avec les eventuelles surcharges enregistrees
    en base. Un champ non renseigne (ou reduit a du vide) retombe sur sa
    valeur par defaut plutot que d'afficher un texte vide sur le kiosque."""
    raw = _get(KEY_KIOSK_TEXTS, None)
    overrides = {}
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                overrides = {
                    k: v for k, v in parsed.items()
                    if k in DEFAULT_KIOSK_TEXTS and str(v).strip()
                }
        except (ValueError, TypeError, AttributeError):
            overrides = {}
    texts = dict(DEFAULT_KIOSK_TEXTS)
    texts.update(overrides)
    return texts


def set_kiosk_texts(texts):
    """texts : {champ: valeur}. Un champ absent du dict, ou dont la valeur est
    vide/uniquement des espaces, est retire de la surcharge -- revient donc
    automatiquement au texte par defaut (pas besoin d'un bouton "reinitialiser"
    distinct : vider le champ dans le formulaire suffit)."""
    cleaned = {
        k: v.strip() for k, v in texts.items()
        if k in DEFAULT_KIOSK_TEXTS and str(v).strip()
    }
    _set(KEY_KIOSK_TEXTS, json.dumps(cleaned))


# --- Mapping manette ----------------------------------------------------------

KEY_GAMEPAD_BUTTON_MAP = "gamepad_button_map"
KEY_GAMEPAD_HAT_MAP = "gamepad_hat_map"
KEY_GAMEPAD_AXIS_MAP = "gamepad_axis_map"

# Actions configurables depuis l'admin.
#
# v0.3 (14/09/2026) : "left"/"right" ont rejoint cette liste, suite a un
# premier signalement de Fabien -- la croix directionnelle de sa manette ne
# fonctionnait pas du tout. A l'epoque, l'hypothese etait que la croix
# remontait comme des boutons numerotes (JOYBUTTONDOWN) plutot que comme un
# "hat" pygame (DEFAULT_HAT_MAP) -- insuffisant, voir v0.4 ci-dessous.
#
# v0.4 (14/09/2026) : le retour de Fabien apres le v0.3 ("la croix n'est
# toujours pas reconnue, meme pas capturable dans l'ecran Réassigner") a
# montre que ni le hat ni le bouton n'etaient en cause sur sa manette --
# elle remonte en fait la croix comme deux AXES analogiques dedies
# (JOYAXISMOTION), un TROISIEME mecanisme cote pygame/SDL, plus courant
# qu'on ne le pense sur les adaptateurs USB bon marche. Voir
# managers/input_bus.py (DEFAULT_AXIS_MAP, AXIS_PRESS_THRESHOLD) pour le
# detail technique. Cote admin, rien de plus a AUTORISER ici (contrairement
# au v0.3) : "left"/"right" etaient deja des actions assignables depuis la
# v0.3, le probleme etait uniquement que le mecanisme de capture/dispatch
# ne savait pas ecouter les axes. C'est desormais le cas -- voir
# assign_gamepad_control() ci-dessous, qui remplace assign_gamepad_button()
# et gere les trois mecanismes (bouton, hat, axe) de maniere unifiee.
GAMEPAD_ACTIONS = [
    {"action": "select", "label": "Valider / entrer (A)"},
    {"action": "back", "label": "Retour au menu (B)"},
    {"action": "left", "label": "Gauche (menu / croix directionnelle)"},
    {"action": "right", "label": "Droite (menu / croix directionnelle)"},
    # v0.9 (16/09/2026, demande par Fabien) : "haut"/"bas" rejoignent "gauche"/
    # "droite" -- utilises dans le menu (equivalents a gauche/droite, la
    # grille de tuiles n'ayant pas un nombre de colonnes fixe cote serveur),
    # sur l'ecran de choix Memòria "Quantas cartas ?" (equivalents a gauche/
    # droite egalement, un choix binaire) et, surtout, pour un vrai
    # deplacement de RANGEE dans la grille de cartes du Memòria (voir
    # config.MEMORIA_GRID_COLUMNS et game_controller.py, on_action). Valeur
    # par defaut sur l'axe Y du hat de la croix directionnelle (voir
    # DEFAULT_HAT_MAP dans input_bus.py) -- comme pour "left"/"right", aucune
    # valeur par defaut sur bouton ou axe dedie (trop variable d'une manette a
    # l'autre, meme raisonnement que "left"/"right" sur l'axe en v0.4).
    {"action": "up", "label": "Haut (menu / croix directionnelle)"},
    {"action": "down", "label": "Bas (menu / croix directionnelle)"},
    {"action": "answer_1", "label": "Ven de l'occitan ? : réponse 1"},
    {"action": "answer_2", "label": "Ven de l'occitan ? : réponse 2"},
    {"action": "start_idle", "label": "Lancer le diaporama (Start)"},
    # v0.7 (15/09/2026) : jeu "Duèl Occitan" -- demande par Fabien comme un
    # jeu a 2 joueurs sur UNE SEULE manette (2 boutons par joueur, ex. A/B
    # pour le joueur 1 et X/Y pour le joueur 2 -- "à configurer" selon ses
    # mots). Contrairement a "answer_1"/"answer_2" (Vertadièr), ces 4 actions
    # n'ont PAS de bouton assigne par defaut : sur une manette SNES USB
    # classique a 8 boutons, les 6 autres actions ci-dessus occupent deja
    # tous les boutons sauf L/R -- impossible de deviner 4 boutons libres qui
    # conviennent sans connaitre le choix de Fabien (memes principe que
    # "left"/"right" sur l'axe dedie en v0.4 : aucune valeur par defaut
    # fiable). "back" (B ET Select) reste volontairement INCHANGE et continue
    # a permettre d'abandonner le Duèl vers le menu -- voir
    # game_controller.py, STATE_DUEL. A assigner depuis Configuration >
    # Manette avant de pouvoir jouer au Duèl Occitan a la manette.
    {"action": "duel_p1_a", "label": "Duèl Occitan : joueur 1 — réponse A"},
    {"action": "duel_p1_b", "label": "Duèl Occitan : joueur 1 — réponse B"},
    {"action": "duel_p2_a", "label": "Duèl Occitan : joueur 2 — réponse A"},
    {"action": "duel_p2_b", "label": "Duèl Occitan : joueur 2 — réponse B"},
    # v0.8 : jeu "Quiz Calandreta" -- 3 reponses possibles (a/b/c) au lieu de
    # 2 pour Vertadièr. Pas de bouton assigne par defaut (meme principe que
    # les actions Duèl ci-dessus).
    {"action": "answer_3", "label": "Quiz Calandreta : réponse 3"},
]


# v1.02 (16/09/2026, demande par Fabien) : la table Configuration > Manèta &
# clavièr listait toutes les actions a plat (une quinzaine de lignes,
# melangeant navigation generale et reponses de jeu) -- devenu difficile a
# lire au fil des versions. Fabien a demande des SECTIONS par activite,
# "général, tròba l'objècte, memòria, etc." -- y compris pour les activites
# qui n'ont aucun bouton dedie, pour que ce soit explicite plutot que de
# laisser deviner. Structure separee de GAMEPAD_ACTIONS (plutot qu'un simple
# champ "categorie" par action) car deux actions (answer_1/answer_2) sont
# reellement PARTAGEES entre deux activites (Ven de l'occitan (ex-« Ven de l'occitan ») ET Quiz
# Calandreta) -- une categorie unique par action n'aurait pas pu le
# representer correctement. Purement une reorganisation d'affichage cote
# admin : ne change rien au comportement du kiosque ni aux actions elles-
# memes, `action` reste toujours la cle utilisee partout ailleurs (dispatch,
# mappings, GAMEPAD_ACTIONS).
ACTIVITY_CONTROL_SECTIONS = [
    {
        "title": "Général (menu et tous les écrans)",
        "note": (
            "Ces contrôles fonctionnent partout : valider/entrer, revenir au "
            "menu, se déplacer. Le diaporama (écran de veille) se ferme "
            "aussi avec n'importe lequel de ces contrôles."
        ),
        "actions": ["select", "back", "left", "right", "up", "down", "start_idle"],
    },
    {
        "title": "Tròba l'objècte",
        "note": (
            "Aucun bouton dédié : on répond en posant l'objet sur le "
            "lecteur NFC, pas à la manette. Seuls les contrôles généraux "
            "ci-dessus s'appliquent (ex. « Retour au menu » pour abandonner "
            "une manche en cours)."
        ),
        "actions": [],
    },
    {
        "title": "Ven de l'occitan ?",
        "note": None,
        "actions": ["answer_1", "answer_2"],
    },
    {
        "title": "Duèl Occitan",
        "note": None,
        "actions": ["duel_p1_a", "duel_p1_b", "duel_p2_a", "duel_p2_b"],
    },
    {
        "title": "Quiz Calandreta",
        "note": (
            "Réponses A et B : mêmes contrôles que « Ven de l'occitan ? » "
            "ci-dessus (partagés entre les deux jeux, se reconfigurent au "
            "même endroit) — seule la réponse C ci-dessous est spécifique "
            "au Quiz Calandreta."
        ),
        "actions": ["answer_3"],
    },
    {
        "title": "Memòria & Memòria vilatge",
        "note": (
            "Aucun bouton dédié : « Valider / entrer » retourne une carte, "
            "« Retour au menu » abandonne la partie, les directions "
            "déplacent le curseur dans la grille — uniquement les contrôles "
            "généraux ci-dessus."
        ),
        "actions": [],
    },
]


def _normalize_action_list(value):
    """v0.81 : les mappings manette/clavier stockent desormais une LISTE
    d'actions par controle physique (voir note en tete de
    managers/input_bus.py) plutot qu'une seule. Convertit en douceur une
    valeur au format v0.8 et anterieur (une simple chaine `action`) vers ce
    nouveau format `[action, ...]`, pour ne pas perdre les assignations deja
    enregistrees en base par Fabien lors de la mise a jour."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return list(value)
    return []


def get_gamepad_button_map():
    """Renvoie {button_index(int): [action(str), ...]}. None si rien n'est
    encore enregistre en base -- l'appelant (app.py) retombe alors sur
    managers.input_bus.DEFAULT_BUTTON_MAP."""
    raw = _get(KEY_GAMEPAD_BUTTON_MAP, None)
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        return {int(k): _normalize_action_list(v) for k, v in parsed.items()}
    except (ValueError, TypeError, AttributeError):
        return None


def set_gamepad_button_map(button_map):
    """button_map : {button_index(int): [action(str), ...]}."""
    _set(KEY_GAMEPAD_BUTTON_MAP, json.dumps({str(k): list(v) for k, v in button_map.items()}))


def get_gamepad_hat_map():
    """Renvoie {(x(int), y(int)): [action, ...]}. None si rien n'est encore
    enregistre en base -- l'appelant (app.py) retombe alors sur
    managers.input_bus.DEFAULT_HAT_MAP."""
    raw = _get(KEY_GAMEPAD_HAT_MAP, None)
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        return {_str_to_int_pair(k): _normalize_action_list(v) for k, v in parsed.items()}
    except (ValueError, TypeError, AttributeError):
        return None


def set_gamepad_hat_map(hat_map):
    """hat_map : {(x(int), y(int)): [action, ...]}."""
    _set(KEY_GAMEPAD_HAT_MAP, json.dumps({f"{k[0]}_{k[1]}": list(v) for k, v in hat_map.items()}))


def get_gamepad_axis_map():
    """Renvoie {(axis_index(int), sign(-1|1)): [action, ...]}. None si rien
    n'est encore enregistre en base -- l'appelant (app.py) retombe alors sur
    managers.input_bus.DEFAULT_AXIS_MAP (vide par defaut : voir input_bus.py,
    aucune valeur par defaut fiable ne peut etre devinee pour l'indice d'axe,
    qui varie trop d'une manette a l'autre -- v0.4)."""
    raw = _get(KEY_GAMEPAD_AXIS_MAP, None)
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        return {_str_to_int_pair(k): _normalize_action_list(v) for k, v in parsed.items()}
    except (ValueError, TypeError, AttributeError):
        return None


def set_gamepad_axis_map(axis_map):
    """axis_map : {(axis_index(int), sign(-1|1)): [action, ...]}."""
    _set(KEY_GAMEPAD_AXIS_MAP, json.dumps({f"{k[0]}_{k[1]}": list(v) for k, v in axis_map.items()}))


def assign_gamepad_control(action, captured):
    """v0.4 : remplace assign_gamepad_button(). Assigne un CONTROLE manette
    (bouton, hat ou axe -- `captured` a la forme renvoyee par
    InputBus.poll_capture(), voir managers/input_bus.py) a une action,
    en partant des trois mappings actuels (ceux en base, ou les mappings par
    defaut si rien n'est encore enregistre).

    Une action ne peut avoir qu'UNE SEULE assignation active a la fois,
    quel que soit le mecanisme : si "left" etait assignee a un bouton et
    qu'on la reassigne maintenant a un axe, l'ancienne assignation bouton
    est retiree (sinon on se retrouverait avec deux controles physiques
    declenchant la meme action, source de confusion en configuration).

    v0.81 : en revanche, le controle physique CIBLE (le bouton/hat/axe
    capture) peut deja declencher d'autres actions -- on ne l'ecrase plus,
    on AJOUTE `action` a sa liste. C'est le correctif demande par Fabien : le
    bouton A doit pouvoir a la fois valider un menu, repondre a un quiz et
    retourner une carte au Memòria.

    Renvoie (button_map, hat_map, axis_map) -- a repercuter sur l'InputBus
    en cours d'execution via set_button_map/set_hat_map/set_axis_map (voir
    blueprints/admin.py gamepad_assign)."""
    from managers.input_bus import DEFAULT_BUTTON_MAP, DEFAULT_HAT_MAP, DEFAULT_AXIS_MAP

    button_map = get_gamepad_button_map()
    if button_map is None:
        button_map = {k: list(v) for k, v in DEFAULT_BUTTON_MAP.items()}
    hat_map = get_gamepad_hat_map()
    if hat_map is None:
        hat_map = {k: list(v) for k, v in DEFAULT_HAT_MAP.items()}
    axis_map = get_gamepad_axis_map()
    if axis_map is None:
        axis_map = {k: list(v) for k, v in DEFAULT_AXIS_MAP.items()}

    # Retire l'action de toute assignation existante, quel que soit le
    # mecanisme (elle n'aura plus qu'UN SEUL controle actif au final) --
    # mais laisse intactes les AUTRES actions eventuellement partagees par
    # ces memes controles.
    button_map = {b: [a for a in acts if a != action] for b, acts in button_map.items()}
    button_map = {b: acts for b, acts in button_map.items() if acts}
    hat_map = {h: [a for a in acts if a != action] for h, acts in hat_map.items()}
    hat_map = {h: acts for h, acts in hat_map.items() if acts}
    axis_map = {ax: [a for a in acts if a != action] for ax, acts in axis_map.items()}
    axis_map = {ax: acts for ax, acts in axis_map.items() if acts}

    kind = captured.get("kind")
    if kind == "button":
        button = int(captured["button"])
        button_map.setdefault(button, [])
        if action not in button_map[button]:
            button_map[button].append(action)
    elif kind == "hat":
        x, y = captured["value"]
        hat = (int(x), int(y))
        hat_map.setdefault(hat, [])
        if action not in hat_map[hat]:
            hat_map[hat].append(action)
    elif kind == "axis":
        axis = (int(captured["axis"]), int(captured["sign"]))
        axis_map.setdefault(axis, [])
        if action not in axis_map[axis]:
            axis_map[axis].append(action)
    else:
        raise ValueError(f"type de controle manette inconnu : {kind!r}")

    set_gamepad_button_map(button_map)
    set_gamepad_hat_map(hat_map)
    set_gamepad_axis_map(axis_map)
    return button_map, hat_map, axis_map


def _str_to_int_pair(key):
    a, b = key.split("_", 1)
    return (int(a), int(b))


# --- Mapping clavier (v0.8) -----------------------------------------------
#
# Demande par Fabien : en plus de la manette, pouvoir assigner des touches de
# CLAVIER aux memes actions logiques (ex. fleche gauche du clavier ET fleche
# gauche de la manette doivent toutes les deux faire "left") -- les deux
# mecanismes doivent COEXISTER, jamais se remplacer l'un l'autre. C'est donc
# une table de mapping totalement independante des 3 tables manette
# ci-dessus : assign_gamepad_control() ci-dessus ne touche jamais au mapping
# clavier, et assign_keyboard_key() ci-dessous ne touche jamais aux mappings
# manette.
#
# Contrairement a la manette (capture cote serveur via pygame, voir
# input_bus.py), la capture d'une touche clavier se fait entierement cote
# NAVIGATEUR (kiosk.js pour le jeu, config.html pour l'ecran d'assignation) :
# un simple ecouteur "keydown" suffit, pas besoin de polling serveur. La cle
# stockee ici est la meme chaine normalisee que celle envoyee par le
# navigateur (voir kiosk.js : touches d'un seul caractere en minuscule,
# sinon event.key tel quel -- ex. "arrowleft", "a", "enter").
KEY_GAMEPAD_KEY_MAP = "gamepad_key_map"


def get_gamepad_key_map():
    """Renvoie {key(str): [action(str), ...]}. {} si rien n'est encore
    enregistre en base -- contrairement aux mappings manette, PAS de valeur
    par defaut : aucune touche n'est assignee tant que Fabien ne l'a pas
    fait depuis Configuration (une touche assignee par defaut pourrait
    entrer en conflit avec la saisie clavier d'un formulaire admin ouvert
    dans le meme navigateur).

    v0.81 : chaque touche peut desormais declencher PLUSIEURS actions (voir
    la note en tete de managers/input_bus.py) -- `_normalize_action_list`
    accepte aussi l'ancien format v0.8 (une simple chaine par touche) pour
    ne pas perdre les assignations deja enregistrees par Fabien."""
    raw = _get(KEY_GAMEPAD_KEY_MAP, None)
    if raw is None:
        return {}
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        return {str(k): _normalize_action_list(v) for k, v in parsed.items()}
    except (ValueError, TypeError, AttributeError):
        return {}


# v1.2 : version de demo -- un PC de bureau n'a generalement pas de manette :
# ce mapping clavier est enregistre au premier demarrage de la demo (jamais
# sur la borne, ou aucune touche n'est assignee par defaut, voir ci-dessus).
# Reste modifiable depuis Configuration > Manèta & clavièr. Duèl : touches
# S/D (joueur 1) et K/L (joueur 2), voisines en AZERTY comme en QWERTY.
DEMO_KEY_MAP = {
    "ArrowLeft": ["left"],
    "ArrowRight": ["right"],
    "ArrowUp": ["up"],
    "ArrowDown": ["down"],
    "Enter": ["select"],
    "Escape": ["back"],
    "1": ["answer_1"],
    "2": ["answer_2"],
    "3": ["answer_3"],
    "p": ["start_idle"],
    "s": ["duel_p1_a"],
    "d": ["duel_p1_b"],
    "k": ["duel_p2_a"],
    "l": ["duel_p2_b"],
}


def seed_demo_key_map():
    """v1.2 (demo) : garantit qu'en demo CHAQUE action a une touche. Au
    premier demarrage, enregistre DEMO_KEY_MAP ; ensuite, ne complete que
    les actions restees sans touche (avec leur touche par defaut, si elle
    n'est pas deja prise) -- sans jamais modifier une touche choisie."""
    if _get(KEY_GAMEPAD_KEY_MAP, None) is None:
        set_gamepad_key_map(DEMO_KEY_MAP)
        return
    key_map = get_gamepad_key_map()
    assigned = {a for acts in key_map.values() for a in acts}
    changed = False
    for key, actions in DEMO_KEY_MAP.items():
        for action in actions:
            if action not in assigned and key not in key_map:
                key_map[key] = [action]
                changed = True
    if changed:
        set_gamepad_key_map(key_map)


def set_gamepad_key_map(key_map):
    """key_map : {key(str): [action(str), ...]}."""
    _set(KEY_GAMEPAD_KEY_MAP, json.dumps({k: list(v) for k, v in key_map.items()}))


def assign_keyboard_key(action, key):
    """Assigne une touche clavier a une action, en retirant d'abord cette
    action de toute AUTRE touche a laquelle elle etait deja assignee (une
    action ne peut avoir qu'UNE SEULE touche active a la fois -- meme
    logique que assign_gamepad_control, mais uniquement au sein du mapping
    clavier : ne touche jamais aux mappings manette).

    v0.81 : la touche CIBLE, elle, peut deja declencher d'autres actions --
    on ne l'ecrase plus, on y AJOUTE `action` (meme principe que
    assign_gamepad_control : le bouton/la touche "A" peut ainsi valider un
    menu ET repondre a un quiz ET retourner une carte au Memòria). Une
    action peut par ailleurs avoir a la fois une touche ET un controle
    manette assignes -- c'est le but recherche depuis la v0.8.

    Renvoie le nouveau key_map complet."""
    key_map = get_gamepad_key_map()
    key_map = {k: [a for a in acts if a != action] for k, acts in key_map.items()}
    key_map = {k: acts for k, acts in key_map.items() if acts}
    key_str = str(key)
    key_map.setdefault(key_str, [])
    if action not in key_map[key_str]:
        key_map[key_str].append(action)
    set_gamepad_key_map(key_map)
    return key_map


def unassign_keyboard_key(action):
    """Retire l'action de la touche clavier a laquelle elle est assignee (si
    elle existe) -- necessaire car, contrairement aux 3 mecanismes manette
    (mutuellement exclusifs, donc automatiquement remplaces), rien ne
    "supersede" automatiquement une assignation clavier existante. Ne
    touche pas aux autres actions eventuellement partagees par cette meme
    touche. Renvoie le nouveau key_map complet."""
    key_map = get_gamepad_key_map()
    key_map = {k: [a for a in acts if a != action] for k, acts in key_map.items()}
    key_map = {k: acts for k, acts in key_map.items() if acts}
    set_gamepad_key_map(key_map)
    return key_map


# --- Libelles de controle (v0.10) -----------------------------------------
#
# v0.10 (16/09/2026, signale par Fabien) : "je configure le bouton A pour
# valider c'est dommage que le jeux parle d'un Y par ex" -- avant cette
# version, les ecrans du kiosque (Vertadièr, Duèl, Quiz, hints du menu/
# Memòria...) affichaient des lettres A/B/X/Y codees EN DUR, qui supposaient
# une disposition de manette SNES precise (voir DEFAULT_BUTTON_MAP dans
# input_bus.py). Des que Fabien reassigne une action a un AUTRE controle
# (ou joue avec une manette qui n'a pas cette disposition), ces lettres ne
# correspondent plus a rien de reel. Les deux fonctions ci-dessous calculent
# le VRAI controle assigne a chaque action, a partir de la meme source de
# verite que l'ecran admin Configuration (qui affichait deja correctement
# les assignations, lui) :
#   - build_action_control_labels() : le calcul EXACT deja utilise par
#     blueprints/admin.py (config_home()) avant la v0.10 -- deplace ici pour
#     que les DEUX ecrans (admin ET kiosque) partagent un seul calcul,
#     plutot que d'avoir deux implementations qui pourraient diverger.
#     Format verbeux ("Bouton 3", "Croix (hat) ▲ haut"), pense pour un
#     tableau avec de la place -- inchange par rapport a l'existant.
#   - build_kiosk_action_labels() : un format COURT derive du meme calcul,
#     pense pour les pastilles/hints du kiosque (peu de place, et le
#     kiosque ne doit jamais employer un mot invente en occitan ou en
#     francais pour designer un bouton/une touche -- seulement l'identifiant
#     technique du controle lui-meme : un numero, une fleche, ou le nom brut
#     de la touche, jamais une traduction).

HAT_ARROWS = {
    (-1, 0): "◀ gauche",
    (1, 0): "▶ droite",
    (0, 1): "▲ haut",
    (0, -1): "▼ bas",
}

HAT_ARROWS_SHORT = {
    (-1, 0): "◀",
    (1, 0): "▶",
    (0, 1): "▲",
    (0, -1): "▼",
}


def build_action_control_labels():
    """Renvoie (action_to_label, action_to_key) -- le libelle manette (bouton/
    hat/axe fusionnes, une seule ligne par action comme avant) et le libelle
    clavier, exactement le calcul utilise par l'ecran admin Configuration."""
    from managers.input_bus import DEFAULT_BUTTON_MAP, DEFAULT_HAT_MAP, DEFAULT_AXIS_MAP

    button_map = get_gamepad_button_map()
    if button_map is None:
        button_map = {k: list(v) for k, v in DEFAULT_BUTTON_MAP.items()}
    hat_map = get_gamepad_hat_map()
    if hat_map is None:
        hat_map = {k: list(v) for k, v in DEFAULT_HAT_MAP.items()}
    axis_map = get_gamepad_axis_map()
    if axis_map is None:
        axis_map = {k: list(v) for k, v in DEFAULT_AXIS_MAP.items()}

    action_to_label = {}
    for button, actions in button_map.items():
        for action in actions:
            action_to_label.setdefault(action, f"Bouton {button}")
    for (x, y), actions in hat_map.items():
        for action in actions:
            action_to_label.setdefault(action, f"Croix (hat) {HAT_ARROWS.get((x, y), f'({x},{y})')}")
    for (axis, sign), actions in axis_map.items():
        for action in actions:
            action_to_label.setdefault(action, f"Axe {axis} ({'−' if sign < 0 else '+'})")

    action_to_key = {}
    for key, actions in get_gamepad_key_map().items():
        for action in actions:
            # v1.03 : la barre d'espace est stockee " " -- illisible telle quelle
            action_to_key.setdefault(action, "Espace (␣)" if key == " " else key)

    return action_to_label, action_to_key


def _short_key_label(key):
    """Libelle court d'une touche clavier pour le kiosque. v1.03 : la barre
    d'espace (stockee " ") s'affichait comme un badge vide -- remplacee par
    le symbole standard de l'espace, sans mot a traduire."""
    if key == " ":
        return "␣"
    return key.upper() if len(key) == 1 else key


def build_kiosk_action_labels():
    """Libelle COURT par action, pense pour l'affichage sur le kiosque (voir
    note ci-dessus) : prefere le controle manette (entree principale d'une
    borne de stand) ; s'il y a AUSSI une touche clavier assignee, les deux
    sont combines ("3 / E") ; si seul le clavier est assigne, la touche
    seule ; si rien n'est assigne du tout, "?" (plutot que de laisser un
    hint vide ou trompeur)."""
    from managers.input_bus import DEFAULT_BUTTON_MAP, DEFAULT_HAT_MAP, DEFAULT_AXIS_MAP

    button_map = get_gamepad_button_map()
    if button_map is None:
        button_map = {k: list(v) for k, v in DEFAULT_BUTTON_MAP.items()}
    hat_map = get_gamepad_hat_map()
    if hat_map is None:
        hat_map = {k: list(v) for k, v in DEFAULT_HAT_MAP.items()}
    axis_map = get_gamepad_axis_map()
    if axis_map is None:
        axis_map = {k: list(v) for k, v in DEFAULT_AXIS_MAP.items()}

    gamepad_label = {}
    for button, actions in button_map.items():
        for action in actions:
            gamepad_label.setdefault(action, str(button))
    for (x, y), actions in hat_map.items():
        for action in actions:
            gamepad_label.setdefault(action, HAT_ARROWS_SHORT.get((x, y), "?"))
    for (axis, sign), actions in axis_map.items():
        for action in actions:
            gamepad_label.setdefault(action, f"A{axis}{'+' if sign > 0 else '−'}")

    key_label = {}
    for key, actions in get_gamepad_key_map().items():
        for action in actions:
            key_label.setdefault(action, _short_key_label(key))

    overrides = get_action_label_overrides()

    labels = {}
    for entry in GAMEPAD_ACTIONS:
        action = entry["action"]
        # v1.01 (16/09/2026, signale par Fabien) : le libelle technique
        # calcule ci-dessus (numero de bouton pygame, code d'axe...) ne
        # correspond pas forcement a ce qui est ECRIT sur la manette
        # physique (ex. pygame voit "bouton 1", mais la manette a "B"
        # imprime dessus) -- une surcharge saisie a la main dans
        # Configuration prend systematiquement le dessus si elle existe,
        # voir get/set_action_label_overrides() plus bas.
        if action in overrides:
            labels[action] = overrides[action]
            continue
        g = gamepad_label.get(action)
        k = key_label.get(action)
        # v1.2 : la version de demo se joue au clavier -- le numero de
        # bouton manette par defaut n'y aurait aucun sens.
        if config.DEMO_MODE and k:
            g = None
        if g and k:
            labels[action] = f"{g} / {k}"
        elif g:
            labels[action] = g
        elif k:
            labels[action] = k
        else:
            labels[action] = "?"
    return labels


# --- Libelles saisis a la main + avertissement de conflit (v1.01) ---------
#
# v1.01 (16/09/2026, signale par Fabien) : "si je prends le B pour réponse 2
# du coup ça ferme aussi [...] il faudrait une colonne en plus où l'on tape
# le texte correspondant au bouton [...] une zone texte où l'on peut mettre
# "A", "select" ou autre et que ça soit repris dans le jeu ou sur
# l'interface". Deux besoins distincts derriere ce message :
#   1) Le libelle technique auto-calcule (build_kiosk_action_labels()) ne
#      correspond pas forcement a ce qui est ecrit sur la manette physique
#      de Fabien -- d'ou cette surcharge texte libre, PAR ACTION, prioritaire
#      sur le calcul automatique. Fabien tape ce qu'il voit sur SA manette
#      ("A", "Select"...), et ce texte est repris tel quel dans le kiosque,
#      quel que soit le mapping technique reel en dessous.
#   2) Le symptome decrit ("B ferme aussi") n'est pas un bug de logique --
#      c'est la consequence attendue du partage de controle (v0.81) : si
#      "back" (assigne par defaut au bouton B) est ENCORE assigne au meme
#      bouton que celui fraichement assigne a "answer_2", ce bouton
#      declenche les deux actions a chaque appui, et "back" ramene toujours
#      au menu. Pas corrige par du code (le partage de controle est une
#      fonctionnalite demandee par Fabien lui-meme en v0.81, pas un bug) --
#      mais desormais SIGNALE explicitement dans Configuration (voir
#      build_action_conflicts()) pour que ce piege soit visible avant de
#      jouer, plutot que decouvert sur le terrain.
KEY_ACTION_LABEL_OVERRIDES = "action_label_overrides"


def get_action_label_overrides():
    """Renvoie {action: texte(str)} -- uniquement les actions ou Fabien a
    saisi un texte manuel dans Configuration. {} si rien n'a ete saisi."""
    raw = _get(KEY_ACTION_LABEL_OVERRIDES, None)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        return {
            k: str(v).strip() for k, v in parsed.items()
            if k in {entry["action"] for entry in GAMEPAD_ACTIONS} and str(v).strip()
        }
    except (ValueError, TypeError, AttributeError):
        return {}


def set_action_label_overrides(overrides):
    """overrides : {action: texte(str)}. Un champ absent ou vide retire la
    surcharge pour cette action -- revient donc au libelle technique
    auto-calcule (pas besoin d'un bouton "reinitialiser" distinct)."""
    valid_actions = {entry["action"] for entry in GAMEPAD_ACTIONS}
    cleaned = {
        k: v.strip() for k, v in overrides.items()
        if k in valid_actions and str(v).strip()
    }
    _set(KEY_ACTION_LABEL_OVERRIDES, json.dumps(cleaned))


def build_action_conflicts():
    """Renvoie {action: [libelle, ...]} -- pour chaque action, les AUTRES
    actions qui partagent au moins un de ses controles (bouton/hat/axe
    manette, touche clavier). Sert a avertir dans Configuration quand deux
    actions partagent un controle -- particulierement utile pour reperer
    d'un coup d'oeil quand une action partage son controle avec "back"
    (retour au menu), qui se declenche alors EN PLUS de l'autre a chaque
    appui (voir note ci-dessus)."""
    from managers.input_bus import DEFAULT_BUTTON_MAP, DEFAULT_HAT_MAP, DEFAULT_AXIS_MAP

    button_map = get_gamepad_button_map()
    if button_map is None:
        button_map = {k: list(v) for k, v in DEFAULT_BUTTON_MAP.items()}
    hat_map = get_gamepad_hat_map()
    if hat_map is None:
        hat_map = {k: list(v) for k, v in DEFAULT_HAT_MAP.items()}
    axis_map = get_gamepad_axis_map()
    if axis_map is None:
        axis_map = {k: list(v) for k, v in DEFAULT_AXIS_MAP.items()}
    key_map = get_gamepad_key_map()

    label_by_action = {entry["action"]: entry["label"] for entry in GAMEPAD_ACTIONS}
    conflicts = {entry["action"]: set() for entry in GAMEPAD_ACTIONS}
    for mapping in (button_map, hat_map, axis_map, key_map):
        for actions in mapping.values():
            if len(actions) < 2:
                continue
            for a in actions:
                if a not in conflicts:
                    continue
                for b in actions:
                    if b != a:
                        conflicts[a].add(b)

    return {
        action: [label_by_action.get(a, a) for a in sorted(others)]
        for action, others in conflicts.items() if others
    }


# --- Interne -------------------------------------------------------------

def _get(key, default):
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row is not None else default


def _set(key, value):
    db = get_db()
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    db.commit()


def _delete(key):
    db = get_db()
    db.execute("DELETE FROM settings WHERE key = ?", (key,))
    db.commit()
