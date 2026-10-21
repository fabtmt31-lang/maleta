# La Maleta Occitana

Borne ludique pour faire découvrir l'occitan et les écoles Calandreta
(objets NFC, jeux, quiz, diaporama). Ce dépôt contient :

| Dossier | Contenu |
|---|---|
| `maleta-occitana/` | L'application elle-même — **version standard** pour la borne (petit PC Debian + lecteur NFC + manette), installée par `install.sh`. Détails, historique des versions : [`maleta-occitana/README.md`](maleta-occitana/README.md). |
| `desktop/` | Le lanceur de la **version démo** : la même application dans une simple fenêtre, sur n'importe quel PC Windows ou Linux. |
| `packaging/` | Construction de l'exécutable Windows (PyInstaller) et du paquet `.deb` Linux. |
| `.github/workflows/` | Construction automatique des deux, publiés dans les **Releases** du dépôt. |
| `tests/` | Tests automatiques de l'export / import du contenu. |

## Version démo

Télécharger depuis la page **Releases** du dépôt (pré-release
« demo-latest », mise à jour à chaque modification, ou une version
numérotée) :

- **Windows 10/11** : `MaletaOccitana-Demo.exe` — double-cliquer, rien à
  installer. (Windows SmartScreen peut avertir d'un éditeur inconnu :
  « Informations complémentaires » > « Exécuter quand même ».)
- **Debian 12+ / Ubuntu 22.04+** : `maleta-occitana-demo_<version>_all.deb`
  ```bash
  sudo apt install ./maleta-occitana-demo_*_all.deb
  maleta-occitana-demo        # ou « La Maleta Occitana (démo) » dans le menu
  ```

Différences avec la borne :

- **Une simple fenêtre** (plein écran avec F11, menu « Maleta » pour
  l'administration, l'export et le dossier des données).
- **Clavier au lieu de la manette**, assigné d'office : flèches, Entrée
  (valider), Échap (retour), 1 / 2 / 3 (réponses), S / D et K / L (Duèl,
  joueurs 1 et 2), P (diaporama). Modifiable dans Configuration.
- **Pas de lecteur NFC** : le bouton « NFC · F2 » en bas à gauche du kiosque
  ouvre la liste des objets ; cliquer sur un objet revient à le poser sur le
  lecteur (Descobèrta, Tròba l'objècte).
- Administration : Ctrl+Alt+A ou l'icône engrenage, **code 1234** (rappelé
  sur l'écran de connexion tant qu'il n'est pas changé).
- Les données (base + médias) sont rangées dans le dossier utilisateur :
  `%APPDATA%\MaletaOccitanaDemo` sous Windows,
  `~/.local/share/maleta-occitana-demo` sous Linux. Désinstaller ou mettre à
  jour la démo ne les efface pas.

## Récupérer le contenu saisi pour la borne (export / import)

Tout ce qui a été saisi à la main — objets (avec images et sons), mots de
« Ven de l'occitan ? », questions du Duèl et du Quiz, vilatges, photos et
vidéos du diaporama, textes et apparence de la borne — s'extrait en un seul
fichier :

1. Dans la démo : **Admin > Exportar / Importar > Telecargar l'export** →
   un fichier `maleta-demo-contenu-AAAAMMJJ-HHMM.zip`.
2. Sur la borne (version standard 1.2 ou plus) : **Admin > Exportar /
   Importar > Importar**, choisir ce .zip tel quel.
   - « Ajouter » garde le contenu déjà présent et ignore les doublons ;
     « Remplacer » efface d'abord les sections cochées.
   - Les objets venant de la démo n'ont pas de tag NFC : les associer depuis
     la fiche de chaque objet (« Associer un nouveau tag »).

Le .zip contient aussi un dossier `tableur/` : le même contenu en fichiers
CSV, lisibles dans Excel / LibreOffice, pour relire les questions et leurs
sources. Ne sont jamais exportés : le code PIN, les réglages manette/clavier
(propres à chaque machine) et les tags NFC simulés de la démo.

L'export marche aussi dans l'autre sens (borne → démo), et sert de
sauvegarde du contenu de la borne.

## Développement

```bash
pip install -r desktop/requirements.txt
python desktop/maleta_desktop.py          # démo dans une fenêtre
python -m pytest tests                     # tests
```

Construire les paquets à la main :

```bash
bash packaging/build_deb.sh                         # -> dist/*.deb (sous Linux)
pyinstaller --noconfirm packaging/maleta-demo.spec  # -> dist/MaletaOccitana-Demo.exe (sous Windows)
```

Sous Linux, la fenêtre utilise WebKitGTK (`python3-gi`,
`gir1.2-webkit2-4.1`, installés automatiquement avec le `.deb`) ; sans
eux, la démo s'ouvre dans le navigateur par défaut.
