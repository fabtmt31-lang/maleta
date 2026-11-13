# La Maleta Occitana

Borne ludique pour faire découvrir l'occitan et les écoles Calandreta
(objets NFC, jeux, quiz, diaporama). Ce dépôt contient :

| Dossier | Contenu |
|---|---|
| `maleta-occitana/` | L'application elle-même — **version standard** pour la borne (petit PC Debian + lecteur NFC + manette), installée par `install.sh`. Détails, historique des versions : [`maleta-occitana/README.md`](maleta-occitana/README.md). |
| `desktop/` | Le lanceur de la **version démo** : la même application dans une simple fenêtre, sur n'importe quel PC Windows ou Linux. |
| `packaging/` | Construction de l'exécutable Windows (PyInstaller), du paquet `.deb` Linux et de l'archive de la borne. |
| `.github/workflows/` | Construction et vérification automatiques des trois, publiés dans les **Releases** du dépôt. |
| `tests/` | Tests automatiques (export / import, clavier et souris de la démo). |
| `docs/` | [Guide import / export pour la borne](docs/import-contenu-version-prod.md) (+ patch pour une borne restée en v1.11) et [modèles CSV](docs/modeles-csv/) pour écrire le contenu dans un tableur. |

## Version borne (Debian)

L'archive `maleta-occitana-v<version>.zip` (page **Releases**) s'installe
et se met à jour exactement comme les précédentes, sans perdre le contenu
déjà saisi :

```bash
unzip -o maleta-occitana-v1.22.zip -d ~
cd ~/maleta-occitana
sudo bash install.sh
```

Depuis la v1.2 elle a, comme la démo, la page **Admin > Exportar /
Importar** (export, import d'un export de la démo) et, depuis la v1.21,
l'import de **fichiers CSV** (voir plus bas).

## Administrer la borne depuis un autre PC (tunnel SSH)

Plutôt que de configurer la borne et d'écrire les questions sur son propre
écran (sans souris, avec un clavier de fortune), on peut ouvrir
l'administration de la borne **dans le navigateur d'un PC portable**, avec
un vrai clavier, le copier-coller et les fichiers du PC (CSV, photos, sons).

Par sécurité, l'appli de la borne n'écoute que sur la borne elle-même
(`127.0.0.1:5000`) : elle est invisible depuis le réseau. Un **tunnel SSH**
fait passer la connexion par une session SSH chiffrée et protégée par mot
de passe : pour le navigateur du PC, la borne apparaît alors comme
`http://localhost:5000`.

### 1. Préparer la borne (une seule fois)

Sur la borne (`Ctrl+Alt+F2` pour une console si le kiosque occupe l'écran,
`Ctrl+Alt+F1` pour revenir) :

```bash
sudo apt install -y openssh-server   # serveur SSH (pas installé par install.sh)
hostname -I                          # adresse IP de la borne, ex. 192.168.1.42
```

Pour se connecter, utiliser le compte créé à l'installation de Debian (celui
qui lance `sudo bash install.sh`). La borne et le PC doivent être sur le
**même réseau** (même box, même wifi, ou un câble entre les deux).

Astuce : `sudo apt install -y avahi-daemon` sur la borne permet ensuite
d'utiliser son nom au lieu de son adresse IP, ex. `maleta.local` (nom
donné à l'installation de Debian, affiché par `hostname`).

### 2. Ouvrir le tunnel depuis le PC

**Windows 10/11, Linux, macOS** — dans un terminal (sous Windows :
PowerShell ou « Invite de commandes », le client SSH est déjà installé) :

```bash
ssh -N -L 5000:localhost:5000 utilisateur@192.168.1.42
```

- `utilisateur` : le compte Debian de la borne, `192.168.1.42` : son
  adresse (ou `maleta.local`).
