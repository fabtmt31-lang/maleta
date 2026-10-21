"""Machine a etats du kiosque, cote serveur.

Etape 2 : ajout du menu "Tria un jòc", du jeu chronometre "Tròba l'objècte"
et du mode veille/diaporama "Cadre fotó & vidèo".
Etape 2 bis (14/09/2026) : le MENU devient l'ecran d'accueil par defaut de
la borne (au demarrage, et apres inactivite), avec une icone Admin en plus
des tuiles de jeu. Etats et transitions :

    MENU (ecran d'accueil, etat de demarrage)
    MENU  --(gauche/droite)-->  MENU (change la tuile/icone selectionnee)
    MENU  --(select, tuile de jeu)-->  TROBA / VERTADIER / DUEL / MEMORIA / MEMORIA_VILATGE / QUIZ
    MENU  --(select, icone Cadre fotó)-->  VEILLE (le diaporama EST la veille, voir plus bas -- lancement volontaire ;
                                                     v0.8 : icone a part, plus une tuile de jeu, voir plus bas)
    MENU  --(select, icone Admin)-->  MENU (inchange ; declenche juste une redirection cote client vers /admin, voir plus bas)
    MENU  --(tag scanne, objet trouve)-->  DESCOBERTA

    DESCOBERTA  --(action "back", ou inactivite)-->  MENU
    DESCOBERTA  --(tag scanne, autre objet)-->  DESCOBERTA (nouvel objet)

    VEILLE  --(n'importe quelle action manette)-->  MENU
    VEILLE  --(tag scanne, objet trouve)-->  DESCOBERTA

    TROBA  --(bon tag scanne)-->  TROBA (mot suivant) ou TROBA_FIN (dernier mot)
    TROBA  --(mauvais tag, ou temps ecoule)-->  TROBA (nouvelle tentative / mot suivant)
    TROBA  --(action "back")-->  MENU
    TROBA_FIN  --(n'importe quelle action, ou delai ecoule)-->  MENU

    N'importe quel etat --(bouton Start, action "start_idle")-->  VEILLE (lancement volontaire du diaporama/ecran vitrine)

    v0.7 (15/09/2026) -- jeu a 2 joueurs "Duèl Occitan" (voir plus bas pour
    le detail) :
    DUEL  --(les 2 joueurs ont repondu, ou temps ecoule)-->  DUEL (question suivante) ou DUEL_FIN (derniere question)
    DUEL  --(action "back")-->  MENU
    DUEL_FIN  --(n'importe quelle action, ou delai ecoule)-->  MENU

    v0.72 (15/09/2026) -- jeu "Memòria" (piste bonus, voir plus bas) :
    MEMORIA  --(2e carte retournee, meme paire)-->  MEMORIA (paire figee) ou MEMORIA_FIN (derniere paire)
    MEMORIA  --(2e carte retournee, paire differente)-->  MEMORIA (les 2 cartes se referment)
    MEMORIA  --(action "back")-->  MENU
    MEMORIA_FIN  --(n'importe quelle action, ou delai ecoule)-->  MENU

    v0.8 -- "Memòria vilatge" (nouvelle activite, meme mecanique generique
    que Memòria -- voir MEMORIA_VARIANTS plus bas) :
    MEMORIA_VILATGE  --(memes transitions que MEMORIA ci-dessus)-->  MEMORIA_VILATGE / MEMORIA_VILATGE_FIN
    MEMORIA_VILATGE  --(action "back")-->  MENU
    MEMORIA_VILATGE_FIN  --(n'importe quelle action, ou delai ecoule)-->  MENU

    v0.8 -- "Quiz Calandreta" (nouvelle activite, 3e piste envisagee depuis le
    13/09/2026 -- voir concept-borne-interactive.md) : meme structure que
    Ven de l'occitan (ex-« Ven de l'occitan ») (1 joueur, retour + explication puis question
    suivante) mais a 3 reponses possibles (A/B/C) au lieu d'un vrai/faux :
    QUIZ  --(reponse donnee, ou temps ecoule)-->  QUIZ (question suivante) ou QUIZ_FIN (derniere question)
    QUIZ  --(action "back")-->  MENU
    QUIZ_FIN  --(n'importe quelle action, ou delai ecoule)-->  MENU

Le lecteur NFC reste dedie au mode "objets" (concept-borne-interactive.md) :
poser un objet ouvre toujours DESCOBERTA depuis le MENU ou la VEILLE, sauf
pendant une manche de TROBA ou poser un objet sert a repondre a la question
en cours plutot qu'a parcourir librement.

Choix de conception a noter (pas de round-trip de confirmation avant de
coder, mais documente ici pour etre facilement ajuste si besoin) :

- Le MENU ("Tria un jòc") est desormais l'ecran d'accueil par defaut de la
  borne : demarrage du service, retour apres inactivite depuis DESCOBERTA
  ou une manche de TROBA, retour depuis l'ecran de fin de TROBA. La VEILLE
  (diaporama/ecran vitrine) n'est plus atteinte automatiquement par
  inactivite -- seulement de facon volontaire (bouton Start, ou tuile
  "Cadre fotó" du menu). Consequence acceptee : sans personne devant la
  borne, l'ecran reste sur le menu plutot que de relancer le diaporama
  tout seul -- Fabien a confirme prefer cette simplicite (14/09/2026).
- VEILLE ne distingue pas "diaporama" de l'ancien ecran "Pausa un objècte" :
  le serveur envoie toujours l'etat "veille" + la liste des medias actifs ;
  c'est le CLIENT (kiosk.js) qui affiche le diaporama si la liste n'est pas
  vide, sinon le message d'accueil "Pausa un objècte" (cas d'une borne toute
  neuve, avant que l'admin n'ait ajoute la moindre photo). Un seul etat
  serveur, deux rendus cote client selon le contenu disponible.
- Icone Admin (14/09/2026) : ce n'est pas une "activite" au sens des jeux --
  elle n'a pas de tuile dans MENU_ACTIVITIES et ne fait jamais changer
  self.state. C'est un slot de navigation virtuel supplementaire, navigable
  comme les tuiles a gauche/droite. La selectionner emet un evenement
  websocket ponctuel "open_admin" (namespace /kiosk) ; c'est kiosk.js qui
  redirige le navigateur vers /admin, exactement comme le raccourci clavier
  Ctrl+Alt+A deja en place -- les deux moyens d'acceder a l'admin coexistent,
  l'icone n'a pas remplace le raccourci (demande explicite de Fabien).
- v0.8 : icone "Cadre fotó" (demande de Fabien : "passer l'appli cadre photo
  avec une petite icone sous la roue cranté comme ça seul les jeux restent en
  grand") -- le diaporama n'est plus une tuile de MENU_ACTIVITIES (il ne
  s'agit pas d'un "jeu" a proprement parler), c'est desormais une seconde
  icone virtuelle a cote de l'icone Admin, meme principe de slot de
  navigation. Il y a donc maintenant DEUX slots virtuels apres les tuiles de
  jeu : index == len(MENU_ACTIVITIES) pour "Cadre fotó" (bascule directement
  sur VEILLE, equivalent a l'ancienne tuile), index == len(MENU_ACTIVITIES) + 1
  pour Admin (inchange). Voir _move_menu_selection/_select_menu_activity.
- Une reponse fausse pendant TROBA relance un minuteur complet pour le meme
  mot (pas le temps restant exact) -- simplification deliberee, largement
  suffisante pour l'usage vise (quelques secondes de generosite en plus
  apres une erreur n'est pas genant sur un stand).
- v0.72 : Memòria (jeu "associer deux cartes qui vont ensemble", tranche par
  Fabien le 15/09/2026) est 100% a l'ecran/manette, SANS les objets physiques
  (le lecteur NFC ne peut scanner qu'un seul objet a la fois -- incompatible
  avec un vrai memory a 2 cartes retournees). Navigation cote manette :
  uniquement "left"/"right" (curseur dans une liste a plat de cartes, ordre
  de lecture) + "select" (retourner la carte sous le curseur) + "back" --
  delibere pour ne demander AUCUNE nouvelle action manette configurable
  (contrairement au Duèl Occitan, qui avait demande 4 boutons a assigner
  manuellement) : le jeu est jouable immediatement, sans aucune configuration
  prealable.
  v0.8 (evolution demandee par Fabien) : chaque paire de cartes montre
  desormais le mot FRANCAIS d'un cote et le mot OCCITAN de l'autre (plus une
  image + un mot -- "plus pertinent" pour vraiment apprendre la traduction).
  DEUX variantes de contenu partagent cette meme mecanique generique (voir
  MEMORIA_VARIANTS ci-dessous et start_memoria) : "memoria" reutilise les
  objets deja actifs (object_manager.list_objects, name_fr/name_oc deja
  obligatoires -- aucun nouveau contenu a saisir) ; "memoria_vilatge"
  (nouvelle activite) reutilise la nouvelle table `villages` (noms de
  villes/vilatges, a saisir depuis Admin > Vilatges -- source fiable exigee,
  jamais improvise, meme principe que Vertadièr/Duèl/Quiz).
- v0.8 : "Quiz Calandreta" (3e piste de quiz envisagee depuis le 13/09/2026,
  developpee ici sur le meme modele que Ven de l'occitan mais a 3 reponses
  possibles au lieu de vrai/faux -- culture occitane, geografia, pedagogia
  Calandreta). Nouvelle action manette "answer_3" (en plus de answer_1/
  answer_2 deja utilisees par Vertadièr) -- comme pour le Duèl, aucun bouton
  par defaut (plus de bouton de facade libre sur une manette SNES classique) :
  a assigner depuis Configuration, au clavier ou a la manette (voir plus bas,
  "clavier"). Contenu volontairement VIDE a la livraison, meme principe que
  Vertadièr/Duèl/Memòria vilatge : jamais improvise, a construire par Fabien
  avec une source fiable.
- v0.8 (demande de Fabien) : en plus du mapping manette (bouton/hat/axe),
  Configuration > Manette permet desormais d'assigner aussi une TOUCHE DE
  CLAVIER a chaque action -- les deux mecanismes COEXISTENT TOUJOURS (jamais
  l'un a la place de l'autre : "la fleche gauche de la manette ET aussi la
  fleche gauche du clavier"), contrairement aux 3 mecanismes manette entre eux
  (bouton/hat/axe), mutuellement exclusifs. Le clavier est capture directement
  cote NAVIGATEUR (kiosk.js, evenement `keydown`), pas cote serveur comme la
  manette (pygame) -- voir managers/settings_manager.py (get_gamepad_key_map)
  et static/js/kiosk.js. Le dispatch reutilise la route existante
  `POST /dev/action/<action>` (deja utilisee par /dev/panel), pas de nouvelle
  route necessaire cote jeu.
- v0.72 (revue de code) : "epoch" de manche (self._epoch, voir _bump_epoch_locked
  ci-dessous) ajoute a TOUS les minuteurs de jeu (mot/question/carte/fin de
  manche). Bug latent identifie en relisant le code : un threading.Timer cree
  APRES avoir relache self._lock (necessaire pour ne jamais tenir le lock
  pendant un broadcast websocket) pouvait echapper a l'annulation d'un
  go_to_menu()/nouvelle manche demarre entre-temps depuis un autre thread
  (manette ou tag NFC, chacun sur son propre thread) -- threading.Timer.cancel()
  n'a par ailleurs aucun effet si le timer a deja commence a s'executer.
  Consequence concrete avant ce correctif : un minuteur "fin de manche" ou
  "mot suivant" orphelin pouvait se declencher plus tard et interrompre une
  toute autre activite lancee entre-temps (ex. un Tròba termine, B appuye
  aussitot, un Duèl relance -- 12s plus tard l'ancien minuteur de fin de Tròba
  renvoyait brutalement au menu en pleine partie de Duèl). Desormais, chaque
  minuteur capture l'epoch courante a sa creation et son callback verifie
  qu'elle n'a pas change avant d'agir -- un minuteur perime devient un no-op
  silencieux plutot que d'agir sur un etat qui n'est plus le sien.
"""

