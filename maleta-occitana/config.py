"""Configuration de la Maleta Occitana.

Etape 1/2 : les reglages restaient de simples constantes/variables
d'environnement. Depuis la v0.2, les reglages que Fabien doit pouvoir changer
SANS toucher au code (PIN admin, theme de couleur, logo/croix personnalises,
mapping manette) vivent dans la table `settings` (voir
managers/settings_manager.py) et sont modifiables depuis l'admin
("Configuration"). Ce fichier garde uniquement : les chemins fixes, les
valeurs qui necessitent un redemarrage de toute facon (HARDWARE_MODE,
DATABASE_PATH...), et les valeurs par defaut utilisees quand aucun reglage
n'a encore ete enregistre en base.
"""

import os

# v0.82 : version affichée dans l'admin (bas de la barre latérale + page de
# connexion, voir blueprints/admin.py inject_app_version() et
# templates/admin/base.html / login.html), demandée par Fabien pour pouvoir
# vérifier d'un coup d'œil que la borne tourne bien sur le code fraîchement
# déployé et pas une version restée en mémoire (service non redémarré,
# navigateur en cache, mauvais dossier déployé...). A METTRE A JOUR à chaque
# nouvelle archive livrée, en même temps que le numéro de version en tête du
# README.md -- les deux doivent toujours rester synchronisés.
APP_VERSION = "1.2"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# v1.2 : version de demonstration (application de bureau Windows/Linux, voir
# desktop/ a la racine du depot). MALETA_DEMO=1 active : un mapping clavier
# par defaut (aucune manette sur un PC de demo), un tag NFC simule pour
# chaque objet et un panneau "Pausar un objècte" sur l'ecran du kiosque (pas
# de lecteur NFC), et un bandeau "Demo" dans l'admin. Jamais active sur la
# borne (install.sh ne la definit pas).
DEMO_MODE = os.environ.get("MALETA_DEMO") == "1"

# v1.2 : dossier des donnees modifiables (base + medias). Par defaut le
# dossier du code, comme avant (rien ne change sur la borne) ; la version de
# demo le place dans le dossier utilisateur, le dossier d'installation d'une
# application de bureau n'etant pas toujours accessible en ecriture.
DATA_DIR = os.environ.get("MALETA_DATA_DIR") or BASE_DIR

# Dossier de la base SQLite
DATABASE_PATH = os.path.join(DATA_DIR, "maleta.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "db", "schema.sql")

# Dossiers medias uploades depuis l'admin (images / audio des objets)
MEDIA_ROOT = os.path.join(DATA_DIR, "media")
OBJECT_IMAGES_DIR = os.path.join(MEDIA_ROOT, "objects", "images")
OBJECT_AUDIO_DIR = os.path.join(MEDIA_ROOT, "objects", "audio")

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "ogg", "m4a"}

# Etape 2 : bibliotheque de medias pour le "Cadre fotó & vidèo" (diaporama /
# ecran de veille). Dossier a part de celui des objets : contenu different
# (photos/videos de la vie d'une Calandreta, pas des illustrations d'objets).
MEDIA_LIBRARY_DIR = os.path.join(MEDIA_ROOT, "library")
ALLOWED_MEDIA_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ALLOWED_MEDIA_VIDEO_EXTENSIONS = {"mp4", "webm", "mov"}

# v0.2 : logo d'ecole / croix occitane personnalises (menu Configuration de
# l'admin), pour remplacer le SVG generique de l'ecran titre. Dossier a part
# des objets/de la bibliotheque : un seul logo et une seule image de croix a
# la fois (voir managers/settings_manager.py, cles "logo_filename"/"crotz_filename").
BRANDING_DIR = os.path.join(MEDIA_ROOT, "branding")
ALLOWED_BRANDING_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "svg"}
# Duree d'affichage par defaut d'une photo dans le diaporama (secondes) si
# aucune duree specifique n'est renseignee dans l'admin. Les videos jouent
# jusqu'a leur fin naturelle, cette valeur ne les concerne pas.
DIAPORAMA_DEFAULT_IMAGE_SECONDS = int(os.environ.get("MALETA_DIAPORAMA_SECONDS", "6"))

