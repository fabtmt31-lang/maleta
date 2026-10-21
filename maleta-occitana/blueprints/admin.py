"""Interface d'administration (protegee par PIN, comme sur HDP).

Etape 1 : section "Objets & tags", la plus urgente (elle alimente le mode
Descobèrta d'objèctes).
Etape 2 : section "Fotos & vidèos" (bibliotheque du "Cadre fotó & vidèo").
Ven de l'occitan (ex-« Ven de l'occitan ») / Quiz / Reglages generaux viendront s'ajouter au meme
gabarit dans une etape ulterieure.
"""

import io
import time
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash,
    current_app, jsonify, send_file,
)

import config
from managers import (
    content_transfer, duel_manager, media_manager, mediatheque_manager, object_manager, quiz_manager, settings_manager,
    vertadier_manager, village_manager,
)
from managers.tag_reader import SimulatedTagReader

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.login"))
        # v1.03 (revue de code) : deconnexion automatique apres
        # config.ADMIN_SESSION_IDLE_MINUTES sans activite dans l'admin. L'admin
        # s'utilise sur la borne elle-meme : une session restee ouverte
        # laissait n'importe quel visiteur y entrer via l'icone du menu.
        # time.time() (et non monotonic) : l'horodatage vit dans le cookie de
        # session, il doit rester valable d'un redemarrage du service a l'autre.
        now = time.time()
        last_seen = session.get("admin_last_seen", now)
        if now - last_seen > config.ADMIN_SESSION_IDLE_MINUTES * 60:
            session.clear()
            flash("Session expirée après une période d'inactivité — reconnecte-toi.")
            return redirect(url_for("admin.login"))
        session["admin_last_seen"] = now
        return view(*args, **kwargs)
    return wrapped


@admin_bp.context_processor
def inject_app_version():
    """v0.82 : rend `app_version` disponible dans TOUTES les pages admin, y
    compris la page de connexion (contrairement a inject_sidebar_counts()
    ci-dessous, qui ne s'active qu'une fois connecte) -- demande par Fabien
    pour pouvoir verifier en un coup d'oeil, sans meme se connecter, que la
    version deployee correspond bien a la derniere archive envoyee (le
    correctif v0.81 sur le partage bouton/touche ne semblait pas s'appliquer
    chez lui, l'hypothese la plus probable etant un service non redemarre ou
    un navigateur qui sert une version en cache)."""
    return {"app_version": config.APP_VERSION, "demo_mode": config.DEMO_MODE}


@admin_bp.context_processor
def inject_ui_template():
    """v1.1 : l'admin prend l'apparence du modele d'interface choisi pour la
    borne (Senhal/Mercat/Nuèch, voir settings_manager.TEMPLATES) -- y compris
    la page de connexion. Voir <body data-template> dans base.html/login.html
    et les blocs [data-template=...] de static/css/admin.css."""
    try:
        template = settings_manager.get_theme()
    except Exception:  # base pas encore initialisee : apparence par defaut
        template = settings_manager.DEFAULT_THEME
    return {"ui_template": template}


@admin_bp.context_processor
def inject_sidebar_counts():
    """v0.5 (refonte visuelle) : la barre latérale groupée (maquette 1k)
    affiche un compteur à côté de chaque section ("Objèctes & tags 24",
    etc.) -- calculé une fois ici plutôt que dans chaque route, pour ne pas
    avoir à y penser à chaque nouvelle page admin (templates/admin/base.html
    est le seul a s'en servir). Ne fait aucune requête tant que la session
    n'est pas connectée (page de login), pour ne pas toucher la base sans
    raison."""
    if not session.get("admin_logged_in"):
        return {}
    return {
        "sidebar_counts": {
            "objects": len(object_manager.list_objects()),
            "media": len(media_manager.list_media()),
            "vertadier": len(vertadier_manager.list_words()),
            "duel": len(duel_manager.list_questions()),
            "villages": len(village_manager.list_villages()),
            "quiz": len(quiz_manager.list_questions()),
        }
    }


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("pin") == settings_manager.get_admin_pin():
            session["admin_logged_in"] = True
            session["admin_last_seen"] = time.time()
            # v1.1 : ouvre le tableau de bord (etat de chaque jeu) plutot que
            # directement la liste des objets.
            return redirect(url_for("admin.dashboard"))
        flash("Code PIN incorrect")
    demo_pin = None
    if config.DEMO_MODE and settings_manager.get_admin_pin() == config.ADMIN_PIN:
        demo_pin = config.ADMIN_PIN
    return render_template("admin/login.html", demo_pin=demo_pin)


@admin_bp.route("/logout")
def logout():
    # v0.6 : ramene a l'accueil du kiosque plutot qu'a l'ecran de login admin
    # -- signale par Fabien (l'admin est censee etre utilisee ponctuellement
    # depuis la borne, pas laissee ouverte sur l'ecran de connexion apres
    # deconnexion). Se reconnecter reste possible via /admin (icone du menu
    # ou raccourci clavier), qui redemande le PIN normalement.
    session.pop("admin_logged_in", None)
    return redirect(url_for("kiosk.index"))


