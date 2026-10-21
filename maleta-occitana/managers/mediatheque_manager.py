"""Médiathèque globale (v0.2) : vue d'ensemble de tous les fichiers médias
présents sur le disque, tous types confondus (objets, bibliothèque photo/
vidéo, branding), avec leur statut d'utilisation, plus l'espace disque
restant sur la machine.

Objectif : repérer d'un coup d'œil les fichiers uploadés puis oubliés (objet
supprimé sans que son image le soit, essai abandonné...) qui prennent de la
place pour rien sur une machine au stockage limité.
"""

import os
import shutil

import config
from db.database import get_db


def scan_media():
    """Renvoie une liste de dicts {category, filename, path, size_bytes, used}
    pour chaque fichier trouvé sur le disque dans les dossiers médias connus.
    `used` est déterminé par recoupement avec les tables de la base (et les
    réglages, pour le logo/la croix) -- un fichier présent sur le disque mais
    jamais référencé nulle part est un candidat au nettoyage."""
    db = get_db()

    used_object_images = {
        row["image_filename"] for row in db.execute(
            "SELECT image_filename FROM objects WHERE image_filename IS NOT NULL"
        )
    }
    used_object_audio = {
        row["audio_filename"] for row in db.execute(
            "SELECT audio_filename FROM objects WHERE audio_filename IS NOT NULL"
        )
    }
    used_library = {
        row["filename"] for row in db.execute("SELECT filename FROM media_items")
    }
    branding_rows = db.execute(
        "SELECT value FROM settings WHERE key IN ('logo_filename', 'crotz_filename')"
    ).fetchall()
    used_branding = {row["value"] for row in branding_rows if row["value"]}

    categories = [
        ("object_image", "Image d'objet", config.OBJECT_IMAGES_DIR, used_object_images),
        ("object_audio", "Audio d'objet", config.OBJECT_AUDIO_DIR, used_object_audio),
        ("library", "Cadre fotó & vidèo", config.MEDIA_LIBRARY_DIR, used_library),
        ("branding", "Logo / croix", config.BRANDING_DIR, used_branding),
    ]

    items = []
    for key, label, directory, used_set in categories:
        if not os.path.isdir(directory):
            continue
        for filename in sorted(os.listdir(directory)):
            # v0.6 : les .gitkeep (placeholders vides gardant les dossiers
            # dans git) ne sont pas des fichiers medias -- les compter comme
            # "orphelins" ne faisait que gonfler artificiellement le chiffre
            # affiche et, maintenant qu'un bouton poubelle existe, aurait pu
            # laisser quelqu'un les supprimer par erreur en pensant nettoyer.
            if filename.startswith("."):
                continue
            full_path = os.path.join(directory, filename)
            if not os.path.isfile(full_path):
                continue
            items.append({
                "key": key,
                "category": label,
                "filename": filename,
                "size_bytes": os.path.getsize(full_path),
                "used": filename in used_set,
            })
    return items


# v0.6 : bouton poubelle dans la médiathèque (demande de Fabien). Un seul
# dossier possible par "key" -- reprend exactement le decoupage de
# scan_media() ci-dessus, pour ne jamais pouvoir supprimer hors des dossiers
# médias connus.
_CATEGORY_DIRS = {
    "object_image": lambda: config.OBJECT_IMAGES_DIR,
    "object_audio": lambda: config.OBJECT_AUDIO_DIR,
    "library": lambda: config.MEDIA_LIBRARY_DIR,
    "branding": lambda: config.BRANDING_DIR,
}


def resolve_existing(key, filename):
    """v0.6 : valide un choix fait via le sélecteur « choisir dans la
    médiathèque » cote client (formulaires objets/médias/bannière). Ne fait
    confiance a rien venant du formulaire : ne renvoie le nom de fichier que
    s'il existe vraiment, tel quel, dans le dossier de cette catégorie ;
    None sinon (l'appelant se rabat alors sur le comportement habituel)."""
    get_dir = _CATEGORY_DIRS.get(key)
    if not get_dir or not filename:
        return None
    safe_name = os.path.basename(filename)
    full_path = os.path.join(get_dir(), safe_name)
    return safe_name if os.path.isfile(full_path) else None


def delete_file(key, filename):
    """Supprime un fichier du disque par categorie + nom. `filename` est
    ramene a son basename pour eviter toute sortie du dossier autorise
    (../ etc.) -- on ne fait confiance qu'a ce qu'on a nous-memes liste dans
    scan_media(). Ne touche jamais aux tables de la base : si le fichier
    etait encore reference quelque part (statut "utilisé"), la reference
    reste en base et pointera vers un fichier disparu -- l'appelant doit
    avoir prevenu l'utilisateur avant d'en arriver la."""
    get_dir = _CATEGORY_DIRS.get(key)
    if get_dir is None:
        raise ValueError(f"categorie mediatheque inconnue : {key}")
    directory = get_dir()
    safe_name = os.path.basename(filename)
    if not safe_name or safe_name in (".", ".."):
        raise ValueError("nom de fichier invalide")
    full_path = os.path.join(directory, safe_name)
    if not os.path.isfile(full_path):
        raise FileNotFoundError(full_path)
    os.remove(full_path)


def disk_usage():
    """Espace disque de la machine qui héberge l'appli (pas seulement le
    dossier médias -- l'appli tourne sur un petit PC/une VM au stockage
    limité, c'est l'espace disque global qui compte)."""
    total, used, free = shutil.disk_usage(config.DATA_DIR)
    return {
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "used_percent": round(used / total * 100, 1) if total else 0,
    }


def format_bytes(n):
    """Formatage lisible simple (Ko/Mo/Go), pas besoin d'une dépendance pour ça."""
    n = float(n)
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if n < 1024 or unit == "To":
            return f"{n:.1f} {unit}" if unit != "o" else f"{int(n)} {unit}"
        n /= 1024
    return f"{n:.1f} To"
