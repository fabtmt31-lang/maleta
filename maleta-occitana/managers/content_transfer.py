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

Module volontairement autonome (ne depend que de config, db.database et
upload_utils, presents depuis la v1.03) : il peut etre depose tel quel sur
une borne plus ancienne, voir docs/import-contenu-version-prod.md.
"""

import csv
import datetime
import hashlib
import io
import json
import os
import re
import unicodedata
import zipfile

import config
from db.database import get_db
from managers.upload_utils import safe_upload_name

# Tags NFC fictifs (memes prefixes que object_manager, repris ici pour que ce
# module reste autonome) : tags simules de la demo et du bouton "Simuler un
# scan" de l'admin. Jamais exportes ni importes.
FAKE_TAG_PREFIXES = ("DEMO-", "SIMU-")


def _is_fake_tag(uid):
    return str(uid).startswith(FAKE_TAG_PREFIXES)


def _demo_mode():
    return getattr(config, "DEMO_MODE", False)

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

# v1.21 : colonnes des fichiers CSV (tableur), en-tetes en francais. Memes
# colonnes a l'export (dossier tableur/ du .zip), dans les modeles CSV et a
# l'import : un CSV exporte, modifie dans un tableur puis reimporte garde
# toutes ses colonnes. (champ, en-tete, explication pour les modeles).
CSV_COLUMNS = {
    "objects": [
        ("name_oc", "mot_occitan", "obligatoire"),
        ("name_fr", "mot_francais", "obligatoire"),
        ("category", "categorie", "facultatif (ex. Animaux)"),
        ("image_filename", "image", "facultatif : l'image s'ajoute ensuite depuis l'admin (fiche de l'objet)"),
        ("audio_filename", "son", "facultatif : le son s'ajoute ensuite depuis l'admin (fiche de l'objet)"),
        ("active", "actif", "oui / non (vide = oui)"),
        ("sort_order", "ordre", "facultatif : numero d'ordre"),
        ("tags", "tags_nfc", "facultatif : UID des tags NFC, separes par des espaces"),
    ],
    "vertadier_words": [
        ("word_fr", "mot_francais", "obligatoire : mot ou expression francaise"),
        ("is_occitan", "vient_de_l_occitan", "obligatoire : oui / non"),
        ("explanation", "explication", "facultatif : affichee apres la reponse"),
        ("source", "source", "facultatif : reference (CNRTL, IEO...)"),
        ("active", "actif", "oui / non (vide = oui)"),
        ("sort_order", "ordre", "facultatif"),
    ],
    "duel_questions": [
        ("question_fr", "question", "obligatoire"),
        ("choice_a", "reponse_a", "obligatoire"),
        ("choice_b", "reponse_b", "obligatoire"),
        ("correct_choice", "bonne_reponse", "obligatoire : A ou B"),
        ("explanation", "explication", "facultatif"),
        ("source", "source", "facultatif"),
        ("active", "actif", "oui / non (vide = oui)"),
        ("sort_order", "ordre", "facultatif"),
    ],
    "quiz_questions": [
        ("question_fr", "question", "obligatoire"),
        ("choice_a", "reponse_a", "obligatoire"),
        ("choice_b", "reponse_b", "obligatoire"),
        ("choice_c", "reponse_c", "obligatoire"),
        ("correct_choice", "bonne_reponse", "obligatoire : A, B ou C"),
        ("explanation", "explication", "facultatif"),
        ("source", "source", "facultatif"),
        ("active", "actif", "oui / non (vide = oui)"),
        ("sort_order", "ordre", "facultatif"),
    ],
    "villages": [
        ("name_fr", "nom_francais", "obligatoire (ex. Toulouse)"),
        ("name_oc", "nom_occitan", "obligatoire (ex. Tolosa)"),
        ("source", "source", "facultatif"),
        ("active", "actif", "oui / non (vide = oui)"),
        ("sort_order", "ordre", "facultatif"),
    ],
    "media_items": [
        ("filename", "fichier", "obligatoire : la photo/video doit deja etre dans la mediatheque de la borne"),
        ("media_type", "type", "obligatoire : image ou video"),
        ("caption", "legende", "facultatif"),
        ("display_seconds", "duree_secondes", "facultatif : duree d'affichage d'une photo"),
        ("active", "actif", "oui / non (vide = oui)"),
        ("sort_order", "ordre", "facultatif"),
    ],
}
# Autres en-tetes acceptes a l'import (en plus du nom technique du champ et
# de l'en-tete ci-dessus), deja normalises (minuscules, sans accent, "_").
CSV_ALIASES = {
    "question_fr": ["question_francais"],
    "correct_choice": ["bonne_reponse", "reponse_correcte", "solution"],
    "explanation": ["explications"],
    "is_occitan": ["occitan", "vient_de_l_occitan", "origine_occitane", "vertadier"],
    "active": ["active", "actif"],
    "sort_order": ["ordre"],
    "display_seconds": ["duree"],
    "caption": ["legende"],
}
# Mots du nom de fichier qui designent une section (import CSV automatique).
CSV_FILENAME_HINTS = [
    ("quiz", "quiz_questions"), ("duel", "duel_questions"),
    ("vertadier", "vertadier_words"), ("ven_de", "vertadier_words"),
    ("vilatge", "villages"), ("village", "villages"),
    ("objecte", "objects"), ("objet", "objects"), ("object", "objects"),
    ("media", "media_items"), ("foto", "media_items"), ("photo", "media_items"), ("diapo", "media_items"),
]
_YES = {"1", "oui", "o", "yes", "y", "true", "vrai", "x", "vertadier", "oc"}
_NO = {"0", "non", "n", "no", "false", "faux", "fals"}


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
        "source": "demo" if _demo_mode() else "borne",
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
                    t["uid"] for t in db.execute("SELECT uid FROM tags WHERE object_id = ?", (row["id"],))
                    if not _is_fake_tag(t["uid"])
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
    prefix = "maleta-demo-contenu" if _demo_mode() else "maleta-contenu"
    return f"{prefix}-{stamp}.zip", buf.getvalue()


def _to_csv(section, items):
    """CSV pour tableur : point-virgule + BOM UTF-8 (lu correctement par
    Excel/LibreOffice en francais, accents occitans compris). Reimportable
    tel quel (voir read_csv)."""
    out = io.StringIO()
    columns = CSV_COLUMNS[section["name"]]
    writer = csv.writer(out, delimiter=";")
    writer.writerow([header for _, header, _ in columns])
    for item in items:
        writer.writerow([_csv_value(field, item.get(field)) for field, _, _ in columns])
    return "\ufeff" + out.getvalue()


def _csv_value(field, value):
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(value)
    if field in ("active", "is_occitan"):
        return "oui" if value else "non"
    if field == "correct_choice":
        return str(value).upper()
    return value


def build_csv_templates():
    """v1.21 : modeles CSV vides (une ligne d'en-tetes par section) + notice,
    pour ecrire le contenu dans un tableur sans l'appli. Renvoie
    (nom_de_fichier, octets_du_zip)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in csv_template_files().items():
            zf.writestr(name, content)
    return "maleta-modeles-csv.zip", buf.getvalue()


def csv_template_files():
    """{nom_de_fichier: contenu} des modeles CSV et de leur notice."""
    files = {f"{s['name']}.csv": _to_csv(s, []) for s in SECTIONS}
    files["LISEZMOI-CSV.txt"] = _csv_readme()
    return files


def _csv_readme():
    lines = [
        "La Maleta Occitana - ecrire le contenu dans un tableur (CSV)",
        "",
        "Un fichier par type de contenu. Ouvrir le modele dans Excel ou",
        "LibreOffice, garder la premiere ligne (en-tetes), ajouter une ligne par",
        "question / mot / objet, puis enregistrer en CSV (separateur",
        "point-virgule ou virgule, UTF-8 de preference).",
        "",
        "Import : Admin > Exportar / Importar > Importar, choisir un ou plusieurs",
        "fichiers .csv. Le type de contenu est reconnu par le nom du fichier",
        "(garder par ex. \"quiz\" dans le nom) ou par ses colonnes. Sur la borne,",
        "en ligne de commande : importer_contenu.py fichier.csv",
        "",
        "Les lignes incompletes sont ignorees et signalees avec leur numero.",
        "Les images et les sons des objets s'ajoutent ensuite depuis l'admin.",
        "",
    ]
    for section in SECTIONS:
        lines.append(f"== {section['name']}.csv : {section['label']} ==")
        for _, header, help_text in CSV_COLUMNS[section["name"]]:
            lines.append(f"  {header:<20} {help_text}")
        lines.append("")
    return "\n".join(lines)


def _readme(data):
    counts = "\n".join(f"  - {s['label']} : {len(data[s['name']])}" for s in SECTIONS)
    return (
        "La Maleta Occitana - export du contenu\n"
        f"Version de l'appli : {data['app_version']} ({data['source']})\n"
        f"Date : {data['exported_at']}\n\n"
        f"Contenu :\n{counts}\n\n"
        "Pour le reimplanter : Admin > Exportar / Importar > Importar, puis\n"
        "choisir ce fichier .zip tel quel (sans le decompresser).\n\n"
        f"Le dossier tableur/ contient le meme contenu en CSV (un fichier par\n"
        "type de contenu) : modifiable dans un tableur puis reimportable seul\n"
        "(Importar > choisir le ou les .csv). Les images et sons ne sont que\n"
        f"dans le .zip complet ({JSON_NAME} + media/).\n"
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


def read_csv(filename, raw, section_name=None):
    """v1.21 : lit un fichier CSV ecrit dans un tableur (ou exporte) et le
    convertit au format de l'export JSON. Renvoie (data, None), utilisable
    tel quel par import_bundle(). `section_name` force le type de contenu ;
    sinon il est deduit du nom du fichier, puis des colonnes."""
    text = None
    for encoding in ("utf-8-sig", "cp1252"):  # cp1252 : CSV d'Excel sous Windows
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    first_line = text.split("\n", 1)[0]
    if not first_line.strip():
        raise ImportError_(f"{filename} : fichier CSV vide.")
    delimiter = max(";,\t", key=first_line.count)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    headers = [_normalize_header(h) for h in next(reader)]

    section_name = section_name or _guess_section(filename, headers)
    section = SECTIONS_BY_NAME.get(section_name)
    if section is None:
        raise ImportError_(
            f"{filename} : type de contenu non reconnu. Garde dans le nom du fichier « quiz », "
            "« duel », « vertadier », « vilatge », « objet » ou « media », ou choisis le type à l'import."
        )
    mapping = _header_mapping(section_name)
    columns = [mapping.get(h) for h in headers]
    missing = [
        header for field, header, _ in CSV_COLUMNS[section_name]
        if field in section["required"] + (["is_occitan"] if section_name == "vertadier_words" else [])
        and field not in columns
    ]
    if missing:
        raise ImportError_(
            f"{filename} ({section['label']}) : colonne(s) obligatoire(s) absente(s) : {', '.join(missing)}. "
            "Partir du modèle CSV (bouton « Modèles CSV »)."
        )

    items = []
    while True:
        line = reader.line_num + 1
        try:
            row = next(reader)
        except StopIteration:
            break
        if not any(cell.strip() for cell in row):
            continue
        item = {"_ligne": line}
        for field, cell in zip(columns, row):
            if field is None:
                continue
            cell = cell.strip()
            if field in ("active", "is_occitan"):
                value = _parse_yes_no(cell)
                if value is None and cell:
                    item["_erreur"] = f"« {cell} » : oui ou non attendu"
                elif value is None and field == "is_occitan":
                    item["_erreur"] = "vient_de_l_occitan vide (oui ou non)"
                item[field] = value
            elif field == "correct_choice":
                item[field] = _parse_choice(cell)
                if cell and item[field] is None:
                    item["_erreur"] = f"bonne réponse « {cell} » invalide"
            elif field == "tags":
                item[field] = cell.split()
            else:
                item[field] = cell or None
        items.append(item)
    data = {"format": FORMAT_NAME, "format_version": FORMAT_VERSION, "source": "csv", section_name: items}
    return data, None


def read_upload(filename, raw, csv_section=None):
    """Point d'entree unique de l'import (page admin et ligne de commande) :
    .zip / .json (export complet) ou .csv (une section). Renvoie
    (data, archive_ou_None)."""
    if not raw:
        raise ImportError_(f"{filename} : fichier vide.")
    if (filename or "").lower().endswith(".csv"):
        return read_csv(filename, raw, csv_section)
    return read_bundle(_Bytes(raw))


class _Bytes:
    def __init__(self, raw):
        self.raw = raw

    def read(self):
        return self.raw


def _normalize_header(header):
    header = unicodedata.normalize("NFKD", header.replace("\ufeff", "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", header.lower()).strip("_")


def _header_mapping(section_name):
    mapping = {}
    for field, header, _ in CSV_COLUMNS[section_name]:
        for name in [field, header] + CSV_ALIASES.get(field, []):
            mapping.setdefault(_normalize_header(name), field)
    return mapping


def _guess_section(filename, headers):
    base = _normalize_header(os.path.splitext(os.path.basename(filename or ""))[0])
    for hint, section_name in CSV_FILENAME_HINTS:
        if hint in base:
            return section_name
    # Sinon : la section dont on reconnait toutes les colonnes obligatoires et
    # le plus de colonnes ; a egalite, on ne devine pas.
    scores = []
    for section in SECTIONS:
        mapping = _header_mapping(section["name"])
        found = {mapping[h] for h in headers if h in mapping}
        if set(section["required"]) <= found:
            scores.append((len(found), section["name"]))
    scores.sort(reverse=True)
    if scores and (len(scores) == 1 or scores[0][0] > scores[1][0]):
        return scores[0][1]
    return None


def _parse_yes_no(cell):
    value = _normalize_header(cell)
    if value in _YES:
        return 1
    if value in _NO:
        return 0
    return None


def _parse_choice(cell):
    value = _normalize_header(cell)
    value = re.sub(r"^(reponse|rep|choix)_?", "", value)
    return {"a": "a", "b": "b", "c": "c", "1": "a", "2": "b", "3": "c"}.get(value)


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
    """Importe un seul fichier deja lu (voir import_bundles)."""
    return import_bundles([("", data, archive)], sections, mode, import_settings, import_tags)


def import_bundles(bundles, sections, mode="merge", import_settings=False, import_tags=True):
    """Importe plusieurs fichiers DEJA LUS (read_upload), en une operation.
    `bundles` : liste de (nom_de_fichier, data, archive).

    mode "merge" : ajoute ce qui n'existe pas encore (doublons ignores,
    contenu existant intact). mode "replace" (v1.22) : vide d'abord, UNE
    seule fois, les sections cochees qui sont PRESENTES dans au moins un des
    fichiers -- un quiz.csv ne vide plus que le Quiz, et deux quiz.csv
    s'additionnent. Une sauvegarde complete est faite juste avant
    (create_backup). Renvoie un rapport
    {"sections": {section: {"label", "added", "skipped", "deleted"}},
     "files": n, "warnings": [...], "backup": chemin_ou_None}."""
    if mode not in ("merge", "replace"):
        raise ImportError_("Mode d'import inconnu.")
    db = get_db()
    report = {"sections": {}, "files": 0, "warnings": [], "backup": None}
    if mode == "replace":
        to_clear = [
            name for name in sections
            if name in SECTIONS_BY_NAME and any(name in data for _, data, _ in bundles)
        ]
        if to_clear:
            report["backup"] = create_backup()
            for name in to_clear:
                section = SECTIONS_BY_NAME[name]
                deleted = db.execute(f"SELECT COUNT(*) AS n FROM {section['table']}").fetchone()["n"]
                db.execute(f"DELETE FROM {section['table']}")
                report["sections"][name] = {"label": section["label"], "added": 0, "skipped": 0, "deleted": deleted}
            db.commit()
    for _, data, archive in bundles:
        # Apparence/textes : seulement depuis un export complet, jamais un CSV.
        with_settings = import_settings and data.get("source") != "csv"
        merge_reports(report, _import_one(data, archive, sections, with_settings, import_tags))
    return report


def _import_one(data, archive, sections, import_settings, import_tags):
    """Ajoute le contenu d'un fichier (jamais d'effacement ici)."""
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
                where = "de l'archive" if archive is not None else "de la médiathèque (à ajouter depuis l'admin)"
                report["warnings"].append(f"Fichier absent {where} : {base}")
        else:
            os.makedirs(target_dir, exist_ok=True)
            result, written = _store_file(target_dir, name, content)
            if written:
                report["files"] += 1
        file_cache[cache_key] = result
        return result

    for section_name in sections:
        section = SECTIONS_BY_NAME.get(section_name)
        if section is None:
            continue
        if section_name not in data:
            continue  # section absente du fichier (ex. un CSV n'en a qu'une)
        items = data.get(section_name) or []
        if not isinstance(items, list):
            raise ImportError_(f"Section « {section['label']} » invalide.")
        added = skipped = 0
        existing_keys = {
            _key(section, dict(row))
            for row in db.execute(f"SELECT {', '.join(section['key'])} FROM {section['table']}")
        }
        max_order = db.execute(f"SELECT MAX(sort_order) AS m FROM {section['table']}").fetchone()["m"] or 0

        def skip(raw_item, reason):
            # Les lignes d'un CSV sont signalees une par une (numero de ligne).
            if isinstance(raw_item, dict) and raw_item.get("_ligne"):
                report["warnings"].append(f"{section['label']}, ligne {raw_item['_ligne']} ignorée : {reason}")

        for raw_item in items:
            if isinstance(raw_item, dict) and raw_item.get("_erreur"):
                skipped += 1
                skip(raw_item, raw_item["_erreur"])
                continue
            item, reason = _clean_item(section, raw_item)
            if item is None:
                skipped += 1
                skip(raw_item, reason)
                continue
            for field, kind in section["files"].items():
                if item.get(field):
                    item[field] = import_file(kind, item[field])
            if any(not item.get(f) for f in section["required"]):
                # ex. photo du diaporama dont le fichier manque
                skipped += 1
                skip(raw_item, "fichier introuvable")
                continue
            key = _key(section, item)
            if key in existing_keys:
                skipped += 1
                skip(raw_item, "déjà présent (doublon)")
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
                    if uid and not _is_fake_tag(uid):
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
    if _demo_mode():
        from managers import object_manager
        object_manager.ensure_demo_tags()
    return report


BACKUP_DIR_NAME = "sauvegardes"
BACKUP_KEEP = 10


def create_backup():
    """v1.22 : export complet (medias compris) enregistre a cote de la base,
    avant un import qui efface du contenu (mode "Remplacer"). Garde les
    BACKUP_KEEP plus recents. Renvoie le chemin du fichier cree."""
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(config.DATABASE_PATH)), BACKUP_DIR_NAME)
    os.makedirs(backup_dir, exist_ok=True)
    _, payload = build_export(include_media=True, include_settings=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(backup_dir, f"maleta-sauvegarde-{stamp}.zip")
    with open(path, "wb") as f:
        f.write(payload)
    backups = sorted(
        name for name in os.listdir(backup_dir)
        if name.startswith("maleta-sauvegarde-") and name.endswith(".zip")
    )
    for name in backups[:-BACKUP_KEEP]:
        os.remove(os.path.join(backup_dir, name))
    return path


def merge_reports(total, part):
    """Additionne le rapport d'import `part` dans `total` (import de
    plusieurs fichiers en une fois)."""
    for name, result in part["sections"].items():
        current = total["sections"].setdefault(
            name, {"label": result["label"], "added": 0, "skipped": 0, "deleted": 0})
        current["added"] += result["added"]
        current["skipped"] += result["skipped"]
        current["deleted"] = current.get("deleted", 0) + result.get("deleted", 0)
    total["files"] += part["files"]
    total["warnings"].extend(part["warnings"])
    if part.get("settings"):
        total["settings"] = True
    if part.get("backup"):
        total["backup"] = part["backup"]


def _store_file(target_dir, name, content):
    """Ecrit `content` dans target_dir sous `name`, sauf si un fichier
    identique y est deja (reutilise), ou renomme si un fichier different
    porte ce nom. Renvoie (nom_local, ecrit)."""
    path = os.path.join(target_dir, name)
    digest = hashlib.sha256(content).hexdigest()
    if os.path.isfile(path):
        with open(path, "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() == digest:
                return name, False
        name = f"{digest[:8]}_{name}"
        path = os.path.join(target_dir, name)
        if os.path.isfile(path):
            return name, False
    with open(path, "wb") as f:
        f.write(content)
    return name, True


def _pair_tag_nocommit(db, uid, object_id):
    # Meme logique que object_manager.pair_tag, sans commit intermediaire.
    if db.execute("SELECT 1 FROM tags WHERE uid = ?", (uid,)).fetchone():
        db.execute("UPDATE tags SET object_id = ? WHERE uid = ?", (object_id, uid))
    else:
        db.execute("INSERT INTO tags (uid, object_id) VALUES (?, ?)", (uid, object_id))


def _key(section, item):
    return tuple(str(item.get(f) or "").strip().casefold() for f in section["key"])


def _clean_item(section, raw):
    """Valide/normalise une entree importee. Renvoie (item, None), ou
    (None, raison) si elle est inutilisable."""
    if not isinstance(raw, dict):
        return None, "format invalide"
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
    missing = [
        header for field, header, _ in CSV_COLUMNS[section["name"]]
        if field in section["required"] and field not in section["files"] and not item.get(field)
    ]
    if missing:
        return None, f"à remplir : {', '.join(missing)}"
    if "choices" in section:
        choice = (item.get("correct_choice") or "").lower()
        if choice not in section["choices"]:
            return None, f"bonne réponse attendue : {' ou '.join(c.upper() for c in section['choices'])}"
        item["correct_choice"] = choice
    if section["name"] == "media_items":
        item["media_type"] = (item.get("media_type") or "").lower()
        if item["media_type"] not in ("image", "video"):
            return None, "type attendu : image ou video"
        if item.get("display_seconds") is not None and item["display_seconds"] <= 0:
            item["display_seconds"] = None
    return item, None
