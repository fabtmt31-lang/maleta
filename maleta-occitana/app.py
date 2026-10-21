"""Point d'assemblage de l'appli Maleta Occitana (factory Flask).

Etape 1 : mode Descobèrta d'objèctes + admin des objets/tags.
Etape 2 : menu "Tria un jòc", jeu "Tròba l'objècte", mode "Cadre fotó &
vidèo" (voir managers/game_controller.py pour le detail des etats).
Voir concept-borne-interactive.md (projet claude.ai "calandreta") pour la
vue d'ensemble et les etapes suivantes prevues.
"""

import logging
import os
import threading
import time

from flask import Flask, send_from_directory
from flask_socketio import SocketIO, emit

import config
from db.database import close_db, init_db
from managers.tag_reader import get_tag_reader
from managers.input_bus import InputBus
from managers.game_controller import GameController
from managers import settings_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY

    init_db()
    app.teardown_appcontext(close_db)

    with app.app_context():
        # v0.2 : filet de securite en cas de PIN admin oublie apres un
        # changement depuis l'admin -- MALETA_RESET_ADMIN_PIN=1 au demarrage
        # efface le PIN enregistre en base, get_admin_pin() retombe alors sur
        # config.ADMIN_PIN (MALETA_ADMIN_PIN). A retirer de l'environnement
        # une fois le PIN reinitialise, sinon impossible de le changer a
        # nouveau depuis l'admin (il serait efface a chaque redemarrage).
        if os.environ.get("MALETA_RESET_ADMIN_PIN") == "1":
            settings_manager.reset_admin_pin()
            logger.warning(
                "PIN admin reinitialise a la valeur par defaut (MALETA_RESET_ADMIN_PIN=1) -- "
                "pense a retirer cette variable d'environnement."
            )
        stored_button_map = settings_manager.get_gamepad_button_map()
        stored_hat_map = settings_manager.get_gamepad_hat_map()
        stored_axis_map = settings_manager.get_gamepad_axis_map()

    socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

    # Etat partage entre le flux "jeu" et le flux "admin" (associer un tag).
    # Un dict simple suffit pour l'etape 1 ; un seul admin actif a la fois est
    # l'hypothese raisonnable pour une borne de stand.
    # v1.03 (revue de code) : + "pairing_started_at" (delai d'expiration),
    # "last_paired_object_id" (a quel objet le dernier tag a ete associe) et
    # un verrou -- ce dict est lu/modifie a la fois par le thread du lecteur
    # NFC et par les requetes de l'admin. Voir handle_uid_scanned.
    admin_state = {
        "pairing_object_id": None,
        "pairing_started_at": None,
        "last_paired_uid": None,
        "last_paired_object_id": None,
        "lock": threading.Lock(),
    }

    game_controller = GameController(socketio, app)

    @socketio.on("connect", namespace="/kiosk")
    def kiosk_connect():
        # Renvoie l'etat courant a chaque (re)connexion (ecran rafraichi,
        # navigateur relance...) pour ne jamais rester desynchronise.
        emit("state_changed", game_controller.get_state_payload())

    def handle_uid_scanned(uid):
        """Point d'entree unique pour tout tag scanne, qu'il vienne du vrai
        lecteur OMNIKEY (sur le petit PC) ou d'un scan simule (dev / admin).

        v1.03 (revue de code) -- trois defauts corriges sur l'association :
        - le mode "association" restait arme indefiniment si l'admin quittait
          la page sans poser de tag : le tag du visiteur suivant (meme des
          heures plus tard) etait alors silencieusement re-associe a cet
          objet au lieu d'ouvrir Descobèrta. Il expire desormais tout seul
          (config.PAIRING_TIMEOUT_SECONDS), et la page admin l'annule quand
          on la quitte ou qu'on clique "Annuler".
        - si l'objet avait ete supprime entre-temps, l'ecriture en base
          echouait AVANT la remise a zero : chaque scan suivant echouait
          pareil, jusqu'au redemarrage du service. Le mode est desormais
          desarme avant toute ecriture, et l'objet verifie.
        - le message de log affichait tout le dict (objet "None") au lieu de
          l'objet reellement associe."""
        with admin_state["lock"]:
            object_id = admin_state["pairing_object_id"]
            started_at = admin_state["pairing_started_at"]
            # Desarme dans tous les cas : un seul tag par demande d'association.
            admin_state["pairing_object_id"] = None
            admin_state["pairing_started_at"] = None
        expired = (
            object_id is not None
            and started_at is not None
            and time.monotonic() - started_at > config.PAIRING_TIMEOUT_SECONDS
        )
        if object_id is None or expired:
            if expired:
                logger.info("Association de tag expiree (objet %s) - scan transmis au jeu", object_id)
            game_controller.on_tag_scanned(uid)
            return

        from managers import object_manager

        with app.app_context():
            if object_manager.get_object(object_id) is None:
                logger.warning("Association annulee : l'objet %s n'existe plus (tag %s ignore)", object_id, uid)
                return
            object_manager.pair_tag(uid, object_id)
        with admin_state["lock"]:
            admin_state["last_paired_uid"] = uid
            admin_state["last_paired_object_id"] = object_id
        socketio.emit("tag_paired", {"uid": uid}, namespace="/admin")
        logger.info("Tag %s associe a l'objet %s", uid, object_id)

    tag_reader = get_tag_reader(config.HARDWARE_MODE)
    tag_reader.start(handle_uid_scanned)

    # v0.2 : reprend le mapping enregistre en base (admin > Configuration >
    # Manette) s'il existe, sinon le mapping par defaut de input_bus.py.
    # v0.4 : idem pour hat_map/axis_map -- une manette dont la croix
    # directionnelle est remontee comme un hat pygame ou comme des axes
    # dedies (plutot que comme des boutons) doit aussi retrouver son
    # assignation apres un redemarrage du service, pas seulement le mapping
    # bouton (voir managers/settings_manager.py et managers/input_bus.py).
    input_bus = InputBus(
        button_map=stored_button_map,
        hat_map=stored_hat_map,
        axis_map=stored_axis_map,
    )
    input_bus.start(game_controller.on_action)

    # Rendus accessibles aux blueprints sans import circulaire
    app.extensions["socketio"] = socketio
    app.extensions["tag_reader"] = tag_reader
    app.extensions["input_bus"] = input_bus
    app.extensions["game_controller"] = game_controller
    app.extensions["admin_state"] = admin_state

    from blueprints.kiosk import kiosk_bp
    from blueprints.admin import admin_bp

    app.register_blueprint(kiosk_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.route("/media/objects/images/<path:filename>")
    def media_object_image(filename):
        return send_from_directory(config.OBJECT_IMAGES_DIR, filename)

    @app.route("/media/objects/audio/<path:filename>")
    def media_object_audio(filename):
        return send_from_directory(config.OBJECT_AUDIO_DIR, filename)

    @app.route("/media/library/<path:filename>")
    def media_library_file(filename):
        """Etape 2 : photos/videos du 'Cadre fotó & vidèo' (diaporama)."""
        return send_from_directory(config.MEDIA_LIBRARY_DIR, filename)

    @app.route("/media/branding/<path:filename>")
    def media_branding_file(filename):
        """v0.2 : logo d'ecole / croix occitane personnalises (Configuration)."""
        return send_from_directory(config.BRANDING_DIR, filename)

    app.extensions["socketio_instance_for_run"] = socketio  # lu par run_dev.py

    return app, socketio


# Pas de bloc `if __name__ == "__main__"` ici : les points d'entree (run_dev.py
# pour le developpement, run_pc.py pour le petit PC de production) restent
# separes de l'assemblage de l'appli, meme organisation que sur Histoires du Soir.
