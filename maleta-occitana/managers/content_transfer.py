"""Export / import du contenu saisi dans l'admin (v1.2).

Demande par Fabien avec la version de demonstration : le contenu saisi a la
main (objets, questions des jeux, vilatges, diaporama, textes de la borne)
doit pouvoir etre extrait d'une installation -- typiquement la demo sur un
PC de bureau -- puis reimplante dans une autre, typiquement la borne
(version standard). Meme code des deux cotes : la page Admin > Exportar /
Importar existe dans les deux versions.

Format : une archive .zip qui contient
- `maleta-contenu.json` : tout le contenu, seul fichier lu a l'import ;
- `media/...` : les images/sons/photos/videos references par ce contenu,
  ranges comme dans le dossier media/ de l'appli ;
- `tableur/*.csv` : le meme contenu en tableaux lisibles dans un tableur
  (relecture, verification des sources) -- jamais lus a l'import.
Un fichier .json seul (sans medias) est aussi accepte a l'import.

Ne sont JAMAIS exportes : le code PIN admin, les mappings manette/clavier
(propres a chaque machine) et les tags NFC fictifs (demo, "Simuler un scan")
qui ne correspondent a aucun tag physique.
"""

import csv
import datetime
import hashlib
import io
import json
import os
import zipfile

import config
from db.database import get_db
from managers import object_manager
from managers.upload_utils import safe_upload_name

FORMAT_NAME = "maleta-occitana-contenu"
FORMAT_VERSION = 1
JSON_NAME = "maleta-contenu.json"

# Dossiers medias : cle -> (sous-dossier dans l'archive, dossier local, extensions)
MEDIA_KINDS = {
    "object_image": ("media/objects/images", lambda: config.OBJECT_IMAGES_DIR, config.ALLOWED_IMAGE_EXTENSIONS),
    "object_audio": ("media/objects/audio", lambda: config.OBJECT_AUDIO_DIR, config.ALLOWED_AUDIO_EXTENSIONS),
    "library": (
        "media/library", lambda: config.MEDIA_LIBRARY_DIR,
        config.ALLOWED_MEDIA_IMAGE_EXTENSIONS | config.ALLOWED_MEDIA_VIDEO_EXTENSIONS,
    ),
    "branding": ("media/branding", lambda: config.BRANDING_DIR, config.ALLOWED_BRANDING_EXTENSIONS),
}

# Une section par table de contenu. `fields` : colonnes exportees (hors id,
# created_at) ; `required` : champs texte obligatoires ; `key` : champs qui
# identifient un doublon en mode "ajouter" ; `files` : champ -> type de media.
SECTIONS = [
    {
        "name": "objects", "table": "objects", "label": "Objèctes",
        "fields": ["name_oc", "name_fr", "category", "image_filename", "audio_filename", "active", "sort_order"],
        "required": ["name_oc", "name_fr"],
        "key": ["name_oc", "name_fr"],
        "files": {"image_filename": "object_image", "audio_filename": "object_audio"},
    },
    {
        "name": "vertadier_words", "table": "vertadier_words", "label": "Ven de l'occitan ?",
        "fields": ["word_fr", "is_occitan", "explanation", "source", "active", "sort_order"],
        "required": ["word_fr"],
        "key": ["word_fr"],
        "files": {},
    },
    {
        "name": "duel_questions", "table": "duel_questions", "label": "Duèl Occitan",
        "fields": ["question_fr", "choice_a", "choice_b", "correct_choice", "explanation", "source", "active", "sort_order"],
        "required": ["question_fr", "choice_a", "choice_b", "correct_choice"],
        "key": ["question_fr"],
        "files": {},
        "choices": ("a", "b"),
    },
    {
        "name": "quiz_questions", "table": "quiz_questions", "label": "Quiz Calandreta",
        "fields": ["question_fr", "choice_a", "choice_b", "choice_c", "correct_choice", "explanation", "source", "active", "sort_order"],
        "required": ["question_fr", "choice_a", "choice_b", "choice_c", "correct_choice"],
        "key": ["question_fr"],
        "files": {},
        "choices": ("a", "b", "c"),
    },
    {
        "name": "villages", "table": "villages", "label": "Vilatges (Memòria)",
        "fields": ["name_fr", "name_oc", "source", "active", "sort_order"],
        "required": ["name_fr", "name_oc"],
        "key": ["name_fr", "name_oc"],
        "files": {},
    },
    {
        "name": "media_items", "table": "media_items", "label": "Fotos & vidèos",
        "fields": ["filename", "media_type", "caption", "display_seconds", "active", "sort_order"],
        "required": ["filename", "media_type"],
        "key": ["filename"],
        "files": {"filename": "library"},
    },
]
SECTIONS_BY_NAME = {s["name"]: s for s in SECTIONS}