@admin_bp.route("/")
@login_required
def dashboard():
    """v1.1 (maquettes « 3 directions ») : une carte par jeu de la borne, avec
    le nombre de contenus actifs et un badge « Jogable » / « A completar »
    calcule avec les MEMES seuils que ceux du kiosque (voir game_controller :
    un jeu sous le seuil affiche un message au visiteur au lieu de se lancer)."""
    objects = object_manager.list_objects()
    media = media_manager.list_media()
    vertadier_words = vertadier_manager.list_words()
    duel_questions = duel_manager.list_questions()
    villages = village_manager.list_villages()
    quiz_questions = quiz_manager.list_questions()
    disk = mediatheque_manager.disk_usage()

    nb_objects_active = len([o for o in objects if o["active"]])
    nb_objects_tagged = len(object_manager.list_objects_with_tag(only_active=True))
    nb_media_active = len([m for m in media if m["active"]])
    nb_vertadier_active = len([w for w in vertadier_words if w["active"]])
    nb_duel_active = len([q for q in duel_questions if q["active"]])
    nb_villages_active = len([v for v in villages if v["active"]])
    nb_quiz_active = len([q for q in quiz_questions if q["active"]])
    memoria_min = config.MEMORIA_PAIR_COUNT_SMALL

    def game(game_id, label, count, unit, playable, manage_endpoint, add_endpoint, need):
        return {
            "id": game_id, "label": label, "count": count, "unit": unit,
            "playable": playable, "need": need,
            "url": url_for(manage_endpoint if playable else add_endpoint),
        }

    games = [
        game("troba_objecte", "Tròba l'objècte", nb_objects_tagged, "objèctes taguejats",
             nb_objects_tagged >= 1, "admin.objects_list", "admin.objects_list",
             "au moins 1 objet actif avec un tag NFC"),
        game("vertadier", "Ven de l'occitan ?", nb_vertadier_active, "mots",
             nb_vertadier_active >= 1, "admin.vertadier_list", "admin.vertadier_new",
             "au moins 1 mot actif"),
        game("duel_occitan", "Duèl Occitan", nb_duel_active, "questions",
             nb_duel_active >= 1, "admin.duel_list", "admin.duel_new",
             "au moins 1 question active"),
        game("memoria", "Memòria", nb_objects_active, "objèctes actius",
             nb_objects_active >= memoria_min, "admin.objects_list", "admin.object_new",
             f"au moins {memoria_min} objets actifs"),
        game("memoria_vilatge", "Memòria vilatge", nb_villages_active, "vilatges",
             nb_villages_active >= memoria_min, "admin.villages_list", "admin.village_new",
             f"au moins {memoria_min} vilatges actifs"),
        game("quiz_calandreta", "Quiz Calandreta", nb_quiz_active, "questions",
             nb_quiz_active >= 1, "admin.quiz_list", "admin.quiz_new",
             "au moins 1 question active"),
    ]

    return render_template(
        "admin/dashboard.html",
        games=games,
        nb_games_to_complete=len([g for g in games if not g["playable"]]),
        nb_objects=len(objects),
        nb_objects_active=nb_objects_active,
        nb_media=len(media),
        nb_media_active=nb_media_active,
        memoria_min_pairs=memoria_min,
        memoria_max_pairs=config.MEMORIA_PAIR_COUNT_LARGE,
        disk=disk,
        disk_free_label=mediatheque_manager.format_bytes(disk["free_bytes"]),
        disk_total_label=mediatheque_manager.format_bytes(disk["total_bytes"]),
    )


# --- Objets ----------------------------------------------------------------

@admin_bp.route("/objects")
@login_required
def objects_list():
    objects = object_manager.list_objects()
    tags_by_object = {
        obj["id"]: object_manager.list_tags_for_object(obj["id"]) for obj in objects
    }
    return render_template("admin/objects_list.html", objects=objects, tags_by_object=tags_by_object)


@admin_bp.route("/objects/new", methods=["GET", "POST"])
@login_required
def object_new():
    if request.method == "POST":
        try:
            _save_object_form()
        except ValueError as exc:
            # v1.03 : un fichier refuse (extension non autorisee) donnait une
            # erreur 500 -- on reaffiche le formulaire, saisie conservee.
            flash(f"Fichier refusé : {exc}")
            return render_template("admin/object_form.html", obj=None, draft=request.form)
        return redirect(url_for("admin.objects_list"))
    return render_template("admin/object_form.html", obj=None)


@admin_bp.route("/objects/<int:object_id>/edit", methods=["GET", "POST"])
@login_required
def object_edit(object_id):
    obj = object_manager.get_object(object_id)
    if obj is None:
        flash("Objet introuvable")
        return redirect(url_for("admin.objects_list"))

    draft = None
    if request.method == "POST":
        try:
            _save_object_form(object_id=object_id)
            return redirect(url_for("admin.objects_list"))
        except ValueError as exc:
            # v1.03 : voir object_new -- plus d'erreur 500 sur un fichier refuse
            flash(f"Fichier refusé : {exc}")
            draft = request.form

    tags = object_manager.list_tags_for_object(object_id)
    admin_state = current_app.extensions["admin_state"]
    pairing_active = admin_state["pairing_object_id"] == object_id
    is_simulated = isinstance(current_app.extensions["tag_reader"], SimulatedTagReader)
    return render_template(
        "admin/object_form.html",
        obj=obj,
        draft=draft,
        tags=tags,
        pairing_active=pairing_active,
        is_simulated=is_simulated,
    )


@admin_bp.route("/objects/<int:object_id>/delete", methods=["POST"])
@login_required
def object_delete(object_id):
    # v1.03 : desarme une association de tag en attente sur cet objet
    admin_state = current_app.extensions["admin_state"]
    with admin_state["lock"]:
        if admin_state["pairing_object_id"] == object_id:
            admin_state["pairing_object_id"] = None
            admin_state["pairing_started_at"] = None
    object_manager.delete_object(object_id)
    flash("Objet supprime (les tags associes restent en base, a re-associer si besoin)")
    return redirect(url_for("admin.objects_list"))


@admin_bp.route("/objects/<int:object_id>/toggle_active", methods=["POST"])
@login_required
def object_toggle_active(object_id):
    obj = object_manager.get_object(object_id)
    if obj is None:
        # v1.03 : element supprime entre-temps (page perimee, 2e onglet) -- evitait une erreur 500
        flash("Élément introuvable (déjà supprimé ?)")
        return redirect(url_for("admin.objects_list"))
    object_manager.set_object_active(object_id, not obj["active"])
    return redirect(url_for("admin.objects_list"))


def _save_object_form(object_id=None):
    name_oc = request.form.get("name_oc", "").strip()
    name_fr = request.form.get("name_fr", "").strip()
    category = request.form.get("category", "").strip()
    active = request.form.get("active") == "on"

    image_filename = None
    audio_filename = None
    if "image" in request.files and request.files["image"].filename:
        image_filename = object_manager.save_image(request.files["image"])
    else:
        # v0.6 : pas de nouvel upload -- l'utilisateur a peut-etre choisi un
        # fichier deja present dans la médiathèque via le sélecteur.
        image_filename = mediatheque_manager.resolve_existing(
            "object_image", request.form.get("existing_image_filename", "")
        )
    if "audio" in request.files and request.files["audio"].filename:
        audio_filename = object_manager.save_audio(request.files["audio"])
    else:
        audio_filename = mediatheque_manager.resolve_existing(
            "object_audio", request.form.get("existing_audio_filename", "")
        )

    if object_id is None:
        object_manager.create_object(name_oc, name_fr, category, image_filename, audio_filename)
    else:
        object_manager.update_object(
            object_id, name_oc, name_fr, category, active, image_filename, audio_filename,
            clear_image=request.form.get("remove_image") == "on",
            clear_audio=request.form.get("remove_audio") == "on",
        )


