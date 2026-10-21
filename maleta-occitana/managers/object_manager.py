"""CRUD des objets et association des tags NFC.

Toute la logique "base de donnees" pour le mode Descobèrta d'objèctes /
Tròba l'objècte passe par ici, aussi bien depuis l'admin que depuis le jeu.
"""

import os

from managers.upload_utils import safe_upload_name

from db.database import get_db
import config


def list_objects(only_active=False):
    """v0.8 : aussi utilisee par le jeu "Memòria" (objets actifs) -- chaque
    objet a deja name_fr/name_oc obligatoires en base, donc aucun filtre
    supplementaire n'est necessaire (contrairement a la v0.72, qui exigeait
    une image -- plus le cas depuis que Memòria associe les mots FR/OC,
    voir concept-borne-interactive.md et managers/game_controller.py)."""
    db = get_db()
    query = "SELECT * FROM objects"
    if only_active:
        query += " WHERE active = 1"
    query += " ORDER BY sort_order ASC, id ASC"
    return db.execute(query).fetchall()


def get_object(object_id):
    db = get_db()
    return db.execute("SELECT * FROM objects WHERE id = ?", (object_id,)).fetchone()


def list_objects_with_tag(only_active=True):
    """Objets utilisables pour le jeu "Tròba l'objècte" : il faut un tag NFC
    physique associe, sinon le visiteur n'aurait aucun moyen de "trouver"
    l'objet demande. DISTINCT car un objet peut avoir plusieurs tags."""
    db = get_db()
    query = """
        SELECT DISTINCT objects.*
        FROM objects
        JOIN tags ON tags.object_id = objects.id
    """
    if only_active:
        query += " WHERE objects.active = 1"
    query += " ORDER BY objects.sort_order ASC, objects.id ASC"
    return db.execute(query).fetchall()


def get_object_by_tag_uid(uid):
    """Utilise par le jeu : un tag est scanne, on retrouve l'objet associe (ou None)."""
    db = get_db()
    row = db.execute(
        """
        SELECT objects.*
        FROM tags
        JOIN objects ON objects.id = tags.object_id
        WHERE tags.uid = ? AND objects.active = 1
        """,
        (uid,),
    ).fetchone()
    return row


def create_object(name_oc, name_fr, category, image_filename=None, audio_filename=None):
    db = get_db()
    cur = db.execute(
        """
        INSERT INTO objects (name_oc, name_fr, category, image_filename, audio_filename)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name_oc, name_fr, category, image_filename, audio_filename),
    )
    db.commit()
    return cur.lastrowid


def update_object(object_id, name_oc, name_fr, category, active,
                   image_filename=None, audio_filename=None,
                   clear_image=False, clear_audio=False):
    """v1.03 : clear_image/clear_audio permettent de RETIRER l'image ou le son
    d'un objet (case "Retirer" de la fiche) -- avant, on pouvait seulement les
    remplacer. Utile notamment apres avoir supprime le fichier depuis la
    Médiathèque : l'objet pointait sinon vers un fichier absent (image
    cassee sur le kiosque). Un nouveau fichier fourni reste prioritaire."""
    db = get_db()
    existing = get_object(object_id)
    if existing is None:
        raise ValueError(f"objet {object_id} introuvable")

    # Ne remplace le fichier que si un nouveau a ete fourni (upload optionnel a l'edition)
    if image_filename:
        new_image = image_filename
    elif clear_image:
        new_image = None
    else:
        new_image = existing["image_filename"]
    if audio_filename:
        new_audio = audio_filename
    elif clear_audio:
        new_audio = None
    else:
        new_audio = existing["audio_filename"]

    db.execute(
        """
        UPDATE objects
        SET name_oc = ?, name_fr = ?, category = ?, active = ?,
            image_filename = ?, audio_filename = ?
        WHERE id = ?
        """,
        (name_oc, name_fr, category, 1 if active else 0, new_image, new_audio, object_id),
    )
    db.commit()


def delete_object(object_id):
    """Supprime l'objet. Les tags qui pointaient dessus restent en base
    (object_id passe a NULL) pour ne pas perdre le tag physique deja colle."""
    db = get_db()
    db.execute("DELETE FROM objects WHERE id = ?", (object_id,))
    db.commit()


def set_object_active(object_id, active):
    db = get_db()
    db.execute("UPDATE objects SET active = ? WHERE id = ?", (1 if active else 0, object_id))
    db.commit()


# --- Tags NFC -----------------------------------------------------------

def list_tags_for_object(object_id):
    db = get_db()
    return db.execute("SELECT * FROM tags WHERE object_id = ?", (object_id,)).fetchall()


def pair_tag(uid, object_id):
    """Associe un tag (deja lu par le lecteur NFC) a un objet.

    Si l'UID existe deja (le tag etait associe a un autre objet, ou reutilise),
    on met simplement a jour l'association plutot que d'echouer -- pratique
    quand on recolle une etiquette sur un nouvel objet.
    """
    db = get_db()
    existing = db.execute("SELECT * FROM tags WHERE uid = ?", (uid,)).fetchone()
    if existing:
        db.execute("UPDATE tags SET object_id = ? WHERE uid = ?", (object_id, uid))
    else:
        db.execute("INSERT INTO tags (uid, object_id) VALUES (?, ?)", (uid, object_id))
    db.commit()


def unpair_tag(uid):
    db = get_db()
    db.execute("UPDATE tags SET object_id = NULL WHERE uid = ?", (uid,))
    db.commit()


# --- Fichiers medias ------------------------------------------------------

def save_image(file_storage):
    return _save_upload(file_storage, config.OBJECT_IMAGES_DIR, config.ALLOWED_IMAGE_EXTENSIONS)


def save_audio(file_storage):
    return _save_upload(file_storage, config.OBJECT_AUDIO_DIR, config.ALLOWED_AUDIO_EXTENSIONS)


def _save_upload(file_storage, target_dir, allowed_extensions):
    if file_storage is None or file_storage.filename == "":
        return None
    # v0.72 (revue de code) : secure_filename() en plus du prefixe aleatoire
    # deja en place -- le nom de fichier original (controle par le client
    # HTTP) n'etait jusqu'ici jamais assaini avant d'etre concatene au chemin
    # de destination. Un nom contenant un "/" (ou un antislash mal interprete
    # depuis un poste Windows) produisait un sous-dossier inexistant et
    # faisait planter file_storage.save() avec une FileNotFoundError non
    # rattrapee par la route admin (500 sur un upload pourtant legitime).
    # secure_filename() retire aussi tout ".." et caracteres speciaux, en plus
    # de os.path.basename() (deja utilise ailleurs, ex. mediatheque_manager.py).
    # v1.03 : voir managers/upload_utils.py (extension traitee a part)
    filename, ext = safe_upload_name(file_storage.filename)
    if ext not in allowed_extensions:
        raise ValueError(f"extension .{ext} non autorisee (autorise : {sorted(allowed_extensions)})")
    os.makedirs(target_dir, exist_ok=True)
    # Prefixe par un id de fichier temporaire pour eviter les collisions de noms
    safe_name = f"{os.urandom(4).hex()}_{filename}"
    file_storage.save(os.path.join(target_dir, safe_name))
    return safe_name