- Taper le mot de passe de ce compte (rien ne s'affiche pendant la saisie,
  c'est normal). À la première connexion, répondre `yes` pour accepter la
  borne.
- Ensuite la commande **ne rend pas la main : c'est normal**, le tunnel est
  ouvert tant que cette fenêtre reste ouverte. `Ctrl+C` pour le fermer.
- Si le port 5000 est déjà pris sur le PC (cas fréquent sur Mac, ou démo
  lancée en développement) : `ssh -N -L 8080:localhost:5000 …` puis
  utiliser `http://localhost:8080` dans la suite.

**Avec PuTTY (Windows)** : *Session* → Host Name = adresse de la borne ;
*Connection > SSH > Tunnels* → Source port `5000`, Destination
`localhost:5000`, bouton **Add** ; revenir à *Session*, **Save** pour la
réutiliser, puis **Open** et se connecter.

### 3. Utiliser la borne depuis le PC

Tunnel ouvert, dans le navigateur du PC :

| Adresse | Pour |
|---|---|
| `http://localhost:5000/admin` | **Administration** (code PIN de la borne) : objets, questions, vilatges, diaporama, Configuration, Exportar / Importar |
| `http://localhost:5000/` | **Voir l'écran de la borne** en direct (miroir) |

- **Écrire les questions** : directement dans les formulaires de l'admin,
  ou dans un tableur sur le PC puis *Exportar / Importar > Importar* (CSV,
  voir plus bas). Les photos et les sons s'envoient depuis le PC dans la
  fiche de chaque objet ou dans *Fotos & vidèos*.
- **Sauvegarder** : *Exportar / Importar > Telecargar l'export*, le .zip est
  enregistré sur le PC.
- **Configurer** : modèle d'interface, textes, bannière, code PIN. Pour
  réassigner un bouton de manette, cliquer « Réassigner » sur le PC puis
  appuyer sur le bouton de la manette **branchée sur la borne**.
- Après un changement d'apparence, de textes ou de touches, l'écran de la
  borne doit être rechargé : `F5` sur un clavier branché à la borne, ou à
  distance, dans une session SSH ordinaire (`ssh utilisateur@…`, sans
  `-N`) : `sudo systemctl restart getty@tty1` (relance l'affichage du
  kiosque, la borne revient sur l'accueil en quelques secondes).
- Attention, le miroir (`/`) n'est pas qu'un affichage : les touches
  tapées dans cette page pilotent **la vraie borne** (même partie, même
  écran que les visiteurs).
- L'admin se déconnecte seule après 20 min sans activité.

### Sans tunnel (déconseillé)

On peut aussi rendre l'appli joignable directement depuis le réseau
(`http://192.168.1.42:5000/admin`, sans SSH) :

```bash
sudo systemctl edit maleta-occitana
#   ajouter :
#   [Service]
#   Environment=MALETA_HOST=0.0.0.0
sudo systemctl restart maleta-occitana
```

Le code PIN est alors la seule protection, et la connexion n'est pas
chiffrée : à réserver à un réseau privé de confiance (jamais le wifi public
d'un salon), et à retirer après usage (`sudo systemctl revert
maleta-occitana` puis `sudo systemctl restart maleta-occitana`). Ce réglage
survit aux mises à jour par `install.sh`.

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
- **Entièrement au clavier et à la souris, aucune manette à configurer** :
  chaque action a une touche par défaut.

  | Touche | Action |
  |---|---|
  | Flèches | se déplacer (menu, cartes Memòria) |
  | Entrée | valider / retourner une carte |
  | Échap | retour au menu |
  | 1 / 2 / 3 | réponses (Ven de l'occitan ?, Quiz) |
  | S / D | Duèl, joueur 1 : réponse A / B |
  | K / L | Duèl, joueur 2 : réponse A / B |
  | P | diaporama |
  | F2 | poser un objet (NFC simulé) |
  | F11 | plein écran |
  | Ctrl+Alt+A | administration |

  À la souris : clic sur une tuile, une carte ou une réponse pour la
  choisir ; clic sur un écran sans choix (accueil, diaporama, fin de partie)
  pour continuer ; **clic droit = retour au menu** ; au Duèl, le 1er clic
  répond pour le joueur 1, le 2e pour le joueur 2. Touches modifiables dans
  Configuration (bouton « Remettre les touches par défaut de la démo »).
- **Pas de lecteur NFC** : le bouton « NFC · F2 » en bas à gauche du kiosque
  ouvre la liste des objets ; cliquer sur un objet (ou flèches + Entrée)
  revient à le poser sur le lecteur (Descobèrta, Tròba l'objècte).
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
2. Sur la borne (version standard 1.22, voir ci-dessus) : **Admin > Exportar /
   Importar > Importar**, choisir ce .zip tel quel. Borne restée en v1.11 :
   voir [`docs/import-contenu-version-prod.md`](docs/import-contenu-version-prod.md)
   (2 fichiers à ajouter pour un import en ligne de commande, ou un patch
   pour la page d'admin).
   - « Ajouter » garde le contenu déjà présent et ignore les doublons ;
     « Remplacer » efface d'abord les sections cochées présentes dans le ou
     les fichiers, après une sauvegarde automatique.
   - Les objets venant de la démo n'ont pas de tag NFC : les associer depuis
     la fiche de chaque objet (« Associer un nouveau tag »).

Le .zip contient aussi un dossier `tableur/` : le même contenu en fichiers
CSV, lisibles dans Excel / LibreOffice, modifiables puis réimportables seuls.
Ne sont jamais exportés : le code PIN, les réglages manette/clavier
(propres à chaque machine) et les tags NFC simulés de la démo.

### Écrire les questions dans un tableur (CSV)

Les questions (Quiz, Duèl), les mots de « Ven de l'occitan ? », les
vilatges et les objets peuvent s'écrire **directement dans Excel ou
LibreOffice, sans l'appli**, puis s'importer (démo ou borne, Admin >
Exportar / Importar > Importar, un ou plusieurs .csv d'un coup). Seuls les
images et les sons des objets s'ajoutent ensuite par l'appli.
Sur la borne, le plus simple est de faire l'import depuis un PC, via le
[tunnel SSH](#administrer-la-borne-depuis-un-autre-pc-tunnel-ssh).

- Modèles (une ligne d'en-têtes par fichier + notice) :
  [`docs/modeles-csv/`](docs/modeles-csv/), ou le lien « modèles CSV » de la
  page d'import.
- Exemple, `quiz_questions.csv` :
  ```
  question;reponse_a;reponse_b;reponse_c;bonne_reponse;explication;source;actif;ordre
  …;…;…;…;B;…;IEO;oui;
  ```
- Point-virgule ou virgule, UTF-8 ou encodage Excel : reconnus. Les lignes
  incomplètes sont ignorées et signalées avec leur numéro.
- Détail des colonnes et des règles :
  [guide, section 5](docs/import-contenu-version-prod.md#5-écrire-le-contenu-en-csv-sans-lappli).

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
bash packaging/build_prod_zip.sh                    # -> dist/maleta-occitana-v*.zip (borne)
bash packaging/build_deb.sh                         # -> dist/*.deb (sous Linux)
pyinstaller --noconfirm packaging/maleta-demo.spec  # -> dist/MaletaOccitana-Demo.exe (sous Windows)
```

Sous Linux, la fenêtre utilise WebKitGTK (`python3-gi`,
`gir1.2-webkit2-4.1`, installés automatiquement avec le `.deb`) ; sans
eux, la démo s'ouvre dans le navigateur par défaut.
