"""Abstraction de la manette (et, plus tard, d'eventuels boutons GPIO).

Objectif du decouplage : le reste du code ne raisonne jamais en "bouton A de
la manette", mais en ACTIONS LOGIQUES ("select", "back", "answer_1"...). Le
mapping ci-dessous est le SEUL endroit a modifier si on change de manette, ou
si on passe a de vrais boutons arcade en v2 -- voir le point d'architecture
discute dans concept-borne-interactive.md.

Etape 1 : seule l'action "back" est utilisee (retour a l'ecran d'accueil
depuis l'ecran Descobèrta). Les autres actions sont deja mappees pour ne pas
avoir a y retoucher quand le menu et les jeux de quiz arriveront.

Le mapping des boutons (indices pygame) est indicatif -- a verifier et
ajuster une fois la manette Super NES USB reellement en main, les indices et
les couleurs pouvant varier d'un modele a l'autre. Le plus simple pour les
ajuster : lancer python -c "import pygame; ..." avec la manette branchee et
noter quel index s'allume pour chaque bouton (voir README).

v0.4 (14/09/2026) : la croix directionnelle peut arriver sous TROIS formes
differentes selon le modele de manette cote pygame/SDL :
  - un "hat" (evenement JOYHATMOTION, valeur (x, y)) -- le cas le plus
    courant, couvert depuis le debut par DEFAULT_HAT_MAP ;
  - des boutons numerotes (JOYBUTTONDOWN), exactement comme A/B/X/Y -- ajoute
    en v0.3 (voir GAMEPAD_ACTIONS dans settings_manager.py) ;
  - un ou deux AXES analogiques dedies (JOYAXISMOTION, valeur continue
    -1.0..1.0), traites par SDL comme une paire d'axes numerique plutot
    qu'un hat -- cas rencontre par Fabien (les deux mecanismes precedents ne
    suffisaient pas). Ajoute ici : chaque axe est surveille pour un
    "franchissement de seuil" (AXIS_PRESS_THRESHOLD) depuis le repos, traite
    comme un appui bouton classique.
Les trois mecanismes cohabitent sans conflit -- une manette qui n'utilise
que l'un des trois n'est simplement jamais concernee par les deux autres.

v0.81 (16/09/2026) : correctif demande par Fabien -- un MEME controle
physique (bouton, hat ou axe) doit pouvoir declencher PLUSIEURS actions a la
fois (ex. le bouton A sert a la fois a valider dans un menu, repondre a un
quiz et retourner une carte au Memòria). Les mappings sont donc desormais
{controle: [action, action, ...]} plutot que {controle: action} -- une seule
action assignee reste le cas le plus courant (liste a un seul element), mais
plusieurs sont maintenant possibles. Sans danger cote dispatch : chaque
`_emit(action)` est traite par GameController.on_action(), qui ignore deja
toute action non pertinente pour l'ecran affiche (voir game_controller.py) --
appuyer sur A pendant le Memòria ne fait donc rien si "select" est aussi
assigne a A, et inversement."""

import logging
import threading
import time

logger = logging.getLogger(__name__)

# index de bouton pygame -> liste d'actions logiques (v0.81 : un controle
# peut declencher plusieurs actions, voir note ci-dessus -- ici, un seul
# element par defaut pour chaque bouton, mais rien n'empeche l'admin d'en
# ajouter d'autres depuis Configuration > Manette).
# Disposition SNES habituelle : 0=B (bas), 1=A (droite), 2=Y (gauche), 3=X (haut),
# 4=L, 5=R, 6=Select, 7=Start. A RE-VERIFIER avec la manette reelle.
DEFAULT_BUTTON_MAP = {
    0: ["back"],         # B
    1: ["select"],       # A
    2: ["answer_2"],     # Y (ex: "Fals")
    3: ["answer_1"],     # X (ex: "Vertadièr")
    6: ["back"],         # Select : retour a l'accueil depuis n'importe quel ecran
    7: ["start_idle"],   # Start : forcer le retour au diaporama de veille
}

DEFAULT_HAT_MAP = {
    (-1, 0): ["left"],
    (1, 0): ["right"],
    # v0.9 (16/09/2026, demande par Fabien) : axe Y du hat pour "up"/"down",
    # meme principe que l'axe X ci-dessus pour "left"/"right" -- convention
    # SDL habituelle, y=+1 = haut, y=-1 = bas. A RE-VERIFIER avec la manette
    # reelle (voir note en tete de fichier), comme le reste de ce mapping.
    (0, 1): ["up"],
    (0, -1): ["down"],
}

# v0.4 : aucune valeur par defaut ici -- contrairement au hat (dont l'axe X
# suit toujours la meme convention -1/+1), l'INDICE de l'axe dedie a la
# croix directionnelle varie trop d'une manette a l'autre pour deviner une
# valeur par defaut fiable. Reste vide tant que rien n'a ete assigne depuis
# Configuration > Manette (voir managers/settings_manager.py).
DEFAULT_AXIS_MAP = {}