# --- Association d'un tag NFC ------------------------------------------------

@admin_bp.route("/objects/<int:object_id>/pair_tag/start", methods=["POST"])
@login_required
def pair_tag_start(object_id):
    """Met le lecteur "en ecoute" pour le prochain tag pose : c'est ce tag qui
    sera associe a cet objet. Voir handle_uid_scanned() dans app.py."""
    admin_state = current_app.extensions["admin_state"]
    if object_manager.get_object(object_id) is None:
        return jsonify({"error": "objet introuvable"}), 404
    with admin_state["lock"]:
        admin_state["pairing_object_id"] = object_id
        # v1.03 : l'ecoute expire toute seule (voir handle_uid_scanned, app.py)
        admin_state["pairing_started_at"] = time.monotonic()
        admin_state["last_paired_uid"] = None
        admin_state["last_paired_object_id"] = None
    return jsonify({"ok": True, "timeout_seconds": config.PAIRING_TIMEOUT_SECONDS})


@admin_bp.route("/objects/<int:object_id>/pair_tag/cancel", methods=["POST"])
@login_required
def pair_tag_cancel(object_id):
    """v1.03 : bouton "Annuler" de la page objet, et envoye automatiquement
    quand on quitte cette page (voir object_form.html) -- sans ca, le mode
    association restait arme apres le depart de l'admin et detournait le tag
    du prochain visiteur."""
    admin_state = current_app.extensions["admin_state"]
    with admin_state["lock"]:
        if admin_state["pairing_object_id"] == object_id:
            admin_state["pairing_object_id"] = None
            admin_state["pairing_started_at"] = None
    return jsonify({"ok": True})


@admin_bp.route("/objects/<int:object_id>/pair_tag/status")
@login_required
def pair_tag_status(object_id):
    """Interrogee en boucle par la page (toutes les secondes) pendant
    l'association, pour savoir si un tag vient d'etre associe."""
    admin_state = current_app.extensions["admin_state"]
    with admin_state["lock"]:
        waiting = admin_state["pairing_object_id"] == object_id
        started_at = admin_state["pairing_started_at"]
        # v1.03 : uniquement le tag associe a CET objet (avant : le dernier
        # tag associe, quel que soit l'objet)
        paired = (
            admin_state["last_paired_uid"]
            if admin_state["last_paired_object_id"] == object_id
            else None
        )
    if waiting and started_at is not None and time.monotonic() - started_at > config.PAIRING_TIMEOUT_SECONDS:
        waiting = False
    return jsonify({"waiting": waiting, "paired_uid": paired})


@admin_bp.route("/objects/<int:object_id>/pair_tag/simulate", methods=["POST"])
@login_required
def pair_tag_simulate(object_id):
    """Bouton "simuler un scan" en mode dev (pas de lecteur NFC branche)."""
    tag_reader = current_app.extensions["tag_reader"]
    if not isinstance(tag_reader, SimulatedTagReader):
        return jsonify({"error": "simulation indisponible (lecteur NFC reel actif)"}), 400
    if object_manager.get_object(object_id) is None:
        return jsonify({"error": "objet introuvable"}), 404
    fake_uid = request.form.get("uid") or f"SIMU-{object_id}"
    tag_reader.simulate_uid(fake_uid)
    return jsonify({"ok": True, "uid": fake_uid})


@admin_bp.route("/objects/<int:object_id>/unpair_tag/<uid>", methods=["POST"])
@login_required
def unpair_tag(object_id, uid):
    object_manager.unpair_tag(uid)
    return redirect(url_for("admin.object_edit", object_id=object_id))


# --- Fotos & vidèos (Etape 2) ------------------------------------------------

@admin_bp.route("/media")
@login_required
def media_list():
    media = media_manager.list_media()
    return render_template(
        "admin/media_list.html", media=media, default_seconds=config.DIAPORAMA_DEFAULT_IMAGE_SECONDS
    )


@admin_bp.route("/media/new", methods=["GET", "POST"])
@login_required
def media_new():
    if request.method == "POST":
        error = _save_media_form()
        if error:
            flash(error)
            return render_template("admin/media_form.html", item=None)
        return redirect(url_for("admin.media_list"))
    return render_template("admin/media_form.html", item=None)


@admin_bp.route("/media/bulk", methods=["GET", "POST"])
@login_required
def media_bulk():
    """v0.10 (demande par Fabien) : ajouter plusieurs photos/videos EN UNE
    FOIS a la mediatheque, plutot que de repeter le formulaire "/media/new"
    fichier par fichier -- utile pour importer d'un coup les photos d'un
    evenement. Une entree media est creee PAR fichier (legende vide, duree
    par defaut, actif) ; rien n'empeche de les editer individuellement
    ensuite (legende, duree, ordre) depuis la liste, exactement comme un
    media ajoute via le formulaire simple. Les fichiers dont l'extension
    n'est pas autorisee sont ignores individuellement (pas d'echec en bloc :
    un seul fichier invalide dans un lot de 30 ne doit pas faire perdre les
    29 autres) et listes dans le message d'erreur."""
    if request.method == "POST":
        files = [f for f in request.files.getlist("files") if f and f.filename]
        if not files:
            flash("Merci de choisir au moins une photo ou une vidéo à importer.")
            return render_template("admin/media_bulk.html")

        added = 0
        failed = []
        for file_storage in files:
            try:
                filename, media_type = media_manager.save_media_file(file_storage)
            except (ValueError, OSError):  # v1.03 : + OSError (disque plein, ecriture impossible)
                failed.append(file_storage.filename)
                continue
            if filename is None:
                continue
            media_manager.create_media(filename, media_type)
            added += 1

        # v0.10 : un seul flash() -- templates/admin/base.html n'affiche que
        # messages[0] (voir "{{ messages[0] }}"), donc tout combiner en un
        # seul message plutot que de risquer de perdre l'un des deux.
        message = f"{added} média(s) ajouté(s) à la médiathèque." if added else "Aucun média ajouté."
        if failed:
            message += " Fichier(s) ignoré(s) (extension non autorisée) : " + ", ".join(failed)
        flash(message)
        return redirect(url_for("admin.media_list"))

    return render_template("admin/media_bulk.html")


