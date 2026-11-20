#!/usr/bin/python3
"""Mise a jour de la borne depuis GitHub (v1.37).

Installe par install.sh dans /usr/local/sbin/maleta-maj (root, 0755).
L'appli (utilisateur "maleta") a le droit de lancer UNIQUEMENT
`sudo /usr/local/sbin/maleta-maj lancer` (regle /etc/sudoers.d/maleta-maj) :

  lancer      demarre la mise a jour en arriere-plan (systemd-run), pour
              qu'elle survive au redemarrage du service de l'appli.
  appliquer   (lance par "lancer") : telecharge la derniere archive de la
              borne publiee sur GitHub, la verifie, puis rejoue son
              install.sh -- exactement comme une mise a jour a la main.

Securite : l'adresse du depot est ecrite ici (ou dans /etc/default/maleta-maj,
modifiable par root seulement) ; l'appli ne peut ni choisir l'archive, ni lui
passer de fichier. L'archive doit avoir l'empreinte SHA-256 annoncee par
GitHub, ne contenir que le dossier maleta-occitana/, et son install.sh.
Si install.sh echoue, l'ancienne version est reinstallee.

Etat lisible par l'appli : /var/lib/maleta-maj/etat.json ; journal :
/var/log/maleta-maj.log. Uniquement la bibliotheque standard de Python.
"""

import datetime
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

DEPOT = "fabtmt31-lang/maleta"
ETIQUETTE = "demo-latest"
CONF = "/etc/default/maleta-maj"
DOSSIER_ETAT = "/var/lib/maleta-maj"
JOURNAL = "/var/log/maleta-maj.log"
DOSSIER_APPLI = "/opt/maleta-occitana"
ARCHIVE_RE = re.compile(r"^maleta-occitana-v(\d+(?:\.\d+)*)\.zip$")
TAILLE_MAX = 300 * 1024 * 1024
DELAI = 60
EXCLUS_COPIE = (".venv", "maleta.db", "media", ".secret_key", "sauvegardes", "__pycache__")


def lire_conf():
    """MAJ_DEPOT=proprietaire/depot, MAJ_ETIQUETTE=tag (fichier root)."""
    conf = {"depot": DEPOT, "etiquette": ETIQUETTE}
    try:
        with open(CONF, encoding="utf-8") as f:
            for ligne in f:
                cle, _, valeur = ligne.strip().partition("=")
                valeur = valeur.strip().strip('"')
                if cle == "MAJ_DEPOT" and re.fullmatch(r"[\w.-]+/[\w.-]+", valeur):
                    conf["depot"] = valeur
                elif cle == "MAJ_ETIQUETTE" and re.fullmatch(r"[\w.-]+", valeur):
                    conf["etiquette"] = valeur
    except OSError:
        pass
    return conf


def journal(message):
    ligne = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {message}"
    print(ligne, flush=True)
    try:
        if os.path.exists(JOURNAL) and os.path.getsize(JOURNAL) > 1024 * 1024:
            os.replace(JOURNAL, JOURNAL + ".1")
        with open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(ligne + "\n")
        os.chmod(JOURNAL, 0o644)
    except OSError:
        pass


