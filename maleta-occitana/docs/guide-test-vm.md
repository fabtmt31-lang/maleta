# Guide de test en machine virtuelle

Objectif : valider l'installation Debian « ligne de commande » + le kiosque
Chromium + le lecteur OMNIKEY (PC/SC) + la manette Super NES **avant** de
toucher au petit PC réel, en pouvant recommencer facilement à chaque essai.

## 1. Choix de l'hyperviseur

**VirtualBox** est le plus simple à utiliser pour ce cas précis (accès USB au
lecteur Omnikey et à la manette depuis un PC de développement Windows) :

- Installer VirtualBox **et** son *Extension Pack* (obligatoire pour le
  passthrough USB 2.0/3.0 — sans lui, seul l'USB 1.1 est disponible, souvent
  trop limité pour un lecteur PC/SC).
- Alternative sur Linux/WSL2 : QEMU/KVM + `virt-manager`, avec le module
  `usbredir` ou l'attachement direct du device USB à la VM (`virsh
  attach-device`). Fonctionne aussi bien mais configuration plus manuelle.

## 2. Créer la VM

- ISO : Debian **netinst** (stable), architecture `amd64` — c'est la même
  architecture que le petit PC réel, donc les paquets et pilotes testés en VM
  sont directement représentatifs.
- Ressources conseillées : 2 vCPU, 2 à 4 Go de RAM, 20 Go de disque (largement
  suffisant pour Debian CLI + l'app + les médias objets/audio).
- **Avant** de lancer l'installation Debian : dans les réglages de la VM,
  activer un contrôleur **USB 2.0 (EHCI)** ou **3.0 (xHCI)** — pas seulement le
  contrôleur USB 1.1 par défaut.
- Activer aussi un contrôleur audio (ex. ICH AC97 ou HD Audio) : sans ça, la
  lecture audio (python-vlc) échouera en VM, alors qu'elle fonctionnera très
  bien sur le petit PC réel — à ne pas confondre avec un vrai bug applicatif.

## 3. Installation Debian : écran « sélection de logiciels »

C'est l'étape qui correspond à « Debian en ligne de commande » :

- **Décocher** « Environnement de bureau Debian » et le bureau proposé
  (GNOME/etc.), ainsi que « serveur d'impression ».
- **Garder** « utilitaires système standard ».
- **Cocher** « serveur SSH » : pratique pour copier les fichiers du projet
  dans la VM et déboguer à distance depuis le PC de dev, sans devoir tout
  faire au clavier branché sur la VM.

## 4. Snapshot de référence

Juste après l'installation Debian de base (avant `install.sh`),
prendre un **snapshot**. Ça permet de relancer le script d'installation à
l'identique à chaque itération sans repasser par l'installeur Debian complet
— précieux pendant la mise au point du kiosque et des règles polkit.

## 5. Copier le projet dans la VM

Par SSH (le plus simple) — décompresser d'abord l'archive `maleta-occitana-vX.Y.zip`
en local de façon à obtenir un dossier `maleta-occitana/`, puis :

```bash
scp -r maleta-occitana/ maleta@<ip-de-la-vm>:~/
```

Le nom du dossier (`maleta-occitana`, directement à la racine du zip depuis
la version v0.1) est important : `install.sh` se repère tout seul par rapport
à son propre emplacement, donc il doit rester dans ce dossier tel quel.

Ou, si SSH n'est pas activé, via un dossier partagé VirtualBox (Guest
Additions requises) ou une clé USB virtuelle.

## 6. Passthrough USB : lecteur Omnikey et manette

Une fois la VM démarrée :

- Brancher le lecteur Omnikey sur la machine hôte.
- Dans VirtualBox : menu **Périphériques > USB**, cocher le lecteur Omnikey
  (ou créer un filtre USB permanent dans les réglages de la VM, pratique pour
  ne pas avoir à recocher à chaque redémarrage).
- Faire de même pour la manette Super NES (USB HID standard — aucun pilote
  particulier requis côté VM).
- ⚠️ Si l'hôte est **Linux** et fait tourner `pcscd` localement, arrêter ce
  service côté hôte (`sudo systemctl stop pcscd`) le temps du test, sinon
  l'hôte peut capter le lecteur avant la VM. Sur un hôte Windows, ce conflit
  ne se pose généralement pas (pas de `pcscd` natif).

## 7. Lancer install.sh

```bash
cd ~/maleta-occitana
sudo bash install.sh
```

Aucun argument à passer : le script installe toujours le contenu du dossier
où il se trouve. La même commande, rejouée telle quelle, sert aussi à mettre
à jour une installation existante (voir le récapitulatif affiché en fin
d'exécution).

## 8. Vérifier le lecteur indépendamment de l'app

Avant de tester l'app complète, valider que le lecteur est bien vu par le
système :

```bash
pcsc_scan
```

(paquet `pcsc-tools`, déjà installé par le script) — doit afficher le lecteur
Omnikey et réagir en temps réel à la pose/au retrait d'un tag. Si rien
n'apparaît : vérifier le passthrough USB (étape 6), puis `systemctl status
pcscd`, puis les règles polkit (`/etc/polkit-1/rules.d/50-pcscd-headless.rules`).

## 9. Résolution d'écran en VM

Sans carte graphique dédiée, le serveur X en VM peut se limiter à une
résolution basse par défaut. Pistes si l'affichage du kiosque est trop petit :

- Installer les **Guest Additions** VirtualBox pour un pilote graphique
  correct et une résolution ajustable.
- Ou fixer une résolution manuellement dans `.xinitrc` avec `xrandr` avant de
  lancer Chromium.

Ce problème est spécifique à la VM : sur le petit PC réel, branché sur un
vrai écran, la sortie vidéo native du PC s'en charge normalement sans réglage
particulier.

## 10. Test de bout en bout

Redémarrer la VM et vérifier la chaîne complète, sans rien taper au clavier :

1. Démarrage → connexion automatique sur tty1 → `startx` automatique
2. Chromium s'ouvre en plein écran sur `http://127.0.0.1:5000`
3. Poser un vrai tag NFC sur le lecteur Omnikey → l'écran de découverte
   s'affiche, le son de prononciation se joue

Si les 3 fonctionnent en VM, `install.sh` peut être exécuté tel quel sur le
petit PC réel — même script, seul le matériel change.

## Limites d'une VM à garder en tête

- Le comportement USB (latence, réinitialisation à la reconnexion) peut
  différer légèrement du matériel réel ; un test propre en VM est une
  **première validation**, pas une garantie absolue sur le petit PC final.
- Le son en VM dépend de la configuration audio de l'hyperviseur, pas
  toujours représentative du petit PC (carte son réelle).
- Les performances graphiques (accélération) sont en général moindres en VM
  qu'avec une vraie sortie vidéo — si Chromium rame en VM sans accélération
  matérielle, ce n'est pas forcément un problème sur le PC réel.
