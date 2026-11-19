# Cahier des charges — Jòcs amagats (jeux cachés)

**Statut : réalisé en v1.3** (lots 0 à 5 ; lot 6 « options » non fait) — écarts
avec ce document en fin de page (§ 12). Maquettes : [`maquettes/jocs-amagats/`](maquettes/jocs-amagats/).
Demandes et remarques pour l'équipe aprene : [`aprene-demandes.md`](aprene-demandes.md).

## 1. Objectif

Ajouter à la Maleta des **jeux absents du menu des visiteurs**, lancés uniquement depuis l'administration :

1. **aprene** — la compétition en ligne d'aprene (`https://aprene.appsdoc.fr/competicion`), pour animer un stand
   avec des jeux occitans plus poussés. Borne **et** version démo.
2. **Centre de jòcs** — un petit centre d'émulation **NES, Super NES, Mega Drive et Atari 2600** (Super NES et Atari 2600 depuis la v1.33), avec sa bibliothèque de jeux et son
   réglage de manette. Borne uniquement.

Pour que la borne puisse joindre aprene : **réglages Wi-Fi dans l'admin** (borne uniquement).

## 2. Décisions prises

| Sujet | Décision |
|---|---|
| Accès | Uniquement depuis **Admin > Jòcs amagats** (sur la borne ou depuis un PC via tunnel SSH). Aucune tuile dans le menu visiteurs. |
| Sortie | **Échap** (le clavier reste toujours branché sur la borne) ; bouton « Arrêter » dans l'admin. |
| Sortie d'aprene | **Double Échap** : 1er appui = bandeau « Quitar aprene ? », 2e appui = retour à la Maleta (Échap sert aussi à fermer des fenêtres sur aprene). |
| Compte aprene | On garde **`compet` / `compet`** pour l'instant (saisis dans l'admin, jamais dans le code). |
| Manette sur aprene | **Oui, pour les joueurs** : croix = se déplacer entre les réponses, A = valider. Le maître du jeu règle la compétition **au clavier et à la souris**. |
| Démo | **aprene seulement** (pas de centre de jeux, pas de Wi-Fi). |
| ROM | La Maleta fournit l'émulateur ; les fichiers de jeux sont **ajoutés par l'école**, jamais livrés (voir § 6.5). |

## 3. Constat sur aprene (archive fournie, version v6.x)

- `frame-ancestors 'none'` (en-tête CSP) : **aprene ne peut pas s'afficher à l'intérieur d'une page de la
  borne**. La borne envoie donc **son navigateur directement sur aprene**, puis le ramène (§ 5.2).
- Le compte de rôle « compétition » est redirigé d'office vers `/competicion` : il ne voit rien d'autre.
- Connexion : formulaire `POST /connexion` (champs `identifiant`, `mdp`, `next`), pas de jeton anti-rejeu :
  la connexion automatique par remplissage du formulaire fonctionne sans changement côté aprene.
- Cookie de session `aprene` (SameSite=Lax, 30 jours) — sans effet ici : le navigateur de la borne tourne en
  navigation privée, la connexion est refaite à chaque lancement.
- Les questions de compétition sont des choix (pas de texte libre) : jouables à la manette par simple
  navigation entre boutons (Tab / Entrée), même sans raccourcis clavier côté aprene.

## 4. Cadre commun

### 4.1 Page Admin > Jòcs amagats

Maquette : `admin-1-jocs-amagats.png`.

- Nouveau lien **Jòcs amagats** dans la barre latérale (section Sistèma).
- Bandeau d'état : ce qui tourne sur la borne en ce moment + bouton **Arrêter et revenir au menu**.
- Carte **aprene** : adresse, identifiant, mot de passe (masqué), case « Manette pour les joueurs »,
  boutons **Lancer sur la borne** et **Tester la connexion**, lien vers les réglages Wi-Fi.
- Carte **Centre de jòcs** : nombre de jeux actifs par console, état du réglage manette, bouton **Lancer**,
  liens Bibliothèque et Manette.
- Lancer depuis un PC (tunnel SSH) ouvre le jeu **sur l'écran de la borne**, pas sur le PC.

### 4.2 Mode « application externe » (serveur)

- Nouvel état du `GameController` : `externe` (avec le nom du jeu caché en cours).
- Dans cet état, les actions habituelles (manette lue par la borne, tags NFC, clavier du kiosque) sont
  **ignorées** — sauf la sortie.
