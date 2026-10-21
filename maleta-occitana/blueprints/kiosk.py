"""Ecran du kiosque (ce qui s'affiche en plein ecran sur la borne) + routes
de test pour developper sans lecteur NFC ni manette branches."""

from flask import Blueprint, render_template, jsonify, current_app, abort, url_for

import config
from managers import object_manager, settings_manager
from managers.tag_reader import SimulatedTagReader

kiosk_bp = Blueprint("kiosk", __name__)


@kiosk_bp.route("/")
def index():
    game_controller = current_app.extensions["game_controller"]
    # v0.2 : logo/croix personnalises (admin > Configuration). v1.1 : le
    # theme de couleur est remplace par un modele d'interface complet
    # (Senhal/Mercat/Nuèch, voir settings_manager.TEMPLATES).
    # Lu a chaque chargement de page (pas via websocket) : un changement fait
    # depuis l'admin necessite de recharger l'ecran du kiosque (F5, ou
    # redemarrer le service) pour etre applique -- suffisant pour un reglage
    # qu'on ne change pas en cours d'evenement, pas besoin de plus complexe.
    branding = settings_manager.get_branding()
    return render_template(
        "kiosk.html",
        initial_state=game_controller.get_state_payload(),
        branding=branding,
        template=branding["theme"],
        # v1.1 : nombre de colonnes de la grille Memòria (doit correspondre a
        # la navigation haut/bas cote serveur, voir config.py).
        memoria_grid_columns=config.MEMORIA_GRID_COLUMNS,
        # v0.8 : mapping clavier (Configuration > Manette/Clavier) -- envoye
        # au chargement de page, meme principe que initial_state, pour que
        # kiosk.js sache quelles touches declenchent quelles actions (voir
        # window.MALETA_KEY_MAP dans kiosk.html).
        key_map=settings_manager.get_gamepad_key_map(),
        # v0.10 (demande par Fabien) : libelle COURT du vrai controle assigne
        # a chaque action (ex. "3", "▲", "A2+", "E", ou une combinaison "3 / E"
        # si manette ET clavier sont assignes) -- rendu ici, une seule fois au
        # chargement de page (meme principe que key_map ci-dessus : un
        # changement de mapping depuis l'admin necessite un rechargement pour
        # etre pris en compte). Remplace les lettres A/B/X/Y codees en dur qui
        # ne correspondaient plus forcement a rien une fois le mapping
        # personnalise -- voir templates/kiosk.html.
        action_labels=settings_manager.build_kiosk_action_labels(),
        # v0.10 (demande par Fabien) : quelques textes visiteur (ecran
        # d'accueil + menu) rendus editables depuis Configuration, pour
        # qu'une ecole puisse adapter le message a son contexte -- meme
        # principe de rendu qu'au-dessus (lu une fois au chargement de page).
        texts=settings_manager.get_kiosk_texts(),
        demo_mode=config.DEMO_MODE,
    )


@kiosk_bp.route("/dev/panel")
def dev_panel():
    """Page de test, utile uniquement en mode dev (pas de lecteur NFC / manette
    branches) : liste les objets et permet de simuler la pose de leur tag."""
    objects = object_manager.list_objects()
    objects_with_tags = []
    for obj in objects:
        tags = object_manager.list_tags_for_object(obj["id"])
        objects_with_tags.append({"object": obj, "tags": tags})
    return render_template("dev_panel.html", objects_with_tags=objects_with_tags)


@kiosk_bp.route("/dev/simulate_tag/<uid>", methods=["POST"])
def dev_simulate_tag(uid):
    tag_reader = current_app.extensions["tag_reader"]
    if not isinstance(tag_reader, SimulatedTagReader):
        return jsonify({"error": "simulation indisponible (lecteur NFC reel actif)"}), 400
    tag_reader.simulate_uid(uid)
    return jsonify({"ok": True, "uid": uid})


@kiosk_bp.route("/dev/action/<action>", methods=["POST"])
def dev_action(action):
    """Simule une action manette (mode dev, sans manette branchee) : back,
    select, left, right, answer_1, answer_2, start_idle. Etape 2 : remplace
    l'ancienne route /dev/back, moins generique (elle forcait toujours le
    retour a l'accueil, sans passer par le dispatcher d'etats)."""
    current_app.extensions["game_controller"].on_action(action)
    return jsonify({"ok": True, "action": action})


# --- Version de demo (v1.2) ---------------------------------------------------
# Aucun lecteur NFC sur un PC de demo : le panneau "Pausar un objècte" du
# kiosque (static/js/kiosk-demo.js) liste les objets actifs et "pose" celui
# qu'on clique, via son tag simule (voir object_manager.ensure_demo_tags).

@kiosk_bp.route("/demo/objects")
def demo_objects():
    if not config.DEMO_MODE:
        abort(404)
    object_manager.ensure_demo_tags()
    items = []
    for obj in object_manager.list_objects(only_active=True):
        items.append({
            "id": obj["id"],
            "name_oc": obj["name_oc"],
            "name_fr": obj["name_fr"],
            "image": url_for("media_object_image", filename=obj["image_filename"]) if obj["image_filename"] else None,
        })
    return jsonify({"objects": items})


@kiosk_bp.route("/demo/place/<int:object_id>", methods=["POST"])
def demo_place(object_id):
    if not config.DEMO_MODE:
        abort(404)
    tag_reader = current_app.extensions["tag_reader"]
    if not isinstance(tag_reader, SimulatedTagReader):
        return jsonify({"error": "simulation indisponible (lecteur NFC reel actif)"}), 400
    object_manager.ensure_demo_tags()
    tags = object_manager.list_tags_for_object(object_id)
    if not tags:
        return jsonify({"error": "objet introuvable"}), 404
    tag_reader.simulate_uid(tags[0]["uid"])
    return jsonify({"ok": True})
