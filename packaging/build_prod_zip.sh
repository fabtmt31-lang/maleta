#!/usr/bin/env bash
#
# Construit l'archive de la VERSION STANDARD (la borne : petit PC Debian),
# au meme format que les archives livrees jusqu'ici :
#
#   bash packaging/build_prod_zip.sh   -> dist/maleta-occitana-v<version>.zip
#
# Le zip contient un dossier maleta-occitana/ a sa racine. Installation et
# mise a jour sur la borne, inchangees :
#   unzip maleta-occitana-v<version>.zip -d ~
#   cd ~/maleta-occitana && sudo bash install.sh
# Jamais de base de donnees ni de medias dedans (seulement les dossiers vides).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' "${ROOT}/maleta-occitana/config.py")"
BUILD="${ROOT}/build/prod"
OUT="${ROOT}/dist/maleta-occitana-v${VERSION}.zip"

rm -rf "${BUILD}"
mkdir -p "${BUILD}" "${ROOT}/dist"
tar -C "${ROOT}" \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='maleta.db' --exclude='.secret_key' --exclude='sauvegardes' \
    -cf - maleta-occitana | tar -C "${BUILD}" -xf -
# Medias : seulement la structure de dossiers (.gitkeep), comme dans git.
find "${BUILD}/maleta-occitana/media" -type f ! -name '.gitkeep' -delete
chmod +x "${BUILD}/maleta-occitana/install.sh" "${BUILD}/maleta-occitana/run_pc.py"

rm -f "${OUT}"
(cd "${BUILD}" && python3 -c "
import os, sys, zipfile
with zipfile.ZipFile(sys.argv[1], 'w', zipfile.ZIP_DEFLATED) as zf:
    for folder, dirs, files in os.walk('maleta-occitana'):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(folder, name)
            info = zipfile.ZipInfo.from_file(path)
            with open(path, 'rb') as f:
                zf.writestr(info, f.read(), zipfile.ZIP_DEFLATED)
" "${OUT}")
echo "== Archive borne : ${OUT} =="