- Retour au menu par : Échap (§ 4.3), bouton « Arrêter » de l'admin, ou fin anormale (page aprene qui ne
  charge pas, déconnexion du compte, émulateur qui plante).
- Option : retour automatique au menu après N minutes sans activité (réglable, désactivable — désactivé par
  défaut pendant une compétition).

### 4.3 Pilotage du navigateur de la borne

- `install.sh` lance Chromium avec son **port de pilotage** (`--remote-debugging-port`, accessible
  **uniquement depuis la borne elle-même**, `127.0.0.1`).
- La Maleta s'en sert pour : envoyer le navigateur sur aprene, le ramener sur la borne, **ajouter sur les
  pages d'aprene** la gestion d'Échap, le bandeau de confirmation et la manette (§ 5.4).
- Indispensable aussi en cas de coupure réseau : sans lui, la borne resterait bloquée sur une page d'erreur
  du navigateur.
- Le centre de jòcs, lui, reste dans la page de la borne : il n'utilise pas ce pilotage.

## 5. aprene (borne et démo)

### 5.1 Lancement

Maquettes : `borne-3-aprene-connexion.png`, `borne-4-aprene-sens-ret.png`.

1. Écran « Competicion aprene » : vérification de la connexion internet puis d'aprene (`/healthz`).
2. En cas d'échec : message clair (« Pas de connexion internet », « aprene ne répond pas »), rappel du
   chemin vers les réglages Wi-Fi, retour automatique au menu au bout de 10 s ou sur A / Échap.
3. Connexion automatique au compte compétition (identifiant et mot de passe de l'admin).
4. Ouverture de `/competicion`. Le maître du jeu règle la compétition au clavier et à la souris (le
   pointeur, masqué par la borne, réapparaît dès que la souris bouge).

### 5.2 Affichage

Le navigateur de la borne quitte la page de la Maleta et affiche aprene **en plein écran, tel quel**. La
Maleta ajoute seulement, par-dessus les pages d'aprene, un petit rappel en bas à droite
(« Échap ×2 : quitar · Manèta : ✥ causir, A validar »).

### 5.3 Sortie par double Échap

Maquette : `borne-5-aprene-quitar.png`.

- 1er Échap : bandeau en haut de l'écran « **Quitar aprene e tornar a la Maleta ?** Torna quichar Échap per
  confirmar — tota autra tòca : contunhar ».
- 2e Échap dans les 5 s : déconnexion du compte compétition (`POST /deconnexion`) puis retour au menu de la
  Maleta. Toute autre touche, ou 5 s sans rien : le bandeau disparaît.
- Sortie automatique si la page d'aprene ne se charge plus, ou si le compte est déconnecté.

### 5.4 Manette pour les joueurs

- Pendant aprene, la manette de la borne est convertie en touches : **croix** = passer d'une réponse à
  l'autre (Tab / Maj+Tab, ou flèches), **A** = Entrée (valider), **B** = rien (pas de retour arrière
  accidentel en pleine partie).
- La réponse sélectionnée est mise en évidence par un cadre épais (ajouté par la Maleta sur la page).
- Activable / désactivable dans la carte aprene de l'admin.

### 5.5 Version démo

- Même carte aprene dans **Admin > Jòcs amagats** de la démo (pas de Wi-Fi, pas de centre de jòcs).
- La fenêtre de la démo charge aprene elle-même et y ajoute le double Échap et le rappel ; pas de pilotage
  de navigateur nécessaire.
- La manette de la démo est convertie de la même façon si une manette est branchée sur le PC.

## 6. Centre de jòcs (borne uniquement)

### 6.1 Écran de la borne

Maquettes : `borne-1-centre-de-jocs.png`, `borne-2-partida.png`.

- Même style que le menu « Tria un jòc » : une tuile par jeu actif (titre, console, nombre de joueurs,
  jaquette si fournie). Navigation à la manette ou au clavier, A / Entrée pour jouer.