@admin_bp.route("/media/<int:media_id>/edit", methods=["GET", "POST"])
@login_required
def media_edit(media_id):
    item = media_manager.get_media(media_id)
    if item is None:
        flash("Media introuvable")
        return redirect(url_for("admin.media_list"))

    if request.method == "POST":
        error = _save_media_form(media_id=media_id)
        if error:
            flash(error)
            return render_template("admin/media_form.html", item=item)
        return redirect(url_for("admin.media_list"))

    return render_template("admin/media_form.html", item=item)


@admin_bp.route("/media/<int:media_id>/delete", methods=["POST"])
@login_required
def media_delete(media_id):
    media_manager.delete_media(media_id)
    flash("Media supprime")
    return redirect(url_for("admin.media_list"))


@admin_bp.route("/media/<int:media_id>/toggle_active", methods=["POST"])
@login_required
def media_toggle_active(media_id):
    item = media_manager.get_media(media_id)
    if item is None:
        # v1.03 : element supprime entre-temps (page perimee, 2e onglet) -- evitait une erreur 500
        flash("Élément introuvable (déjà supprimé ?)")
        return redirect(url_for("admin.media_list"))
    media_manager.set_media_active(media_id, not item["active"])
    return redirect(url_for("admin.media_list"))


@admin_bp.route("/media/<int:media_id>/move/<direction>", methods=["POST"])
@login_required
def media_move(media_id, direction):
    if direction in ("up", "down"):  # v1.03 : toute autre valeur donnait une erreur 500
        media_manager.move_media(media_id, direction)
    return redirect(url_for("admin.media_list"))


def _save_media_form(media_id=None):
    """Renvoie un message d'erreur (str) si l'upload echoue, None sinon --
    meme convention simple que le reste de l'admin (pas de validation WTForms
    pour l'instant, coherent avec _save_object_form)."""
    caption = request.form.get("caption", "").strip() or None
    display_seconds_raw = request.form.get("display_seconds", "").strip()
    display_seconds = int(display_seconds_raw) if display_seconds_raw.isdigit() else None
    active = request.form.get("active") == "on"

    filename = None
    media_type = None
    if "file" in request.files and request.files["file"].filename:
        try:
            filename, media_type = media_manager.save_media_file(request.files["file"])
        except ValueError as exc:
            return str(exc)
    else:
        # v0.6 : reutilisation d'un fichier deja present dans la médiathèque
        # (sélecteur), le type se deduit de l'extension comme pour un upload.
        existing = mediatheque_manager.resolve_existing(
            "library", request.form.get("existing_filename", "")
        )
        if existing:
            filename = existing
            media_type = media_manager.guess_media_type(existing)

    if media_id is None:
        if filename is None:
            return "Merci de choisir une photo ou une vidéo à ajouter."
        media_manager.create_media(filename, media_type, caption, display_seconds)
    else:
        media_manager.update_media(media_id, caption, display_seconds, active, filename, media_type)
    return None


# --- Ven de l'occitan (v0.2) ----------------------------------------------
#
# Contenu volontairement vide a la livraison -- voir vertadier_manager.py et
# concept-borne-interactive.md : la liste doit etre verifiee avec une source
# fiable avant d'etre saisie ici, jamais improvisee.

@admin_bp.route("/vertadier")
@login_required
def vertadier_list():
    words = vertadier_manager.list_words()
    return render_template("admin/vertadier_list.html", words=words)


@admin_bp.route("/vertadier/new", methods=["GET", "POST"])
@login_required
def vertadier_new():
    if request.method == "POST":
        _save_vertadier_form()
        return redirect(url_for("admin.vertadier_list"))
    return render_template("admin/vertadier_form.html", word=None)


@admin_bp.route("/vertadier/<int:word_id>/edit", methods=["GET", "POST"])
@login_required
def vertadier_edit(word_id):
    word = vertadier_manager.get_word(word_id)
    if word is None:
        flash("Mot introuvable")
        return redirect(url_for("admin.vertadier_list"))
    if request.method == "POST":
        _save_vertadier_form(word_id=word_id)
        return redirect(url_for("admin.vertadier_list"))
    return render_template("admin/vertadier_form.html", word=word)


@admin_bp.route("/vertadier/<int:word_id>/delete", methods=["POST"])
@login_required
def vertadier_delete(word_id):
    vertadier_manager.delete_word(word_id)
    flash("Mot supprimé")
    return redirect(url_for("admin.vertadier_list"))


@admin_bp.route("/vertadier/<int:word_id>/toggle_active", methods=["POST"])
@login_required
def vertadier_toggle_active(word_id):
    word = vertadier_manager.get_word(word_id)
    if word is None:
        # v1.03 : element supprime entre-temps (page perimee, 2e onglet) -- evitait une erreur 500
        flash("Élément introuvable (déjà supprimé ?)")
        return redirect(url_for("admin.vertadier_list"))
    vertadier_manager.set_word_active(word_id, not word["active"])
    return redirect(url_for("admin.vertadier_list"))


def _save_vertadier_form(word_id=None):
    word_fr = request.form.get("word_fr", "").strip()
    is_occitan = request.form.get("is_occitan") == "on"
    explanation = request.form.get("explanation", "").strip() or None
    source = request.form.get("source", "").strip() or None
    active = request.form.get("active") == "on"

    if word_id is None:
        vertadier_manager.create_word(word_fr, is_occitan, explanation, source)
    else:
        vertadier_manager.update_word(word_id, word_fr, is_occitan, explanation, source, active)