# PIN de l'interface d'admin (comme sur Histoires du Soir).
# v0.2 : ceci reste la valeur PAR DEFAUT (utilisee tant qu'aucun PIN n'a ete
# enregistre en base) -- le PIN reellement actif se change desormais depuis
# l'admin (Configuration > mot de passe), voir managers/settings_manager.py
# get_admin_pin(). Cette variable d'environnement reste utile pour reinitialiser
# le PIN en cas d'oubli : MALETA_RESET_ADMIN_PIN=1 au demarrage l'efface de la
# base et retombe sur cette valeur (voir run_pc.py / run_dev.py).
ADMIN_PIN = os.environ.get("MALETA_ADMIN_PIN", "1234")

# Cle secrete Flask (sessions admin). A changer en prod via variable d'environnement.
SECRET_KEY = os.environ.get("MALETA_SECRET_KEY", "dev-secret-a-changer")

# Materiel : "dev" (pas de lecteur NFC branche -> simulation) ou "pc" (petit
# PC Debian avec le vrai lecteur OMNIKEY en USB/PC-SC).
# "pi" reste accepte comme alias historique de "pc" (voir managers/tag_reader.py) :
# le pivot du 13/09/2026 a abandonne la cible Raspberry Pi + PN532 au profit
# d'un petit PC + lecteur OMNIKEY, repris de la brique deja validee sur HDP.
# Se regle automatiquement plus tard ; pour l'instant force via variable d'environnement.
HARDWARE_MODE = os.environ.get("MALETA_HARDWARE", "dev")  # "dev" | "pc"

# Delai d'inactivite (secondes) avant de revenir a l'ecran d'accueil (menu
# "Tria un jòc") depuis l'ecran de decouverte d'un objet. Depuis le
# 14/09/2026, le menu est l'ecran d'accueil par defaut de la borne -- ce
# delai ne concerne plus le diaporama/veille, atteint uniquement de facon
# volontaire (bouton Start ou tuile "Cadre fotó", voir game_controller.py).
IDLE_TIMEOUT_SECONDS = int(os.environ.get("MALETA_IDLE_TIMEOUT", "20"))

# v0.10 (16/09/2026, signale par Fabien) : "verrou d'entree" -- quand un
# meme bouton/touche sert a la fois a VALIDER l'ecran precedent (ex. "select"
# pour lancer un jeu depuis le menu) et a une action DANS le jeu qui s'ouvre
# (ex. "answer_1", si le meme bouton lui est aussi assigne -- possible depuis
# la v0.81, un controle peut declencher plusieurs actions), le meme appui
# physique declenche les deux actions l'une derriere l'autre : la premiere
# fait entrer dans le jeu, la seconde est alors interpretee comme une
# reponse DANS ce jeu, validant sa premiere question sans que le joueur l'ait
# vraiment choisi. GameController ignore desormais toute action recue dans
# les X secondes qui suivent une transition d'ecran (voir _bump_epoch_locked/
# on_action dans managers/game_controller.py) -- assez court pour etre
# imperceptible dans le jeu normal, assez long pour absorber ce genre de
# double-declenchement (synchronise en quelques millisecondes cote manette,
# quelques dizaines de ms cote clavier/reseau).
ACTION_LOCKOUT_SECONDS = float(os.environ.get("MALETA_ACTION_LOCKOUT", "0.35"))

# v1.03 (revue de code) : duree maximale pendant laquelle le lecteur NFC reste
# "en ecoute" apres un clic sur "Associer un nouveau tag" dans l'admin. Passe
# ce delai, le tag pose repart normalement vers le jeu (Descobèrta) au lieu
# d'etre associe -- evite qu'une association oubliee ne detourne le tag d'un
# visiteur bien plus tard. Voir handle_uid_scanned dans app.py.
PAIRING_TIMEOUT_SECONDS = int(os.environ.get("MALETA_PAIRING_TIMEOUT", "60"))

# v1.03 (revue de code) : deconnexion automatique de l'admin apres ce nombre
# de minutes SANS aucune page admin ouverte/rechargee. L'admin est utilisee
# sur la borne elle-meme : sans ce delai, une session restee ouverte laissait
# n'importe quel visiteur entrer dans l'admin via l'icone du menu.
ADMIN_SESSION_IDLE_MINUTES = int(os.environ.get("MALETA_ADMIN_IDLE_MINUTES", "20"))

