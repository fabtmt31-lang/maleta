#!/usr/bin/env bash
#
# Construit le paquet .deb de la version de demonstration (Debian 12+ /
# Ubuntu 22.04+, amd64 comme arm64 : tout est en Python pur).
#
#   bash packaging/build_deb.sh            -> dist/maleta-occitana-demo_<version>_all.deb
#
# Le paquet installe :
#   /opt/maleta-occitana-demo/      code de l'appli + lanceur + dependances Python
#   /usr/bin/maleta-occitana-demo   commande de lancement
#   menu des applications           "La Maleta Occitana (démo)"
# La fenetre utilise WebKitGTK du systeme (dependances apt ci-dessous), les
# dependances Python (Flask, Flask-SocketIO, pywebview...) sont embarquees.
# Necessite : python3 + pip, dpkg-deb.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
VERSION="$("${PYTHON}" -c "import re,sys;print(re.search(r'APP_VERSION = \"([^\"]+)\"', open(sys.argv[1], encoding='utf-8').read()).group(1))" "${ROOT}/maleta-occitana/config.py")"
DEB_VERSION="${DEB_VERSION:-${VERSION}}"
PKG="maleta-occitana-demo"
BUILD="${ROOT}/build/deb"
STAGE="${BUILD}/${PKG}"
OPT="${STAGE}/opt/${PKG}"

rm -rf "${BUILD}"
mkdir -p "${OPT}" "${STAGE}/DEBIAN" "${STAGE}/usr/bin" \
         "${STAGE}/usr/share/applications" \
         "${STAGE}/usr/share/icons/hicolor/256x256/apps" \
         "${STAGE}/usr/share/icons/hicolor/scalable/apps" \
         "${STAGE}/usr/share/doc/${PKG}"

echo "== Code de l'appli =="
# Jamais de base ni de medias de developpement dans le paquet : les donnees
# vivent dans ~/.local/share/maleta-occitana-demo.
tar -C "${ROOT}" \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='maleta.db' \
    --exclude='maleta-occitana/media/*/*' --exclude='maleta-occitana/media/*/*/*' \
    -cf - maleta-occitana desktop | tar -C "${OPT}" -xf -
rm -f "${OPT}/desktop/assets/maleta-occitana.ico"

echo "== Dependances Python embarquees =="
"${PYTHON}" -m pip install --quiet --no-compile --target "${OPT}/lib" -r "${ROOT}/desktop/requirements.txt"
rm -rf "${OPT}/lib/bin"
# MarkupSafe embarque une acceleration en C optionnelle (repli automatique en
# Python pur) : on la retire pour que le paquet marche avec n'importe quelle
# version de Python 3 du systeme.
find "${OPT}/lib" -name '*.so' -delete
find "${OPT}/lib" -name '__pycache__' -prune -exec rm -rf {} +
if find "${OPT}/lib" -name '*.so*' -o -name '*.pyd' | grep -q .; then
    echo "!! module compile inattendu dans lib/" >&2
    exit 1
fi

echo "== Lanceur, menu, icones =="
cat > "${STAGE}/usr/bin/${PKG}" <<LAUNCH
#!/bin/sh
# La Maleta Occitana - version de demonstration
exec /usr/bin/python3 /opt/${PKG}/desktop/maleta_desktop.py "\$@"
LAUNCH
chmod 755 "${STAGE}/usr/bin/${PKG}"

cat > "${STAGE}/usr/share/applications/${PKG}.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=La Maleta Occitana (démo)
Comment=Borne ludique pour découvrir l'occitan — version de démonstration
Exec=${PKG}
Icon=${PKG}
Terminal=false
Categories=Education;Game;
StartupWMClass=${PKG}
DESK

cp "${ROOT}/desktop/assets/maleta-occitana.png" "${STAGE}/usr/share/icons/hicolor/256x256/apps/${PKG}.png"
cp "${ROOT}/desktop/assets/maleta-occitana.svg" "${STAGE}/usr/share/icons/hicolor/scalable/apps/${PKG}.svg"
cp "${ROOT}/README.md" "${STAGE}/usr/share/doc/${PKG}/README.md"

INSTALLED_KB="$(du -sk "${STAGE}" | cut -f1)"
cat > "${STAGE}/DEBIAN/control" <<CTRL
Package: ${PKG}
Version: ${DEB_VERSION}
Section: education
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0
Installed-Size: ${INSTALLED_KB}
Maintainer: La Maleta Occitana <fab.tmt31@gmail.com>
Description: La Maleta Occitana - version de demonstration
 Borne interactive pour faire decouvrir l'occitan (jeux, objets, quiz),
 en version de demonstration pour un PC de bureau : une simple fenetre,
 pilotee au clavier et a la souris, sans lecteur NFC ni manette.
 Le contenu saisi peut etre exporte pour la version standard (borne).
CTRL

cat > "${STAGE}/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then update-desktop-database -q || true; fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then gtk-update-icon-cache -q /usr/share/icons/hicolor || true; fi
POST
chmod 755 "${STAGE}/DEBIAN/postinst"

find "${STAGE}" -type d -exec chmod 755 {} +
find "${OPT}" -type f -exec chmod 644 {} +

mkdir -p "${ROOT}/dist"
OUT="${ROOT}/dist/${PKG}_${DEB_VERSION}_all.deb"
dpkg-deb --root-owner-group --build "${STAGE}" "${OUT}"
echo "== Paquet : ${OUT} =="