# --- Duèl Occitan (v0.7, jeu a 2 joueurs) ------------------------------------
#
# Contenu volontairement vide a la livraison -- meme principe que
# Ven de l'occitan : voir duel_manager.py et concept-borne-interactive.md,
# le contenu doit etre verifie avec une source fiable avant d'etre saisi ici,
# jamais improvise.

@admin_bp.route("/duel")
@login_required
def duel_list():
    questions = duel_manager.list_questions()
    return render_template("admin/duel_list.html", questions=questions)


@admin_bp.route("/duel/new", methods=["GET", "POST"])
@login_required
def duel_new():
    if request.method == "POST":
        _save_duel_form()
        return redirect(url_for("admin.duel_list"))
    return render_template("admin/duel_form.html", question=None)


@admin_bp.route("/duel/<int:question_id>/edit", methods=["GET", "POST"])
@login_required
def duel_edit(question_id):
    question = duel_manager.get_question(question_id)
    if question is None:
        flash("Question introuvable")
        return redirect(url_for("admin.duel_list"))
    if request.method == "POST":
        _save_duel_form(question_id=question_id)
        return redirect(url_for("admin.duel_list"))
    return render_template("admin/duel_form.html", question=question)


@admin_bp.route("/duel/<int:question_id>/delete", methods=["POST"])
@login_required
def duel_delete(question_id):
    duel_manager.delete_question(question_id)
    flash("Question supprimée")
    return redirect(url_for("admin.duel_list"))


@admin_bp.route("/duel/<int:question_id>/toggle_active", methods=["POST"])
@login_required
def duel_toggle_active(question_id):
    question = duel_manager.get_question(question_id)
    if question is None:
        # v1.03 : element supprime entre-temps (page perimee, 2e onglet) -- evitait une erreur 500
        flash("Élément introuvable (déjà supprimé ?)")
        return redirect(url_for("admin.duel_list"))
    duel_manager.set_question_active(question_id, not question["active"])
    return redirect(url_for("admin.duel_list"))


def _save_duel_form(question_id=None):
    question_fr = request.form.get("question_fr", "").strip()
    choice_a = request.form.get("choice_a", "").strip()
    choice_b = request.form.get("choice_b", "").strip()
    correct_choice = request.form.get("correct_choice", "a")
    explanation = request.form.get("explanation", "").strip() or None
    source = request.form.get("source", "").strip() or None
    active = request.form.get("active") == "on"

    if question_id is None:
        duel_manager.create_question(question_fr, choice_a, choice_b, correct_choice, explanation, source)
    else:
        duel_manager.update_question(
            question_id, question_fr, choice_a, choice_b, correct_choice, explanation, source, active
        )


# --- Memòria vilatge (v0.8) ---------------------------------------------------
#
# Contenu volontairement vide a la livraison -- meme principe que
# Vertadièr/Duèl : voir village_manager.py et concept-borne-interactive.md,
# les noms de villes/vilatges doivent etre verifies avec une source fiable
# avant d'etre saisis ici, jamais improvises.

@admin_bp.route("/villages")
@login_required
def villages_list():
    villages = village_manager.list_villages()
    return render_template("admin/villages_list.html", villages=villages)


@admin_bp.route("/villages/new", methods=["GET", "POST"])
@login_required
def village_new():
    if request.method == "POST":
        _save_village_form()
        return redirect(url_for("admin.villages_list"))
    return render_template("admin/village_form.html", village=None)


@admin_bp.route("/villages/<int:village_id>/edit", methods=["GET", "POST"])
@login_required
def village_edit(village_id):
    village = village_manager.get_village(village_id)
    if village is None:
        flash("Vilatge introuvable")
        return redirect(url_for("admin.villages_list"))
    if request.method == "POST":
        _save_village_form(village_id=village_id)
        return redirect(url_for("admin.villages_list"))
    return render_template("admin/village_form.html", village=village)


@admin_bp.route("/villages/<int:village_id>/delete", methods=["POST"])
@login_required
def village_delete(village_id):
    village_manager.delete_village(village_id)
    flash("Vilatge supprimé")
    return redirect(url_for("admin.villages_list"))


@admin_bp.route("/villages/<int:village_id>/toggle_active", methods=["POST"])
@login_required
def village_toggle_active(village_id):
    village = village_manager.get_village(village_id)
    if village is None:
        # v1.03 : element supprime entre-temps (page perimee, 2e onglet) -- evitait une erreur 500
        flash("Élément introuvable (déjà supprimé ?)")
        return redirect(url_for("admin.villages_list"))
    village_manager.set_village_active(village_id, not village["active"])
    return redirect(url_for("admin.villages_list"))


def _save_village_form(village_id=None):
    name_fr = request.form.get("name_fr", "").strip()
    name_oc = request.form.get("name_oc", "").strip()
    source = request.form.get("source", "").strip() or None
    active = request.form.get("active") == "on"

    if village_id is None:
        village_manager.create_village(name_fr, name_oc, source)
    else:
        village_manager.update_village(village_id, name_fr, name_oc, source, active)


# --- Quiz Calandreta (v0.8) -----------------------------------------------------
#
# Contenu volontairement vide a la livraison -- meme principe que
# Vertadièr/Duèl : voir quiz_manager.py et concept-borne-interactive.md, les
# questions doivent etre verifiees avec une source fiable avant d'etre
# saisies ici, jamais improvisees.

@admin_bp.route("/quiz")
@login_required
def quiz_list():
    questions = quiz_manager.list_questions()
    return render_template("admin/quiz_list.html", questions=questions)


@admin_bp.route("/quiz/new", methods=["GET", "POST"])
@login_required
def quiz_new():
    if request.method == "POST":
        _save_quiz_form()
        return redirect(url_for("admin.quiz_list"))
    return render_template("admin/quiz_form.html", question=None)


@admin_bp.route("/quiz/<int:question_id>/edit", methods=["GET", "POST"])
@login_required
def quiz_edit(question_id):
    question = quiz_manager.get_question(question_id)
    if question is None:
        flash("Question introuvable")
        return redirect(url_for("admin.quiz_list"))
    if request.method == "POST":
        _save_quiz_form(question_id=question_id)
        return redirect(url_for("admin.quiz_list"))
    return render_template("admin/quiz_form.html", question=question)


