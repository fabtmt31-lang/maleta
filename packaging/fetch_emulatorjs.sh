#!/usr/bin/env bash
#
# Recupere EmulatorJS (version figee) et ses moteurs NES / Mega Drive dans
# maleta-occitana/static/vendor/emulatorjs/ -- servis en local par la borne,
# qui fonctionne sans reseau (v1.3, centre de jòcs).
#
#   bash packaging/fetch_emulatorjs.sh
#
# Necessite npm (paquets publies sur le registre npm par le projet
# EmulatorJS). Le resultat est versionne dans le depot : ce script ne sert
# qu'a le mettre a jour (changer EJS_VERSION).
#
# Licences : EmulatorJS GPL-3.0 ; moteurs FCEUmm (GPL-2.0) et Genesis Plus GX
# (licence non commerciale) -- voir LICENSES.md dans le dossier produit.

set -euo pipefail

EJS_VERSION="4.2.3"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${ROOT}/maleta-occitana/static/vendor/emulatorjs"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

cd "${WORK}"
npm pack --silent "@emulatorjs/emulatorjs@${EJS_VERSION}" \
    "@emulatorjs/core-fceumm@${EJS_VERSION}" \
    "@emulatorjs/core-genesis_plus_gx@${EJS_VERSION}" > /dev/null
for pkg in *.tgz; do mkdir -p "x/${pkg%.tgz}"; tar -xzf "${pkg}" -C "x/${pkg%.tgz}"; done
EJS="x/emulatorjs-emulatorjs-${EJS_VERSION}/package"

rm -rf "${DEST}"
mkdir -p "${DEST}/data/src" "${DEST}/data/compression" "${DEST}/data/cores/reports"
cp "${EJS}/data/loader.js" "${EJS}/data/emulator.css" "${EJS}/data/version.json" "${DEST}/data/"
cp "${EJS}"/data/src/*.js "${DEST}/data/src/"
# Jeux non compresses seulement (.nes, .md...) : pas besoin de l'extracteur RAR.
cp "${EJS}/data/compression/extract7z.js" "${EJS}/data/compression/extractzip.js" "${DEST}/data/compression/"
cp "${EJS}/LICENSE" "${DEST}/LICENSE-EmulatorJS.txt"
for core in fceumm genesis_plus_gx; do
    CORE="x/emulatorjs-core-${core}-${EJS_VERSION}/package"
    # Version standard et version "legacy" (sans WebGL2) : EmulatorJS choisit
    # selon la carte graphique. Pas de version "thread" (en-tetes HTTP speciaux).
    cp "${CORE}/${core}-wasm.data" "${CORE}/${core}-legacy-wasm.data" "${DEST}/data/cores/"
    cp "${CORE}/reports/${core}.json" "${DEST}/data/cores/reports/"
done

cat > "${DEST}/LICENSES.md" <<LIC
# Composants tiers du centre de jòcs

Recuperes par \`packaging/fetch_emulatorjs.sh\` (EmulatorJS ${EJS_VERSION}, paquets npm
\`@emulatorjs/emulatorjs\`, \`@emulatorjs/core-fceumm\`, \`@emulatorjs/core-genesis_plus_gx\`),
non modifies.

| Composant | Licence | Sources |
|---|---|---|
| EmulatorJS | GPL-3.0 (\`LICENSE-EmulatorJS.txt\`) | https://github.com/EmulatorJS/EmulatorJS |
| FCEUmm (NES) | GPL-2.0 | https://github.com/EmulatorJS/libretro-fceumm |
| Genesis Plus GX (Mega Drive) | licence non commerciale (usage scolaire OK) | https://github.com/EmulatorJS/Genesis-Plus-GX |

Detail de chaque moteur (licence, options) : \`data/cores/reports/*.json\`.
Aucun jeu n'est fourni : les fichiers de jeux sont ajoutes par l'ecole depuis l'admin.
LIC

du -sh "${DEST}"