- **Échap** : depuis le centre → retour au menu de la Maleta ; pendant une partie → retour au centre de jòcs.
- En partie : l'image du jeu occupe la hauteur de l'écran (proportions d'origine), fond noir, rappel discret
  « Échap · tornar al centre de jòcs ».

### 6.2 Émulateur

- **EmulatorJS** (émulateurs libretro compilés pour le navigateur) : moteur NES et moteur Mega Drive
  (Genesis Plus GX), **installés sur la borne** (fonctionne hors réseau, rien chargé depuis internet).
- Son par le navigateur ; 1 ou 2 joueurs.
- **Repli** si la borne est trop lente pour la Mega Drive : RetroArch installé sur Debian, lancé par-dessus le
  navigateur et refermé par Échap — à décider après mesure sur la borne réelle.

### 6.3 Bibliothèque des jeux

Maquette : `admin-3-bibliotheque.png`.

- Page **Admin > Jòcs amagats > Bibliotèca** : envoi de plusieurs fichiers d'un coup ; console reconnue à
  l'extension — NES `.nes` (≤ 1 Mo), Mega Drive `.md .gen .bin .smd` (≤ 8 Mo).
- Par jeu : titre, console, nombre de joueurs, jaquette facultative, actif / inactif, ordre.
- Fichiers rangés dans `media/roms/` (protégé lors des mises à jour comme le reste de `media/`).

### 6.4 Réglage de la manette

Maquette : `admin-4-manette.png`.

- Page **Admin > Jòcs amagats > Manèta** : un tableau par console et par joueur (1 et 2), une ligne par
  bouton de la console, colonnes Manette et Clavier, bouton **Assignar** puis appui sur le bouton voulu
  (comme la page Configuration actuelle).
- Lecture de la manette **par le navigateur de la borne** (gère aussi les manettes USB bon marché aux
  boutons « non standard ») ; zone **Tester la manette** où les boutons s'allument.
- Valeurs par défaut pour une manette SNES : NES A ← A, B ← B ; Mega Drive A ← Y, B ← B, C ← A ;
  Select / Start à l'identique. Option **manette 6 boutons** (X, Y, Z, Mode).
- Clavier par défaut (joueur 1) : flèches, X / W / C, Entrée, Maj.

### 6.5 Fichiers de jeux (ROM) et licences

- Les jeux du commerce (ex. Super Mario Bros. 3) sont protégés par le droit d'auteur : la Maleta **ne livre,
  ne télécharge et n'exporte aucune ROM**. Elles sont ajoutées par l'école, sous sa responsabilité (copie de
  ses propres cartouches). Les jeux libres « homebrew » sont une alternative sans souci.
- `media/roms/` est exclu des exports de contenu, des releases et de git.
- EmulatorJS et les moteurs libretro sont sous licences libres (GPL ; Genesis Plus GX : usage non
  commercial) : à garder comme composants séparés, licences citées dans `static/`.

### 6.6 Sauvegardes de partie (option)

Le navigateur de la borne efface tout au redémarrage : les sauvegardes de partie seraient à enregistrer
côté borne (par jeu). Non prévu au premier lot.

## 7. Wi-Fi (borne uniquement)

Maquette : `admin-2-wifi.png`.

- `install.sh` installe **NetworkManager** et une règle d'autorisation permettant à l'utilisateur de l'appli
  de gérer le Wi-Fi (même principe que les règles polkit du lecteur NFC).
- Page **Admin > Configuracion > Wi-Fi** : état (réseau, adresse IP, internet, aprene joignable), liste des
  réseaux avec force du signal, connexion avec mot de passe, réseau caché, oublier un réseau, actualiser.
- Les mots de passe Wi-Fi sont gardés par le système : jamais dans la base de la Maleta, jamais exportés,
  jamais réaffichés.
- Tout le reste de la borne continue de fonctionner **sans réseau**.

## 8. Sécurité

- Identifiant et mot de passe aprene : dans les réglages de la borne, champ masqué, exclus des exports.
- Port de pilotage du navigateur : `127.0.0.1` uniquement.
- Lancement des jeux cachés : uniquement depuis l'admin (protégée par le code PIN).
- Bibliothèque : extensions et tailles contrôlées, noms de fichiers assainis.

## 9. Découpage en lots

| Lot | Contenu | Où | Dépend de |
|---|---|---|---|
| 0 | Page Jòcs amagats, état `externe`, sortie Échap, bouton Arrêter, pilotage du navigateur (`install.sh`) | borne | — |
| 1 | Wi-Fi dans l'admin | borne | test sur la borne réelle |
| 2 | aprene : vérifications, connexion auto, double Échap, rappel, sorties de secours | borne + démo | 0, 1 |
| 3 | Manette → touches pour les joueurs d'aprene | borne + démo | 2 |
| 4 | Centre de jòcs : bibliothèque, écran, EmulatorJS NES + Mega Drive installé sur la borne | borne | 0 |
| 5 | Réglage de la manette de l'émulateur (2 joueurs, clavier, test) | borne | 4 |
| 6 | Options : sauvegardes de partie, retour automatique après inactivité | borne | 4 |

## 10. Vérifications prévues

- Tests automatiques : état `externe` (actions ignorées, sorties), réglages aprene (masqués, non exportés),
  bibliothèque (extensions, tailles, exclusion des exports), réglage manette (enregistrement, valeurs par
  défaut).
- Navigateur de test : écrans centre de jòcs et partie, bandeau double Échap, conversion manette sur une
  page de test imitant aprene.
- **Sur la borne réelle** (impossible ici) : Wi-Fi, fluidité de la Mega Drive sur le petit PC, manettes
  USB réelles, compétition aprene complète.

## 11. Risques et points ouverts

- **Performance Mega Drive** sur le petit PC : à mesurer tôt (lot 4) ; repli RetroArch.
- **Évolutions d'aprene** : si la page de connexion change, la connexion automatique est à adapter (un lien
  de connexion par jeton côté aprene supprimerait ce risque, voir [`aprene-demandes.md`](aprene-demandes.md)).
