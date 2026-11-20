"""Mise a jour de la borne depuis GitHub (v1.37) -- Admin > Mise a jour.

L'appli ne fait que :
  - regarder sur GitHub la derniere archive de la borne publiee
    (maleta-occitana-v<version>.zip) et la comparer a APP_VERSION ;
  - lancer `sudo -n /usr/local/sbin/maleta-maj lancer`, seule commande que
    l'utilisateur de l'appli a le droit de lancer en root (install.sh). C'est
    ce programme (maj/maleta-maj.py) qui telecharge, verifie et installe ;
  - lire son etat (/var/lib/maleta-maj/etat.json) et son journal.
Une sauvegarde du contenu (comme avant un import "Remplacer") est faite juste
avant de lancer la mise a jour.
"""

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation

import config

DEPOT = "fabtmt31-lang/maleta"
ETIQUETTE = "demo-latest"
PROGRAMME = "/usr/local/sbin/maleta-maj"
FICHIER_ETAT = "/var/lib/maleta-maj/etat.json"
JOURNAL = "/var/log/maleta-maj.log"
ARCHIVE_RE = re.compile(r"^maleta-occitana-v(\d+(?:\.\d+)*)\.zip$")
EN_COURS = ("lancee", "recherche", "telechargement", "verification", "installation", "retour")
TIMEOUT = 15


class UpdateError(Exception):
    """Erreur affichable."""


def release_url():
    return f"https://github.com/{DEPOT}/releases/tag/{ETIQUETTE}"


def version_key(version):
    """"1.36" < "1.4" < "1.41" : les versions se lisent comme des nombres
    decimaux (v1.3 -> v1.31 -> ... -> v1.4, voir README)."""
    try:
        return Decimal(version)
    except (InvalidOperation, TypeError):
        return Decimal(0)


def _fetch_release():
    url = f"https://api.github.com/repos/{DEPOT}/releases/tags/{ETIQUETTE}"
    request = urllib.request.Request(url, headers={"User-Agent": "maleta-occitana", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"GitHub a répondu {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise UpdateError("pas d'accès à Internet (vérifier le Wi-Fi dans Jòcs amagats > Wi-Fi)") from exc
    except ValueError as exc:
        raise UpdateError("réponse de GitHub illisible") from exc


def check(fetch=_fetch_release):
    """{current, latest, newer, published_at, commit, size} ; UpdateError si
    GitHub est injoignable ou si la publication n'a pas d'archive de borne."""
    release = fetch()
    for asset in release.get("assets", []):
        match = ARCHIVE_RE.match(asset.get("name", ""))
        if match:
            latest = match.group(1)
            return {
                "current": config.APP_VERSION,
                "latest": latest,
                "newer": version_key(latest) > version_key(config.APP_VERSION),
                "published_at": (release.get("published_at") or "")[:16].replace("T", " "),
                "commit": (release.get("target_commitish") or "")[:7],
                "size_mb": round((asset.get("size") or 0) / (1024 * 1024), 1),
            }
    raise UpdateError("la publication GitHub ne contient pas d'archive de la borne")


def installer_available():
    """Le programme de mise a jour est installe par install.sh (v1.37+)."""
    return os.path.isfile(PROGRAMME) and os.access(PROGRAMME, os.X_OK)


def read_state():
    try:
        with open(FICHIER_ETAT, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        return None
    state["running"] = state.get("etat") in EN_COURS
    return state


def read_log(lines=40):
    try:
        with open(JOURNAL, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except OSError:
        return ""


def launch(run=subprocess.run):
    """Sauvegarde du contenu puis lancement de la mise a jour (detachee)."""
    if not installer_available():
        raise UpdateError("programme de mise à jour absent : faire une fois la mise à jour à la main "
                          "(sudo bash install.sh) avec la version 1.37 ou suivante")
    state = read_state()
    if state and state["running"]:
        raise UpdateError("une mise à jour est déjà en cours")
    from managers.content_transfer import create_backup
    backup = create_backup()
    try:
        result = run(["sudo", "-n", PROGRAMME, "lancer"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateError(f"lancement impossible ({exc.__class__.__name__})") from exc
    if result.returncode == 3:
        raise UpdateError("une mise à jour est déjà en cours")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        raise UpdateError("lancement refusé" + (f" : {detail[-1]}" if detail else "")
                          + " (refaire une fois sudo bash install.sh)")
    return os.path.basename(backup)