def ecrire_etat(**champs):
    os.makedirs(DOSSIER_ETAT, exist_ok=True)
    os.chmod(DOSSIER_ETAT, 0o755)
    etat = lire_etat()
    etat.update(champs, maj=datetime.datetime.now().isoformat(timespec="seconds"))
    tmp = os.path.join(DOSSIER_ETAT, "etat.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False)
    os.chmod(tmp, 0o644)
    os.replace(tmp, os.path.join(DOSSIER_ETAT, "etat.json"))


def lire_etat():
    try:
        with open(os.path.join(DOSSIER_ETAT, "etat.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def http(url, accept="application/json"):
    requete = urllib.request.Request(url, headers={"User-Agent": "maleta-maj", "Accept": accept})
    return urllib.request.urlopen(requete, timeout=DELAI)


def chercher_archive(conf):
    url = f"https://api.github.com/repos/{conf['depot']}/releases/tags/{conf['etiquette']}"
    with http(url) as reponse:
        publication = json.load(reponse)
    for fichier in publication.get("assets", []):
        trouve = ARCHIVE_RE.match(fichier.get("name", ""))
        if trouve:
            digest = fichier.get("digest") or ""
            return {
                "version": trouve.group(1),
                "nom": fichier["name"],
                "url": fichier["browser_download_url"],
                "taille": fichier.get("size") or 0,
                "sha256": digest[7:] if digest.startswith("sha256:") else None,
            }
    raise RuntimeError("aucune archive de la borne dans la publication GitHub")


def telecharger(archive, chemin):
    if archive["taille"] > TAILLE_MAX:
        raise RuntimeError("archive trop volumineuse")
    empreinte = hashlib.sha256()
    total = 0
    with http(archive["url"], accept="application/octet-stream") as reponse, open(chemin, "wb") as f:
        while True:
            bloc = reponse.read(1024 * 1024)
            if not bloc:
                break
            total += len(bloc)
            if total > TAILLE_MAX:
                raise RuntimeError("archive trop volumineuse")
            empreinte.update(bloc)
            f.write(bloc)
    if archive["sha256"] and empreinte.hexdigest() != archive["sha256"]:
        raise RuntimeError("empreinte SHA-256 differente de celle annoncee par GitHub (telechargement abime ?)")
    return empreinte.hexdigest()


def extraire(chemin, destination):
    """Verifie puis decompresse l'archive. Renvoie le dossier maleta-occitana/."""
    with zipfile.ZipFile(chemin) as z:
        if z.testzip() is not None:
            raise RuntimeError("archive abimee")
        for nom in z.namelist():
            if not nom.startswith("maleta-occitana/") or ".." in nom.split("/") or nom.startswith("/"):
                raise RuntimeError(f"contenu inattendu dans l'archive : {nom}")
        noms = set(z.namelist())
        for requis in ("maleta-occitana/install.sh", "maleta-occitana/config.py", "maleta-occitana/requirements.txt"):
            if requis not in noms:
                raise RuntimeError(f"archive incomplete ({requis} absent)")
        shutil.rmtree(destination, ignore_errors=True)
        z.extractall(destination)
    return os.path.join(destination, "maleta-occitana")


def version_installee():
    try:
        with open(os.path.join(DOSSIER_APPLI, "config.py"), encoding="utf-8") as f:
            trouve = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', f.read())
            return trouve.group(1) if trouve else None
    except OSError:
        return None


def executer(commande):
    """Lance une commande, sa sortie va dans le journal. Renvoie le code retour."""
    env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
    with open(JOURNAL, "a", encoding="utf-8") as sortie:
        processus = subprocess.run(commande, stdout=sortie, stderr=subprocess.STDOUT, env=env, timeout=3600)
    return processus.returncode


def appliquer():
    os.makedirs(DOSSIER_ETAT, exist_ok=True)
    verrou = open(os.path.join(DOSSIER_ETAT, "verrou"), "w")
    try:
        fcntl.flock(verrou, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        journal("Une mise a jour est deja en cours.")
        return 3
    conf = lire_conf()
    avant = version_installee()
    ecrire_etat(etat="recherche", message="Recherche de la dernière version sur GitHub…", depuis=avant,
                debut=datetime.datetime.now().isoformat(timespec="seconds"), version=None, erreur=None)
    journal(f"== Mise a jour depuis {conf['depot']} ({conf['etiquette']}), version installee : {avant}")
    precedente = os.path.join(DOSSIER_ETAT, "precedente")
    installation_commencee = False
    try:
        archive = chercher_archive(conf)
        journal(f"Archive : {archive['nom']} ({archive['taille']} octets)")
        ecrire_etat(etat="telechargement", message=f"Téléchargement de la version {archive['version']}…",
                    version=archive["version"])
        chemin = os.path.join(DOSSIER_ETAT, "archive.zip")
        empreinte = telecharger(archive, chemin)
        journal(f"SHA-256 : {empreinte}" + ("" if archive["sha256"] else " (pas d'empreinte publiee par GitHub)"))
        ecrire_etat(etat="verification", message="Vérification de l'archive…")
        source = extraire(chemin, os.path.join(DOSSIER_ETAT, "nouvelle"))

        # Copie du code actuel : retour arriere si install.sh echoue.
        if os.path.isdir(DOSSIER_APPLI):
            commande = ["rsync", "-a", "--delete"]
            for exclu in EXCLUS_COPIE:
                commande += ["--exclude", exclu]
            if executer(commande + [DOSSIER_APPLI + "/", precedente + "/"]) != 0:
                raise RuntimeError("copie de sauvegarde du code impossible")

        ecrire_etat(etat="installation", message=f"Installation de la version {archive['version']} "
                    "(paquets, code, redémarrage de l'appli : quelques minutes)…")
        installation_commencee = True
        code = executer(["bash", os.path.join(source, "install.sh")])
        if code != 0:
            raise RuntimeError(f"install.sh a echoue (code {code}), voir {JOURNAL}")
        ecrire_etat(etat="termine", message=f"Version {version_installee()} installée.", erreur=None)
        journal(f"== Mise a jour terminee : {avant} -> {version_installee()}")
        return 0
    except Exception as exc:  # noqa: BLE001 -- tout echec est rapporte a l'admin
        message = str(exc) or exc.__class__.__name__
        journal(f"!! Echec : {message}")
        retour = ""
        if installation_commencee and os.path.isfile(os.path.join(precedente, "install.sh")):
            journal("Reinstallation de la version precedente…")
            ecrire_etat(etat="retour", message="Échec : réinstallation de la version précédente…")
            if executer(["bash", os.path.join(precedente, "install.sh")]) == 0:
                retour = " L'ancienne version a été réinstallée."
            else:
                retour = " La réinstallation de l'ancienne version a aussi échoué : voir le journal."
        ecrire_etat(etat="erreur", message="La mise à jour a échoué." + retour, erreur=message)
        return 1


def lancer():
    """Detache la mise a jour du service de l'appli (que install.sh redemarre)."""
    if lire_etat().get("etat") in ("recherche", "telechargement", "verification", "installation", "retour"):
        try:
            verrou = open(os.path.join(DOSSIER_ETAT, "verrou"), "w")
            fcntl.flock(verrou, fcntl.LOCK_EX | fcntl.LOCK_NB)
            verrou.close()
        except OSError:
            print("deja en cours")
            return 3
    ecrire_etat(etat="lancee", message="Mise à jour lancée…", erreur=None)
    unite = "maleta-maj-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    return subprocess.run(["systemd-run", "--unit", unite, "--collect", "--quiet",
                           os.path.abspath(sys.argv[0]), "appliquer"]).returncode


def main():
    if os.geteuid() != 0:
        print("A lancer en root (sudo).", file=sys.stderr)
        return 2
    commande = sys.argv[1] if len(sys.argv) > 1 else ""
    if commande == "lancer":
        return lancer()
    if commande == "appliquer":
        return appliquer()
    print("Usage : maleta-maj lancer|appliquer", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
