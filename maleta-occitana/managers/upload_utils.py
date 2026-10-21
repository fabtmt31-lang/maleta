"""Assainissement des noms de fichiers uploades depuis l'admin (v1.03).

Avant cette version, chaque upload (objets, diaporama, banniere) passait le
nom d'origine entier a werkzeug.secure_filename(). Celui-ci ne garde que les
caracteres ASCII : un nom sans aucune lettre latine (ex. "日本.jpg", ou un
nom entierement en caracteres speciaux) devenait "jpg" -- sans extension --
et le fichier etait refuse comme "extension non autorisee" alors qu'il etait
parfaitement valide. L'extension est desormais traitee A PART du nom, pour ne
jamais etre perdue.
"""

import os

from werkzeug.utils import secure_filename


def safe_upload_name(original_filename):
    """Renvoie (nom_assaini, extension_en_minuscules_sans_point).

    - retire tout chemin (y compris un chemin Windows "C:\\...\\photo.jpg",
      que os.path.basename ne decoupe pas sous Linux) ;
    - assainit le nom et l'extension separement ;
    - si le nom lui-meme ne contient plus rien d'utilisable, le remplace par
      "fichier" (l'appelant ajoute de toute facon un prefixe aleatoire).
    L'extension renvoyee est "" s'il n'y en a pas."""
    base = os.path.basename((original_filename or "").replace("\\", "/"))
    stem, ext = os.path.splitext(base)
    ext = secure_filename(ext.lstrip(".")).lower()
    stem = secure_filename(stem) or "fichier"
    name = f"{stem}.{ext}" if ext else stem
    return name, ext
