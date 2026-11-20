"""Mise a jour depuis GitHub (v1.37) : page admin, appli, programme root."""

import importlib.util
import io
import json
import os
import subprocess
import sys
import zipfile

import pytest

from test_content_transfer import make_client

ROOT = os.path.join(os.path.dirname(__file__), "..")
RELEASE = {
    "published_at": "2026-11-20T14:07:16Z", "target_commitish": "21de665b81a7",
    "assets": [
        {"name": "MaletaOccitana-Demo.exe", "size": 1},
        {"name": "maleta-occitana-v9.9.zip", "size": 10 * 1024 * 1024},
    ],
}


def _client(tmp_path):
    app, client = make_client(tmp_path / "pc", demo=False)
    return app, client, sys.modules["managers.update_manager"]


def test_version_order(tmp_path):
    _, _, um = _client(tmp_path)
    assert um.version_key("1.4") > um.version_key("1.36") > um.version_key("1.3")
    assert um.version_key("1.31") > um.version_key("1.3") and um.version_key("x") == 0


def test_check_and_page(tmp_path, monkeypatch):
    app, client, um = _client(tmp_path)
    monkeypatch.setattr(um, "_fetch_release", lambda: RELEASE)
    monkeypatch.setattr(um.check, "__defaults__", (lambda: RELEASE,))
    page = client.get("/admin/maj").get_data(as_text=True)
    assert "Chercher une mise à jour" in page and "Mesa a jorn" in page
    assert "sudo bash install.sh" in page  # programme absent dans ce conteneur de test
    page = client.post("/admin/maj/verificar", follow_redirects=True).get_data(as_text=True)
    assert "v9.9" in page and "Une nouvelle version est disponible" in page and "Installer la v9.9" in page

    def offline():
        raise um.UpdateError("pas d'accès à Internet")
    monkeypatch.setattr(um.check, "__defaults__", (offline,))
    page = client.post("/admin/maj/verificar", follow_redirects=True).get_data(as_text=True)
    assert "Vérification impossible : pas d" in page and "Internet" in page
    assert client.get("/version").get_json() == {"version": sys.modules["config"].APP_VERSION}


def test_launch(tmp_path, monkeypatch):
    app, client, um = _client(tmp_path)
    # Programme absent : refus clair, rien de lance
    page = client.post("/admin/maj/installar", follow_redirects=True).get_data(as_text=True)
    assert "programme de mise à jour absent" in page

    fake = tmp_path / "maleta-maj"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setattr(um, "PROGRAMME", str(fake))
    monkeypatch.setattr(um, "FICHIER_ETAT", str(tmp_path / "etat.json"))
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(um.launch, "__defaults__", (run,))
    page = client.post("/admin/maj/installar", follow_redirects=True).get_data(as_text=True)
    assert calls == [["sudo", "-n", str(fake), "lancer"]]
    assert "Mise à jour lancée (contenu sauvegardé : maleta-sauvegarde-" in page
    assert any(n.startswith("maleta-sauvegarde-") for n in os.listdir(tmp_path / "pc" / "sauvegardes"))

    # Etat "en cours" : pas de second lancement ; la page suit l'avancement
    (tmp_path / "etat.json").write_text(json.dumps({"etat": "installation", "message": "Installation…"}))
    page = client.post("/admin/maj/installar", follow_redirects=True).get_data(as_text=True)
    assert "déjà en cours" in page and len(calls) == 1 and "Redémarrage de l'appli" in page
    assert client.get("/admin/maj/estat").get_json()["state"]["running"] is True

    # sudo refuse (regle absente) : message clair
    (tmp_path / "etat.json").write_text(json.dumps({"etat": "termine", "message": "ok"}))
    monkeypatch.setattr(um.launch, "__defaults__", (lambda cmd, **k: subprocess.CompletedProcess(
        cmd, 1, "", "sudo: a password is required"),))
    page = client.post("/admin/maj/installar", follow_redirects=True).get_data(as_text=True)
    assert "lancement refusé : sudo: a password is required" in page


def test_demo_has_no_update(tmp_path):
    _, client = make_client(tmp_path / "demo", demo=True)
    assert client.get("/admin/maj").status_code == 302
    assert "Mesa a jorn" not in client.get("/admin/jocs").get_data(as_text=True)


# --- Programme root (maj/maleta-maj.py), sans reseau ni installation ---------------

def _maj_module():
    spec = importlib.util.spec_from_file_location("maleta_maj", os.path.join(ROOT, "maleta-occitana", "maj", "maleta-maj.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _zip(path, names):
    with zipfile.ZipFile(path, "w") as z:
        for name in names:
            z.writestr(name, 'APP_VERSION = "9.9"\n' if name.endswith("config.py") else "x")


def test_archive_checks(tmp_path):
    m = _maj_module()
    good = ["maleta-occitana/install.sh", "maleta-occitana/config.py", "maleta-occitana/requirements.txt"]
    _zip(tmp_path / "ok.zip", good)
    assert m.extraire(str(tmp_path / "ok.zip"), str(tmp_path / "x")).endswith("maleta-occitana")
    for bad, message in ((good + ["../evil.sh"], "contenu inattendu"), (good + ["autre/fichier"], "contenu inattendu"),
                         (good[1:], "incomplete")):
        _zip(tmp_path / "bad.zip", bad)
        with pytest.raises(RuntimeError, match=message):
            m.extraire(str(tmp_path / "bad.zip"), str(tmp_path / "y"))
    assert m.ARCHIVE_RE.match("maleta-occitana-v1.37.zip").group(1) == "1.37"
    assert not m.ARCHIVE_RE.match("maleta-occitana-demo_1.37_all.deb")


def test_download_checks_sha256(tmp_path, monkeypatch):
    m = _maj_module()
    payload = b"contenu"

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(m, "http", lambda url, accept=None: Response(payload))
    import hashlib
    good = {"url": "u", "taille": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    assert m.telecharger(good, str(tmp_path / "a.zip")) == good["sha256"]
    with pytest.raises(RuntimeError, match="SHA-256"):
        m.telecharger(dict(good, sha256="0" * 64), str(tmp_path / "b.zip"))


def test_install_script_sets_up_updater():
    script = open(os.path.join(ROOT, "maleta-occitana", "install.sh"), encoding="utf-8").read()
    assert "/usr/local/sbin/maleta-maj lancer" in script and "visudo -cf" in script
    assert 'install -m 0755 -o root -g root "${SOURCE_DIR}/maj/maleta-maj.py" /usr/local/sbin/maleta-maj' in script