# Sous ce seuil (valeur absolue, echelle pygame -1.0..1.0), un axe est
# considere au repos. Au-dessus, on considere que la direction est "pressee".
# 0.5 laisse une bonne marge avec le bruit d'un axe analogique inutilise
# (typiquement proche de 0) tout en restant bien en dessous des valeurs
# franches -1.0/+1.0 envoyees par un axe numerique de croix directionnelle.
AXIS_PRESS_THRESHOLD = 0.5


class InputBus:
    """Poll les manettes connectees dans un thread a part et transforme les
    evenements pygame en actions logiques via `on_action(action: str)`.

    Fonctionne sans manette branchee (aucune erreur : simplement aucun
    evenement ne sera jamais emis), ce qui permet de developper le reste de
    l'appli avant d'avoir la manette Super NES en main.
    """

    def __init__(self, button_map=None, hat_map=None, axis_map=None):
        # v0.82 (revue de code, suite au signalement de Fabien sur le
        # partage bouton/touche) : `button_map or DEFAULT_BUTTON_MAP` retombe
        # a tort sur le mapping par defaut si `button_map` vaut `{}` (dict
        # vide, donc "falsy" en Python) -- par exemple si Fabien avait un
        # jour retire TOUTES les assignations d'un mecanisme depuis
        # Configuration. Un dict vide explicitement enregistre en base doit
        # rester vide, pas etre remplace par les valeurs par defaut. `is None`
        # distingue desormais "rien n'a jamais ete enregistre" (repli sur le
        # defaut, comportement voulu) de "un dict vide a ete enregistre"
        # (respecte tel quel).
        self.button_map = dict(button_map if button_map is not None else DEFAULT_BUTTON_MAP)
        self.hat_map = dict(hat_map if hat_map is not None else DEFAULT_HAT_MAP)
        # v0.4 : cles (axis_index: int, sign: -1|1) -> action.
        self.axis_map = dict(axis_map if axis_map is not None else DEFAULT_AXIS_MAP)
        self._on_action = None
        self._stop_event = threading.Event()
        self._thread = None

        # v0.2 : reconfiguration du mapping depuis l'admin (Configuration >
        # Manette). pygame_available vaut None tant que le thread n'a pas
        # encore essaye d'importer pygame, puis True/False -- l'admin s'en
        # sert pour afficher un message clair si aucune manette/pygame n'est
        # disponible sur la machine (ex. PC de developpement).
        self.pygame_available = None
        self._capture_lock = threading.Lock()
        self._capturing = False
        # v0.4 : remplace l'ancien _captured_button (un simple int). Un
        # controle capture peut maintenant etre un bouton, un hat ou un axe
        # -- voir begin_capture/poll_capture. Forme :
        #   {"kind": "button", "button": int}
        #   {"kind": "hat", "value": [int, int]}
        #   {"kind": "axis", "axis": int, "sign": -1|1}
        self._captured = None

    def start(self, on_action):
        self._on_action = on_action
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def set_button_map(self, button_map):
        """Remplace le mapping bouton -> action a chaud (sans redemarrer le
        service), utilise par l'admin apres une reconfiguration manette."""
        with self._capture_lock:
            self.button_map = dict(button_map)

    def set_hat_map(self, hat_map):
        with self._capture_lock:
            self.hat_map = dict(hat_map)

    def set_axis_map(self, axis_map):
        with self._capture_lock:
            self.axis_map = dict(axis_map)

    def begin_capture(self):
        """Passe en mode "ecoute" : le PROCHAIN bouton/hat/axe active sur la
        manette est intercepte (il ne declenche pas son action habituelle)
        et memorise pour poll_capture(), au lieu d'etre dispatche
        normalement -- utilise par l'ecran de reconfiguration manette de
        l'admin pour demander "appuie sur le bouton (ou la direction) a
        assigner"."""
        with self._capture_lock:
            self._capturing = True
            self._captured = None

    def cancel_capture(self):
        with self._capture_lock:
            self._capturing = False
            self._captured = None

    def poll_capture(self):
        """Renvoie (captured, still_capturing). `captured` est None tant que
        rien n'a ete capture ; une fois capture, l'appelant recoit un dict
        {"kind": ..., ...} (voir __init__) une seule fois (l'etat interne
        est alors reinitialise)."""
        with self._capture_lock:
            captured = self._captured
            if captured is not None:
                self._capturing = False
                self._captured = None
            return captured, self._capturing

    def _run(self):
        try:
            import os

            # Ce module ne fait jamais de rendu, seulement de la lecture
            # d'evenements manette -- mais SDL (via pygame.event.get()) a
            # besoin que le sous-systeme video soit initialise pour faire
            # tourner sa boucle d'evenements, meme sans ecran. Le pilote
            # "dummy" satisfait cette exigence sans necessiter de serveur
            # d'affichage reel : indispensable quand ce service demarre
            # avant le kiosque X (cas du service systemd sur le petit PC),
            # et sans effet negatif si un vrai affichage est disponible.
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            # v1.03 (revue de code, symptomes vus dans les logs de Fabien) :
            # - SDL installe par defaut son propre gestionnaire du signal
            #   SIGTERM et le transforme en simple evenement "quitter", que
            #   cette boucle ignore : un "systemctl stop/restart" attendait
            #   donc les 10 s de TimeoutStopSec avant que systemd ne tue le
            #   process (SIGKILL). SDL_NO_SIGNAL_HANDLERS le lui interdit (et
            #   run_pc.py installe de toute facon son propre gestionnaire
            #   AVANT le demarrage de pygame, voir la-bas).
            # - pygame.init() initialisait AUSSI l'audio (pygame.mixer), qui
            #   ouvre la carte son pour rien : flot de messages "ALSA ...
            #   underrun occurred" dans le journal, et carte son disputee a
            #   Chromium, qui en a besoin pour la prononciation des objets.
            #   Seuls la video "dummy" (necessaire a la boucle d'evenements)
            #   et les manettes sont desormais initialises ; le pilote audio
            #   "dummy" est une securite supplementaire.
            os.environ.setdefault("SDL_NO_SIGNAL_HANDLERS", "1")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
            import pygame
        except ImportError:
            logger.warning("pygame indisponible - manette desactivee")
            self.pygame_available = False
            return

        self.pygame_available = True
        pygame.display.init()
        pygame.joystick.init()
        joysticks = {}

        # v0.4 : dernier "cran" connu de chaque axe (-1, 0 ou 1), pour ne
        # declencher une action qu'au FRANCHISSEMENT du seuil depuis le repos
        # (front montant), jamais en continu tant que l'axe reste pousse --
        # meme logique qu'un JOYBUTTONDOWN, qui ne se declenche qu'une fois
        # par appui. Cle : event.axis (int).
        axis_state = {}

        logger.info(
            "InputBus demarre (%d manette(s) detectee(s) au lancement)",
            pygame.joystick.get_count(),
        )

        while not self._stop_event.is_set():
            for event in pygame.event.get():
                if event.type == pygame.JOYDEVICEADDED:
                    joy = pygame.joystick.Joystick(event.device_index)
                    joy.init()
                    joysticks[joy.get_instance_id()] = joy
                    logger.info("Manette connectee : %s", joy.get_name())
                elif event.type == pygame.JOYDEVICEREMOVED:
                    joysticks.pop(event.instance_id, None)
                    logger.info("Manette deconnectee")
                elif event.type == pygame.JOYBUTTONDOWN:
                    # v0.2 : un ecran de reconfiguration manette en attente
                    # d'un appui intercepte ce bouton au lieu de le dispatcher
                    # normalement (voir begin_capture/poll_capture ci-dessus).
                    if self._try_capture({"kind": "button", "button": event.button}):
                        logger.info("Bouton manette capture pour reconfiguration : %d", event.button)
                        continue
                    for action in self.button_map.get(event.button) or []:
                        self._emit(action)
                elif event.type == pygame.JOYHATMOTION:
                    if event.value != (0, 0) and self._try_capture({"kind": "hat", "value": list(event.value)}):
                        logger.info("Hat manette capture pour reconfiguration : %s", event.value)
                        continue
                    for action in self.hat_map.get(event.value) or []:
                        self._emit(action)
                elif event.type == pygame.JOYAXISMOTION:
                    # v0.4 : franchissement de seuil traite comme un "appui"
                    # (front montant uniquement -- voir axis_state ci-dessus).
                    axis = event.axis
                    value = event.value
                    if value > AXIS_PRESS_THRESHOLD:
                        bucket = 1
                    elif value < -AXIS_PRESS_THRESHOLD:
                        bucket = -1
                    else:
                        bucket = 0
                    previous = axis_state.get(axis, 0)
                    axis_state[axis] = bucket
                    if bucket != 0 and previous == 0:
                        if self._try_capture({"kind": "axis", "axis": axis, "sign": bucket}):
                            logger.info("Axe manette capture pour reconfiguration : axe %d, signe %d", axis, bucket)
                            continue
                        for action in self.axis_map.get((axis, bucket)) or []:
                            self._emit(action)
            time.sleep(0.02)

        pygame.joystick.quit()
        pygame.quit()

    def _try_capture(self, value):
        """Si un mode "ecoute" est en cours (voir begin_capture), memorise
        `value` (dict) pour poll_capture() et renvoie True -- l'appelant
        doit alors `continue` sans dispatcher l'evenement normalement.
        Renvoie False si aucune ecoute n'est en cours (dispatch normal)."""
        with self._capture_lock:
            if not self._capturing:
                return False
            self._captured = value
            self._capturing = False
            return True

    def _emit(self, action):
        logger.info("Action manette : %s", action)
        if self._on_action:
            # v1.03 (revue de code) : une exception dans le traitement d'une
            # action (bug d'un jeu, base indisponible...) remontait jusqu'a
            # _run() et arretait ce thread pour de bon -- manette morte
            # jusqu'au prochain redemarrage du service. On la journalise et
            # on continue d'ecouter la manette.
            try:
                self._on_action(action)
            except Exception:
                logger.exception("Erreur pendant le traitement de l'action manette %r", action)