import logging
import random
import threading
import time

import config
from managers import duel_manager, media_manager, object_manager, quiz_manager, vertadier_manager, village_manager

logger = logging.getLogger(__name__)

STATE_VEILLE = "veille"
STATE_DESCOBERTA = "descoberta"
STATE_MENU = "menu"
STATE_TROBA = "troba"
STATE_TROBA_FIN = "troba_fin"
STATE_VERTADIER = "vertadier"
STATE_VERTADIER_FIN = "vertadier_fin"
STATE_DUEL = "duel"
STATE_DUEL_FIN = "duel_fin"
STATE_MEMORIA = "memoria"
STATE_MEMORIA_FIN = "memoria_fin"
STATE_MEMORIA_VILATGE = "memoria_vilatge"
STATE_MEMORIA_VILATGE_FIN = "memoria_vilatge_fin"
# v0.9 : ecran intermediaire "Quantas cartas ?" entre le menu et le jeu
# lui-meme, un par variante (voir MEMORIA_VARIANTS/_open_memoria_choice) --
# remplace le tirage au sort de la v0.83.
STATE_MEMORIA_CHOICE = "memoria_choice"
STATE_MEMORIA_VILATGE_CHOICE = "memoria_vilatge_choice"
STATE_QUIZ = "quiz"
STATE_QUIZ_FIN = "quiz_fin"

# v1.03 : parties EN COURS pendant lesquelles poser un objet sur la maleta
# est ignore (voir on_tag_scanned) -- Tròba l'objècte n'y figure pas : le
# tag y sert justement a repondre.
GAME_IN_PROGRESS_STATES = (
    STATE_VERTADIER,
    STATE_DUEL,
    STATE_MEMORIA,
    STATE_MEMORIA_VILATGE,
    STATE_QUIZ,
)

# Activites du menu "Tria un jòc" -- UNIQUEMENT des jeux (v0.8 : "Cadre fotó"
# n'en fait plus partie, voir plus bas MENU_EXTRA_ICONS/docstring "icone Cadre
# fotó"). L'icone Admin n'est PAS non plus dans cette liste : elle occupe,
# avec l'icone Cadre fotó, un slot de navigation virtuel apres la derniere
# tuile (voir MENU_EXTRA_ICONS ci-dessous).
#
# v0.2 : "Ven de l'occitan" -- vrai/faux sur l'origine occitane d'un mot,
# reponse a la manette (X = Vertadièr, Y = Fals, voir input_bus.py). Comme
# pour "Tròba l'objècte", la tuile est toujours visible : si Fabien n'a pas
# encore saisi de mots depuis l'admin (vertadier_manager, CRUD dedie -- voir
# concept-borne-interactive.md, le contenu ne doit JAMAIS etre improvise ici),
# la selectionner affiche juste un menu_notice au lieu de planter (meme
# principe que "Pas assez d'objets tagués" pour Tròba l'objècte).
#
# v0.7 (15/09/2026) : "Duèl Occitan" -- jeu a 2 joueurs demande par Fabien.
# Question de culture/langue occitane avec 2 reponses possibles ; les DEUX
# joueurs repondent chacun de leur cote (voir duel_manager.py, STATE_DUEL
# plus bas, et managers/input_bus.py pour les 4 actions dediees
# duel_p1_a/duel_p1_b/duel_p2_a/duel_p2_b). Meme principe que Vertadièr : la
# tuile est toujours visible, un menu_notice s'affiche si aucune question
# n'est encore saisie plutot que de planter.
#
# v0.72 (15/09/2026) : "Memòria" -- piste bonus tranchee par Fabien (associer
# deux cartes qui vont ensemble), jeu 100% ecran/manette sans objet physique.
# v0.8 : "Memòria vilatge" (villes/vilatges FR/OC, voir MEMORIA_VARIANTS) et
# "Quiz Calandreta" (3 reponses possibles, voir STATE_QUIZ plus bas)
# rejoignent le menu, meme principe que les jeux precedents : la tuile est
# toujours visible, un menu_notice s'affiche si pas assez de contenu plutot
# que de planter.
MENU_ACTIVITIES = [
    {"id": "troba_objecte", "label_oc": "Tròba l'objècte", "label_fr": "Trouve l'objet"},
    {"id": "vertadier", "label_oc": "Ven de l'occitan ?", "label_fr": "Vient de l'occitan ?"},
    {"id": "duel_occitan", "label_oc": "Duèl Occitan", "label_fr": "Duel à 2 joueurs"},
    {"id": "memoria", "label_oc": "Memòria", "label_fr": "Jeu de mémoire"},
    {"id": "memoria_vilatge", "label_oc": "Memòria vilatge", "label_fr": "Vilas e vilatges"},
    {"id": "quiz_calandreta", "label_oc": "Quiz Calandreta", "label_fr": "Quiz culture occitane"},
]

# v0.8 : les deux icones virtuelles apres les tuiles de jeu (Cadre fotó, puis
# Admin) -- ni l'une ni l'autre n'est un "jeu" au sens de MENU_ACTIVITIES,
# toutes deux occupent un slot de navigation supplementaire (voir
# _move_menu_selection/_select_menu_activity). L'ordre de cette liste est
# l'ordre de navigation (index len(MENU_ACTIVITIES) = "diaporama", index
# len(MENU_ACTIVITIES) + 1 = "admin").
MENU_EXTRA_ICONS = ["diaporama", "admin"]

# v0.8 : les deux jeux "Memòria" partagent EXACTEMENT la meme mecanique
# (retourner 2 cartes ; meme "pair_id" -> paire figee, sinon refermeture
# apres un delai) -- seul le CONTENU differe (objets vs villages/vilatges),
# d'ou ce dict plutot que du code duplique. Voir start_memoria plus bas.
#
# v0.83 (16/09/2026) : "not_enough_notice" devient un gabarit avec {count}/
# {needed} -- Fabien a signale que la Memòria refusait de se lancer ("pas
# d'objet") alors que Tròba l'objècte, lui, trouvait bien des objets. Apres
# verification complete du code (aucun bug trouve dans la logique elle-meme,
# reproduite avec succes en local), l'explication la plus probable est un
# nombre d'objets ACTIFS reellement en dessous du minimum requis par la
# Memòria (5 desormais, voir MEMORIA_PAIR_COUNT_SMALL/config.py) -- un seuil
# que Tròba l'objècte n'a pas (il se contente d'UN SEUL objet tague). Le
# message affiche desormais le compte reel trouve vs necessaire, pour que ce
# genre de situation soit imediatement comprehensible cote kiosque plutot que
# de rester un simple "pas assez de contenu" enigmatique.
# v0.9 : "state_choice" -- l'ecran de choix de taille ("Quantas cartas ?"),
# ouvert par _open_memoria_choice AVANT start_memoria (voir plus bas).
MEMORIA_VARIANTS = {
    "memoria": {
        "state": STATE_MEMORIA,
        "state_fin": STATE_MEMORIA_FIN,
        "state_choice": STATE_MEMORIA_CHOICE,
        "label_oc": "Memòria",
        "not_enough_notice": "Pas pro d'objèctes actius per jogar a la Memòria ({count} trobat(s), {needed} necessaris al minimum).",
    },
    "memoria_vilatge": {
        "state": STATE_MEMORIA_VILATGE,
        "state_fin": STATE_MEMORIA_VILATGE_FIN,
        "state_choice": STATE_MEMORIA_VILATGE_CHOICE,
        "label_oc": "Memòria vilatge",
        "not_enough_notice": "Pas pro de vilatges saisits per jogar a la Memòria vilatge ({count} trobat(s), {needed} necessaris al minimum).",
    },
}

# v0.9 : les 2 tailles de partie proposees sur l'ecran de choix, dans l'ordre
# d'affichage (petite -> grande). Construit a partir de config.py pour que
# les deux restent toujours synchronises avec MEMORIA_PAIR_COUNT_SMALL/LARGE.
MEMORIA_CHOICE_OPTIONS = [config.MEMORIA_PAIR_COUNT_SMALL, config.MEMORIA_PAIR_COUNT_LARGE]



