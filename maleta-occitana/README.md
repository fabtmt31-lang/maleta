# La Maleta Occitana

Objet interactif Raspberry Pi puis petit PC (NFC + écran + son) pour faire
connaître l'occitan et les écoles Calandreta sur un stand, de façon ludique
et interactive. Concept complet dans le projet claude.ai « calandreta »,
fichier `concept-borne-interactive.md`.

**Version de cette archive : v1.2** (voir « Versions » en bas de ce fichier).

> **Anciennement « La Malissa Occitana »** — l'appli, le dossier, le service
> systemd, les variables d'environnement (`MALETA_*`) et le nom de la base de
> données (`maleta.db`) ont tous été renommés le 14/09/2026. Si tu as une
> installation existante sous l'ancien nom, désactive/supprime l'ancien
> service (`sudo systemctl disable --now malissa-occitana`) avant d'installer
> celle-ci — les deux noms ne sont pas interchangeables (nouvel utilisateur
> Linux `maleta`, nouveau dossier `/opt/maleta-occitana`, nouvelle base
> `maleta.db` qui démarre vide).

**Pivot matériel (13/09/2026)** : la cible n'est plus le Raspberry Pi 4 mais
un **petit PC x86 sous Debian en ligne de commande** (sans environnement de
bureau), avec un **lecteur NFC OMNIKEY en USB/PC-SC** au lieu du PN532 en
I2C. L'écran reste branché sur la sortie vidéo de la machine, la manette USB
Super NES ne change pas. Détail complet de la décision dans
`concept-borne-interactive.md`, section « Pivot matériel ».

**Fonctionnement 100% hors réseau (14/09/2026)** : la borne est destinée à
tourner sur un stand sans accès internet garanti. Toutes les dépendances
externes (bibliothèque `socket.io`, polices d'écran) sont donc servies en
local, sur la machine elle-même — aucun appel réseau n'est nécessaire une
fois l'installation terminée. Détail plus bas.

## Ce qui est fait

- Base SQLite + gestion des **objets** (mot occitan, traduction, image, audio,
  catégorie, actif/inactif) et association à un **tag NFC** depuis l'admin
- **Interface d'administration** protégée par PIN (`/admin`) : objets & tags,
  bibliothèque de photos/vidéos (« Cadre fotó & vidèo »), contenu de
  « Ven de l'occitan ? » et du « Duèl Occitan », médiathèque globale,
  configuration générale
- **Écran du kiosque** (`/`), mis à jour en temps réel par websocket :
  - **Écran d'accueil « Tria un jòc »** (menu), affiché par défaut au
    démarrage et après un temps d'inactivité, avec le nom « La Maleta
    Occitana » affiché en toutes lettres (+ logo d'école et/ou croix
    occitane si personnalisés depuis l'admin)
  - **Descobèrta d'objèctes** : poser un objet sur le lecteur NFC affiche son
    nom occitan, sa traduction et joue la prononciation
  - **Jòc « Tròba l'objècte »** : manche chronométrée, un mot est annoncé, il
    faut poser le bon objet à temps
  - **Jòc « Ven de l'occitan ? »** (v0.2, ex-« Vertadièr o Occitan »,
    renommé en v1.1) : un mot/une expression française
    est affichée, il faut répondre à la manette si elle vient réellement de
    l'occitan (bouton X) ou non (bouton Y) — voir plus bas, contenu à saisir
    depuis l'admin
  - **Jòc « Duèl Occitan »** (v0.7) : jeu à 2 joueurs, une question de
    culture/langue occitane à 2 réponses possibles, chaque joueur répond de
    son côté avec ses propres boutons (aucun bouton assigné par défaut, à
    configurer — voir plus bas) — voir plus bas, contenu à saisir depuis
    l'admin
  - **Jòc « Memòria »** (v0.72, redessiné en v0.8) : jeu de paires à la
    manette/au clavier, une grille de cartes retournées, il faut retrouver
    les paires en retournant deux cartes à la fois — 100% écran, aucun objet
    physique ni lecteur NFC nécessaire. Depuis la v0.8, chaque paire montre
    le mot **français** d'un côté et le mot **occitan** de l'autre (plus une
    image + un mot) : plus pertinent pédagogiquement, ça fait vraiment
    travailler la traduction. Réutilise directement les objets déjà saisis
    dans **Admin > Objèctes & tags** (aucun contenu à créer spécifiquement,
    aucun nouveau bouton manette à assigner : seuls ◀ ▶ / Select (A) / Back
    (B), déjà connus des autres jeux, sont utilisés)
  - **Jòc « Memòria vilatge »** (v0.8) : même mécanique que « Memòria »
    ci-dessus, mais avec des noms de villes/vilatges (français ↔ occitan) au
    lieu des objets — contenu à saisir depuis **Admin > Vilatges (Memòria)**,
    voir plus bas
  - **Quiz Calandreta** (v0.8) : quiz solo, une question de culture/langue
    occitane à 3 réponses possibles (A/B/C), même principe que « Ven de
    l'occitan ? » mais avec un choix de plus — contenu à saisir depuis **Admin >
    Quiz Calandreta**, voir plus bas
  - **Cadre fotó & vidèo** : diaporama photos/vidéos, accessible depuis une
    petite icône dédiée sur l'écran d'accueil (v0.8 : plus une grande tuile
    de jeu, voir « Refonte de l'écran d'accueil » plus bas), plus en écran
    de veille automatique
  - **Icône Admin** sur l'écran d'accueil, navigable à la manette/au clavier,
    plus le raccourci clavier `Ctrl+Alt+A` en secours — les deux ouvrent
    `/admin`. Depuis la v0.8, cliquer dessus sans connaître le code PIN
    n'enferme plus sur l'écran de connexion : un bouton « Tornar al quiòsc »
    y ramène.
- Support **manette USB** (via pygame), **clavier** (v0.8, voir plus bas) et
  lecteur NFC : mode simulé (dev) **et** lecteur OMNIKEY réel en PC/SC (mode
  "pc"), repris de la brique déjà validée sur Histoires du Soir — voir
  `managers/tag_reader.py`
- **Admin > Configuration** (v0.2, gauche/droite ajoutés en v0.3, croix
  directionnelle réellement détectée quel que soit le type de manette
  depuis la v0.4, mapping clavier ajouté en v0.8) : changement du code PIN,
  personnalisation de la bannière de l'écran titre (logo d'école + image de
  croix occitane, à la place du dessin générique), choix parmi **3 modèles
  d'interface** (Senhal, Mercat, Nuèch — v1.1, voir plus bas), reconfiguration des contrôles de la
  manette (mode « écoute » : cliquer sur « Réassigner » puis actionner le
  bouton/la direction à associer) — **gauche/droite compris**, quel que soit
  le mécanisme utilisé par la manette (bouton, « hat » pygame ou axe
  analogique dédié, voir « Croix directionnelle qui ne répond pas » plus
  bas). Depuis la v0.8, chaque action peut **en plus** recevoir une touche
  de clavier (« Assignar tòca »), qui fonctionne **en complément** de la
  manette, jamais à sa place — la touche clavier reste assignable même sur
  une machine sans manette détectée (le tableau ne se cache plus dans ce
  cas, voir « Mapping clavier » plus bas).