# Reglages exportables (Configuration) : apparence et textes de la borne.
# Jamais le PIN ni les mappings manette/clavier.
SETTINGS_KEYS = ["theme", "kiosk_texts", "action_label_overrides", "logo_filename", "crotz_filename"]
SETTINGS_FILES = {"logo_filename": "branding", "crotz_filename": "branding"}


class ImportError_(ValueError):
    """Archive illisible ou contenu invalide (message affiche tel quel)."""


# --- Export ----------------------------------------------------------------

def build_export(include_media=True, include_settings=True):
    """Renvoie (nom_de_fichier, octets_du_zip)."""
    db = get_db()
    data = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "app_version": config.APP_VERSION,
        "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "source": "demo" if config.DEMO_MODE else "borne",
    }
    files = set()  # (kind, filename)

    for section in SECTIONS:
        rows = db.execute(
            f"SELECT id, {', '.join(section['fields'])} FROM {section['table']} ORDER BY sort_order, id"
        ).fetchall()
        items = []
        for row in rows:
            item = {field: row[field] for field in section["fields"]}
            for field, kind in section["files"].items():
                if item.get(field):
                    files.add((kind, item[field]))
            if section["name"] == "objects":
                item["tags"] = [
                    t["uid"] for t in object_manager.list_tags_for_object(row["id"])
                    if not object_manager.is_fake_tag(t["uid"])
                ]
            items.append(item)
        data[section["name"]] = items

    if include_settings:
        settings = {}
        for key in SETTINGS_KEYS:
            row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if row is not None and row["value"] not in (None, ""):
                settings[key] = row["value"]
                if key in SETTINGS_FILES:
                    files.add((SETTINGS_FILES[key], row["value"]))
        data["settings"] = settings

    buf = io.BytesIO()
    missing = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if include_media:
            for kind, filename in sorted(files):
                archive_dir, get_dir, _ = MEDIA_KINDS[kind]
                path = os.path.join(get_dir(), os.path.basename(filename))
                if os.path.isfile(path):
                    zf.write(path, f"{archive_dir}/{os.path.basename(filename)}")
                else:
                    missing.append(f"{archive_dir}/{filename}")
        data["media_included"] = bool(include_media)
        data["missing_media"] = missing
        zf.writestr(JSON_NAME, json.dumps(data, ensure_ascii=False, indent=2))
        for section in SECTIONS:
            zf.writestr(f"tableur/{section['name']}.csv", _to_csv(section, data[section["name"]]))
        zf.writestr("LISEZMOI.txt", _readme(data))

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    prefix = "maleta-demo-contenu" if config.DEMO_MODE else "maleta-contenu"
    return f"{prefix}-{stamp}.zip", buf.getvalue()


def _to_csv(section, items):
    """CSV pour tableur : point-virgule + BOM UTF-8 (lu correctement par
    Excel/LibreOffice en francais, accents occitans compris)."""
    out = io.StringIO()
    columns = section["fields"] + (["tags"] if section["name"] == "objects" else [])
    writer = csv.writer(out, delimiter=";")
    writer.writerow(columns)
    for item in items:
        row = []
        for col in columns:
            value = item.get(col)
            if isinstance(value, list):
                value = " ".join(value)
            row.append("" if value is None else value)
        writer.writerow(row)
    return "﻿" + out.getvalue()


