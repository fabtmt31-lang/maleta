# Composants tiers du centre de jòcs

Recuperes par `packaging/fetch_emulatorjs.sh` (EmulatorJS 4.2.3, paquets npm
`@emulatorjs/emulatorjs`, `@emulatorjs/core-fceumm`, `@emulatorjs/core-genesis_plus_gx`,
`@emulatorjs/core-snes9x`, `@emulatorjs/core-stella2014`), non modifies -- `data/emulator.min.js` est
la simple concatenation des scripts de `data/src/` du paquet (ordre de `loader.js`).

| Composant | Licence | Sources |
|---|---|---|
| EmulatorJS | GPL-3.0 (`LICENSE-EmulatorJS.txt`) | https://github.com/EmulatorJS/EmulatorJS |
| FCEUmm (NES) | GPL-2.0 | https://github.com/EmulatorJS/libretro-fceumm |
| Genesis Plus GX (Mega Drive) | licence non commerciale (usage scolaire OK) | https://github.com/EmulatorJS/Genesis-Plus-GX |
| Snes9x (Super NES) | licence non commerciale (usage scolaire OK) | https://github.com/EmulatorJS/snes9x |
| Stella 2014 (Atari 2600) | GPL-2.0 | https://github.com/EmulatorJS/stella2014-libretro |

Detail de chaque moteur (licence, options) : `data/cores/reports/*.json`.
Aucun jeu n'est fourni : les fichiers de jeux sont ajoutes par l'ecole depuis l'admin.