- **Admin > Médiathèque** (v0.2, aperçu + suppression + réutilisation
  depuis la v0.6) : liste de tous les fichiers médias présents sur le
  disque (images/audio d'objets, photos/vidéos du diaporama, logo/croix),
  avec un point vert si le fichier est utilisé quelque part ou gris s'il
  est orphelin (bon candidat à supprimer), un aperçu (miniature ou lecteur
  audio) et un bouton poubelle par fichier, plus l'espace disque restant de
  la machine (repris aussi en haut du tableau de bord). Les fichiers déjà
  présents peuvent aussi être réutilisés directement depuis les formulaires
  d'upload (objets, diaporama, bannière) via **« Choisir dans la
  médiathèque »**, sans réupload.
- **Admin > Tableau de bord** (refait en v1.1) : une carte par jeu de la
  borne, avec le nombre de contenus actifs et un badge **« Jogable »** ou
  **« A completar »** calculé avec les mêmes seuils que le kiosque, plus le
  Cadre fotó et l'espace disque. C'est la page ouverte après la connexion.

## Pas encore fait (prochaines étapes)

- Contenu de « Ven de l'occitan ? » : la table est prête et le jeu
  fonctionne dès qu'au moins un mot est saisi depuis l'admin, mais **aucun
  mot n'est pré-rempli** — à vérifier avec une source fiable (CNRTL, Institut
  d'Estudis Occitan...) avant saisie, jamais improvisé
- Contenu du « Duèl Occitan » : même principe, la table est prête et le jeu
  fonctionne dès qu'au moins une question est saisie, mais **aucune n'est
  pré-remplie** — à vérifier avec une source fiable avant saisie
- Contenu de « Memòria vilatge » (Admin > Vilatges) et du « Quiz Calandreta »
  (Admin > Quiz Calandreta) : mêmes tables prêtes et vides à la livraison,
  même principe — à vérifier avec une source fiable avant saisie, jamais
  improvisé
- Mapping manette du « Duèl Occitan » et de « Quiz Calandreta : réponse 3 » :
  à assigner soi-même depuis Configuration > Manette (aucun bouton par
  défaut, voir plus bas)
- Serveur Flask lié à `0.0.0.0` (accessible depuis n'importe quelle machine
  du même réseau, pas seulement en local) : décision assumée, pas un oubli —
  utile par exemple pour ouvrir l'admin depuis un téléphone/une tablette sur
  le même réseau lors d'un stand. À revoir uniquement si un besoin de
  sécurité réseau se présente.

## Installation (PC de développement, sans matériel)

```
pip install -r requirements.txt
python run_dev.py
```

Puis ouvrir :

- `http://localhost:5000/` — l'écran du kiosque
- `http://localhost:5000/admin` — administration (PIN par défaut `1234`,
  à changer avec la variable d'environnement `MALETA_ADMIN_PIN`)
- `http://localhost:5000/dev/panel` — panneau de test pour simuler la pose
  d'un tag NFC sans lecteur branché

## Tester le flux complet sans aucun matériel

1. Aller dans `/admin`, créer un objet (ex. "Fromatge" / "Fromage"), avec une
   image si vous en avez une sous la main.
2. Ouvrir la fiche de l'objet, cliquer sur "Associer un nouveau tag", puis
   "Simuler un scan (mode dev)" — un faux tag lui est associé.
3. Ouvrir `/` (le kiosque) dans un autre onglet.
4. Depuis `/dev/panel`, cliquer sur "Simuler le scan" pour cet objet : le
   kiosque doit basculer sur l'écran de découverte en direct.
5. Brancher la manette USB Super NES : la croix directionnelle navigue dans
   le menu, A valide, Select ramène au menu.

## Tester « Ven de l'occitan ? » sans manette branchée

1. Aller dans `/admin` > « Ven de l'occitan ? », ajouter au moins 2 mots
   (un marqué « vient réellement de l'occitan », un non), avec une courte
   explication pour chacun.
2. Depuis le menu du kiosque (`/`), sélectionner la tuile « Vertadièr o
   Occitan » (ou lancer la manche directement depuis `/dev/panel`, boutons
   « X — Vertadièr » / « Y — Fals » une fois la manche démarrée) pour
   répondre sans manette branchée.
3. Tant qu'aucun mot n'est saisi, la tuile affiche un message dans le menu
   au lieu de planter — c'est normal, pas un bug.

## Tester « Duèl Occitan » (jeu à 2 joueurs) sans manette branchée

1. Aller dans `/admin` > « Duèl Occitan », ajouter au moins 1 question avec
   ses 2 réponses possibles et la bonne réponse (« A » ou « B »).
2. Depuis le menu du kiosque (`/`), sélectionner la tuile « Duèl Occitan »
   (ou lancer la manche directement depuis `/dev/panel`, boutons « Jogador 1
   — A/B » / « Jogador 2 — A/B » une fois la manche démarrée) pour répondre
   sans manette branchée.
3. La bonne réponse et le score de chaque joueur ne sont révélés qu'une fois
   que **les deux** ont répondu (ou que le temps est écoulé) — c'est
   volontaire, pour qu'un joueur ne puisse pas deviner la réponse de l'autre.
4. Tant qu'aucune question n'est saisie, la tuile affiche un message dans le
   menu au lieu de planter — c'est normal, pas un bug.
5. Une fois une vraie manette branchée, assigner les 4 boutons (2 par
   joueur) depuis Configuration > Manette, section « Duèl Occitan : joueur
   1/2 — réponse A/B » — aucun bouton n'est assigné par défaut (voir
   « Ajuster le mapping de la manette » ci-dessous).

## Personnaliser la bannière, le modèle d'interface et la manette

Tout se passe dans `/admin` > **Configuration** :

- **Bannière** : uploader un logo d'école et/ou une image de croix occitane
  remplace le dessin générique de l'écran titre. Un bouton « Revenir à
  l'image par défaut » réapparaît une fois un fichier personnalisé actif.
- **Modèle d'interface** (v1.1) : 3 modèles complets tirés des maquettes
  « La Maleta Occitana — 3 directions » — **Senhal** (par défaut : jaune et
  rouge, gros caractères, contours noirs), **Mercat** (terre cuite, olive et
  soleil, formes arrondies) et **Nuèch** (bleu nuit étoilé et or, police à
  empattements). Chaque modèle change tous les écrans de la borne (accueil,
  menu, jeux, fins de manche, diaporama) **et** l'apparence de l'admin. Le
  changement s'applique après rechargement de l'écran du kiosque (touche F5,
  ou redémarrage du service).
- **Manette** : cliquer sur « Réassigner » à côté d'une action, puis appuyer
  sur le bouton de la manette à lui associer (mode « écoute », quelques
  secondes). Nécessite une manette/pygame détectés sur la machine — sur un
  PC de développement sans manette branchée, la section l'indique clairement
  plutôt que de planter.

## Ajuster le mapping de la manette

Une fois la manette en main, ses index de boutons peuvent différer de ceux
supposés dans `managers/input_bus.py` (`DEFAULT_BUTTON_MAP`). Pour les
identifier : lancer l'appli, appuyer sur chaque bouton en regardant les logs
dans la console (`Action manette : ...` ou l'absence de log si l'index n'est
pas mappé), et ajuster le dictionnaire en conséquence — ou, plus simple,
passer directement par `/admin` > Configuration > Manette (voir plus haut),
qui fait exactement ça sans toucher au code.

**Cas particulier du Duèl Occitan (v0.7)** : ses 4 actions (`duel_p1_a`,
`duel_p1_b`, `duel_p2_a`, `duel_p2_b`) n'ont **aucun bouton assigné par
défaut**, contrairement au reste — une manette SNES USB classique à 8
boutons est déjà entièrement occupée par les autres actions (A/B/croix/X/Y/
Select/Start), il ne reste que L/R de libres, pas assez pour 4 actions.
Direction Configuration > Manette pour choisir soi-même les 4 boutons (ou
réassigner d'autres actions ailleurs pour libérer de la place) avant de
pouvoir jouer au Duèl Occitan à la manette — en attendant, le jeu reste
testable sans manette depuis `/dev/panel` (voir plus haut). Même remarque
pour l'action `answer_3` du **Quiz Calandreta** (v0.8) : pas de bouton
assigné par défaut non plus (les 3 réponses A/B/C d'une manette SNES
classique entrent en conflit avec les boutons déjà utilisés ailleurs) — à
assigner soi-même, ou à répondre depuis `/dev/panel`/le clavier (voir
« Mapping clavier » plus haut) en attendant.

## Mapping clavier (v0.8)

En plus de la manette, chaque action peut recevoir une touche de clavier
depuis `/admin` > Configuration > Manèta & clavièr : clique sur « Assignar
tòca » à côté de l'action voulue, puis appuie sur la touche à associer.
Contrairement à la manette, ça ne nécessite ni pygame ni matériel détecté
(la capture se fait entièrement dans le navigateur) — le tableau reste donc
toujours visible et utilisable, même sur une machine de développement sans
manette branchée.

**Manette et clavier coexistent toujours**, jamais l'un ne remplace l'autre :
assigner une touche à « Gauche » n'efface pas le bouton manette déjà assigné
à « Gauche », et vice-versa. Une touche ne peut en revanche déclencher
qu'**une seule action** à la fois (comme pour la manette) : la réassigner
retire automatiquement son ancienne assignation. Un bouton « Retirar » à côté
de chaque touche assignée permet de la retirer sans la réattribuer ailleurs.

Aucune touche n'est assignée par défaut (contrairement à certaines actions
manette) : une touche assignée par défaut pourrait entrer en conflit avec la
saisie clavier d'un formulaire admin ouvert dans le même navigateur.

## Croix directionnelle qui ne répond pas (v0.3 puis v0.4)

Selon le modèle de manette, pygame/SDL peut remonter la croix directionnelle
de **trois façons différentes**, et une manette donnée n'en utilise
généralement qu'une seule :

1. un vrai « hat » de manette (`JOYHATMOTION`) — le cas le plus courant,
   supporté depuis le début (`DEFAULT_HAT_MAP` dans `managers/input_bus.py`) ;
2. des boutons numérotés (`JOYBUTTONDOWN`), exactement comme A/B/X/Y — le cas
   de certaines manettes USB « type SNES » bon marché, supporté depuis la
   **v0.3** ;
3. un ou deux **axes analogiques dédiés** (`JOYAXISMOTION`, valeur continue
   -1.0 à 1.0) — un troisième mécanisme, rencontré sur d'autres manettes bon
   marché, supporté depuis la **v0.4**. Sur ce type de manette, ni le hat ni
   le mapping bouton ne pouvaient jamais détecter la croix : elle n'était
   même pas capturable dans l'écran « Réassigner », d'où le signalement
   initial malgré le correctif v0.3.

**Depuis la v0.4**, les trois mécanismes sont détectés automatiquement et
coexistent sans se gêner. « Gauche » et « Droite » (comme n'importe quelle
autre action) restent reconfigurables depuis `/admin` > Configuration >
Manette : clique sur « Réassigner » à côté de l'action voulue, puis actionne
la croix directionnelle sur la manette — que ce soit techniquement un
bouton, un hat ou un axe pour pygame n'a plus d'importance, la page le
détecte dans les trois cas.

## Dépendances servies en local (fonctionnement 100% hors réseau)

Deux dépendances qui étaient historiquement chargées depuis le web sont
désormais servies **localement**, pour que la borne fonctionne sans aucun
accès réseau dès le démarrage (utile sur un stand sans wifi/4G fiable) :

- **`socket.io` (client)** — `static/js/socket.io.min.js` (Socket.IO v4.7.5),
  inclus directement dans ce zip, chargé via une route Flask locale au lieu
  d'un CDN externe. `kiosk.js` reste par ailleurs robuste à une absence de ce
  fichier : même sans lui, l'écran d'accueil et les deux accès admin
  fonctionnent (seules les mises à jour en direct manqueraient).
- **Polices d'écran** — le kiosque n'appelle jamais Google Fonts
  (`fonts.googleapis.com`). Depuis la v1.1, les polices des 3 modèles
  (Unbounded + Manrope, Bagel Fat One + Lexend, Young Serif + Instrument
  Sans) sont vendorées localement dans `static/fonts/` (voir
  `static/fonts/README.md`, déclarées dans `static/css/fonts.css`) et
  chargées sans aucun appel réseau — rendu fidèle aux maquettes. Repli sur
  les polices système installées par `install.sh` (paquets `fonts-dejavu-core`,
  `fonts-noto-core` — bonne couverture des caractères occitans avec
  diacritiques : ò, à, è, ç...), au cas où un fichier de police viendrait à
  manquer.

**Pourquoi ce choix** : une bibliothèque JS chargée depuis un CDN externe
inaccessible (réseau filtré, borne isolée...) ne provoque pas qu'un simple
défaut d'affichage — si le script qui échoue est placé avant du code
essentiel, ça peut bloquer toute la page (c'est ce qui s'est passé avec
`socket.io` le 14/09/2026 : l'écran restait figé sur « Pausa un objècte » et
aucun raccourci admin ne répondait, alors même que le serveur fonctionnait
parfaitement). Toute dépendance web externe est donc à éviter par principe
sur ce projet.

## Installation / mise à jour sur le petit PC Debian (production)

**Étape unique, identique pour la première installation et pour toutes les
mises à jour suivantes :**

```bash
cd ~/maleta-occitana
sudo bash install.sh
```

`install.sh` se repère tout seul par rapport à son propre emplacement (pas
besoin de passer un chemin ou un nom d'utilisateur en argument). Il installe
les paquets système (pcscd, pyscard, X minimal, Chromium, polices locales),
crée les règles polkit pour un accès headless au lecteur, copie le code vers
`/opt/maleta-occitana` (sans jamais toucher à l'environnement virtuel Python
déjà en place ni à la base de données `maleta.db` — le contenu saisi dans
l'admin est toujours préservé), installe/actualise les dépendances Python, et
(re)démarre le service systemd `maleta-occitana` ainsi que le kiosque
Chromium plein écran au démarrage (autologin tty1 + `startx`).

**Pour mettre à jour une installation existante** : décompresser la nouvelle
archive au même endroit (`~/maleta-occitana`, en écrasant l'ancien contenu),
puis relancer exactement la même commande `sudo bash install.sh` — rien
d'autre à faire.

Après installation :

```bash
pcsc_scan
```

(paquet `pcsc-tools`, déjà installé par le script) pour vérifier que le
lecteur OMNIKEY est détecté indépendamment de l'app, puis redémarrer la
machine pour valider la chaîne complète.

**Avant le petit PC réel, tester en machine virtuelle** : voir
`docs/guide-test-vm.md` — même script, juste le passthrough USB du lecteur
et de la manette à activer côté hyperviseur.

## Refonte visuelle (v0.5)

L'apparence du kiosque et de l'admin a été refaite à partir des maquettes
transmises par Fabien (canevas Claude Design, 14/09/2026) : fond terracotta
profond et cartouches arrondies sur l'écran d'accueil « Tria un jòc »
(tuiles à icônes, bandeau NFC, aide manette en pastilles), grands blocs de
couleur pour les réponses Vertadièr/Fals, et une admin réorganisée en barre
latérale groupée « Contengut » / « Sistèma » avec compteurs, Configuration
en grille de cartes. Aucun changement de comportement — mêmes routes, mêmes
formulaires, même logique de jeu, uniquement l'habillage visuel (CSS +
gabarits HTML). Les 4 thèmes de couleur (Occitan, Miègjorn, Pirenèus,
Nuèch) restent inchangés et continuent de s'appliquer au kiosque comme
avant. Les polices "Caprasimo"/"Figtree" des maquettes sont référencées en
premier choix (repli sur les polices système si non installées) — même
principe que "Baloo 2"/"Work Sans" précédemment, aucune dépendance réseau
ajoutée.

## Versions

Les archives livrées sont numérotées de façon incrémentale
(`maleta-occitana-v0.1.zip`, `v0.2.zip`, ...) plutôt que par nom d'étape.
Chaque zip contient directement un dossier `maleta-occitana/` à sa racine
(et non plus les fichiers en vrac) : décompresser à la racine du dossier
personnel (`unzip maleta-occitana-vX.Y.zip -d ~`) reproduit toujours
`~/maleta-occitana/`, prêt pour `install.sh` — plus de risque de se tromper
de dossier de destination.

**Granularité des versions (depuis le 15/09/2026)** : une évolution notable
(nouvel écran, nouvelle activité, refonte visuelle...) avance le premier
chiffre après le point (`v0.6` → `v0.7`) ; une correction ou un petit ajout
ponctuel (comme les 5 points de la v0.6) avance seulement le deuxième
chiffre (`v0.6` → `v0.61`, `v0.62`...). Objectif : que le numéro de version
donne une idée de l'ampleur du changement sans avoir à ouvrir le changelog.

- **v1.2** (21/10/2026) — **version de démonstration + export/import du
  contenu**.
  1. **Admin > Exportar / Importar** (nouvelle page, section Sistèma) :
     extrait tout le contenu saisi à la main (objets avec images/sons, Ven de
     l'occitan ?, Duèl, Quiz, Vilatges, Fotos & vidèos, apparence et textes de
     la borne) dans un seul `.zip`, et le réimplante sur une autre
     installation — mode « Ajouter » (doublons ignorés) ou « Remplacer ». Le
     .zip contient aussi des CSV (`tableur/`) pour relire le contenu dans un
     tableur. Jamais exportés : PIN, réglages manette/clavier, tags NFC
     simulés. Code : `managers/content_transfer.py`. Même import en ligne
     de commande : `importer_contenu.py` (utilisable aussi sur une borne
     restée en v1.11, voir `docs/import-contenu-version-prod.md` à la racine
     du dépôt).
  2. **Version démo** (`MALETA_DEMO=1`, utilisée par l'application de bureau
     du dossier `desktop/` à la racine du dépôt — exécutable Windows et
     paquet .deb), jouable entièrement au clavier et à la souris sans
     manette : une touche par défaut pour chaque action (complétée au
     démarrage si une action n'en a plus), clic sur les tuiles, cartes et
     réponses (`GameController.on_pointer`), clic droit = retour au menu, un
     tag NFC simulé par objet et un panneau « Pausar un objècte » (F2) sur
     le kiosque, rappel du code
     PIN par défaut sur la connexion admin, mention DÉMO dans la barre
     latérale. **Aucun effet sur la borne** : `install.sh` ne définit pas
     cette variable.
  3. **Dossier des données réglable** (`MALETA_DATA_DIR`, base + médias) :
     par défaut le dossier du code, comme avant — rien ne change sur la
     borne.
  Mise à jour de la borne : comme d'habitude, `sudo bash install.sh`.
- **v1.11** (04/10/2026) — **écran de la borne limité à la moitié gauche
  (zone noire à droite) sur une machine physique**. La page n'est pas en
  cause : c'est la fenêtre de Chromium qui restait plus petite que l'écran.
  Sans gestionnaire de fenêtres, le dimensionnement automatique de `--kiosk`
  n'est pas fiable (Chromium lit la taille de l'écran trop tôt après le
  démarrage de X). Même correctif que sur le projet « digital-signage » de
  Fabien, où il a déjà fait ses preuves en VM et sur matériel réel :
  `.xinitrc` lit la résolution réelle avec `xrandr` et la passe explicitement
  à Chromium (`--window-position=0,0`, `--window-size=LARGEUR,HAUTEUR`,
  `--force-device-scale-factor=1`, `--high-dpi-support=0`). Le `xrandr --auto`
  de la v1.02 est conservé juste avant. Rien d'autre ne change : relancer
  `sudo bash install.sh` puis redémarrer la machine (`sudo reboot`).
- **v1.1** (01/10/2026) — **refonte complète de l'interface** sur les
  maquettes « La Maleta Occitana — 3 directions » fournies par Fabien.
  1. **3 modèles d'interface au lieu des 4 thèmes de couleur** : Senhal
     (par défaut), Mercat et Nuèch, au choix dans Configuration > Aparença.
     Chaque modèle a ses polices, ses formes et ses décorations (croix
     occitane, soleil et collines, ciel étoilé...) sur **tous** les écrans :
     veille, menu, Descobèrta, Tròba l'objècte, Ven de l'occitan ?, Duèl,
     Memòria (choix de la taille + grille), Quiz, fins de manche, diaporama.
     Les écrans absents des maquettes (Tròba, Duèl, Quiz, choix Memòria) ont
     été dessinés dans le même esprit que leurs voisins. Une ancienne valeur
     de thème enregistrée en base retombe simplement sur Senhal.
  2. **L'admin suit le modèle choisi** (couleurs, polices, barre latérale à
     icônes) et son **tableau de bord est refait** comme sur les maquettes :
     une carte par jeu avec un badge « Jogable » / « A completar » (mêmes
     seuils que la borne), le Cadre fotó et l'espace disque. La connexion
     ouvre désormais ce tableau de bord, accessible aussi depuis la barre
     latérale (lien « Tableau de bord » et nom de la borne).
  3. **Plus de rappel de touche sur les tuiles du menu** (ni sur les tuiles
     « Quantas cartas ? ») : il devenait faux dès que les touches étaient
     réassignées, et la barre d'aide en bas d'écran l'indique déjà — avec le
     texte saisi dans Configuration > Manèta & clavièr.
  4. **« Vertadièr o Occitan » devient « Ven de l'occitan ? »** (« Vient de
     l'occitan ? » en sous-titre) partout : menu, écran de jeu, fin de
     manche, admin, Configuration. Rien ne change pour le contenu déjà saisi.
  5. **Mise à l'échelle automatique** : chaque écran est dessiné pour du
     1280×720 puis agrandi/réduit à la taille réelle de l'écran, sans bande
     noire (vérifié en 1280×720, 1366×768, 1920×1080, 1024×768, 1280×1024 et
     2560×1080). Les textes longs (mot occitan, question, réponse de Quiz)
     se réduisent tout seuls pour rester entièrement visibles.
  6. Descobèrta : bouton « Escota » affiché seulement si l'objet a une
     prononciation enregistrée (et cliquable pour la rejouer).
  Nouveaux fichiers : `static/css/fonts.css`, `kiosk-base.css`,
  `kiosk-senhal.css`, `kiosk-mercat.css`, `kiosk-nuech.css`,
  `templates/kiosk/_macros.html` ; `kiosk.css` et les polices
  Caprasimo/Figtree sont retirées.
- **v1.03** (28/09/2026) — revue complète du code demandée par Fabien
  (« vérifie les bugs, s'il y a des améliorations ou ajustements à faire »).
  Pas de nouvelle fonction de jeu : uniquement des corrections et des
  ajustements de robustesse, vérifiés un par un.
  **Côté borne (jeux et écran)** :
  1. **Tròba l'objècte ne se terminait jamais si personne ne jouait** —
     quand le temps était écoulé, le même mot était reposé indéfiniment, et
     la borne restait bloquée sur ce jeu. Désormais, temps écoulé = on
     révèle l'objet attendu puis on passe au mot suivant ; une mauvaise
     réponse, elle, redonne toujours une nouvelle chance sur le même mot.
  2. **Poser un objet interrompait la partie en cours** (Vertadièr, Duèl,
     Quiz, Memòria) en basculant sur Descobèrta. Pendant ces jeux, un objet
     posé est maintenant ignoré ; il fonctionne toujours depuis le menu, le
     diaporama, les écrans de choix et de fin (et sert toujours de réponse
     dans Tròba l'objècte).
  3. **Barre de temps qui repartait à 100 %** — au Duèl, dès que le joueur 1
     répondait, la barre se remplissait à nouveau alors que le temps
     continuait de s'écouler côté serveur. Le serveur envoie désormais le
     temps restant, la barre reste juste dans tous les cas (y compris après
     un rechargement de la page).
  4. **Mise en page qui débordait de l'écran** — la Memòria à 12 paires (6×4)
     coupait sa première et sa dernière rangée sur les écrans 16:9
     (1920×1080, 1366×768, 1280×720) ; les questions longues du Duèl et du
     Quiz s'affichaient dans la police géante prévue pour un seul mot et
     sortaient par le haut (la barre de temps disparaissait). La grille se
     cale maintenant aussi sur la hauteur de l'écran, et la taille du texte
     des questions s'adapte à leur longueur.
  5. **Diaporama** — il pouvait continuer de tourner en arrière-plan après
     en être sorti, ou tourner en double (photos affichées 1 s seulement),
     à cause d'une vidéo dont la lecture échouait après l'arrêt. Corrigé.
     Les photos/vidéos plus petites que l'écran sont désormais agrandies
     (proportions conservées) au lieu de rester minuscules au centre d'un
     fond noir.
  6. **Clavier** — une touche maintenue enfoncée se répétait toute seule et
     pouvait ouvrir un jeu PUIS valider sa première réponse ; les
     répétitions sont ignorées et les actions d'une même touche partent
     dans l'ordre.
  7. **Double appui simultané** — deux actions arrivant exactement en même
     temps (ex. deux requêtes clavier, ou une réponse pile au moment où la
     question change) pouvaient se croiser côté serveur : réponse comptée
     sur la mauvaise question, voire erreur. Les événements (manette,
     clavier, tags, minuteurs) sont désormais traités strictement un par un.
  8. **Manette : une erreur la rendait muette jusqu'au redémarrage** du
     service — elle est maintenant journalisée et la manette continue de
     fonctionner.
  9. **Son de l'objet** qui continuait de jouer par-dessus l'écran suivant
     (ex. retour au menu depuis Descobèrta) : coupé en quittant l'écran.
  10. **Page de connexion admin sans issue à la manette** — un visiteur qui
      sélectionnait l'icône Admin restait bloqué sur le formulaire de PIN
      (le navigateur n'y écoute plus la manette). Le bouton « retour » de la
      manette ramène maintenant au kiosque, et sans aucune activité pendant
      60 s la page y revient toute seule.
  **Côté service / matériel (symptômes vus dans les journaux de Fabien)** :
  11. **`systemctl restart` qui attendait 10 s puis tuait le service**
      (« State 'stop-sigterm' timed out. Killing. ») — la bibliothèque de la
      manette (pygame/SDL) interceptait le signal d'arrêt. Le service
      s'arrête maintenant immédiatement.
  12. **Flot de messages « ALSA … underrun occurred »** — pygame ouvrait la
      carte son sans raison (et la disputait à Chromium, qui en a besoin
      pour la prononciation des objets). Seules la manette et la boucle
      d'événements sont initialisées désormais.
  13. **Lecteur NFC** : la connexion au tag est refermée proprement après
      lecture, et une erreur de traitement d'un tag ne peut plus bloquer le
      lecteur.
  **Côté administration** :
  14. **Association de tag restée « en écoute »** — si on quittait la fiche
      objet sans poser de tag après « Associer un nouveau tag », le tag du
      visiteur suivant (même des heures plus tard) était silencieusement
      ré-associé à cet objet au lieu d'ouvrir Descobèrta ; et si l'objet
      avait été supprimé entre-temps, tous les scans suivants échouaient
      jusqu'au redémarrage. L'écoute expire maintenant toute seule (60 s,
      compte à rebours affiché), s'annule avec le nouveau bouton
      « Annuler » ou en quittant la page, et la suppression de l'objet la
      désarme. Le message du journal indique aussi le bon objet (il
      affichait « None »).
  15. **Médiathèque : la poubelle supprimait sans demander confirmation**
      (la fenêtre d'avertissement « ce fichier est encore utilisé » ne
      s'affichait jamais, à cause d'un guillemet mal placé). Corrigé.
  16. **Erreurs 500** : envoi d'une image/d'un son au format refusé sur une
      fiche objet (le formulaire est maintenant réaffiché avec un message,
      saisie conservée), fichier dont le nom n'a aucune lettre latine
      (refusé à tort comme « extension non autorisée »), boutons
      actif/inactif ou « simuler un scan » sur un élément supprimé entre-
      temps, et réglages enregistrés corrompus (qui pouvaient empêcher le
      service de démarrer).
  17. **Nouveau : retirer l'image ou le son d'un objet** (cases « Retirer…
      » sur la fiche). Avant, on pouvait seulement les remplacer — et un
      objet dont le fichier avait été supprimé de la Médiathèque restait
      avec une image cassée.
  18. **Déconnexion automatique de l'admin** après 20 min sans activité
      (`MALETA_ADMIN_IDLE_MINUTES`) : une session laissée ouverte sur la
      borne laissait n'importe quel visiteur entrer dans l'admin par l'icône
      du menu.
  19. **Petits ajustements** : l'assignation d'une touche clavier ignore
      Maj/Ctrl/Alt pressées seules et s'annule avec Échap ; la barre
      d'espace s'affiche « ␣ » sur la borne (le badge était vide).
  20. **Adresse d'écoute réglable** (`MALETA_HOST`) : par défaut l'appli
      n'écoute toujours que sur la borne elle-même (127.0.0.1, accès à
      distance par tunnel SSH). Voir le commentaire dans `install.sh` pour
      l'ouvrir au réseau sans que les mises à jour ne l'écrasent.
  **Vérification faite côté développement** : 39 tests automatiques de
  non-régression (base de données temporaire, jamais `maleta.db`) couvrant
  chacun des points ci-dessus côté serveur ; contrôle dans un vrai
  navigateur (Chromium headless) de la mise en page Memòria 12 paires, Duèl
  et Quiz à 1920×1080, 1366×768, 1280×720 et 1024×768, du diaporama (image
  agrandie, arrêt effectif), de l'absence d'erreur JavaScript sur tous les
  écrans du kiosque, de la fenêtre de confirmation de la Médiathèque et du
  compte à rebours/« Annuler » de l'association de tag ; arrêt immédiat sur
  SIGTERM vérifié avec un vrai serveur Werkzeug. **À confirmer sur la
  borne** (pas de manette ni de pygame dans cet environnement) : qu'un
  `sudo systemctl restart maleta-occitana` est maintenant instantané et que
  les messages ALSA ont disparu du journal.
- **v1.02** (16/09/2026) — trois retours de Fabien après la v1.01/v1.0,
  tous livrés dans cette version.
  1. **Diaporama sans bouton visible pour en sortir** — fonctionnellement,
     n'importe quelle action quittait déjà le diaporama depuis toujours
     (`game_controller.py`, état veille), mais rien ne le signalait à
     l'écran, contrairement à l'écran d'accueil statique qui affiche déjà
     une phrase d'aide. Une petite croix discrète + « Quin bouton per tornar
     al menú » (texte générique, cohérent avec les écrans de fin de jeu :
     n'importe quelle action fonctionnant, il n'y a pas un bouton précis à
     nommer) sont désormais affichées en haut à droite de l'écran du
     diaporama, assez discrètes pour ne pas gêner la lecture des
     photos/vidéos.
  2. **Configuration des boutons réorganisée en sections par activité** —
     demandé par Fabien (« général, tròba l'objècte, memòria, etc. ») : la
     page Configuration > Manèta & clavièr, qui listait jusqu'ici une
     quinzaine d'actions à plat, les regroupe désormais par section —
     Général (valider, retour, directions, lancer le diaporama, communs à
     tous les écrans), puis une section par jeu (Tròba l'objècte, Vertadièr
     o Occitan, Duèl Occitan, Quiz Calandreta, Memòria & Memòria vilatge).
     Les activités sans bouton dédié (Tròba l'objècte, Memòria — qui
     réutilisent uniquement les contrôles généraux) ont quand même leur
     section, avec une note explicative plutôt qu'un tableau vide. Purement
     une réorganisation d'affichage : aucun changement de comportement.
  3. **Écran qui ne remplit pas tout l'affichage (zone noire à droite)** —
     `kiosk.css` (aujourd'hui `kiosk-base.css`) demande déjà 100% de la largeur/hauteur au navigateur
     (vérifié), donc la zone noire vient très probablement du serveur
     d'affichage X qui démarre sur une résolution différente de la
     résolution native réelle de l'écran (l'EDID n'est pas toujours lu
     correctement avant que X choisisse un mode). `install.sh` ajoute
     désormais `xrandr --auto` au démarrage du kiosque (`.xinitrc`), qui
     force chaque sortie vidéo à repasser sur son mode préféré/natif —
     corrige la grande majorité des cas de ce type sans configuration
     manuelle, sans effet si la résolution était déjà correcte. Non
     vérifiable dans cet environnement de développement (pas d'écran ni de
     serveur X réels) — si le problème persiste malgré ça chez Fabien,
     `xrandr` (sans argument, depuis une session X) liste les résolutions
     disponibles pour en forcer une à la main.
  **Vérification faite côté développement** : rendu du diaporama vérifié
  par capture d'écran (Playwright/Chromium headless, serveur Flask isolé
  avec un média de test) — croix + texte bien positionnés en haut à droite,
  sans chevaucher la légende en bas. Page Configuration revérifiée par
  capture d'écran : les 6 sections s'affichent avec les bons titres/notes,
  les 14 actions apparaissent chacune une seule fois (aucune perdue ni
  dupliquée malgré le partage answer_1/answer_2 entre Vertadièr et Quiz),
  l'avertissement de contrôle partagé (v1.01) et les textes de bouton
  personnalisés (v1.01) continuent de fonctionner dans la nouvelle mise en
  page. `bash -n install.sh` pour la syntaxe du script, `py_compile` sur
  tous les fichiers Python modifiés. Base de données remise à son état par
  défaut après vérification, aucune donnée de test livrée. Le point 3
  (résolution X) reste le seul des trois à confirmer sur le terrain — les
  points 1 et 2 sont vérifiables entièrement en développement et donc
  considérés réglés.
- **v1.01** (16/09/2026) — un correctif/complément suite au retour de Fabien
  après la v1.0. **Signalement : « si je prends le B pour réponse 2 du coup
  ça ferme aussi »** — pas un bug de logique : c'est la conséquence attendue
  du partage de contrôle (v0.81, un même bouton peut déclencher plusieurs
  actions à la fois). Si « Retour au menu » (assigné par défaut au bouton B)
  reste assigné au même bouton qu'une réponse fraîchement configurée dessus,
  ce bouton déclenche les deux actions à chaque appui, et « Retour au menu »
  ramène toujours à l'accueil. Deux réponses apportées, demandées ensemble
  par Fabien :
  1. **Avertissement de contrôle partagé** — la page Configuration > Manèta
     & clavièr signale désormais, sous chaque action, si son contrôle
     (bouton, hat, axe ou touche) est aussi utilisé par une autre action —
     et précise explicitement quand l'une d'elles est « Retour au menu »
     (« — un appui ramènera aussi au menu »), pour repérer ce piège avant de
     jouer plutôt que sur le terrain.
  2. **Texte de bouton personnalisable, par action** — nouvelle colonne
     « Tèxte afichat » dans ce même tableau : un champ de texte libre par
     action, où Fabien peut taper exactement ce qui est écrit sur sa
     manette physique (ex. « A », « Select »), au lieu du libellé technique
     auto-calculé (numéro de bouton pygame, code d'axe…) qui ne correspond
     pas forcément à l'inscription réelle sur le boîtier. Ce texte, une fois
     saisi, remplace systématiquement le calcul automatique partout où le
     kiosque affiche un libellé de bouton (menu, Vertadièr, Duèl, Quiz
     Calandreta, Memòria) — un champ laissé vide revient au calcul
     automatique.
  **Vérification faite côté développement** : reproduction exacte du
  scénario signalé (réponse 2 réassignée sur le même bouton que « Retour au
  menu ») confirmant que l'avertissement apparaît bien et mentionne
  explicitement le retour au menu ; aller-retour complet sur les textes de
  bouton personnalisés via les vraies routes admin (saisie, propagation
  jusque dans le rendu du kiosque — menu et badges de réponse — champ vidé
  qui revient bien au calcul automatique) ; rendu de la page Configuration
  vérifié sans balise Jinja non résolue. Base de données remise à son état
  par défaut après ces vérifications (aucune donnée de test livrée).
- **v1.0** (16/09/2026) — un bug corrigé (double-validation à l'entrée d'un
  jeu) + trois évolutions demandées par Fabien. **Numérotation** : d'après la
  convention habituelle (un bug + plusieurs évolutions groupées n'avance que
  le deuxième chiffre), ce paquet serait une « v0.10 » — mais il clôt les
  deux derniers bugs de cycle de vie connus (perte de médiathèque en v0.9,
  double-validation ici) et rend la borne vraiment adaptable école par
  école (textes personnalisables), ce qui en fait une bonne étape pour
  marquer un premier palier stable : **v1.0**.
  **Bug « je configure le bouton A pour valider, c'est dommage que le jeu
  parle d'un Y » / double-validation à l'entrée d'un jeu** : deux signalements
  liés, un seul correctif commun. (1) Les écrans de jeu (Vertadièr, Duèl,
  Quiz, hints du menu et du Memòria) affichaient des lettres A/B/X/Y codées
  EN DUR, qui ne correspondaient plus à rien dès que Fabien réassignait une
  action à un autre bouton. Chaque hint/badge affiche désormais le VRAI
  contrôle assigné (numéro de bouton, flèche, axe, ou touche clavier — ex.
  « 3 », « A2+ », « E », ou « 3 / E » si manette et clavier sont assignés
  tous les deux), calculé à partir du même réglage que la page Configuration
  (aucun mot inventé en occitan ou en français, uniquement l'identifiant
  technique du contrôle). Cas particulier du Duèl (4 actions séparées, une
  par joueur × réponse, qui ne correspondent pas à un seul bouton partagé) :
  les badges A/B restent des repères de position neutres, chaque joueur a
  en plus une ligne dédiée avec son propre contrôle réel. (2) **Si le même
  bouton sert à la fois à entrer dans un jeu ET à répondre dans ce jeu
  (possible depuis la v0.81, un bouton peut déclencher plusieurs actions),
  entrer dans le jeu validait immédiatement la première réponse** — corrigé
  par un court verrou (0,35 s, `config.ACTION_LOCKOUT_SECONDS`) qui ignore
  toute action déclenchée juste après un changement d'écran, imperceptible
  à l'usage normal mais qui absorbe ce double-déclenchement.
  **Import en masse dans la médiathèque du diaporama** : nouveau bouton
  « Import en masse » sur la page Médiathèque, qui accepte une sélection de
  plusieurs fichiers d'un coup (photos et vidéos, mêmes formats qu'à l'ajout
  simple) — une entrée est créée par fichier sans légende ni durée
  particulière (à affiner ensuite individuellement si besoin) ; un fichier
  invalide dans le lot est signalé sans bloquer l'import des autres.
  **Textes du kiosque personnalisables par école** (première passe) :
  nouvelle section « Tèxtes de la borna » dans Configuration, qui permet de
  modifier le nom de la borne et les textes de l'écran d'accueil/menu
  (titre, sous-titre, phrase d'explication, bandeau « pose un objet ») —
  utile pour qu'une autre école Calandreta adapte le message à son propre
  contexte. Un champ laissé vide revient au texte d'origine. Volontairement
  limité à ces quelques textes les plus visibles pour cette première
  version — à signaler si d'autres textes du kiosque doivent devenir
  éditables.
  **Vérification faite côté développement** : suite de tests fonctionnels
  isolés sur le verrou anti-double-validation (scénario exact du bug +
  non-régression sur les transitions Tròba/Vertadièr/Duèl/Quiz/Memòria avec
  un rythme réaliste, et confirmation que la navigation rapide dans le menu
  n'est pas affectée), rendu de la page du kiosque vérifié sans balise Jinja
  non résolue pour plusieurs configurations de mapping (par défaut, un
  réassignement personnalisé, une action non assignée avec repli sur
  « ? »), aller-retour complet sur les textes personnalisables (saisie,
  champ vidé qui revient bien au texte par défaut, remise à zéro complète)
  via les vraies routes admin.
- **v0.9** (16/09/2026) — un bug corrigé (perte de médiathèque à la mise à
  jour) + deux évolutions demandées par Fabien.
  **Bug : la médiathèque (images/sons des objets) était effacée à chaque
  mise à jour** — `install.sh` copie le code avec `rsync -a --delete`, qui
  supprime dans `/opt/maleta-occitana` tout fichier absent de l'archive
  fraîchement décompressée. Le dossier `media/` n'était PAS dans la liste
  d'exclusions (seuls `.venv` et `maleta.db` l'étaient) : chaque mise à jour
  supprimait donc les vraies images/sons uploadés par Fabien, puisque
  l'archive livrée ne contient que la structure de dossiers vide
  (`.gitkeep`). La base de données, elle, était préservée (exclue) — d'où le
  symptôme exact signalé : la fiche de l'objet garde le nom du fichier, mais
  l'image/le son ne remonte plus nulle part. `media` rejoint désormais la
  liste des exclusions, exactement comme `.venv` et `maleta.db` : plus
  jamais touché par une mise à jour, première installation comme mises à
  jour suivantes (chaque route d'upload crée déjà son sous-dossier à la
  volée si besoin, `os.makedirs(..., exist_ok=True)`, donc rien à
  pré-créer). **Fabien doit reprendre en photo/son tout objet dont le
  fichier a été perdu par une mise à jour précédente** — ce correctif
  empêche que ça se reproduise, il ne récupère pas ce qui a déjà été
  supprimé.
  **Navigation haut/bas (manette et clavier)** : les actions `up`/`down`
  rejoignent `left`/`right` (assignables séparément depuis Configuration >
  Manette/Clavier, avec une valeur par défaut sur l'axe Y de la croix
  directionnelle de la manette — à vérifier avec le matériel réel comme le
  reste du mapping). Dans le menu, haut/bas se comportent comme gauche/
  droite (la grille de tuiles n'a pas un nombre de colonnes fixe côté
  serveur) ; dans la grille de cartes du Memòria, un vrai déplacement de
  RANGÉE (voir ci-dessous).
  **Memòria et Memòria vilatge : choix explicite de la taille de partie,
  passée à 6/12 paires** — deux changements liés. (1) Un écran « Quantas
  cartas ? » s'affiche désormais entre le menu et le lancement de la partie,
  proposant un choix simple entre les deux tailles (remplace le tirage au
  sort de la v0.83) ; une taille non jouable faute de contenu reste visible
  mais grisée/annotée, la sélectionner affiche un message explicatif sans
  bloquer l'écran. (2) Les tailles passent de 5/10 à **6/12 paires** (12/24
  cartes) et la grille utilise désormais un nombre de colonnes FIXE (6,
  `config.MEMORIA_GRID_COLUMNS`) au lieu de s'adapter à la largeur d'écran :
  12 cartes forment une grille 6×2, 24 cartes une grille 6×4 — deux
  rectangles bien réguliers, plus symétriques qu'avant, et ce nombre de
  colonnes fixe est ce qui rend possible le déplacement de rangée par
  haut/bas mentionné plus haut.
  **Vérification faite côté développement** : suite de tests fonctionnels
  isolés (choix 6/12, garde-fou en dessous du minimum, option non jouable
  bloquée avec message, aucune régression sur Tròba/Vertadièr/Duèl/Quiz),
  vérification via les vraies routes admin (`/admin/config/gamepad/assign`,
  `/admin/config/keyboard/assign`) que les actions `up`/`down` sont bien
  assignables et affichées sur la page Configuration, et vérification
  visuelle complète (Playwright/Chromium headless) : écran « Quantas cartas
  ? » avec les 2 options (dont le cas où la grande taille est grisée),
  grille 6×2 correcte pour 6 paires, déplacement bas puis droite confirmé
  case par case. Le correctif `install.sh` a été vérifié par lecture de code
  (`rsync --delete` + liste d'exclusions) plutôt que par un test d'exécution
  réelle du script (nécessiterait une VM Debian, hors de cet environnement
  de développement) — **à confirmer par Fabien lors de sa prochaine mise à
  jour réelle : les images/sons déjà en place doivent survivre**.
- **v0.83** (16/09/2026) — un bug signalé + trois évolutions demandées par
  Fabien. **Bug « le Memòria ne se lance pas, il dit pas d'objet »** : revue
  complète de `start_memoria` (`managers/game_controller.py`) — aucun bug
  fonctionnel trouvé (le calcul d'éligibilité et le lancement de partie
  étaient corrects), mais deux vrais défauts d'ergonomie expliquant très
  probablement le signalement : (1) le seuil minimum d'objets nécessaires
  pour jouer était fixe et le message refusant de lancer la partie ne
  donnait aucun chiffre — impossible de savoir s'il manquait 1 objet ou 10 ;
  (2) ce seuil (6 objets) n'était pas rappelé ailleurs dans l'admin. Les
  deux sont corrigés par l'évolution ci-dessous (taille de partie variable +
  message de diagnostic chiffré), qui répond donc directement au bug
  **et** à la demande d'évolution en une seule fois. **Taille de partie
  Memòria variable** (Memòria et Memòria vilatge) : au lieu d'un nombre de
  paires fixe (6), chaque partie tire désormais au hasard entre **10 cartes
  (5 paires)** et **20 cartes (10 paires)**, mais uniquement si assez de
  contenu est enregistré pour les deux tailles (`MEMORIA_PAIR_COUNT_LARGE`
  = 10 objets/vilatges actifs) — sinon la partie tombe automatiquement sur
  la petite taille (`MEMORIA_PAIR_COUNT_SMALL` = 5, qui est aussi le minimum
  requis pour pouvoir jouer). En dessous de ce minimum, l'écran menu affiche
  désormais un message précis (ex. « Pas pro d'objèctes actius per jogar a
  la Memòria (4 trobat(s), 5 necessaris al minimum) ») au lieu de bloquer
  silencieusement. Le tableau de bord admin rappelle les deux seuils.
  **Son de l'objet trouvé (Tròba l'objècte)** : le son associé à l'objet se
  joue désormais automatiquement dès qu'une réponse est donnée (bonne ou
  fausse — comme la révélation de l'image, déjà en place), pas seulement en
  mode Descobèrta (dépôt libre d'un objet sans jeu en cours, qui jouait déjà
  son son immédiatement — comportement inchangé, confirmé correct). Au
  passage, correctif d'anti-fuite : le nom de fichier audio de l'objet
  courant était envoyé au client en permanence, y compris avant toute
  réponse (fuite de donnée dormante, jamais exploitée côté client jusqu'ici)
  — il suit maintenant exactement la même règle que l'image (révélé
  uniquement une fois la réponse donnée). L'élément `<audio>` partagé a été
  déplacé hors de l'écran Descobèrta pour rester utilisable une fois
  l'écran caché. **Tròba l'objècte et Duèl Occitan limités à 10 questions**
  par manche (au lieu de 5 et 6 respectivement) — variables
  `TROBA_ROUND_WORD_COUNT`/`DUEL_ROUND_QUESTION_COUNT`, toujours des
  limites hautes : avec moins de contenu disponible, la manche utilise
  simplement tout ce qu'il y a, comme avant.
- **v0.82** (16/09/2026) — Fabien a signalé que le correctif v0.81 (partage
  bouton/touche entre plusieurs actions) **ne semblait pas fonctionner** chez
  lui, et a demandé (1) un numéro de version visible dans l'admin pour
  vérifier que la borne tourne bien sur le dernier code livré, et (2) une
  revue du mécanisme d'assignation clavier à la recherche d'un bug.
  **Numéro de version** : `config.APP_VERSION` (à mettre à jour à chaque
  archive, en même temps que le numéro en tête de ce README) est désormais
  affiché en bas de la barre latérale de l'admin **et sur la page de
  connexion elle-même** (donc consultable sans même taper le code PIN) —
  objectif : permettre de confirmer en un coup d'œil que le service tourne
  bien sur le code fraîchement déployé, et pas une version restée en mémoire
  après une mise à jour de fichiers sans redémarrage du service, ou une page
  servie depuis le cache du navigateur. **Revue du mécanisme d'assignation** :
  toute la chaîne (stockage `settings_manager`, routes `/admin/config/
  gamepad/assign` et `/admin/config/keyboard/assign`, rendu de la page
  Configuration, `window.MALETA_KEY_MAP` transmis au kiosque) a été
  retestée de bout en bout via les vraies routes Flask (pas seulement les
  fonctions internes) : un bouton/une touche assignés à deux actions
  différentes coexistent bien, se réassigner une des deux actions à un
  autre contrôle ne perturbe pas l'autre, retirer une touche d'une action
  ne retire pas les autres actions qui partagent cette même touche — tout
  fonctionne correctement dans ces tests. Un vrai bug **préexistant**, sans
  rapport direct avec le correctif v0.81, a tout de même été trouvé et
  corrigé au passage dans `managers/input_bus.py` : `InputBus.__init__`
  retombait à tort sur le mapping par défaut quand un mapping vide (`{}`,
  donc "falsy" en Python) lui était passé, au lieu de ne retomber sur le
  défaut que lorsqu'aucun mapping n'existe encore (`None`) — cas limite qui
  ne correspond pas au scénario décrit par Fabien (il ajoutait des
  assignations, il n'était pas parti d'un mapping entièrement vidé), mais
  corrigé par principe de précaution. **Hypothèse la plus probable pour le
  signalement de Fabien**, faute d'avoir pu reproduire un bug fonctionnel :
  un service non redémarré après le déploiement des fichiers v0.81 (`sudo
  bash install.sh` redémarre bien le service à sa toute fin — s'il n'a pas
  été relancé jusqu'au bout, ou si les fichiers ont été copiés à la main
  sans passer par ce script, l'ancien code v0.8 reste actif en mémoire même
  si les fichiers sur disque sont à jour), ou un navigateur Chromium kiosque
  qui sert `config.html`/`kiosk.js` depuis son cache plutôt que la version
  fraîchement déployée. Le numéro de version ajouté dans cette livraison est
  fait pour lever le doute sur ce point précis avant d'aller chercher plus
  loin.
- **v0.81** (16/09/2026) — correctif demandé par Fabien sur le mapping
  manette/clavier de la v0.8 : un même bouton (ou une même touche) doit
  pouvoir être assigné à **plusieurs actions différentes en même temps** —
  ex. le bouton A doit pouvoir à la fois valider un menu, répondre à un jeu
  à plusieurs réponses et retourner une carte au Memòria. Jusqu'ici,
  assigner un bouton déjà utilisé par une action à une nouvelle action
  remplaçait silencieusement l'ancienne assignation (les mappings étaient
  stockés `{contrôle: action}`, une seule action par contrôle). Les quatre
  mappings (bouton, hat, axe, touche) stockent désormais `{contrôle:
  [action, action, ...]}` — assigner un contrôle à une action l'AJOUTE à sa
  liste au lieu de l'écraser ; une action garde toujours un seul contrôle
  actif à la fois (comme avant), mais ce contrôle peut être partagé avec
  d'autres actions. Aucun risque de conflit à l'usage : `GameController.
  on_action()` ignore déjà toute action non pertinente pour l'écran affiché,
  donc un bouton partagé entre « select » et « answer_1 » ne déclenche que
  celui qui a un sens sur l'écran en cours. Migration automatique et
  transparente des mappings déjà enregistrés (l'ancien format à une seule
  action par contrôle continue d'être lu correctement). Aucun changement
  visible côté écrans admin — le tableau Configuration > Manèta & clavièr
  affiche toujours une ligne par action avec son contrôle assigné, une
  phrase d'aide a juste été ajoutée pour expliquer le partage possible.
- **v0.8** (15/09/2026) — évolution demandée par Fabien, en 7 points :
  (1) **Memòria redessiné** : chaque paire montre désormais le mot français
  d'un côté et le mot occitan de l'autre (au lieu d'une image + un mot) —
  jugé plus pertinent pédagogiquement, ça fait vraiment travailler la
  traduction ; (2) nouvelle activité **« Memòria vilatge »** : même
  mécanique, mais sur des noms de villes/vilatges (français ↔ occitan),
  avec sa propre section admin (**Admin > Vilatges**, contenu vide à la
  livraison, à saisir avec une source fiable, jamais improvisé) — les deux
  variantes partagent tout leur code (voir `MEMORIA_VARIANTS` dans
  `managers/game_controller.py`), seul le contenu change ; (3) **mapping
  clavier** (Configuration > Manèta & clavièr) : chaque action peut
  désormais recevoir une touche de clavier en plus d'un contrôle manette,
  les deux fonctionnant toujours ensemble, jamais l'un à la place de
  l'autre — voir « Mapping clavier » plus haut ; (4) nouvelle activité
  **« Quiz Calandreta »** : quiz solo à 3 réponses possibles (A/B/C), même
  structure que Vertadièr o Occitan avec un choix de plus, contenu vide à
  la livraison (**Admin > Quiz Calandreta**) ; (5) **correctif** : cliquer
  sur la roue crantée sans connaître le code PIN bloquait sur l'écran de
  connexion sans aucun moyen d'en sortir — un bouton « Tornar al quiòsc » y
  a été ajouté ; (6) le texte d'indice « Select · administracion » en bas à
  droite de l'écran d'accueil a été retiré (l'icône Admin elle-même reste,
  inchangée) ; (7) **refonte de l'écran d'accueil** : « Cadre fotó » n'est
  plus une grande tuile de jeu mais une petite icône sous la roue crantée de
  l'Admin (voir `MENU_EXTRA_ICONS`), pour que seules les vraies activités de
  jeu restent en grandes tuiles pour les visiteurs. Au passage, un bug de
  spécificité CSS pré-existant (v0.7) a été corrigé au passage sur l'écran
  Duèl Occitan : la bonne réponse révélée en fin de manche ne se colorait
  jamais réellement en rouge (elle restait visuellement indiscernable d'une
  réponse simplement "pas encore révélée"), à cause d'une règle de couleur
  neutre plus spécifique que la règle de couleur "bonne réponse" — corrigé
  du même coup pour le nouveau Quiz Calandreta, qui partage le même CSS.
- **v0.72** (15/09/2026) — nouvelle activité **« Memòria »**, jeu de paires
  100% écran/manette dont le principe avait été tranché avec Fabien le
  15/09/2026 : pas d'objet physique ni de lecteur NFC, la grille de cartes
  réutilise directement les objets déjà illustrés dans **Admin > Objèctes &
  tags** (image ↔ mot occitan), aucun contenu à créer et aucun nouveau
  bouton manette à assigner (◀ ▶ / Select / Back, déjà utilisés ailleurs).
  Un compteur « objets amb imatge (Memòria) » a été ajouté au tableau de
  bord admin. Au passage, revue de code ciblée sur les jeux existants :
  (1) correctif d'une race condition sur les minuteries internes (Tròba,
  Vertadièr, Duèl) — une minuterie de fin de manche pouvait, dans de rares
  cas, survivre à un retour au menu et interrompre plus tard une activité
  différente lancée entre-temps ; un compteur de génération ignore
  désormais silencieusement toute minuterie devenue obsolète (garde
  d'« epoch », voir `managers/game_controller.py`) ; (2) les noms de
  fichiers envoyés depuis l'admin (image/audio d'un objet, photo/vidéo,
  logo/croix de bannière) sont maintenant systématiquement nettoyés
  (`secure_filename`) avant écriture sur le disque, comme c'était déjà le
  cas pour la médiathèque — un nom de fichier contenant `/` pouvait
  auparavant provoquer une erreur serveur à l'upload. Aucune régression
  constatée sur les jeux existants (tests + vérification visuelle). Le
  serveur Flask reste volontairement lié à `0.0.0.0` (voir « Pas encore
  fait ») : décision assumée, pas un oubli.
- **v0.71** (15/09/2026) — les fichiers de police des maquettes
  (Caprasimo/Figtree) sont maintenant réellement vendorés dans
  `static/fonts/` (Fabien a fourni les `.ttf` originaux) : plus aucun
  repli sur les polices système, le rendu correspond enfin aux maquettes.
  Format `.woff` (et non `.woff2` comme prévu initialement) — la
  compression WOFF2 nécessite la bibliothèque `brotli`, indisponible
  dans l'environnement de développement ; WOFF (v1) est un format
  standard tout aussi supporté par les navigateurs modernes et tout
  aussi conforme à la contrainte 100% hors réseau, voir
  `static/fonts/README.md` pour le détail et comment repasser en
  `.woff2` plus tard si besoin. Licences SIL Open Font License des deux
  familles incluses (`static/fonts/OFL-*.txt`).
- **v0.7** (15/09/2026) — nouvelle activité **« Duèl Occitan »**, jeu à 2
  joueurs demandé par Fabien : une question de culture/langue occitane
  s'affiche avec 2 réponses possibles, et les deux joueurs répondent chacun
  de leur côté avec leurs propres boutons manette (4 nouvelles actions
  configurables, `Duèl Occitan : joueur 1/2 — réponse A/B`, à assigner
  depuis Configuration > Manette — aucun bouton par défaut, une manette SNES
  USB classique n'a pas assez de boutons libres pour deviner un mapping
  fiable). Même principe que Vertadièr o Occitan : contenu géré depuis
  **Admin > Duèl Occitan**, volontairement vide à la livraison, à construire
  avec une source fiable (CNRTL, Institut d'Estudis Occitan...), jamais
  improvisé. Le bouton « B » (abandonner vers le menu) reste inchangé et
  fonctionne pendant le Duèl comme dans les autres jeux. Nouvelle table
  `duel_questions` (aucune migration à faire à la main, `init_db()` la crée
  au démarrage). Au passage : les polices des maquettes (Caprasimo/Figtree)
  peuvent maintenant être vendorées localement dans `static/fonts/` (voir
  `static/fonts/README.md`) — le CSS les charge automatiquement si les
  fichiers sont présents, sinon aucun changement par rapport au repli
  système déjà en place depuis la v0.1.
- **v0.6** (14/09/2026) — corrections et ajouts suite aux retours de Fabien
  sur la v0.5 : (1) la croix/logo de l'écran d'accueil n'avait aucune taille
  imposée en CSS pour une image importée (elle s'affichait à sa taille
  naturelle) — corrigé, et le nom « La Maleta Occitana » est maintenant
  nettement plus grand et positionné juste sous les logos (au lieu d'être
  épinglé en haut, séparé du reste par un grand vide) ; (2) se déconnecter
  depuis l'admin ramène maintenant à l'écran d'accueil du kiosque plutôt
  qu'à l'écran de connexion admin ; (3) **Admin > Médiathèque** affiche
  désormais un aperçu (miniature image, lecteur audio) et un bouton
  poubelle par fichier, avec confirmation renforcée si le fichier est
  encore utilisé quelque part ; (4) le jeu **Tròba l'objècte** révèle
  maintenant l'image de l'objet au moment du retour visuel (correct/faux/
  temps écoulé) — elle n'apparaissait nulle part auparavant, seul le mot
  occitan s'affichait ; (5) tous les champs d'upload de l'admin (image/
  audio d'un objet, photo/vidéo du diaporama, logo/croix de la bannière)
  proposent maintenant un bouton **« Choisir dans la médiathèque »** pour
  réutiliser un fichier déjà présent sur le disque, en plus de l'upload
  depuis l'ordinateur. Aucune de ces corrections ne touche au comportement
  de jeu déjà en place (scores, timers, thèmes, manette).
- **v0.5** (14/09/2026) — refonte visuelle complète du kiosque et de
  l'admin à partir des maquettes transmises par Fabien (fond terracotta et
  cartouches arrondies sur l'accueil, tuiles à icônes, réponses Vertadièr
  en grands blocs de couleur, admin réorganisée en barre latérale
  « Contengut »/« Sistèma » avec Configuration en grille de cartes). Aucun
  changement de comportement, voir « Refonte visuelle » plus haut.
- **v0.4** (14/09/2026) — la croix directionnelle est désormais détectée
  quel que soit son mécanisme côté pygame/SDL : ajout du support des **axes
  analogiques dédiés** (`JOYAXISMOTION`) dans `managers/input_bus.py`, en
  plus du hat et des boutons déjà supportés. C'est ce troisième mécanisme
  qui expliquait que la croix restait totalement muette (pas même
  capturable dans l'écran « Réassigner ») malgré le correctif v0.3 sur
  certaines manettes. Configuration > Manette affiche maintenant le type de
  contrôle assigné à chaque action (bouton / hat / axe).
- **v0.3** (14/09/2026) — gauche/droite (croix directionnelle) ajoutés aux
  actions reconfigurables de Configuration > Manette, pour les manettes qui
  remontent leur croix directionnelle comme des boutons plutôt que comme un
  « hat » (cause du signalement « les flèches ne répondent pas »). Insuffisant
  à lui seul pour les manettes à axes dédiés — voir v0.4.
- **v0.2** (14/09/2026) — nom « La Maleta Occitana » affiché sur l'écran
  titre ; nouveau menu **Admin > Configuration** (mot de passe, bannière
  logo/croix personnalisable, 4 thèmes de couleur occitans, remapping des
  boutons de la manette) ; nouvelle **Admin > Médiathèque** (fichiers
  utilisés/orphelins, espace disque) ; nouveau jeu **« Vertadièr o Occitan »**
  (vrai/faux sur l'origine occitane d'un mot, réponse à la manette, contenu à
  saisir depuis l'admin — rien n'est pré-rempli). Tous les réglages
  personnalisables depuis l'admin vivent désormais dans une table `settings`
  en base (voir `managers/settings_manager.py`), les variables
  d'environnement de `config.py` ne servent plus que de valeurs par défaut.
- **v0.1** (14/09/2026) — renommage complet Malissa → Maleta (dossier,
  service systemd, utilisateur Linux, variables d'environnement, base de
  données) ; fonctionnement 100% local (police système au lieu de Google
  Fonts) ; `install.sh` unique et rejouable pour l'installation comme pour
  les mises à jour ; structure de zip avec dossier racine `maleta-occitana/`.