def _readme(data):
    counts = "\n".join(f"  - {s['label']} : {len(data[s['name']])}" for s in SECTIONS)
    return (
        "La Maleta Occitana - export du contenu\n"
        f"Version de l'appli : {data['app_version']} ({data['source']})\n"
        f"Date : {data['exported_at']}\n\n"
        f"Contenu :\n{counts}\n\n"
        "Pour le reimplanter : Admin > Exportar / Importar > Importar, puis\n"
        "choisir ce fichier .zip tel quel (sans le decompresser).\n\n"
        f"{JSON_NAME} est le seul fichier lu a l'import. Le dossier tableur/\n"
        "contient le meme contenu en CSV, pour relecture dans un tableur.\n"
    )


# --- Import ----------------------------------------------------------------

def read_bundle(file_storage):
    """Lit un .zip (ou un .json) envoye depuis la page d'import. Renvoie
    (data, zipfile_ou_None). Leve ImportError_ si illisible."""
    raw = file_storage.read()
    if not raw:
        raise ImportError_("Fichier vide.")
    archive = None
    if zipfile.is_zipfile(io.BytesIO(raw)):
        archive = zipfile.ZipFile(io.BytesIO(raw))
        try:
            payload = archive.read(JSON_NAME)
        except KeyError:
            raise ImportError_(f"Cette archive ne contient pas de {JSON_NAME} : ce n'est pas un export de la Maleta.")
    else:
        payload = raw
    try:
        data = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        raise ImportError_("Fichier illisible : il faut un .zip (ou .json) exporté depuis la Maleta.")
    if not isinstance(data, dict) or data.get("format") != FORMAT_NAME:
        raise ImportError_("Ce fichier n'est pas un export de contenu de la Maleta Occitana.")
    if int(data.get("format_version", 0)) > FORMAT_VERSION:
        raise ImportError_("Export fait avec une version plus récente de l'appli : mets d'abord cette installation à jour.")
    return data, archive


def build_counts():
    """Contenu actuel de cette installation, au format de summarize()."""
    db = get_db()
    return {
        s["name"]: db.execute(f"SELECT id FROM {s['table']}").fetchall()
        for s in SECTIONS
    }


def summarize(data):
    """Nombre d'elements par section (affiche avant/apres import)."""
    return [
        {"name": s["name"], "label": s["label"], "count": len(data.get(s["name"]) or [])}
        for s in SECTIONS
    ]


def import_bundle(data, archive, sections, mode="merge", import_settings=False, import_tags=True):
    """Importe les sections demandees. mode "merge" : ajoute ce qui n'existe
    pas encore (doublons ignores, contenu existant intact) ; mode "replace" :
    vide d'abord chaque section importee. Renvoie un rapport
    {section: {"added": n, "skipped": n}, "files": n, "warnings": [...]}."""
    if mode not in ("merge", "replace"):
        raise ImportError_("Mode d'import inconnu.")
    db = get_db()
    report = {"sections": {}, "files": 0, "warnings": []}
    file_cache = {}

    def import_file(kind, filename):
        """Copie un media de l'archive vers le dossier local. Renvoie le nom
        local (renomme si un fichier DIFFERENT porte deja ce nom), ou None."""
        if not filename:
            return None
        cache_key = (kind, filename)
        if cache_key in file_cache:
            return file_cache[cache_key]
        archive_dir, get_dir, allowed = MEDIA_KINDS[kind]
        result = None
        base = os.path.basename(str(filename).replace("\\", "/"))
        content = None
        if archive is not None:
            try:
                content = archive.read(f"{archive_dir}/{base}")
            except KeyError:
                content = None
        target_dir = get_dir()
        name, ext = safe_upload_name(base)
        if ext not in allowed:
            report["warnings"].append(f"Fichier ignoré (format non autorisé) : {base}")
        elif content is None:
            # Pas dans l'archive : garde la reference seulement si le fichier
            # existe deja ici (ex. reimport sur la meme machine).
            if os.path.isfile(os.path.join(target_dir, name)):
                result = name
            else:
                report["warnings"].append(f"Fichier absent de l'archive : {base}")
        else:
            os.makedirs(target_dir, exist_ok=True)
            result = _store_file(target_dir, name, content)
            report["files"] += 1
        file_cache[cache_key] = result
        return result

    for section_name in sections:
        section = SECTIONS_BY_NAME.get(section_name)
        if section is None:
            continue
        items = data.get(section_name) or []
        if not isinstance(items, list):
            raise ImportError_(f"Section « {section['label']} » invalide.")
        added = skipped = 0
        if mode == "replace":
            db.execute(f"DELETE FROM {section['table']}")
        existing_keys = {
            _key(section, dict(row))
            for row in db.execute(f"SELECT {', '.join(section['key'])} FROM {section['table']}")
        }
        max_order = db.execute(f"SELECT MAX(sort_order) AS m FROM {section['table']}").fetchone()["m"] or 0

        for raw_item in items:
            item = _clean_item(section, raw_item)
            if item is None:
                skipped += 1
                continue
            for field, kind in section["files"].items():
                if item.get(field):
                    item[field] = import_file(kind, item[field])
            if any(not item.get(f) for f in section["required"]):
                # ex. photo du diaporama dont le fichier manque
                skipped += 1
                continue
            key = _key(section, item)
            if key in existing_keys:
                skipped += 1
                continue
            existing_keys.add(key)
            item["sort_order"] = max_order + int(item.get("sort_order") or 0) + 1
            cols = section["fields"]
            cur = db.execute(
                f"INSERT INTO {section['table']} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                [item.get(c) for c in cols],
            )
            if section_name == "objects" and import_tags:
                for uid in raw_item.get("tags") or []:
                    uid = str(uid).strip()
                    if uid and not object_manager.is_fake_tag(uid):
                        _pair_tag_nocommit(db, uid, cur.lastrowid)
            added += 1
        report["sections"][section_name] = {"label": section["label"], "added": added, "skipped": skipped}

    if import_settings:
        settings = data.get("settings") or {}
        for key in SETTINGS_KEYS:
            value = settings.get(key)
            if not isinstance(value, str) or not value:
                continue
            if key in SETTINGS_FILES:
                value = import_file(SETTINGS_FILES[key], value)
                if not value:
                    continue
            db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        report["settings"] = True

    db.commit()
    if config.DEMO_MODE:
        object_manager.ensure_demo_tags()
    return report


