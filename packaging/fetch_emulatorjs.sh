#!/usr/bin/env bash
#
# Recupere EmulatorJS (version figee) et ses moteurs NES / Mega Drive /
# Super NES / Atari 2600 dans
# maleta-occitana/static/vendor/emulatorjs/ -- servis en local par la borne,
# qui fonctionne sans reseau (v1.3, centre de jòcs).
#
#   bash packaging/fetch_emulatorjs.sh
#
# Necessite npm (paquets publies sur le registre npm par le projet
# EmulatorJS). Le resultat est versionne dans le depot : ce script ne sert
# qu'a le mettre a jour (changer EJS_VERSION).
#
# Licences : EmulatorJS GPL-3.0 ; moteurs FCEUmm (GPL-2.0), Genesis Plus GX
# et Snes9x (licences non commerciales), Stella 2014 (GPL-2.0) -- voir
# LICENSES.md dans le dossier produit.
#
# v1.33 : npm ne publie que les scripts NON minifies d'EmulatorJS, qu'il
# fallait charger en mode "debug" -- or ce mode rend l'emulateur verbeux
# (option -v, un message console a chaque evenement) et le jeu ralentit au
# bout de quelques secondes (60 -> 45 images/s). Le script assemble donc
# lui-meme data/emulator.min.js (simple concatenation, dans l'ordre de
# loader.js) et data/emulator.min.css : la page de jeu n'utilise plus le
# mode debug.

set -euo pipefail

EJS_VERSION="4.2.3"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${ROOT}/maleta-occitana/static/vendor/emulatorjs"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

cd "${WORK}"
npm pack --silent "@emulatorjs/emulatorjs@${EJS_VERSION}" \
    "@emulatorjs/core-fceumm@${EJS_VERSION}" \
    "@emulatorjs/core-genesis_plus_gx@${EJS_VERSION}" \
    "@emulatorjs/core-snes9x@${EJS_VERSION}" \
    "@emulatorjs/core-stella2014@${EJS_VERSION}" > /dev/null
for pkg in *.tgz; do mkdir -p "x/${pkg%.tgz}"; tar -xzf "${pkg}" -C "x/${pkg%.tgz}"; done
EJS="x/emulatorjs-emulatorjs-${EJS_VERSION}/package"

rm -rf "${DEST}"
mkdir -p "${DEST}/data/compression" "${DEST}/data/cores/reports"
cp "${EJS}/data/loader.js" "${EJS}/data/version.json" "${DEST}/data/"
cp "${EJS}/data/emulator.css" "${DEST}/data/emulator.min.css"
# Meme ordre que la liste "scripts" de loader.js.
for js in emulator.js nipplejs.js shaders.js storage.js gamepad.js GameManager.js socket.io.min.js compression.js; do
    cat "${EJS}/data/src/${js}"
    printf '\n;\n'
done > "${DEST}/data/emulator.min.js"
# Jeux non compresses seulement (.nes, .md...) : pas besoin de l'extracteur RAR.
cp "${EJS}/data/compression/extract7z.js" "${EJS}/data/compression/extractzip.js" "${DEST}/data/compression/"
cp "${EJS}/LICENSE" "${DEST}/LICENSE-EmulatorJS.txt"
for core in fceumm genesis_plus_gx snes9x stella2014; do
    CORE="x/emulatorjs-core-${core}-${EJS_VERSION}/package"
    # Version standard et version "legacy" (sans WebGL2) : EmulatorJS choisit
    # selon la carte graphique. Pas de version "thread" (en-tetes HTTP speciaux).
    cp "${CORE}/${core}-wasm.data" "${CORE}/${core}-legacy-wasm.data" "${DEST}/data/cores/"
    cp "${CORE}/reports/${core}.json" "${DEST}/data/cores/reports/"
done

cat > "${DEST}/LICENSES.md" <<LIC
# Composants tiers du centre de jòcs

Recuperes par \`packaging/fetch_emulatorjs.sh\` (EmulatorJS ${EJS_VERSION}, paquets npm
\`@emulatorjs/emulatorjs\`, \`@emulatorjs/core-fceumm\`, \`@emulatorjs/core-genesis_plus_gx\`,
\`@emulatorjs/core-snes9x\`, \`@emulatorjs/core-stella2014\`), non modifies -- \`data/emulator.min.js\` est
la simple concatenation des scripts de \`data/src/\` du paquet (ordre de \`loader.js\`).

| Composant | Licence | Sources |
|---|---|---|
| EmulatorJS | GPL-3.0 (\`LICENSE-EmulatorJS.txt\`) | https://github.com/EmulatorJS/EmulatorJS |
| FCEUmm (NES) | GPL-2.0 | https://github.com/EmulatorJS/libretro-fceumm |
| Genesis Plus GX (Mega Drive) | licence non commerciale (usage scolaire OK) | https://github.com/EmulatorJS/Genesis-Plus-GX |
| Snes9x (Super NES) | licence non commerciale (usage scolaire OK) | https://github.com/EmulatorJS/snes9x |
| Stella 2014 (Atari 2600) | GPL-2.0 | https://github.com/EmulatorJS/stella2014-libretro |

Detail de chaque moteur (licence, options) : \`data/cores/reports/*.json\`.
Aucun jeu n'est fourni : les fichiers de jeux sont ajoutes par l'ecole depuis l'admin.
LIC

du -sh "${DEST}"