# v1.03 (revue de code) : temps RESTANT sur la question en cours, envoye
# dans le payload (champ "time_left", en secondes) pour que la barre de temps
# du kiosque reparte de la bonne position a chaque nouvel envoi d'etat. Avant,
# kiosk.js relancait la barre a 100 % a chaque payload sans retour visuel --
# ex. au Duèl, quand le joueur 1 repond, la barre de l'ecran repartait pleine
# alors que le minuteur du serveur, lui, continuait de tourner (le joueur 2
# croyait avoir plus de temps qu'en realite). Meme chose apres une
# reconnexion websocket ou un rechargement de la page.
def _arm_deadline_locked(game, seconds):
    """A appeler avec self._lock tenu, au demarrage du minuteur de la
    question courante. `deadline_index` rattache l'echeance a CETTE question :
    une echeance restee d'une question precedente n'est jamais reutilisee."""
    if game is None:
        return
    game["deadline"] = time.monotonic() + seconds
    game["deadline_index"] = game["index"]


def _time_left(game):
    """Secondes restantes (arrondies) sur la question en cours, ou None si le
    minuteur n'est pas (encore) arme pour elle -- le client repart alors de la
    duree complete, ce qui est exact puisque le minuteur est arme juste apres
    l'envoi de l'etat."""
    if game is None or game.get("feedback") is not None:
        return None
    deadline = game.get("deadline")
    if deadline is None or game.get("deadline_index") != game.get("index"):
        return None
    return round(max(0.0, deadline - time.monotonic()), 2)