@admin_bp.route("/quiz/<int:question_id>/delete", methods=["POST"])
@login_required
def quiz_delete(question_id):
    quiz_manager.delete_question(question_id)
    flash("Question supprimée")
    return redirect(url_for("admin.quiz_list"))


@admin_bp.route("/quiz/<int:question_id>/toggle_active", methods=["POST"])
@login_required
def quiz_toggle_active(question_id):
    question = quiz_manager.get_question(question_id)
    if question is None:
        # v1.03 : element supprime entre-temps (page perimee, 2e onglet) -- evitait une erreur 500
        flash("Élément introuvable (déjà supprimé ?)")
        return redirect(url_for("admin.quiz_list"))
    quiz_manager.set_question_active(question_id, not question["active"])
    return redirect(url_for("admin.quiz_list"))


def _save_quiz_form(question_id=None):
    question_fr = request.form.get("question_fr", "").strip()
    choice_a = request.form.get("choice_a", "").strip()
    choice_b = request.form.get("choice_b", "").strip()
    choice_c = request.form.get("choice_c", "").strip()
    correct_choice = request.form.get("correct_choice", "a")
    explanation = request.form.get("explanation", "").strip() or None
    source = request.form.get("source", "").strip() or None
    active = request.form.get("active") == "on"

    if question_id is None:
        quiz_manager.create_question(question_fr, choice_a, choice_b, choice_c, correct_choice, explanation, source)
    else:
        quiz_manager.update_question(
            question_id, question_fr, choice_a, choice_b, choice_c, correct_choice, explanation, source, active
        )


# --- Médiathèque globale (v0.2) -----------------------------------------------

# v0.6 : endpoint de service (media_object_image, etc. definis dans app.py)
# + extensions considerees "image"/"audio" pour choisir le type d'apercu --
# reprend ALLOWED_IMAGE_EXTENSIONS/ALLOWED_AUDIO_EXTENSIONS de config.py.
_MEDIATHEQUE_ENDPOINTS = {
    "object_image": "media_object_image",
    "object_audio": "media_object_audio",
    "library": "media_library_file",
    "branding": "media_branding_file",
}