# Etape 2 : jeu "Tròba l'objècte" (chronometre). Pas encore de page de
# reglages dans l'admin pour ces valeurs -- prevu avec la section "Reglages
# generaux" d'une etape ulterieure (voir concept-borne-interactive.md).
# v0.83 (16/09/2026, demande par Fabien) : 5 -> 10 mots par manche (limite
# haute -- si moins de 10 objets tagues sont disponibles, la manche utilise
# simplement tout ce qu'il y a, voir start_troba : `eligible[:N]` ne plante
# jamais si `eligible` est plus court que N).
TROBA_ROUND_WORD_COUNT = int(os.environ.get("MALETA_TROBA_WORDS", "10"))
TROBA_SECONDS_PER_WORD = int(os.environ.get("MALETA_TROBA_SECONDS", "15"))
# Duree d'affichage du retour visuel (correct/faux) avant de continuer
TROBA_FEEDBACK_SECONDS = 1.5
# Duree d'affichage de l'ecran de score avant retour automatique a la veille
TROBA_FIN_DISPLAY_SECONDS = 12

# v0.2 : jeu "Ven de l'occitan (ex-« Ven de l'occitan »)" (vrai/faux, reponse a la manette -- voir
# managers/input_bus.py, actions answer_1/answer_2). Memes principes de
# duree que Tròba l'objècte ci-dessus.
VERTADIER_ROUND_WORD_COUNT = int(os.environ.get("MALETA_VERTADIER_WORDS", "5"))
VERTADIER_SECONDS_PER_WORD = int(os.environ.get("MALETA_VERTADIER_SECONDS", "12"))
VERTADIER_FEEDBACK_SECONDS = 2.5  # un peu plus long que Tròba : il y a une explication a lire
VERTADIER_FIN_DISPLAY_SECONDS = 12

# v0.7 (15/09/2026) : jeu "Duèl Occitan" (2 joueurs, 2 reponses possibles par
# question, chaque joueur repond de son cote -- voir managers/game_controller.py
# et managers/input_bus.py, actions duel_p1_a/duel_p1_b/duel_p2_a/duel_p2_b).
# Memes principes de duree que Ven de l'occitan ci-dessus ; le delai par
# question est un peu plus long par defaut car il faut laisser le temps aux
# DEUX joueurs de repondre, pas a un seul.
# v0.83 (16/09/2026, demande par Fabien) : 6 -> 10 questions par manche
# (meme principe que TROBA_ROUND_WORD_COUNT ci-dessus -- limite haute, pas un
# minimum : moins de contenu disponible utilise simplement tout ce qu'il y a).
DUEL_ROUND_QUESTION_COUNT = int(os.environ.get("MALETA_DUEL_QUESTIONS", "10"))
DUEL_SECONDS_PER_QUESTION = int(os.environ.get("MALETA_DUEL_SECONDS", "15"))
DUEL_FEEDBACK_SECONDS = 3.0  # un peu plus long que Vertadièr : 2 scores + 1 explication a lire
DUEL_FIN_DISPLAY_SECONDS = 14

