# -*- mode: python ; coding: utf-8 -*-
# PyInstaller : executable Windows de la version de demonstration.
#   pyinstaller --noconfirm packaging/maleta-demo.spec   (depuis la racine du depot)
# -> dist/MaletaOccitana-Demo.exe (un seul fichier, rien a installer)
import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
APP = os.path.join(ROOT, "maleta-occitana")
# Modules de l'appli : livres en fichiers source dans maleta-occitana/ (et non
# dans l'archive PyInstaller), pour que Flask retrouve templates/ et static/
# a cote d'eux et config.py le schema SQL -- maleta_desktop.py ajoute ce
# dossier au sys.path au demarrage.
APP_PACKAGES = ("app", "config", "managers", "blueprints", "db", "run_dev", "run_pc")


def app_datas():
    out = []
    for folder, dirs, files in os.walk(APP):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "media", "docs")]
        for name in files:
            if name.endswith((".pyc", ".db")) or name == "install.sh":
                continue
            out.append((os.path.join(folder, name), os.path.relpath(folder, ROOT)))
    return out


a = Analysis(
    [os.path.join(ROOT, "desktop", "maleta_desktop.py")],
    # pathex + hiddenimports : seulement pour que PyInstaller trouve les
    # dependances de l'appli (Flask, Flask-SocketIO...) qu'elle importe.
    pathex=[APP],
    datas=app_datas() + [(os.path.join(ROOT, "desktop", "assets"), "assets")],
    hiddenimports=(
        ["app", "blueprints.admin", "blueprints.kiosk", "simple_websocket"]
        + collect_submodules("engineio.async_drivers")
    ),
    excludes=["pygame", "smartcard", "vlc", "tkinter", "PIL"],
    noarchive=False,
)
a.pure = [m for m in a.pure if m[0].split(".")[0] not in APP_PACKAGES]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MaletaOccitana-Demo",
    icon=os.path.join(ROOT, "desktop", "assets", "maleta-occitana.ico"),
    console=False,
    upx=False,
)