def _mediatheque_preview_kind(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in config.ALLOWED_IMAGE_EXTENSIONS:
        return "image"
    if ext in config.ALLOWED_AUDIO_EXTENSIONS:
        return "audio"
    if ext in {"mp4", "webm", "mov"}:
        return "video"
    return "other"


@admin_bp.route("/mediatheque")
@login_required
def mediatheque():
    items = mediatheque_manager.scan_media()
    disk = mediatheque_manager.disk_usage()
    nb_orphans = len([m for m in items if not m["used"]])
    for item in items:
        item["url"] = url_for(_MEDIATHEQUE_ENDPOINTS[item["key"]], filename=item["filename"])
        item["preview_kind"] = _mediatheque_preview_kind(item["filename"])
    return render_template(
        "admin/mediatheque.html",
        items=items,
        disk=disk,
        nb_orphans=nb_orphans,
        format_bytes=mediatheque_manager.format_bytes,
    )


@admin_bp.route("/mediatheque/browse")
@login_required
def mediatheque_browse():
    """v0.6 : alimente le sélecteur « choisir dans la médiathèque » (JS,
    voir static/js/admin.js) affiché a cote des champs d'upload -- une
    catégorie a la fois (meme decoupage que scan_media()/delete_file()),
    pour rester coherent avec le dossier ou le fichier choisi sera reellement
    utilise (pas de copie entre dossiers)."""
    key = request.args.get("key", "")
    endpoint = _MEDIATHEQUE_ENDPOINTS.get(key)
    items = [item for item in mediatheque_manager.scan_media() if item["key"] == key] if endpoint else []
    for item in items:
        item["url"] = url_for(endpoint, filename=item["filename"])
        item["preview_kind"] = _mediatheque_preview_kind(item["filename"])
    return jsonify({"items": items})


@admin_bp.route("/mediatheque/delete", methods=["POST"])
@login_required
def mediatheque_delete():
    key = request.form.get("key", "")
    filename = request.form.get("filename", "")
    try:
        mediatheque_manager.delete_file(key, filename)
        flash(f"Fichier « {filename} » supprimé.")
    except FileNotFoundError:
        flash(f"Fichier « {filename} » introuvable (déjà supprimé ?).")
    except ValueError as e:
        flash(f"Suppression impossible : {e}")
    return redirect(url_for("admin.mediatheque"))


# --- Configuration (v0.2) -----------------------------------------------------
#
# Regroupe tout ce qui n'est plus dans config.py/les variables d'environnement
# depuis la v0.2 : mot de passe, banniere (logo/croix), theme de couleur,
# mapping manette. Voir managers/settings_manager.py pour le stockage.
# v0.10 : HAT_ARROWS a demenage dans settings_manager.py (voir
# build_action_control_labels), partage avec le kiosque.


@admin_bp.route("/config")
@login_required
def config_home():
    branding = settings_manager.get_branding()
    input_bus = current_app.extensions["input_bus"]

    # v0.10 : ce calcul vivait ici avant (duplique a l'identique) -- deplace
    # dans settings_manager.build_action_control_labels() pour que le kiosque
    # puisse aussi s'en servir (afficher le VRAI bouton/touche assigne dans
    # les jeux, au lieu de lettres A/B/X/Y codees en dur, voir
    # blueprints/kiosk.py). Comportement inchange ici.
    action_to_label, action_to_key = settings_manager.build_action_control_labels()

    return render_template(
        "admin/config.html",
        branding=branding,
        templates=settings_manager.TEMPLATES,
        gamepad_actions=settings_manager.GAMEPAD_ACTIONS,
        action_to_label=action_to_label,
        action_to_key=action_to_key,
        pygame_available=input_bus.pygame_available,
        # v0.10 : textes du kiosque personnalisables (voir config_texts()
        # plus bas) -- valeurs COURANTES (defaut ou deja surchargees) et la
        # liste des champs editables avec leurs libelles admin.
        kiosk_texts=settings_manager.get_kiosk_texts(),
        kiosk_text_fields=settings_manager.KIOSK_TEXT_FIELDS,
        # v1.01 (signale par Fabien) : texte affiche sur le kiosque, saisi a
        # la main par action (prioritaire sur le libelle technique
        # auto-calcule -- voir action_to_label ci-dessus) + les conflits de
        # controle partage a signaler (voir config_action_labels() plus bas).
        action_label_overrides=settings_manager.get_action_label_overrides(),
        action_conflicts=settings_manager.build_action_conflicts(),
        # v1.01 : libelle technique auto-calcule ACTUEL de chaque action --
        # affiche en indication (placeholder) dans le champ de saisie libre,
        # pour que Fabien voie ce qui s'affiche tant qu'il ne surcharge rien.
        kiosk_action_labels=settings_manager.build_kiosk_action_labels(),
        # v1.02 : table de Configuration > Manèta & clavièr regroupee par
        # activite plutot qu'en une seule liste a plat -- voir
        # settings_manager.ACTIVITY_CONTROL_SECTIONS. `gamepad_actions_by_key`
        # permet au template de retrouver l'entree GAMEPAD_ACTIONS complete
        # (libelle...) a partir du nom d'action liste dans chaque section.
        activity_control_sections=settings_manager.ACTIVITY_CONTROL_SECTIONS,
        gamepad_actions_by_key={entry["action"]: entry for entry in settings_manager.GAMEPAD_ACTIONS},
    )


@admin_bp.route("/config/password", methods=["POST"])
@login_required
def config_password():
    current_pin = request.form.get("current_pin", "")
    new_pin = request.form.get("new_pin", "").strip()
    confirm_pin = request.form.get("confirm_pin", "").strip()

    if current_pin != settings_manager.get_admin_pin():
        flash("Mot de passe actuel incorrect")
    elif not new_pin or not new_pin.isdigit():
        flash("Le nouveau code doit être composé uniquement de chiffres")
    elif new_pin != confirm_pin:
        flash("Les deux saisies du nouveau code ne correspondent pas")
    else:
        settings_manager.set_admin_pin(new_pin)
        flash("Mot de passe changé")
    return redirect(url_for("admin.config_home"))


@admin_bp.route("/config/branding", methods=["POST"])
@login_required
def config_branding():
    try:
        if "logo" in request.files and request.files["logo"].filename:
            filename = settings_manager.save_branding_upload(request.files["logo"])
            settings_manager.set_logo_filename(filename)
        else:
            existing = mediatheque_manager.resolve_existing(
                "branding", request.form.get("existing_logo_filename", "")
            )
            if existing:
                settings_manager.set_logo_filename(existing)
        if "crotz" in request.files and request.files["crotz"].filename:
            filename = settings_manager.save_branding_upload(request.files["crotz"])
            settings_manager.set_crotz_filename(filename)
        else:
            existing = mediatheque_manager.resolve_existing(
                "branding", request.form.get("existing_crotz_filename", "")
            )
            if existing:
                settings_manager.set_crotz_filename(existing)
    except ValueError as exc:
        flash(str(exc))
        return redirect(url_for("admin.config_home"))
    flash("Bannière mise à jour — recharge l'écran du kiosque pour la voir (touche F5, ou redémarre le service).")
    return redirect(url_for("admin.config_home"))


@admin_bp.route("/config/branding/reset", methods=["POST"])
@login_required
def config_branding_reset():
    """Revient au SVG genere par defaut (retire le logo/la croix personnalises,
    sans supprimer les fichiers deja uploades -- juste le reglage qui pointe
    dessus, plus simple et moins risque qu'une suppression de fichier)."""
    which = request.form.get("which")
    if which == "logo":
        settings_manager.set_logo_filename(None)
    elif which == "crotz":
        settings_manager.set_crotz_filename(None)
    flash("Repassé à l'image par défaut")
    return redirect(url_for("admin.config_home"))


@admin_bp.route("/config/theme", methods=["POST"])
@login_required
def config_theme():
    theme_key = request.form.get("theme")
    try:
        settings_manager.set_theme(theme_key)
        flash("Modèle d'interface changé — recharge l'écran du kiosque pour le voir (touche F5, ou redémarre le service).")
    except ValueError:
        flash("Modèle inconnu")
    return redirect(url_for("admin.config_home"))


@admin_bp.route("/config/texts", methods=["POST"])
@login_required
def config_texts():
    """v0.10 : enregistre les textes visiteur personnalises (ecran d'accueil +
    menu). Un champ laisse vide revient a son texte par defaut -- voir
    settings_manager.set_kiosk_texts()."""
    texts = {
        field["key"]: request.form.get(field["key"], "")
        for field in settings_manager.KIOSK_TEXT_FIELDS
    }
    settings_manager.set_kiosk_texts(texts)
    flash("Textes du kiosque mis à jour — recharge l'écran du kiosque pour les voir (touche F5, ou redémarre le service).")
    return redirect(url_for("admin.config_home"))


@admin_bp.route("/config/action_labels", methods=["POST"])
@login_required
def config_action_labels():
    """v1.01 (signale par Fabien) : enregistre les libelles saisis a la main
    (un par action, ex. "A", "Select"...) qui remplacent desormais le
    libelle technique auto-calcule affiche dans les jeux -- utile quand la
    manette physique de Fabien n'affiche pas les memes textes que ceux
    devinés par le code (numero de bouton pygame, code d'axe...). Un champ
    laisse vide revient au libelle technique automatique."""
    overrides = {
        entry["action"]: request.form.get(entry["action"], "")
        for entry in settings_manager.GAMEPAD_ACTIONS
    }
    settings_manager.set_action_label_overrides(overrides)
    flash("Textes de bouton mis à jour — recharge l'écran du kiosque pour les voir (touche F5, ou redémarre le service).")
    return redirect(url_for("admin.config_home"))


# --- Configuration manette (v0.2) ---------------------------------------------

@admin_bp.route("/config/gamepad/listen/<action>", methods=["POST"])
@login_required
def gamepad_listen(action):
    input_bus = current_app.extensions["input_bus"]
    if not input_bus.pygame_available:
        return jsonify({"error": "aucune manette/pygame disponible sur cette machine"}), 400
    input_bus.begin_capture()
    return jsonify({"ok": True, "action": action})


@admin_bp.route("/config/gamepad/status")
@login_required
def gamepad_status():
    """Interrogee en boucle par la page pendant l'ecoute, meme principe que
    pair_tag_status() pour l'association de tags NFC.

    v0.4 : `captured` est desormais un dict {"kind": "button"|"hat"|"axis",
    ...} (ou None tant que rien n'est capture) au lieu d'un simple indice de
    bouton -- voir InputBus.poll_capture()."""
    input_bus = current_app.extensions["input_bus"]
    captured, still_capturing = input_bus.poll_capture()
    return jsonify({"captured": captured, "capturing": still_capturing})


@admin_bp.route("/config/gamepad/cancel", methods=["POST"])
@login_required
def gamepad_cancel():
    current_app.extensions["input_bus"].cancel_capture()
    return jsonify({"ok": True})


@admin_bp.route("/config/gamepad/assign", methods=["POST"])
@login_required
def gamepad_assign():
    """v0.4 : gere desormais les trois mecanismes (bouton/hat/axe) -- le
    formulaire cache envoie `kind` en plus de `action`, et les champs
    correspondant au type captu re (voir templates/admin/config.html)."""
    action = request.form.get("action")
    kind = request.form.get("kind")
    valid_actions = {a["action"] for a in settings_manager.GAMEPAD_ACTIONS}

    captured = None
    if action in valid_actions:
        if kind == "button":
            button_raw = request.form.get("button", "")
            if button_raw.isdigit():
                captured = {"kind": "button", "button": int(button_raw)}
        elif kind == "hat":
            hat_x = request.form.get("hat_x", "")
            hat_y = request.form.get("hat_y", "")
            if hat_x.lstrip("-").isdigit() and hat_y.lstrip("-").isdigit():
                captured = {"kind": "hat", "value": [int(hat_x), int(hat_y)]}
        elif kind == "axis":
            axis_raw = request.form.get("axis", "")
            sign_raw = request.form.get("sign", "")
            if axis_raw.lstrip("-").isdigit() and sign_raw.lstrip("-").isdigit():
                captured = {"kind": "axis", "axis": int(axis_raw), "sign": int(sign_raw)}

    if captured is None:
        flash("Assignation invalide")
        return redirect(url_for("admin.config_home"))

    button_map, hat_map, axis_map = settings_manager.assign_gamepad_control(action, captured)
    input_bus = current_app.extensions["input_bus"]
    input_bus.set_button_map(button_map)
    input_bus.set_hat_map(hat_map)
    input_bus.set_axis_map(axis_map)
    flash("Contrôle manette assigné")
    return redirect(url_for("admin.config_home"))


# --- Configuration clavier (v0.8) ----------------------------------------------
#
# Independant de la manette (voir settings_manager.py, section "Mapping
# clavier") : les deux coexistent, jamais l'un ne remplace l'autre. La
# capture de la touche se fait entierement cote navigateur (un ecouteur
# "keydown", voir templates/admin/config.html) -- ces routes se contentent
# d'enregistrer la touche deja capturee, pas de polling serveur necessaire
# contrairement a /config/gamepad/status.

@admin_bp.route("/config/keyboard/assign", methods=["POST"])
@login_required
def config_keyboard_assign():
    action = request.form.get("action", "")
    key = request.form.get("key", "")
    valid_actions = {a["action"] for a in settings_manager.GAMEPAD_ACTIONS}
    if action not in valid_actions or not key:
        flash("Assignation clavier invalide")
        return redirect(url_for("admin.config_home"))
    settings_manager.assign_keyboard_key(action, key)
    flash("Touche clavier assignée")
    return redirect(url_for("admin.config_home"))


@admin_bp.route("/config/keyboard/unassign", methods=["POST"])
@login_required
def config_keyboard_unassign():
    action = request.form.get("action", "")
    valid_actions = {a["action"] for a in settings_manager.GAMEPAD_ACTIONS}
    if action in valid_actions:
        settings_manager.unassign_keyboard_key(action)
        flash("Touche clavier retirée")
    return redirect(url_for("admin.config_home"))


# --- Exportar / Importar (v1.2) ----------------------------------------------
# Extraire le contenu saisi a la main (typiquement dans la version de demo)
# pour le reimplanter dans une autre installation (typiquement la borne).
# Voir managers/content_transfer.py pour le format.

@admin_bp.route("/transfer")
@login_required
def transfer():
    current = content_transfer.summarize(content_transfer.build_counts())
    return render_template(
        "admin/transfer.html",
        sections=content_transfer.SECTIONS,
        current=current,
        report=None,
    )


@admin_bp.route("/transfer/export")
@login_required
def transfer_export():
    filename, payload = content_transfer.build_export(
        include_media=request.args.get("media", "1") == "1",
        include_settings=request.args.get("settings", "1") == "1",
    )
    return send_file(
        io.BytesIO(payload), mimetype="application/zip",
        as_attachment=True, download_name=filename,
    )


@admin_bp.route("/transfer/import", methods=["POST"])
@login_required
def transfer_import():
    upload = request.files.get("bundle")
    if not upload or not upload.filename:
        flash("Choisis d'abord un fichier d'export (.zip).")
        return redirect(url_for("admin.transfer"))
    try:
        data, archive = content_transfer.read_bundle(upload)
        sections = [s["name"] for s in content_transfer.SECTIONS if request.form.get(f"section_{s['name']}")]
        if not sections and not request.form.get("settings"):
            flash("Coche au moins une section à importer.")
            return redirect(url_for("admin.transfer"))
        report = content_transfer.import_bundle(
            data, archive, sections,
            mode=request.form.get("mode", "merge"),
            import_settings=bool(request.form.get("settings")),
            import_tags=bool(request.form.get("tags")),
        )
    except content_transfer.ImportError_ as exc:
        flash(str(exc))
        return redirect(url_for("admin.transfer"))
    return render_template(
        "admin/transfer.html",
        sections=content_transfer.SECTIONS,
        current=content_transfer.summarize(content_transfer.build_counts()),
        report=report,
        bundle_info={
            "app_version": data.get("app_version"),
            "source": data.get("source"),
            "exported_at": data.get("exported_at"),
        },
    )