# v0.72 (15/09/2026) : jeu "Memòria" (piste bonus tranchee le 15/09/2026 --
# associer deux cartes qui vont ensemble). Decide 100% a l'ecran/manette, SANS
# les objets physiques (le lecteur NFC ne peut scanner qu'un seul objet a la
# fois, incompatible avec un vrai memory a 2 cartes retournees -- voir
# concept-borne-interactive.md).
#
# v0.8 (evolution demandee par Fabien) : chaque paire de cartes montre
# desormais le mot FRANCAIS d'un cote et le mot OCCITAN de l'autre (plus
# jamais une image + un mot) -- plus pertinent pedagogiquement, ca fait
# vraiment travailler la traduction plutot que juste retrouver 2 images
# identiques. Deux variantes reutilisent la MEME mecanique generique
# (managers/game_controller.py, MEMORIA_VARIANTS) avec un contenu different :
# "Memòria" reutilise les objets deja saisis pour Descobèrta/Tròba (aucun
# nouveau contenu a saisir, name_fr/name_oc sont deja obligatoires sur chaque
# objet) ; "Memòria vilatge" (nouvelle activite) reutilise la nouvelle table
# `villages` (noms de villes/vilatges en francais et en occitan, a saisir
# depuis Admin > Vilatges -- source fiable exigee, jamais improvise, meme
# principe que Vertadièr/Duèl). Les deux variantes partagent les memes
# reglages de duree ci-dessous.
#
# v0.83 (16/09/2026, demande par Fabien) : remplace l'ancien nombre de paires
# FIXE (MEMORIA_PAIR_COUNT = 6) par un choix entre DEUX tailles de partie,
# tire au hasard a chaque lancement quand assez de contenu est disponible
# pour les deux, sinon repli automatique sur la petite taille.
#
# v0.9 (16/09/2026, demande par Fabien) : DEUX changements. (1) Le tirage au
# SORT est remplace par un ECRAN DE CHOIX explicite au lancement ("Memòria"/
# "Memòria vilatge" ouvrent desormais un ecran "Quantas cartas ?" avec les 2
# tailles proposees, plutot que de decider a la place du visiteur -- voir
# STATE_MEMORIA_CHOICE/STATE_MEMORIA_VILATGE_CHOICE et _open_memoria_choice
# dans managers/game_controller.py). (2) Les tailles elles-memes passent de
# 5/10 a 6/12 paires (12/24 cartes) : Fabien a demande ce changement pour un
# AFFICHAGE PLUS SYMETRIQUE -- avec MEMORIA_GRID_COLUMNS = 6 colonnes fixes
# (voir plus bas), 12 cartes forment une grille 6x2 et 24 cartes une grille
# 6x4, deux rectangles bien reguliers (5/10 cartes sur 6 colonnes donnait des
# grilles incompletes, moins harmonieuses). MEMORIA_PAIR_COUNT_SMALL reste le
# minimum de contenu requis pour pouvoir jouer du tout (en dessous, un
# menu_notice s'affiche plutot que de proposer un choix inutilisable).
MEMORIA_PAIR_COUNT_SMALL = int(os.environ.get("MALETA_MEMORIA_PAIRS_SMALL", "6"))
MEMORIA_PAIR_COUNT_LARGE = int(os.environ.get("MALETA_MEMORIA_PAIRS_LARGE", "12"))
# v0.9 : nombre de colonnes FIXE de la grille de cartes (voir kiosk-base.css,
# .memoria-grid -- couplage a garder synchronise si cette valeur change un
# jour). Fixe (plutot que "auto-fit" comme avant) pour deux raisons : (1) un
# affichage plus symetrique/previsible (voir commentaire ci-dessus), et (2)
# permettre une navigation manette/clavier HAUT/BAS fiable dans la grille
# (voir _move_memoria_cursor : monter/descendre d'une rangee, c'est ajouter
# ou retirer ce nombre de colonnes a l'index du curseur -- ne fonctionne
# juste que si le nombre de colonnes reellement affiche cote client est
# TOUJOURS le meme que celui-ci, d'ou le passage a une grille fixe).
MEMORIA_GRID_COLUMNS = int(os.environ.get("MALETA_MEMORIA_GRID_COLUMNS", "6"))
# Duree d'affichage des 2 cartes retournees avant de les refermer (si elles ne
# correspondent pas) ou de les figer definitivement (si elles correspondent) --
# assez long pour qu'un enfant ait le temps de memoriser ce qu'il voit.
MEMORIA_REVEAL_SECONDS = 1.4
MEMORIA_FIN_DISPLAY_SECONDS = 12

# v0.8 : jeu "Quiz Calandreta" (question de culture/langue occitane, 3
# reponses possibles a/b/c -- voir managers/game_controller.py et
# managers/quiz_manager.py). Memes principes de duree que Ven de
# l'occitan/Duèl Occitan ci-dessus ; le delai par question est un peu plus long
# par defaut que Vertadièr car il y a 3 choix a lire au lieu de 2.
QUIZ_ROUND_QUESTION_COUNT = int(os.environ.get("MALETA_QUIZ_QUESTIONS", "6"))
QUIZ_SECONDS_PER_QUESTION = int(os.environ.get("MALETA_QUIZ_SECONDS", "15"))
QUIZ_FEEDBACK_SECONDS = 3.0
QUIZ_FIN_DISPLAY_SECONDS = 14
