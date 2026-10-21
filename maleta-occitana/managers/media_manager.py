"""CRUD de la bibliotheque de medias (Etape 2 : "Cadre fotó & vidèo").

Meme esprit que object_manager.py : pas d'ORM, acces direct via get_db().
Le type (photo/video) est deduit automatiquement de l'extension du fichier
uploade -- pas de champ a choisir a la main dans le formulaire d'admin.
"""

import os

from managers.upload_utils import safe_upload_name

from db.database import get_db
import config


def list_media(only_active=False):
    db = get_db()
    query = "SELECT * FROM media_items"
    if only_active:
        query += " WHERE active = 1"
    query += " ORDER BY sort_order ASC, id ASC"
    return db.execute(query).fetchall()


def get_media(media_id):
    db = get_db()
    return db.execute("SELECT * FROM media_items WHERE id = ?", (media_id,)).fetchone()


def create_media(filename, media_type, caption=None, display_seconds=None):
    db = get_db()
    # Nouvel element ajoute a la fin de la boucle par defaut
    max_order = db.execute("SELECT MAX(sort_order) AS m FROM media_items").fetchone()["m"]
    sort_order = (max_order or 0) + 1
    cur = db.execute(
        """
        INSERT INTO media_items (filename, media_type, caption, display_seconds, sort_order)
        VALUES (?, ?, ?, ?, ?)
        """,
        (filename, media_type, caption, display_seconds, sort_order),
    )
    db.commit()
    return cur.lastrowid


def update_media(media_id, caption, display_seconds, active, filename=None, media_type=None):
    db = get_db()
    existing = get_media(media_id)
    if existing is None:
        raise ValueError(f"media {media_id} introuvable")

    new_filename = filename if filename else existing["filename"]
    new_media_type = media_type if filename else existing["media_type"]

    db.execute(
        """
        UPDATE media_items
        SET filename = ?, media_type = ?, caption = ?, display_seconds = ?, active = ?
        WHERE id = ?
        """,
        (new_filename, new_media_type, caption, display_seconds, 1 if active else 0, media_id),
    )
    db.commit()


def delete_media(media_id):
    db = get_db()
    db.execute("DELETE FROM media_items WHERE id = ?", (media_id,))
    db.commit()


def set_media_active(media_id, active):
    db = get_db()
    db.execute("UPDATE media_items SET active = ? WHERE id = ?", (1 if active else 0, media_id))
    db.commit()


def move_media(media_id, direction):
    """Deplace un media d'un cran dans l'ordre d'affichage (direction: "up" ou "down"),
    en echangeant son sort_order avec celui du voisin concerne. Pas de vrai
    glisser-deposer pour cette etape (voir concept-borne-interactive.md,
    section admin) -- simple et suffisant pour une dizaine de medias."""
    db = get_db()
    media = get_media(media_id)
    if media is None:
        return

    if direction == "up":
        neighbor = db.execute(
            "SELECT * FROM media_items WHERE sort_order < ? ORDER BY sort_order DESC LIMIT 1",
            (media["sort_order"],),
        ).fetchone()
    elif direction == "down":
        neighbor = db.execute(
            "SELECT * FROM media_items WHERE sort_order > ? ORDER BY sort_order ASC LIMIT 1",
            (media["sort_order"],),
        ).fetchone()
    else:
        raise ValueError(f"direction inconnue : {direction!r}")

    if neighbor is None:
        return  # deja en premiere/derniere position

    db.execute("UPDATE media_items SET sort_order = ? WHERE id = ?", (neighbor["sort_order"], media["id"]))
    db.execute("UPDATE media_items SET sort_order = ? WHERE id = ?", (media["sort_order"], neighbor["id"]))
    db.commit()


# --- Fichiers -------------------------------------------------------------

def guess_media_type(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in config.ALLOWED_MEDIA_IMAGE_EXTENSIONS:
        return "image"
    if ext in config.ALLOWED_MEDIA_VIDEO_EXTENSIONS:
        return "video"
    raise ValueError(
        f"extension .{ext} non autorisee (images : {sorted(config.ALLOWED_MEDIA_IMAGE_EXTENSIONS)}, "
        f"videos : {sorted(config.ALLOWED_MEDIA_VIDEO_EXTENSIONS)})"
    )


def save_media_file(file_storage):
    """Enregistre le fichier uploade et renvoie (filename, media_type).
    Renvoie (None, None) si aucun fichier n'a ete fourni."""
    if file_storage is None or file_storage.filename == "":
        return None, None
    # v0.72 (revue de code) : meme correctif que object_manager._save_upload --
    # secure_filename() evite qu'un nom de fichier contenant un "/" ne fasse
    # planter file_storage.save() (sous-dossier inexistant, 500 non rattrapee).
    # v1.03 : voir managers/upload_utils.py (extension traitee a part)
    filename, _ext = safe_upload_name(file_storage.filename)
    media_type = guess_media_type(filename)  # leve ValueError si extension refusee
    os.makedirs(config.MEDIA_LIBRARY_DIR, exist_ok=True)
    safe_name = f"{os.urandom(4).hex()}_{filename}"
    file_storage.save(os.path.join(config.MEDIA_LIBRARY_DIR, safe_name))
    return safe_name, media_type