def _store_file(target_dir, name, content):
    """Ecrit `content` dans target_dir sous `name`, sauf si un fichier
    identique y est deja (reutilise), ou renomme si un fichier different
    porte ce nom."""
    path = os.path.join(target_dir, name)
    digest = hashlib.sha256(content).hexdigest()
    if os.path.isfile(path):
        with open(path, "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() == digest:
                return name
        name = f"{digest[:8]}_{name}"
        path = os.path.join(target_dir, name)
        if os.path.isfile(path):
            return name
    with open(path, "wb") as f:
        f.write(content)
    return name


def _pair_tag_nocommit(db, uid, object_id):
    # Meme logique que object_manager.pair_tag, sans commit intermediaire.
    if db.execute("SELECT 1 FROM tags WHERE uid = ?", (uid,)).fetchone():
        db.execute("UPDATE tags SET object_id = ? WHERE uid = ?", (object_id, uid))
    else:
        db.execute("INSERT INTO tags (uid, object_id) VALUES (?, ?)", (uid, object_id))


def _key(section, item):
    return tuple(str(item.get(f) or "").strip().casefold() for f in section["key"])


def _clean_item(section, raw):
    """Valide/normalise une entree importee. None si inutilisable."""
    if not isinstance(raw, dict):
        return None
    item = {}
    for field in section["fields"]:
        value = raw.get(field)
        if field in ("active", "is_occitan"):
            item[field] = 1 if value in (1, True, "1", "true", "True") else 0
            if field == "active" and value is None:
                item[field] = 1
        elif field in ("sort_order", "display_seconds"):
            try:
                item[field] = int(value) if value not in (None, "") else None
            except (TypeError, ValueError):
                item[field] = None
        else:
            item[field] = str(value).strip() if value not in (None, "") else None
    if "choices" in section:
        choice = (item.get("correct_choice") or "").lower()
        if choice not in section["choices"]:
            return None
        item["correct_choice"] = choice
    if section["name"] == "media_items" and item.get("media_type") not in ("image", "video"):
        return None
    if section["name"] == "media_items" and item.get("display_seconds") is not None and item["display_seconds"] <= 0:
        item["display_seconds"] = None
    if any(not item.get(f) for f in section["required"] if f not in section["files"]):
        return None
    return item