- **Mot de passe `compet`** : connu de tous (README d'aprene, comptes de test) ; à changer avant
  l'ouverture au public, puis à reporter dans l'admin de la borne.

## 12. Réalisation (v1.3) et écarts

- Lots 0 à 5 réalisés ; **lot 6 non fait** (sauvegardes de partie, retour
  automatique après inactivité dans le centre de jòcs).
- **Version démo, messages vers la borne** : la politique de sécurité d'aprene
  (CSP `script-src 'self'`, `default-src 'self'`) bloque le pont JavaScript de
  la fenêtre de la démo et toute requête vers la borne. Le script ajouté sur
  aprene renvoie donc la fenêtre sur `/externe/retour?message=…` de la borne
  (une navigation n'est jamais bloquée). Sur la borne, le pilote Chromium a son
  propre canal, sans ce détour.
- **Capture des boutons de manette** : faite par l'écran de la borne (et par la
  page de réglage si elle est ouverte sur la borne), pour que le réglage marche
  aussi depuis un PC distant (tunnel SSH), où la manette n'est pas branchée.
- **Vérifié** : avec le code d'aprene fourni (lancé localement) et un vrai
  Chromium piloté — connexion automatique, arrivée sur `/competicion`,
  manette, double Échap, mot de passe refusé, aprene injoignable ; la même
  chose dans la fenêtre de la démo sous Linux (WebKitGTK) ; NES et Mega Drive
  démarrent dans l'émulateur (ROM de test générées, aucun jeu réel), sans
  aucune requête hors de la borne ; Wi-Fi avec un faux `nmcli`.
- **À vérifier sur le matériel réel** : Wi-Fi (NetworkManager), fluidité de la
  Mega Drive sur le petit PC, manettes USB (y compris le réglage à distance),
  compétition aprene en ligne, démo aprene sous Windows (WebView2).

## 13. Évolutions v1.33

- **Fluidité** : la page de jeu n'utilise plus le mode « debug » d'EmulatorJS,
  qui rendait l'émulateur verbeux et faisait chuter le jeu de 60 à ~45 images/s
  après quelques secondes (NES et Mega Drive, carte Intel HD 530 pourtant bien
  utilisée). `emulator.min.js` est assemblé par `packaging/fetch_emulatorjs.sh`.
- **Super NES** (Snes9x, `.sfc .smc`, ≤ 8 Mo) et **Atari 2600** (Stella 2014,
  `.a26 .bin`, ≤ 512 Ko). `.bin` ≤ 64 Ko → Atari 2600, sinon Mega Drive ;
  console modifiable dans la bibliothèque.
- **Jaquettes** : affichées en grand dans les tuiles ; recherche automatique
  dans la base libre de vignettes de libretro (thumbnails.libretro.com,
  noms « No-Intro », version France > Europe > Monde > USA), à l'ajout d'un jeu
  ou par bouton ; image jointe du même nom que le jeu ; ajout manuel.
  Code : `managers/cover_lookup.py`.