class GameController:
    def __init__(self, socketio, app):
        self.socketio = socketio
        self.app = app

        # Le MENU (ecran d'accueil) est l'etat de demarrage depuis le
        # 14/09/2026 -- voir docstring.
        self.state = STATE_MENU
        self.current_object = None
        self.menu_index = 0
        self.menu_notice = None
        self.troba = None  # dict {words, index, score, feedback} pendant une manche
        self.vertadier = None  # dict {words, index, score, feedback} pendant une manche
        self.duel = None  # dict {questions, index, score_p1, score_p2, answered_p1, answered_p2, feedback}
        # v0.8 : "memoria" sert desormais aux DEUX variantes (memoria/memoria_vilatge,
        # voir MEMORIA_VARIANTS) -- self.memoria["activity_id"] dit laquelle est en
        # cours. dict {activity_id, cards, cursor, flipped, matched, attempts, feedback, total_pairs}.
        self.memoria = None
        # v0.9 : dict {activity_id, eligible_count, selected_index, notice}
        # pendant que l'ecran de choix "Quantas cartas ?" est affiche (entre
        # le menu et start_memoria) -- voir _open_memoria_choice.
        self.memoria_choice = None
        self.quiz = None  # dict {questions, index, score, feedback} pendant une manche -- v0.8

        self._idle_timer = None
        self._troba_word_timer = None
        self._troba_feedback_timer = None
        self._troba_fin_timer = None
        self._vertadier_word_timer = None
        self._vertadier_feedback_timer = None
        self._vertadier_fin_timer = None
        self._duel_question_timer = None
        self._duel_feedback_timer = None
        self._duel_fin_timer = None
        self._memoria_reveal_timer = None
        self._memoria_fin_timer = None
        self._quiz_word_timer = None
        self._quiz_feedback_timer = None
        self._quiz_fin_timer = None
        self._lock = threading.Lock()
        # v1.03 (revue de code) : verrou de SERIALISATION des evenements
        # entrants (actions manette/clavier, tags NFC, callbacks de
        # minuteurs). Avant, chaque evenement lisait l'etat sous self._lock
        # puis agissait dans une AUTRE section critique : deux evenements
        # quasi simultanes (ex. un appui clavier qui envoie 2 actions en
        # parallele, ou une reponse qui arrive pile quand le minuteur de
        # retour visuel fait avancer la question) pouvaient s'intercaler
        # entre les deux, d'ou une reponse traitee sur la mauvaise question
        # (IndexError sur la derniere) ou un verrou anti double-appui
        # contourne. Un seul evenement est desormais traite a la fois, du
        # debut a la fin. RLock : un meme thread peut le reprendre sans
        # blocage (ex. go_to_menu appele depuis on_action). Toujours pris
        # AVANT self._lock, jamais l'inverse -- aucun risque d'interblocage.
        self._dispatch_lock = threading.RLock()

        # v0.72 : "epoch" de manche, incrementee a chaque entree dans un etat
        # de haut niveau (go_to_veille/go_to_menu/start_troba/start_vertadier/
        # start_duel/start_memoria/start_quiz). Voir _bump_epoch_locked et
        # _start_epoch_timer ci-dessous -- protege contre les minuteurs
        # perimes (docstring en tete de fichier, "v0.72 (revue de code)").
        self._epoch = 0
        # v0.10 : verrou d'entree anti double-declenchement (voir
        # config.ACTION_LOCKOUT_SECONDS et on_action ci-dessous).
        self._input_lockout_until = 0.0

    # --- evenements entrants ------------------------------------------------

    def on_tag_scanned(self, uid):
        with self.app.app_context():
            obj = object_manager.get_object_by_tag_uid(uid)
        if obj is None:
            logger.info("Tag %s scanne mais associe a aucun objet actif", uid)
            return
        obj = dict(obj)

        with self._dispatch_lock:
            with self._lock:
                state = self.state
            if state == STATE_TROBA:
                self._handle_troba_answer(obj)
                return

            # v1.03 (revue de code) : poser un objet n'interrompt plus une
            # partie en cours. Avant, un tag scanne pendant Vertadièr, le
            # Duèl, le Quiz ou le Memòria basculait directement sur
            # Descobèrta et abandonnait la partie -- contraire a la regle
            # ecrite en tete de ce fichier ("poser un objet ouvre DESCOBERTA
            # depuis le MENU ou la VEILLE") et facile a declencher sur un
            # stand (un enfant qui manipule les objets pendant qu'un autre
            # joue). Les ecrans "hors partie" (menu, veille, Descobèrta,
            # ecrans de choix et de fin) restent ouverts a la decouverte.
            if state in GAME_IN_PROGRESS_STATES:
                logger.info("Tag %s ignore : partie en cours (%s)", uid, state)
                return

            self._cancel_all_timers()
            with self._lock:
                self._bump_epoch_locked()
                self.state = STATE_DESCOBERTA
                self.current_object = obj
                self.troba = None
                self.vertadier = None
                self.duel = None
                self.memoria = None
                self.memoria_choice = None
                self.quiz = None
            self._broadcast_state()
            self._reset_idle_timer()

    def on_action(self, action):
        """Appelee par l'InputBus (manette). Le sens d'une action depend de
        l'ecran courant -- c'est ce dispatcher qui fait le lien, jamais
        l'InputBus lui-meme (qui ne connait que des boutons, voir la couche
        d'abstraction manette/actions logiques du concept).

        v0.10 (signale par Fabien) : ignore toute action recue pendant le
        verrou d'entree qui suit une transition d'ecran (voir
        _bump_epoch_locked). Sans ca, un bouton assigne a LA FOIS a "select"
        (valider une tuile de menu) et a une action de reponse du jeu qui
        s'ouvre (ex. "answer_1") declenche les deux actions l'une derriere
        l'autre au meme appui : la 1ere fait entrer dans le jeu, la 2e est
        alors traitee comme une reponse DANS ce jeu et valide sa premiere
        question sans que le joueur l'ait choisi. Verifie AVANT toute autre
        logique (y compris le raccourci global "start_idle" ci-dessous), pour
        qu'aucune action ne puisse jamais passer au travers.

        v1.03 : tout le traitement se fait sous self._dispatch_lock (voir
        __init__) -- le test du verrou d'entree et la lecture de l'ecran
        courant ne peuvent plus etre separes par une autre action traitee
        en parallele (ex. deux requetes clavier simultanees)."""
        with self._dispatch_lock:
            with self._lock:
                if time.monotonic() < self._input_lockout_until:
                    return
            if action == "back":
                # v1.03 : evenement ponctuel pour la page de connexion admin
                # (voir templates/admin/login.html) -- un visiteur qui
                # selectionne l'icone Admin a la manette atterrit sur le
                # formulaire de PIN, ou le navigateur n'ecoute plus la manette
                # : sans ca, impossible d'en ressortir sans clavier/souris.
                # L'ecran du kiosque lui-meme ignore cet evenement.
                self.socketio.emit("kiosk_back", {}, namespace="/kiosk")
            self._dispatch_action(action)

    def _dispatch_action(self, action):
        """Corps de on_action (voir sa docstring), toujours appele sous
        self._dispatch_lock."""
        if action == "start_idle":
            # Raccourci global (bouton Start) : lancement volontaire du
            # diaporama/ecran vitrine, depuis n'importe quel ecran.
            self.go_to_veille()
            return

        with self._lock:
            state = self.state

        if state == STATE_VEILLE:
            # N'importe quelle action ouvre le menu : "diaporama en veille,
            # une action relance le menu" (concept-borne-interactive.md).
            self.go_to_menu()

        elif state == STATE_DESCOBERTA:
            if action == "back":
                self.go_to_menu()

        elif state == STATE_MENU:
            # v0.9 : "up"/"down" acceptes en plus de "left"/"right", demande
            # par Fabien -- la grille de tuiles s'affiche sur plusieurs
            # rangees (CSS responsive, nombre de colonnes non fixe cote
            # serveur, contrairement a la grille Memòria plus bas), donc pas
            # de vrai deplacement 2D possible ici sans le savoir : haut/bas
            # se comportent comme gauche/droite (meme liste, meme ordre) --
            # au moins la fleche qu'on presse instinctivement fait toujours
            # quelque chose de coherent, plutot que rien du tout.
            if action in ("left", "up"):
                self._move_menu_selection(-1)
            elif action in ("right", "down"):
                self._move_menu_selection(1)
            elif action == "select":
                self._select_menu_activity()
            # "back" ne fait rien ici : le menu est deja l'ecran d'accueil,
            # il n'y a nulle part "en arriere" ou revenir.

        elif state == STATE_TROBA:
            if action == "back":
                self.go_to_menu()
            # les autres actions (select/answer_1/answer_2/left/right) ne font
            # rien : dans ce jeu on repond en posant un objet, pas a la manette.

        elif state == STATE_TROBA_FIN:
            # n'importe quelle action saute l'attente et revient au menu
            self.go_to_menu()

        elif state == STATE_VERTADIER:
            if action == "back":
                self.go_to_menu()
            elif action in ("answer_1", "answer_2"):
                # answer_1 = bouton X ("Vertadièr"), answer_2 = bouton Y
                # ("Fals") -- voir DEFAULT_BUTTON_MAP dans input_bus.py.
                self._handle_vertadier_answer(answered_occitan=(action == "answer_1"))

        elif state == STATE_VERTADIER_FIN:
            self.go_to_menu()

        elif state == STATE_DUEL:
            if action == "back":
                self.go_to_menu()
            elif action in ("duel_p1_a", "duel_p1_b"):
                self._handle_duel_answer("p1", "a" if action == "duel_p1_a" else "b")
            elif action in ("duel_p2_a", "duel_p2_b"):
                self._handle_duel_answer("p2", "a" if action == "duel_p2_a" else "b")

        elif state == STATE_DUEL_FIN:
            self.go_to_menu()

        elif state in (STATE_MEMORIA_CHOICE, STATE_MEMORIA_VILATGE_CHOICE):
            # v0.9 : ecran "Quantas cartas ?" -- un choix binaire (petite/
            # grande taille), gauche/droite ET haut/bas font tous les deux
            # basculer entre les 2 options (peu importe l'orientation visuelle
            # choisie pour les 2 tuiles, les 4 directions restent utiles).
            if action == "back":
                self.go_to_menu()
            elif action in ("left", "up"):
                self._move_memoria_choice_selection(-1)
            elif action in ("right", "down"):
                self._move_memoria_choice_selection(1)
            elif action == "select":
                self._confirm_memoria_choice()

        elif state in (STATE_MEMORIA, STATE_MEMORIA_VILATGE):
            if action == "back":
                self.go_to_menu()
            elif action == "left":
                self._move_memoria_cursor(-1)
            elif action == "right":
                self._move_memoria_cursor(1)
            elif action == "up":
                # v0.9 (demande par Fabien) : la grille de cartes utilise
                # desormais un nombre de colonnes FIXE cote serveur ET cote
                # CSS (config.MEMORIA_GRID_COLUMNS, voir config.py) -- monter
                # d'une rangee, c'est donc simplement reculer le curseur de ce
                # nombre de positions dans la liste a plat des cartes.
                # _move_memoria_cursor fait deja un modulo sur le total, qui
                # est toujours un multiple exact de MEMORIA_GRID_COLUMNS (12
                # ou 24 cartes / 6 colonnes) : la colonne du curseur est donc
                # toujours preservee, y compris en cas de rebouclage haut/bas.
                self._move_memoria_cursor(-config.MEMORIA_GRID_COLUMNS)
            elif action == "down":
                self._move_memoria_cursor(config.MEMORIA_GRID_COLUMNS)
            elif action == "select":
                self._flip_memoria_card()

        elif state in (STATE_MEMORIA_FIN, STATE_MEMORIA_VILATGE_FIN):
            self.go_to_menu()

        elif state == STATE_QUIZ:
            if action == "back":
                self.go_to_menu()
            elif action in ("answer_1", "answer_2", "answer_3"):
                self._handle_quiz_answer({"answer_1": "a", "answer_2": "b", "answer_3": "c"}[action])

        elif state == STATE_QUIZ_FIN:
            self.go_to_menu()

    # --- transitions d'etat ---------------------------------------------------

    def go_to_veille(self):
        self._cancel_all_timers()
        with self._lock:
            self._bump_epoch_locked()
            self.state = STATE_VEILLE
            self.current_object = None
            self.troba = None
            self.vertadier = None
            self.duel = None
            self.memoria = None
            self.memoria_choice = None
            self.quiz = None
        self._broadcast_state()

    def go_to_menu(self, notice=None):
        self._cancel_all_timers()
        with self._lock:
            self._bump_epoch_locked()
            self.state = STATE_MENU
            self.menu_index = 0
            self.menu_notice = notice
            self.current_object = None
            self.troba = None
            self.vertadier = None
            self.duel = None
            self.memoria = None
            self.memoria_choice = None
            self.quiz = None
        self._broadcast_state()
        # Pas de minuteur d'inactivite ici : le menu EST l'ecran d'accueil,
        # rien ne doit en faire sortir tout seul (voir docstring).

    def _move_menu_selection(self, delta):
        with self._lock:
            if self.state != STATE_MENU:
                return
            # v0.8 : +2 slots de navigation (icones "Cadre fotó" puis Admin),
            # apres la derniere tuile de jeu -- voir MENU_EXTRA_ICONS/docstring.
            slot_count = len(MENU_ACTIVITIES) + len(MENU_EXTRA_ICONS)
            self.menu_index = (self.menu_index + delta) % slot_count
        self._broadcast_state()

    def _select_menu_activity(self):
        with self._lock:
            index = self.menu_index
        if index >= len(MENU_ACTIVITIES):
            icon = MENU_EXTRA_ICONS[index - len(MENU_ACTIVITIES)]
            if icon == "diaporama":
                # Icone "Cadre fotó" (v0.8, ex-tuile) : bascule directement
                # sur la veille/diaporama, exactement comme l'ancienne tuile
                # ou le bouton Start (voir on_action, action "start_idle").
                self.go_to_veille()
            elif icon == "admin":
                # Icone Admin : pas un jeu, pas de changement d'etat -- un seul
                # evenement ponctuel pour que kiosk.js redirige vers /admin
                # (meme principe que le raccourci clavier Ctrl+Alt+A).
                self.socketio.emit("open_admin", {}, namespace="/kiosk")
            return

        activity_id = MENU_ACTIVITIES[index]["id"]
        if activity_id == "troba_objecte":
            self.start_troba()
        elif activity_id == "vertadier":
            self.start_vertadier()
        elif activity_id == "duel_occitan":
            self.start_duel()
        elif activity_id == "memoria":
            # v0.9 : n'ouvre plus directement la partie -- passe d'abord par
            # l'ecran de choix "Quantas cartas ?" (voir _open_memoria_choice).
            self._open_memoria_choice("memoria")
        elif activity_id == "memoria_vilatge":
            self._open_memoria_choice("memoria_vilatge")
        elif activity_id == "quiz_calandreta":
            self.start_quiz()

    # --- Tròba l'objècte -------------------------------------------------------

    def start_troba(self):
        self._cancel_all_timers()
        with self.app.app_context():
            eligible = [dict(o) for o in object_manager.list_objects_with_tag(only_active=True)]

        if not eligible:
            # Pas d'objet tague : rien a demander. On le signale via
            # menu_notice plutot que de planter ou d'ouvrir un ecran vide.
            self.go_to_menu(notice="Pas assez d'objets tagués pour jouer à Tròba l'objècte.")
            return

        random.shuffle(eligible)
        words = eligible[: config.TROBA_ROUND_WORD_COUNT]

        with self._lock:
            self._bump_epoch_locked()
            self.state = STATE_TROBA
            self.troba = {"words": words, "index": 0, "score": 0, "feedback": None}
        self._broadcast_state()
        self._start_troba_word_timer()

    def _start_troba_word_timer(self):
        self._cancel_troba_word_timer()
        with self._lock:
            _arm_deadline_locked(self.troba, config.TROBA_SECONDS_PER_WORD)
        self._start_epoch_timer("_troba_word_timer", config.TROBA_SECONDS_PER_WORD, self._on_troba_timeout)

    def _on_troba_timeout(self):
        with self._lock:
            if self.state != STATE_TROBA or self.troba is None or self.troba["feedback"] is not None:
                return
            self.troba["feedback"] = "timeout"
        self._broadcast_state()
        # v1.03 (revue de code) : temps ecoule = on passe au mot SUIVANT
        # (l'image de l'objet attendu est revelee pendant le retour visuel,
        # l'enfant apprend quand meme la reponse). Avant, le meme mot etait
        # repose indefiniment : si personne ne jouait, la manche ne se
        # terminait jamais et la borne restait bloquee sur Tròba l'objècte
        # (aucun retour automatique a l'accueil). Une MAUVAISE reponse, elle,
        # relance toujours le meme mot (il faut finir par trouver l'objet).
        self._schedule_troba_feedback_end(advance=True)

    def _handle_troba_answer(self, scanned_object):
        with self._lock:
            if self.state != STATE_TROBA or self.troba is None or self.troba["feedback"] is not None:
                # deja en cours de retour visuel (correct/faux) : on ignore
                # les scans suivants jusqu'au mot suivant, pour eviter de
                # sauter plusieurs mots d'un coup sur un double scan.
                return
            target = self.troba["words"][self.troba["index"]]
            correct = scanned_object["id"] == target["id"]
            self.troba["feedback"] = "correct" if correct else "wrong"
            if correct:
                self.troba["score"] += 1
        self._cancel_troba_word_timer()
        self._broadcast_state()
        self._schedule_troba_feedback_end(advance=correct)

    def _schedule_troba_feedback_end(self, advance):
        """advance=True : bonne reponse ou temps ecoule -> mot suivant.
        advance=False : mauvaise reponse -> meme mot, nouvelle tentative."""
        self._cancel_troba_feedback_timer()
        self._start_epoch_timer(
            "_troba_feedback_timer",
            config.TROBA_FEEDBACK_SECONDS,
            lambda: self._after_troba_feedback(advance),
        )

    def _after_troba_feedback(self, advance):
        with self._lock:
            if self.state != STATE_TROBA or self.troba is None:
                return
            if not advance:
                self.troba["feedback"] = None
                self.troba["deadline"] = None  # le minuteur repart de zero (voir _start_troba_word_timer)
        if advance:
            self._advance_troba()
        else:
            self._broadcast_state()
            self._start_troba_word_timer()

    def _advance_troba(self):
        with self._lock:
            if self.troba is None:
                return
            self.troba["index"] += 1
            self.troba["feedback"] = None
            finished = self.troba["index"] >= len(self.troba["words"])
            if finished:
                self.state = STATE_TROBA_FIN

        if finished:
            self._broadcast_state()
            # Retour a l'accueil (menu), pas a la veille -- voir docstring.
            self._start_epoch_timer("_troba_fin_timer", config.TROBA_FIN_DISPLAY_SECONDS, self.go_to_menu)
        else:
            self._broadcast_state()
            self._start_troba_word_timer()

    # --- Ven de l'occitan ----------------------------------------------------
    #
    # Contrairement a Tròba l'objècte (ou une mauvaise reponse relance le meme
    # mot -- il faut bien finir par trouver le bon objet), Ven de l'occitan
    # est un quiz classique : correct, faux ou temps ecoule affichent tous les
    # trois un retour (avec l'explication du mot) puis avancent au mot suivant
    # -- on ne repose jamais la meme question deux fois dans la meme manche.

    def start_vertadier(self):
        self._cancel_all_timers()
        with self.app.app_context():
            eligible = [dict(w) for w in vertadier_manager.list_words(only_active=True)]

        if not eligible:
            # Pas encore de mots saisis depuis l'admin : on le signale via
            # menu_notice plutot que de planter ou d'ouvrir un ecran vide
            # (meme principe que Tròba l'objècte sans objet tague).
            self.go_to_menu(notice="Pas encara de mots per « Ven de l'occitan ? ».")
            return

        random.shuffle(eligible)
        words = eligible[: config.VERTADIER_ROUND_WORD_COUNT]

        with self._lock:
            self._bump_epoch_locked()
            self.state = STATE_VERTADIER
            self.vertadier = {"words": words, "index": 0, "score": 0, "feedback": None}
        self._broadcast_state()
        self._start_vertadier_word_timer()

    def _start_vertadier_word_timer(self):
        self._cancel_vertadier_word_timer()
        with self._lock:
            _arm_deadline_locked(self.vertadier, config.VERTADIER_SECONDS_PER_WORD)
        self._start_epoch_timer(
            "_vertadier_word_timer", config.VERTADIER_SECONDS_PER_WORD, self._on_vertadier_timeout
        )

    def _on_vertadier_timeout(self):
        with self._lock:
            if self.state != STATE_VERTADIER or self.vertadier is None or self.vertadier["feedback"] is not None:
                return
            self.vertadier["feedback"] = "timeout"
        self._broadcast_state()
        self._schedule_vertadier_feedback_end()

    def _handle_vertadier_answer(self, answered_occitan):
        with self._lock:
            if self.state != STATE_VERTADIER or self.vertadier is None or self.vertadier["feedback"] is not None:
                # deja en cours de retour visuel : on ignore les appuis
                # suivants jusqu'au mot suivant (meme garde-fou que Tròba).
                return
            target = self.vertadier["words"][self.vertadier["index"]]
            correct = bool(target["is_occitan"]) == answered_occitan
            self.vertadier["feedback"] = "correct" if correct else "wrong"
            if correct:
                self.vertadier["score"] += 1
        self._cancel_vertadier_word_timer()
        self._broadcast_state()
        self._schedule_vertadier_feedback_end()

    def _schedule_vertadier_feedback_end(self):
        self._cancel_vertadier_feedback_timer()
        self._start_epoch_timer(
            "_vertadier_feedback_timer", config.VERTADIER_FEEDBACK_SECONDS, self._advance_vertadier
        )

    def _advance_vertadier(self):
        with self._lock:
            if self.vertadier is None:
                return
            self.vertadier["index"] += 1
            self.vertadier["feedback"] = None
            finished = self.vertadier["index"] >= len(self.vertadier["words"])
            if finished:
                self.state = STATE_VERTADIER_FIN

        if finished:
            self._broadcast_state()
            # Retour a l'accueil (menu), pas a la veille -- meme choix que
            # Tròba l'objècte (voir docstring en tete de fichier).
            self._start_epoch_timer(
                "_vertadier_fin_timer", config.VERTADIER_FIN_DISPLAY_SECONDS, self.go_to_menu
            )
        else:
            self._broadcast_state()
            self._start_vertadier_word_timer()

    # --- Duèl Occitan (v0.7, jeu a 2 joueurs) --------------------------------
    #
    # Meme structure que Ven de l'occitan (une question a la fois, retour
    # + explication, puis question suivante -- jamais reposee deux fois dans
    # la meme manche), mais avec DEUX reponses independantes a suivre par
    # question (answered_p1/answered_p2) et DEUX scores. Le retour visuel
    # ("feedback") se declenche des que les DEUX joueurs ont repondu, ou au
    # bout du delai si l'un des deux (ou les deux) n'a pas repondu a temps --
    # un joueur qui n'a pas repondu est alors simplement compte faux, sans
    # bloquer indefiniment la partie pour l'autre joueur.

    def start_duel(self):
        self._cancel_all_timers()
        with self.app.app_context():
            eligible = [dict(q) for q in duel_manager.list_questions(only_active=True)]

        if not eligible:
            # Pas encore de questions saisies depuis l'admin : meme principe
            # que Tròba l'objècte sans objet tague / Vertadièr sans mot.
            self.go_to_menu(notice="Pas encara de questions per lo Duèl Occitan.")
            return

        random.shuffle(eligible)
        questions = eligible[: config.DUEL_ROUND_QUESTION_COUNT]

        with self._lock:
            self._bump_epoch_locked()
            self.state = STATE_DUEL
            self.duel = {
                "questions": questions,
                "index": 0,
                "score_p1": 0,
                "score_p2": 0,
                "answered_p1": None,
                "answered_p2": None,
                "feedback": None,
            }
        self._broadcast_state()
        self._start_duel_question_timer()

    def _start_duel_question_timer(self):
        self._cancel_duel_question_timer()
        with self._lock:
            _arm_deadline_locked(self.duel, config.DUEL_SECONDS_PER_QUESTION)
        self._start_epoch_timer("_duel_question_timer", config.DUEL_SECONDS_PER_QUESTION, self._on_duel_timeout)

    def _on_duel_timeout(self):
        with self._lock:
            if self.state != STATE_DUEL or self.duel is None or self.duel["feedback"] is not None:
                return
            self._reveal_duel_locked()
        self._broadcast_state()
        self._schedule_duel_feedback_end()

    def _handle_duel_answer(self, player, choice):
        """`player` vaut "p1" ou "p2". Un joueur qui a deja repondu ne peut
        pas changer d'avis (appuis suivants ignores) -- meme garde-fou que
        Tròba/Vertadièr contre un double declenchement."""
        revealed = False
        with self._lock:
            if self.state != STATE_DUEL or self.duel is None or self.duel["feedback"] is not None:
                return
            key = f"answered_{player}"
            if self.duel[key] is not None:
                return
            self.duel[key] = choice
            if self.duel["answered_p1"] is not None and self.duel["answered_p2"] is not None:
                self._reveal_duel_locked()
                revealed = True
        if revealed:
            self._cancel_duel_question_timer()
        self._broadcast_state()
        if revealed:
            self._schedule_duel_feedback_end()

    def _reveal_duel_locked(self):
        """A appeler avec self._lock deja tenu. Calcule les points (un
        joueur qui n'a pas repondu, ex. en cas de temps ecoule, ne marque
        simplement pas de point) et bascule sur le retour visuel."""
        target = self.duel["questions"][self.duel["index"]]
        correct = target["correct_choice"]
        if self.duel["answered_p1"] == correct:
            self.duel["score_p1"] += 1
        if self.duel["answered_p2"] == correct:
            self.duel["score_p2"] += 1
        self.duel["feedback"] = "revealed"

    def _schedule_duel_feedback_end(self):
        self._cancel_duel_feedback_timer()
        self._start_epoch_timer("_duel_feedback_timer", config.DUEL_FEEDBACK_SECONDS, self._advance_duel)

    def _advance_duel(self):
        with self._lock:
            if self.duel is None:
                return
            self.duel["index"] += 1
            self.duel["feedback"] = None
            self.duel["answered_p1"] = None
            self.duel["answered_p2"] = None
            finished = self.duel["index"] >= len(self.duel["questions"])
            if finished:
                self.state = STATE_DUEL_FIN

        if finished:
            self._broadcast_state()
            # Retour a l'accueil (menu), pas a la veille -- meme choix que
            # Tròba l'objècte et Vertadièr (voir docstring en tete de fichier).
            self._start_epoch_timer("_duel_fin_timer", config.DUEL_FIN_DISPLAY_SECONDS, self.go_to_menu)
        else:
            self._broadcast_state()
            self._start_duel_question_timer()

    # --- Memòria (v0.72, jeu "associer deux cartes qui vont ensemble") -------
    #
    # 100% a l'ecran/manette (voir docstring en tete de fichier). Navigation :
    # "left"/"right" deplacent le curseur dans une liste a plat de cartes
    # (ordre de lecture -- gauche->droite, haut->bas, en wrap-around, meme
    # principe que la navigation du menu), "select" retourne la carte sous le
    # curseur. Deux cartes retournees qui ne correspondent pas se referment
    # apres un court delai (MEMORIA_REVEAL_SECONDS) ; deux cartes qui
    # correspondent restent revelees definitivement ("matched"). Le contenu
    # d'une carte face cachee n'est JAMAIS envoye au client (voir
    # _memoria_payload) -- meme discipline anti-fuite que Vertadièr/Duèl, pour
    # qu'il ne soit pas possible de "tricher" en lisant le payload reseau.
    #
    # v0.8 : generalisee a 2 variantes de CONTENU (voir MEMORIA_VARIANTS en
    # tete de fichier) qui partagent cette meme mecanique -- start_memoria
    # prend desormais un `activity_id` ("memoria" ou "memoria_vilatge"), et
    # chaque carte porte un "pair_id" (au lieu de "object_id") + un "kind"
    # ("fr" ou "oc") + son "text" -- les 2 cartes d'une paire partagent le
    # meme pair_id, l'une en francais, l'autre en occitan (plus une image).

    @staticmethod
    def _list_memoria_eligible(activity_id):
        """Contenu eligible pour la variante donnee -- objets actifs pour
        "memoria", vilatges actifs pour "memoria_vilatge". A appeler depuis un
        `with self.app.app_context():` (utilise object_manager/village_manager,
        qui font tous deux appel a la base). Partage entre _open_memoria_choice
        et start_memoria pour ne jamais avoir deux implementations de ce
        calcul qui pourraient diverger (v0.9)."""
        if activity_id == "memoria":
            return [dict(o) for o in object_manager.list_objects(only_active=True)]
        return [dict(v) for v in village_manager.list_villages(only_active=True)]

    def _open_memoria_choice(self, activity_id):
        """v0.9 : premiere etape du lancement de Memòria/Memòria vilatge --
        ouvre l'ecran "Quantas cartas ?" plutot que de lancer la partie
        directement (voir STATE_MEMORIA_CHOICE/_confirm_memoria_choice plus
        bas). Le controle "assez de contenu pour jouer AU MINIMUM" reste ici
        (avant meme d'afficher un choix, inutile de proposer un choix si le
        visiteur ne peut de toute facon pas jouer) -- identique au controle
        qui existait avant dans start_memoria (v0.83)."""
        self._cancel_all_timers()
        variant = MEMORIA_VARIANTS[activity_id]
        with self.app.app_context():
            eligible_count = len(self._list_memoria_eligible(activity_id))

        if eligible_count < config.MEMORIA_PAIR_COUNT_SMALL:
            notice = variant["not_enough_notice"].format(
                count=eligible_count, needed=config.MEMORIA_PAIR_COUNT_SMALL
            )
            self.go_to_menu(notice=notice)
            return

        with self._lock:
            self._bump_epoch_locked()
            self.state = variant["state_choice"]
            self.memoria_choice = {
                "activity_id": activity_id,
                "eligible_count": eligible_count,
                "selected_index": 0,
                "notice": None,
            }
        self._broadcast_state()

    def _move_memoria_choice_selection(self, delta):
        with self._lock:
            if self.memoria_choice is None or self.state not in (
                STATE_MEMORIA_CHOICE,
                STATE_MEMORIA_VILATGE_CHOICE,
            ):
                return
            self.memoria_choice["selected_index"] = (
                self.memoria_choice["selected_index"] + delta
            ) % len(MEMORIA_CHOICE_OPTIONS)
            self.memoria_choice["notice"] = None
        self._broadcast_state()

    def _confirm_memoria_choice(self):
        """Valide l'option en surbrillance sur l'ecran "Quantas cartas ?" et
        lance la partie -- sauf si le contenu disponible ne suffit plus pour
        la taille choisie (ex. Fabien a desactive des objets depuis l'admin,
        dans un autre onglet, pendant que l'ecran de choix etait affiche :
        rare en pratique, mais mieux vaut un message clair sur l'ecran de
        choix lui-meme qu'un plantage ou une partie tronquee sans prevenir)."""
        with self._lock:
            if self.memoria_choice is None or self.state not in (
                STATE_MEMORIA_CHOICE,
                STATE_MEMORIA_VILATGE_CHOICE,
            ):
                return
            activity_id = self.memoria_choice["activity_id"]
            eligible_count = self.memoria_choice["eligible_count"]
            pair_count = MEMORIA_CHOICE_OPTIONS[self.memoria_choice["selected_index"]]

        if pair_count > eligible_count:
            with self._lock:
                if self.memoria_choice is not None:
                    self.memoria_choice["notice"] = (
                        f"Pas pro de contengut per {pair_count} parelhs "
                        f"({eligible_count} trobat(s) — causissètz "
                        f"{config.MEMORIA_PAIR_COUNT_SMALL} parelhs)."
                    )
            self._broadcast_state()
            return

        self.start_memoria(activity_id, pair_count)

    # v0.83 (16/09/2026, signale par Fabien) : chaque carte porte un "pair_id"
    # (au lieu de "object_id") + un "kind" ("fr" ou "oc") + son "text" -- les
    # 2 cartes d'une paire partagent le meme pair_id, l'une en francais,
    # l'autre en occitan.
    def start_memoria(self, activity_id, pair_count):
        """Lance effectivement la partie -- appele une fois la taille choisie
        sur l'ecran "Quantas cartas ?" (voir _confirm_memoria_choice ci-dessus).
        `pair_count` doit normalement toujours etre l'une des deux valeurs de
        MEMORIA_CHOICE_OPTIONS, deja validee par l'appelant ; reste tout de
        meme borne par le contenu reellement disponible ci-dessous, par
        precaution (meme raisonnement que _confirm_memoria_choice)."""
        self._cancel_all_timers()
        variant = MEMORIA_VARIANTS[activity_id]
        with self.app.app_context():
            eligible = self._list_memoria_eligible(activity_id)

        if len(eligible) < config.MEMORIA_PAIR_COUNT_SMALL:
            notice = variant["not_enough_notice"].format(
                count=len(eligible), needed=config.MEMORIA_PAIR_COUNT_SMALL
            )
            self.go_to_menu(notice=notice)
            return

        pair_count = min(pair_count, len(eligible))

        random.shuffle(eligible)
        chosen = eligible[:pair_count]

        cards = []
        for item in chosen:
            cards.append({"kind": "fr", "pair_id": item["id"], "text": item["name_fr"]})
            cards.append({"kind": "oc", "pair_id": item["id"], "text": item["name_oc"]})
        random.shuffle(cards)

        with self._lock:
            self._bump_epoch_locked()
            self.state = variant["state"]
            self.memoria_choice = None
            self.memoria = {
                "activity_id": activity_id,
                "cards": cards,
                "cursor": 0,
                "flipped": [],
                "matched": set(),
                "attempts": 0,
                "feedback": None,
                "total_pairs": len(chosen),
            }
        self._broadcast_state()

    def _move_memoria_cursor(self, delta):
        with self._lock:
            if self.memoria is None or self.state not in (STATE_MEMORIA, STATE_MEMORIA_VILATGE):
                return
            # Pas de deplacement pendant qu'un couple de cartes est expose en
            # attente de refermeture/validation -- meme garde-fou que les
            # autres jeux pendant leur "feedback" (evite de perturber la
            # lecture du resultat en plein milieu).
            if self.memoria["feedback"] is not None:
                return
            total = len(self.memoria["cards"])
            self.memoria["cursor"] = (self.memoria["cursor"] + delta) % total
        self._broadcast_state()

    def _flip_memoria_card(self):
        reveal_pending = False
        finished = False
        with self._lock:
            if self.memoria is None or self.state not in (STATE_MEMORIA, STATE_MEMORIA_VILATGE):
                return
            memoria = self.memoria
            if memoria["feedback"] is not None:
                # Un couple est deja expose en attente de refermeture/
                # validation : on ignore tout nouvel appui sur "select"
                # jusque-la (meme principe que les autres jeux).
                return
            cursor = memoria["cursor"]
            if cursor in memoria["matched"] or cursor in memoria["flipped"]:
                # Carte deja figee (paire trouvee) ou deja retournee cette
                # manche-ci : rien a faire.
                return

            memoria["flipped"].append(cursor)
            if len(memoria["flipped"]) < 2:
                # Premiere carte de la paire : simplement revelee, on attend
                # la seconde -- pas de minuteur tant qu'il n'y a qu'une carte.
                pass
            else:
                first_idx, second_idx = memoria["flipped"]
                same_pair = (
                    memoria["cards"][first_idx]["pair_id"] == memoria["cards"][second_idx]["pair_id"]
                )
                memoria["attempts"] += 1
                memoria["feedback"] = "match" if same_pair else "mismatch"
                if same_pair:
                    memoria["matched"].add(first_idx)
                    memoria["matched"].add(second_idx)
                    finished = len(memoria["matched"]) == len(memoria["cards"])
                reveal_pending = True
        self._broadcast_state()
        if reveal_pending:
            self._start_epoch_timer(
                "_memoria_reveal_timer", config.MEMORIA_REVEAL_SECONDS, lambda: self._resolve_memoria_reveal(finished)
            )

    def _resolve_memoria_reveal(self, finished):
        with self._lock:
            if self.memoria is None:
                return
            self.memoria["flipped"] = []
            self.memoria["feedback"] = None
            if finished:
                self.state = MEMORIA_VARIANTS[self.memoria["activity_id"]]["state_fin"]

        if finished:
            self._broadcast_state()
            # Retour a l'accueil (menu), pas a la veille -- meme choix que les
            # autres jeux (voir docstring en tete de fichier).
            self._start_epoch_timer("_memoria_fin_timer", config.MEMORIA_FIN_DISPLAY_SECONDS, self.go_to_menu)
        else:
            self._broadcast_state()

    # --- Quiz Calandreta (v0.8, quiz solo a 3 reponses) -----------------------
    #
    # Meme structure que Ven de l'occitan (1 joueur, une question a la
    # fois, retour + explication puis question suivante, jamais reposee 2x
    # dans la meme manche) mais avec 3 reponses possibles (a/b/c) au lieu de
    # vrai/faux -- voir managers/quiz_manager.py et managers/settings_manager.py
    # (action "answer_3").

    def start_quiz(self):
        self._cancel_all_timers()
        with self.app.app_context():
            eligible = [dict(q) for q in quiz_manager.list_questions(only_active=True)]

        if not eligible:
            self.go_to_menu(notice="Pas encara de question per lo Quiz Calandreta.")
            return

        random.shuffle(eligible)
        questions = eligible[: config.QUIZ_ROUND_QUESTION_COUNT]

        with self._lock:
            self._bump_epoch_locked()
            self.state = STATE_QUIZ
            self.quiz = {"questions": questions, "index": 0, "score": 0, "feedback": None}
        self._broadcast_state()
        self._start_quiz_word_timer()

    def _start_quiz_word_timer(self):
        self._cancel_quiz_word_timer()
        with self._lock:
            _arm_deadline_locked(self.quiz, config.QUIZ_SECONDS_PER_QUESTION)
        self._start_epoch_timer("_quiz_word_timer", config.QUIZ_SECONDS_PER_QUESTION, self._on_quiz_timeout)

    def _on_quiz_timeout(self):
        with self._lock:
            if self.state != STATE_QUIZ or self.quiz is None or self.quiz["feedback"] is not None:
                return
            self.quiz["feedback"] = "timeout"
        self._broadcast_state()
        self._schedule_quiz_feedback_end()

    def _handle_quiz_answer(self, choice):
        with self._lock:
            if self.state != STATE_QUIZ or self.quiz is None or self.quiz["feedback"] is not None:
                return
            target = self.quiz["questions"][self.quiz["index"]]
            correct = choice == target["correct_choice"]
            self.quiz["feedback"] = "correct" if correct else "wrong"
            if correct:
                self.quiz["score"] += 1
        self._cancel_quiz_word_timer()
        self._broadcast_state()
        self._schedule_quiz_feedback_end()

    def _schedule_quiz_feedback_end(self):
        self._cancel_quiz_feedback_timer()
        self._start_epoch_timer("_quiz_feedback_timer", config.QUIZ_FEEDBACK_SECONDS, self._advance_quiz)

    def _advance_quiz(self):
        with self._lock:
            if self.quiz is None:
                return
            self.quiz["index"] += 1
            self.quiz["feedback"] = None
            finished = self.quiz["index"] >= len(self.quiz["questions"])
            if finished:
                self.state = STATE_QUIZ_FIN

        if finished:
            self._broadcast_state()
            self._start_epoch_timer("_quiz_fin_timer", config.QUIZ_FIN_DISPLAY_SECONDS, self.go_to_menu)
        else:
            self._broadcast_state()
            self._start_quiz_word_timer()

    # --- epoch de manche / minuteurs proteges (v0.72, revue de code) ---------
    #
    # Voir "v0.72 (revue de code)" dans la docstring en tete de fichier pour
    # le detail du bug corrige. En resume : un threading.Timer.cancel() ne
    # garantit rien si le timer a deja commence a s'executer, et un timer peut
    # etre cree juste apres qu'un go_to_menu()/nouvelle manche (sur un autre
    # thread : manette ou tag NFC) a deja fini de tout annuler -- il echappe
    # alors a l'annulation et peut agir plus tard sur un etat qui n'est plus
    # le sien. Chaque minuteur de jeu passe desormais par _start_epoch_timer,
    # qui fige l'epoch courante a la creation et l'exige inchangee au moment
    # de l'execution -- sinon le callback est un no-op silencieux.

    def _bump_epoch_locked(self):
        """A appeler avec self._lock deja tenu, au tout debut de chaque point
        d'entree dans un etat de haut niveau (go_to_veille/go_to_menu/
        start_troba/start_vertadier/start_duel/start_memoria) : invalide tout
        minuteur cree pour un etat/une manche precedente.

        v0.10 : pose aussi le verrou d'entree anti double-declenchement (voir
        config.ACTION_LOCKOUT_SECONDS et on_action) -- chaque entree dans un
        etat de haut niveau passe par ici, c'est donc le point unique le plus
        fiable pour armer ce verrou a chaque transition d'ecran, sans avoir a
        le repeter dans chaque go_to_*/start_*."""
        self._epoch += 1
        self._input_lockout_until = time.monotonic() + config.ACTION_LOCKOUT_SECONDS

    def _start_epoch_timer(self, attr_name, seconds, callback):
        """Cree, enregistre (sur self.<attr_name>, pour que les _cancel_*
        existants continuent de fonctionner sans changement) et demarre un
        threading.Timer dont le callback ne s'executera que si aucune
        nouvelle manche n'a ete demarree entre-temps (voir _bump_epoch_locked
        ci-dessus)."""
        with self._lock:
            epoch = self._epoch

        def guarded():
            # v1.03 : sous self._dispatch_lock, comme les actions et les tags
            # (voir __init__) -- le test d'epoch et le callback ne peuvent
            # plus etre separes par une transition d'ecran survenue entre
            # les deux.
            with self._dispatch_lock:
                with self._lock:
                    if epoch != self._epoch:
                        return
                callback()

        timer = threading.Timer(seconds, guarded)
        timer.daemon = True
        setattr(self, attr_name, timer)
        timer.start()

    # --- minuteur d'inactivite -----------------------------------------------

    def _reset_idle_timer(self):
        """Utilise seulement depuis DESCOBERTA (voir on_tag_scanned) : si
        personne ne fait rien apres avoir decouvert un objet, on revient a
        l'accueil (menu). Le MENU lui-meme n'a plus de minuteur d'inactivite
        (voir go_to_menu) et TROBA gere son propre rythme via ses minuteurs
        de mot/feedback/fin de manche."""
        self._cancel_idle_timer()
        self._start_epoch_timer("_idle_timer", config.IDLE_TIMEOUT_SECONDS, self.go_to_menu)

    def _cancel_idle_timer(self):
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None

    def _cancel_troba_word_timer(self):
        if self._troba_word_timer is not None:
            self._troba_word_timer.cancel()
            self._troba_word_timer = None

    def _cancel_troba_feedback_timer(self):
        if self._troba_feedback_timer is not None:
            self._troba_feedback_timer.cancel()
            self._troba_feedback_timer = None

    def _cancel_troba_fin_timer(self):
        if self._troba_fin_timer is not None:
            self._troba_fin_timer.cancel()
            self._troba_fin_timer = None

    def _cancel_vertadier_word_timer(self):
        if self._vertadier_word_timer is not None:
            self._vertadier_word_timer.cancel()
            self._vertadier_word_timer = None

    def _cancel_vertadier_feedback_timer(self):
        if self._vertadier_feedback_timer is not None:
            self._vertadier_feedback_timer.cancel()
            self._vertadier_feedback_timer = None

    def _cancel_vertadier_fin_timer(self):
        if self._vertadier_fin_timer is not None:
            self._vertadier_fin_timer.cancel()
            self._vertadier_fin_timer = None

    def _cancel_duel_question_timer(self):
        if self._duel_question_timer is not None:
            self._duel_question_timer.cancel()
            self._duel_question_timer = None

    def _cancel_duel_feedback_timer(self):
        if self._duel_feedback_timer is not None:
            self._duel_feedback_timer.cancel()
            self._duel_feedback_timer = None

    def _cancel_duel_fin_timer(self):
        if self._duel_fin_timer is not None:
            self._duel_fin_timer.cancel()
            self._duel_fin_timer = None

    def _cancel_memoria_reveal_timer(self):
        if self._memoria_reveal_timer is not None:
            self._memoria_reveal_timer.cancel()
            self._memoria_reveal_timer = None

    def _cancel_memoria_fin_timer(self):
        if self._memoria_fin_timer is not None:
            self._memoria_fin_timer.cancel()
            self._memoria_fin_timer = None

    def _cancel_quiz_word_timer(self):
        if self._quiz_word_timer is not None:
            self._quiz_word_timer.cancel()
            self._quiz_word_timer = None

    def _cancel_quiz_feedback_timer(self):
        if self._quiz_feedback_timer is not None:
            self._quiz_feedback_timer.cancel()
            self._quiz_feedback_timer = None

    def _cancel_quiz_fin_timer(self):
        if self._quiz_fin_timer is not None:
            self._quiz_fin_timer.cancel()
            self._quiz_fin_timer = None

    def _cancel_all_timers(self):
        self._cancel_idle_timer()
        self._cancel_troba_word_timer()
        self._cancel_troba_feedback_timer()
        self._cancel_troba_fin_timer()
        self._cancel_vertadier_word_timer()
        self._cancel_vertadier_feedback_timer()
        self._cancel_vertadier_fin_timer()
        self._cancel_duel_question_timer()
        self._cancel_duel_feedback_timer()
        self._cancel_duel_fin_timer()
        self._cancel_memoria_reveal_timer()
        self._cancel_memoria_fin_timer()
        self._cancel_quiz_word_timer()
        self._cancel_quiz_feedback_timer()
        self._cancel_quiz_fin_timer()

    # --- diffusion aux clients (l'ecran du kiosque) ---------------------------

    def _broadcast_state(self):
        payload = self.get_state_payload()
        self.socketio.emit("state_changed", payload, namespace="/kiosk")

    def get_state_payload(self):
        """Reconstruit le payload complet a partir de l'etat courant --
        utilisee aussi bien pour la diffusion en direct que pour l'etat
        envoye a une (re)connexion (voir kiosk_connect() dans app.py), pour
        que les deux ne puissent jamais diverger."""
        with self._lock:
            state = self.state
            current_object = self.current_object
            menu_index = self.menu_index
            menu_notice = self.menu_notice
            troba = dict(self.troba) if self.troba else None
            vertadier = dict(self.vertadier) if self.vertadier else None
            duel = dict(self.duel) if self.duel else None
            memoria = None
            if self.memoria:
                # v0.72 : contrairement a troba/vertadier/duel (dont les seuls
                # champs mutables sont des int/str/None, correctement figes
                # par dict(...)), self.memoria contient une liste ("flipped")
                # et un set ("matched") mutes EN PLACE par _flip_memoria_card/
                # _resolve_memoria_reveal -- un simple dict(self.memoria)
                # laisserait cette copie pointer vers les MEMES objets, lus
                # ici hors verrou pendant qu'un autre thread pourrait encore
                # les modifier. Copie explicite de ces deux champs.
                memoria = dict(self.memoria)
                memoria["flipped"] = list(self.memoria["flipped"])
                memoria["matched"] = set(self.memoria["matched"])
            memoria_choice = dict(self.memoria_choice) if self.memoria_choice else None
            quiz = dict(self.quiz) if self.quiz else None

        if state == STATE_VEILLE:
            with self.app.app_context():
                media = [self._media_to_dict(m) for m in media_manager.list_media(only_active=True)]
            return {"state": state, "media": media}

        if state == STATE_DESCOBERTA:
            return {"state": state, "object": current_object}

        if state == STATE_MENU:
            return {
                "state": state,
                "activities": MENU_ACTIVITIES,
                "selected_index": menu_index,
                "notice": menu_notice,
            }

        if state in (STATE_TROBA, STATE_TROBA_FIN):
            return self._troba_payload(state, troba)

        if state in (STATE_VERTADIER, STATE_VERTADIER_FIN):
            return self._vertadier_payload(state, vertadier)

        if state in (STATE_DUEL, STATE_DUEL_FIN):
            return self._duel_payload(state, duel)

        if state in (STATE_MEMORIA_CHOICE, STATE_MEMORIA_VILATGE_CHOICE):
            return self._memoria_choice_payload(state, memoria_choice)

        if state in (STATE_MEMORIA, STATE_MEMORIA_FIN, STATE_MEMORIA_VILATGE, STATE_MEMORIA_VILATGE_FIN):
            return self._memoria_payload(state, memoria)

        if state in (STATE_QUIZ, STATE_QUIZ_FIN):
            return self._quiz_payload(state, quiz)

        return {"state": state}

    @staticmethod
    def _media_to_dict(row):
        return {
            "filename": row["filename"],
            "media_type": row["media_type"],
            "caption": row["caption"],
            "display_seconds": row["display_seconds"] or config.DIAPORAMA_DEFAULT_IMAGE_SECONDS,
        }

    @staticmethod
    def _troba_payload(state, troba):
        if troba is None:
            # Etat incoherent (ne devrait pas arriver) -- on repli sur le menu
            # plutot que de renvoyer un payload que le client ne saurait pas
            # afficher.
            return {"state": STATE_MENU, "activities": MENU_ACTIVITIES, "selected_index": 0, "notice": None}

        total = len(troba["words"])
        if state == STATE_TROBA_FIN:
            return {"state": state, "score": troba["score"], "total": total}

        current_word = troba["words"][troba["index"]]
        return {
            "state": state,
            "index": troba["index"],
            "total": total,
            "score": troba["score"],
            "feedback": troba["feedback"],
            "word_oc": current_word["name_oc"],
            "word_fr": current_word["name_fr"],
            # v0.6 : l'image n'est envoyee que pour le retour visuel
            # (correct/faux/temps ecoule), jamais pendant la recherche --
            # sinon ca donnerait la reponse avant que l'enfant ait pose
            # l'objet. Signale par Fabien : "dans le jeu [...] l'image ne
            # remonte pas" (aucune image n'apparaissait, meme en retour).
            "image_filename": current_word["image_filename"] if troba["feedback"] else None,
            # v0.83 (demande par Fabien) : meme discipline anti-fuite que
            # l'image ci-dessus -- avant ce correctif, "audio_filename"
            # etait envoye en PERMANENCE (des la recherche), ce qui aurait
            # permis de deviner/reveler le mot a trouver avant meme de poser
            # l'objet si jamais le client s'en etait servi (il ne le
            # faisait pas encore, mais c'etait une fuite de donnees dormante
            # dans le payload). Desormais uniquement transmis une fois la
            # reponse donnee, pour que kiosk.js puisse jouer le son de
            # l'objet trouve en retour (voir showTroba dans kiosk.js).
            "audio_filename": current_word["audio_filename"] if troba["feedback"] else None,
            "seconds_per_word": config.TROBA_SECONDS_PER_WORD,
            "time_left": _time_left(troba),
        }

    @staticmethod
    def _vertadier_payload(state, vertadier):
        if vertadier is None:
            # Etat incoherent (ne devrait pas arriver) -- meme repli que
            # _troba_payload ci-dessus.
            return {"state": STATE_MENU, "activities": MENU_ACTIVITIES, "selected_index": 0, "notice": None}

        total = len(vertadier["words"])
        if state == STATE_VERTADIER_FIN:
            return {"state": state, "score": vertadier["score"], "total": total}

        current_word = vertadier["words"][vertadier["index"]]
        payload = {
            "state": state,
            "index": vertadier["index"],
            "total": total,
            "score": vertadier["score"],
            "feedback": vertadier["feedback"],
            "word_fr": current_word["word_fr"],
            "seconds_per_word": config.VERTADIER_SECONDS_PER_WORD,
            "time_left": _time_left(vertadier),
        }
        if vertadier["feedback"] is not None:
            # Revele la reponse + l'explication seulement une fois qu'une
            # reponse a ete donnee (ou le temps ecoule) -- jamais avant, pour
            # ne pas spoiler le mot affiche.
            payload["is_occitan"] = bool(current_word["is_occitan"])
            payload["explanation"] = current_word["explanation"]
        return payload

    @staticmethod
    def _duel_payload(state, duel):
        if duel is None:
            # Etat incoherent (ne devrait pas arriver) -- meme repli que
            # _troba_payload/_vertadier_payload ci-dessus.
            return {"state": STATE_MENU, "activities": MENU_ACTIVITIES, "selected_index": 0, "notice": None}

        total = len(duel["questions"])
        if state == STATE_DUEL_FIN:
            score_p1 = duel["score_p1"]
            score_p2 = duel["score_p2"]
            if score_p1 > score_p2:
                winner = "p1"
            elif score_p2 > score_p1:
                winner = "p2"
            else:
                winner = "tie"
            return {
                "state": state,
                "score_p1": score_p1,
                "score_p2": score_p2,
                "total": total,
                "winner": winner,
            }

        current_question = duel["questions"][duel["index"]]
        payload = {
            "state": state,
            "index": duel["index"],
            "total": total,
            "score_p1": duel["score_p1"],
            "score_p2": duel["score_p2"],
            "answered_p1": duel["answered_p1"],
            "answered_p2": duel["answered_p2"],
            "feedback": duel["feedback"],
            "question_fr": current_question["question_fr"],
            "choice_a": current_question["choice_a"],
            "choice_b": current_question["choice_b"],
            "seconds_per_question": config.DUEL_SECONDS_PER_QUESTION,
            "time_left": _time_left(duel),
        }
        if duel["feedback"] is not None:
            # Revele la bonne reponse + l'explication seulement une fois que
            # les deux joueurs ont repondu (ou le temps ecoule) -- jamais
            # avant, pour ne pas influencer le joueur le plus lent.
            payload["correct_choice"] = current_question["correct_choice"]
            payload["explanation"] = current_question["explanation"]
        return payload

    @staticmethod
    def _memoria_choice_payload(state, choice):
        """v0.9 : ecran "Quantas cartas ?" -- propose les 2 tailles definies
        par MEMORIA_CHOICE_OPTIONS, chacune marquee "available" ou non selon
        le contenu reellement eligible au moment ou l'ecran a ete ouvert
        (voir _open_memoria_choice). Le client peut ainsi griser/annoter
        l'option non jouable sans avoir a redemander au serveur."""
        if choice is None:
            # Etat incoherent (ne devrait pas arriver) -- meme repli que les
            # autres jeux ci-dessous.
            return {"state": STATE_MENU, "activities": MENU_ACTIVITIES, "selected_index": 0, "notice": None}

        activity_label_oc = MEMORIA_VARIANTS[choice["activity_id"]]["label_oc"]
        options = [
            {
                "pairs": pairs,
                "cards": pairs * 2,
                "available": pairs <= choice["eligible_count"],
            }
            for pairs in MEMORIA_CHOICE_OPTIONS
        ]
        return {
            "state": state,
            "activity_label_oc": activity_label_oc,
            "options": options,
            "selected_index": choice["selected_index"],
            "notice": choice["notice"],
        }

    @staticmethod
    def _memoria_payload(state, memoria):
        if memoria is None:
            # Etat incoherent (ne devrait pas arriver) -- meme repli que les
            # autres jeux ci-dessus.
            return {"state": STATE_MENU, "activities": MENU_ACTIVITIES, "selected_index": 0, "notice": None}

        total_pairs = memoria["total_pairs"]
        # v0.8 : le libelle occitan de l'activite en cours ("Memòria" ou
        # "Memòria vilatge") est envoye avec le payload, pour que le client
        # puisse afficher le bon en-tete SANS avoir besoin de 2 ecrans
        # distincts -- les deux variantes partagent le meme gabarit HTML/JS
        # (voir MEMORIA_VARIANTS en tete de fichier).
        activity_label_oc = MEMORIA_VARIANTS[memoria["activity_id"]]["label_oc"]
        if state in (STATE_MEMORIA_FIN, STATE_MEMORIA_VILATGE_FIN):
            return {
                "state": state,
                "attempts": memoria["attempts"],
                "total_pairs": total_pairs,
                "activity_label_oc": activity_label_oc,
            }

        matched = memoria["matched"]
        flipped = memoria["flipped"]
        cards_payload = []
        for idx, card in enumerate(memoria["cards"]):
            visible = idx in matched or idx in flipped
            entry = {
                "matched": idx in matched,
                "flipped": idx in flipped,
                # Le contenu (kind/text) n'est envoye que si la carte est
                # effectivement visible cote client (retournee ou figee) --
                # jamais pour une carte face cachee, pour qu'il ne soit pas
                # possible de "lire" la grille entiere via le payload reseau
                # (meme discipline anti-fuite que Vertadièr/Duèl).
                # v0.8 : "kind" vaut desormais "fr" ou "oc" (mot francais ou
                # occitan) au lieu de "image"/"word" -- voir start_memoria.
                "kind": card["kind"] if visible else None,
            }
            if visible:
                entry["text"] = card["text"]
            cards_payload.append(entry)

        return {
            "state": state,
            "cards": cards_payload,
            "cursor": memoria["cursor"],
            "matched_pairs": len(matched) // 2,
            "total_pairs": total_pairs,
            "attempts": memoria["attempts"],
            "feedback": memoria["feedback"],
            "activity_label_oc": activity_label_oc,
        }

    @staticmethod
    def _quiz_payload(state, quiz):
        if quiz is None:
            # Etat incoherent (ne devrait pas arriver) -- meme repli que les
            # autres jeux ci-dessus.
            return {"state": STATE_MENU, "activities": MENU_ACTIVITIES, "selected_index": 0, "notice": None}

        total = len(quiz["questions"])
        if state == STATE_QUIZ_FIN:
            return {"state": state, "score": quiz["score"], "total": total}

        current_question = quiz["questions"][quiz["index"]]
        payload = {
            "state": state,
            "index": quiz["index"],
            "total": total,
            "score": quiz["score"],
            "feedback": quiz["feedback"],
            "question_fr": current_question["question_fr"],
            "choice_a": current_question["choice_a"],
            "choice_b": current_question["choice_b"],
            "choice_c": current_question["choice_c"],
            "seconds_per_question": config.QUIZ_SECONDS_PER_QUESTION,
            "time_left": _time_left(quiz),
        }
        if quiz["feedback"] is not None:
            # Revele la bonne reponse + l'explication seulement une fois
            # qu'une reponse a ete donnee (ou le temps ecoule) -- jamais
            # avant, meme discipline anti-fuite que Vertadièr/Duèl.
            payload["correct_choice"] = current_question["correct_choice"]
            payload["explanation"] = current_question["explanation"]
        return payload
