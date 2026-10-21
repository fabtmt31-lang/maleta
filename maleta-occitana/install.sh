#!/usr/bin/env bash
#
# install.sh — installe (premiere fois) OU met a jour (fois suivantes) La
# Maleta Occitana sur un petit PC Debian en ligne de commande (sans
# environnement de bureau).
#
# Usage — toujours pareil, premiere installation comme mise a jour :
#
#   cd ~/maleta-occitana
#   sudo bash install.sh
#
# Le script se repere tout seul : il installe TOUJOURS le contenu du dossier
# dans lequel il se trouve lui-meme (~/maleta-occitana si tu as decompresse
# l'archive normalement) vers /opt/maleta-occitana, quel que soit l'endroit
# d'ou tu lances la commande. Pas de "$(pwd)" ni de nom d'utilisateur a
# passer en argument -- c'est fait expres pour qu'une mise a jour soit aussi
# simple que l'installation initiale : decompresser la nouvelle archive au
# meme endroit (~/maleta-occitana) puis relancer exactement la meme commande.
#
# Remplace install_debian.sh (etapes 1-2) : le nom du dossier/service change
# (voir "Renommage Malissa -> Maleta" dans le concept), et le script devient
# rejouable a volonte pour les mises a jour, plutot qu'un copier/coller
# manuel de commandes a chaque fois (source d'erreurs, voir l'historique du
# 14/09/2026 -- dossier d'extraction incorrect, .venv supprime par erreur,
# rsync manquant...).
#
# Teste d'abord en machine virtuelle (voir docs/guide-test-vm.md) avant
# execution sur le petit PC reel -- le script est le meme dans les deux cas.

set -euo pipefail

# Dossier source : toujours celui qui contient ce script, jamais le
# repertoire courant du terminal (evite l'erreur classique "j'ai lance la
# commande depuis le mauvais dossier").
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APP_DIR="/opt/maleta-occitana"
APP_USER="maleta"
SERVICE_NAME="maleta-occitana"
VENV_DIR="${APP_DIR}/.venv"

if [ "$(id -u)" -ne 0 ]; then
    echo "Ce script doit être lancé avec sudo (règles polkit, systemd, création d'utilisateur)." >&2
    exit 1
fi

if [ ! -f "${SOURCE_DIR}/requirements.txt" ]; then
    echo "!! ${SOURCE_DIR} ne ressemble pas à un dossier du projet (pas de requirements.txt)." >&2
    echo "   Lance ce script depuis le dossier où l'archive a été décompressée." >&2
    exit 1
fi

FIRST_INSTALL=1
if [ -d "${APP_DIR}" ]; then
    FIRST_INSTALL=0
    echo "== Installation existante détectée dans ${APP_DIR} -> mode mise à jour =="
else
    echo "== Aucune installation existante -> mode première installation =="
fi

echo "== 1. Paquets système =="
apt-get update
apt-get install -y \
    python3 python3-venv python3-pip python3-dev build-essential swig \
    rsync \
    pcscd libpcsclite-dev libpcsclite1 pcsc-tools \
    libvlc-dev vlc \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libfreetype6-dev libportmidi-dev libjpeg-dev libpng-dev \
    fonts-dejavu-core fonts-noto-core \
    xserver-xorg xinit x11-xserver-utils unclutter chromium \
    git curl
# - libsdl2-*-dev/libfreetype6-dev/libportmidi-dev/libjpeg-dev/libpng-dev :
#   filet de securite pour pygame (compilation depuis les sources si jamais
#   aucun wheel precompile ne correspond).
# - rsync : necessaire a l'etape 5 ci-dessous (copie du code source), et sert
#   aussi si Fabien veut re-synchroniser le dossier a la main.
# - fonts-dejavu-core/fonts-noto-core : polices systeme installees localement
#   (aucun telechargement Google Fonts au demarrage du kiosque -- la borne
#   doit fonctionner sans reseau, voir kiosk.html/kiosk-base.css).

echo "== 2. Utilisateur applicatif =="
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    # groupe "plugdev" utile pour l'accès USB direct (manette) sans sudo ;
    # "audio" pour la sortie son
    useradd --create-home --shell /bin/bash --groups plugdev,audio "${APP_USER}"
    echo "Utilisateur '${APP_USER}' créé. Pense à lui définir un mot de passe si besoin (passwd ${APP_USER})."
fi

echo "== 3. Service pcscd =="
systemctl enable pcscd
systemctl restart pcscd

echo "== 4. Règles polkit pour un accès headless à pcscd =="
# Sans session graphique active (cas d'un Debian CLI), polkit refuse par défaut
# l'accès au lecteur PC/SC. Deux règles distinctes sont nécessaires — même
# principe que celles déjà validées sur Histoires du Soir (Raspberry Pi OS).
mkdir -p /etc/polkit-1/rules.d
cat > /etc/polkit-1/rules.d/50-pcscd-headless.rules <<'EOF'
// Autorise l'accès au démon pcscd sans session graphique active (borne headless).
// Deux actions distinctes à autoriser explicitement (cf. leçons Histoires du Soir).
polkit.addRule(function(action, subject) {
    if (action.id == "org.debian.pcsc-lite.access_pcsc") {
        return polkit.Result.YES;
    }
});

polkit.addRule(function(action, subject) {
    if (action.id == "org.debian.pcsc-lite.access_card") {
        return polkit.Result.YES;
    }
});
EOF
systemctl restart polkit || true

echo "== 5. Copie du code applicatif =="
# rsync plutôt qu'un simple "cp -r" : ne touche jamais l'environnement
# virtuel (.venv) ni la base de données (maleta.db) déjà en place -- une mise
# à jour ne doit ni tout réinstaller, ni effacer le contenu déjà saisi dans
# l'admin (objets, tags, médias). __pycache__ est aussi ignoré (résidu de
# dev, jamais utile à copier).
#
# BUG CORRIGE EN v0.9 (16/09/2026, signale par Fabien) : "media" ne faisait
# PAS partie de cette liste d'exclusions. Or l'archive livree contient un
# dossier "media/" (avec seulement des fichiers .gitkeep vides -- structure
# de dossiers, aucun contenu reel). Avec `--delete`, rsync synchronise
# ${APP_DIR} pour qu'il devienne identique a ${SOURCE_DIR} : tout fichier
# present cote APP_DIR mais absent cote SOURCE_DIR est supprime. Les vraies
# images/sons uploades par Fabien depuis l'admin (dans media/objects/images,
# media/objects/audio, media/library, media/branding) etaient donc EFFACES a
# chaque mise a jour, puisqu'ils n'existent evidemment pas dans l'archive de
# code fraichement decompressee. La base de donnees, elle, est exclue donc
# preservee -- d'ou le symptome exact signale : la fiche de l'objet garde le
# nom du fichier (ligne DB intacte), mais l'image/le son ne remonte plus
# nulle part (fichier physique disparu). "media" rejoint donc la liste des
# exclusions, exactement comme ".venv" et "maleta.db" : jamais touche par
# une mise a jour.
mkdir -p "${APP_DIR}"
rsync -a --delete \
    --exclude '.venv' \
    --exclude 'maleta.db' \
    --exclude 'media' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    "${SOURCE_DIR}/" "${APP_DIR}/"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

echo "== 6. Environnement virtuel Python =="
if [ ! -x "${VENV_DIR}/bin/python" ]; then
    sudo -u "${APP_USER}" python3 -m venv "${VENV_DIR}"
fi
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip
# Toujours rejoué, y compris en mise à jour : peu coûteux si rien n'a changé
# (pip saute ce qui est déjà satisfait), indispensable si requirements.txt a
# changé entre deux versions.
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "== 7. Service systemd de l'application =="
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=La Maleta Occitana - app Flask/SocketIO
After=network.target pcscd.service
Wants=pcscd.service

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment=MALETA_HARDWARE=pc
# v1.03 : par defaut l'appli n'ecoute que sur 127.0.0.1 (acces a distance par
# tunnel SSH). Pour l'ouvrir aux autres appareils du reseau SANS que la
# prochaine mise a jour ne l'efface (ce fichier est regenere a chaque
# install.sh) : `sudo systemctl edit maleta-occitana`, y ajouter
#   [Service]
#   Environment=MALETA_HOST=0.0.0.0
# puis `sudo systemctl restart maleta-occitana`.
ExecStart=${VENV_DIR}/bin/python ${APP_DIR}/run_pc.py
Restart=on-failure
RestartSec=2
# Evite qu'un "systemctl stop/restart" reste bloque jusqu'a 90s (defaut
# systemd) si le process met du temps a reagir au SIGTERM : au bout de 10s
# sans reponse, systemd force l'arret (SIGKILL) au lieu d'attendre.
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
# restart (pas start) : fonctionne aussi bien pour une premiere installation
# (le service n'existe pas encore comme actif -> demarre simplement) que
# pour une mise a jour (redemarre pour charger le nouveau code).
systemctl restart "${SERVICE_NAME}"

echo "== 8. Kiosque Chromium sans environnement de bureau =="
# Pas de bureau installé : on démarre X manuellement au login sur tty1, puis
# Chromium en plein écran par-dessus. Alternative plus légère si ça pose
# problème en VM/GPU : le paquet "cage" (compositeur Wayland minimal), avec
# `cage -- chromium --kiosk http://127.0.0.1:5000` à la place du bloc X ci-dessous.

sudo -u "${APP_USER}" tee "/home/${APP_USER}/.xinitrc" > /dev/null <<'EOF'
#!/bin/sh
# Pas d'économiseur d'écran / de mise en veille sur une borne de stand
xset s off
xset s noblank
xset -dpms

# v1.02 (signalé par Fabien : "il manque 1/4 à droite, zone noire") : sur
# certaines machines/pilotes vidéo, le serveur X démarre sur une résolution
# par défaut différente de la résolution native réelle de l'écran (l'EDID
# n'est pas toujours lu correctement avant que X ne choisisse un mode) --
# kiosk-base.css remplit bien 100% de CE QUE X CROIT être l'écran (voir
# `html, body { width: 100%; height: 100% }`), donc si une bande reste
# noire, c'est que X utilise une résolution plus petite/différente de
# l'écran physique, pas un souci côté page web. `xrandr --auto` force
# chaque sortie vidéo à repasser sur son mode préféré/natif annoncé par
# l'écran -- corrige la grande majorité des cas sans configuration
# manuelle. Sans effet (donc inoffensif) si la résolution était déjà
# correcte. Si le problème persiste malgré ça, lister les modes
# disponibles avec `xrandr` (sans argument, depuis une session X) permet
# de forcer la bonne résolution à la main, ex. :
#   xrandr --output <nom-sortie> --mode 1920x1080
xrandr --auto 2>/dev/null || true

# Cache le curseur souris (inutile, pilotage 100% manette)
unclutter -idle 0.5 -root &

# Attend que le serveur Flask/SocketIO (service systemd) réponde avant
# d'ouvrir le navigateur, plutôt qu'un délai fixe fragile
for i in $(seq 1 30); do
    curl -s -o /dev/null http://127.0.0.1:5000/ && break
    sleep 1
done

# v1.11 (signalé par Fabien sur une machine physique : "Chromium ne prend que
# la moitié gauche de l'écran, zone noire à droite") : le dimensionnement
# automatique de --kiosk n'est pas fiable sans gestionnaire de fenêtres --
# Chromium lit la géométrie de l'écran trop tôt après le démarrage de X et
# garde une fenêtre plus petite que l'écran. Même problème, et même solution,
# que sur le projet « digital-signage » de Fabien (confirmé là-bas en VM comme
# sur matériel réel) : lire la résolution réelle avec xrandr et la donner
# EXPLICITEMENT à Chromium (--window-position=0,0 + --window-size), en
# neutralisant la mise à l'échelle HiDPI qui fausserait ce calcul.
detect_screen_resolution() {
    xrandr --current 2>/dev/null | grep -oE '[0-9]+x[0-9]+\+0\+0' | head -n 1 | cut -d'+' -f1
}
SCREEN_RES=""
for i in $(seq 1 10); do
    SCREEN_RES=$(detect_screen_resolution)
    [ -n "$SCREEN_RES" ] && break
    sleep 0.5
done
SCREEN_RES="${SCREEN_RES:-1920x1080}"  # repli si la détection échoue malgré tout
SCREEN_WIDTH="${SCREEN_RES%x*}"
SCREEN_HEIGHT="${SCREEN_RES#*x}"

exec chromium \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --incognito \
    --autoplay-policy=no-user-gesture-required \
    --force-device-scale-factor=1 \
    --high-dpi-support=0 \
    --window-position=0,0 \
    --window-size="${SCREEN_WIDTH},${SCREEN_HEIGHT}" \
    http://127.0.0.1:5000/
EOF
chmod +x "/home/${APP_USER}/.xinitrc"

# Démarre X automatiquement à l'ouverture de session sur tty1 uniquement
# (idempotent : n'ajoute le bloc au .bash_profile que s'il n'y est pas déjà,
# pour qu'une mise à jour ne le duplique pas à chaque exécution).
BASH_PROFILE="/home/${APP_USER}/.bash_profile"
if ! grep -q "startx" "${BASH_PROFILE}" 2>/dev/null; then
    sudo -u "${APP_USER}" tee -a "${BASH_PROFILE}" > /dev/null <<'EOF'

if [ -z "${DISPLAY:-}" ] && [ "$(tty)" = "/dev/tty1" ]; then
    startx
fi
EOF
fi

echo "== 9. Connexion automatique sur tty1 =="
mkdir -p "/etc/systemd/system/getty@tty1.service.d"
cat > "/etc/systemd/system/getty@tty1.service.d/autologin.conf" <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${APP_USER} --noclear %I \$TERM
EOF
systemctl daemon-reload

if [ "${FIRST_INSTALL}" -eq 1 ]; then
    RECAP_TITLE="== Installation terminée =="
else
    RECAP_TITLE="== Mise à jour terminée =="
fi

cat <<EOF

${RECAP_TITLE}

- Service applicatif : systemctl status ${SERVICE_NAME}
  (tourne avec MALETA_HARDWARE=pc -> lecteur OMNIKEY réel, pas le mode simulé)
- Lecteur NFC : pcsc_scan (paquet pcsc-tools) pour vérifier que l'OMNIKEY est
  détecté et réagit à la pose/au retrait d'un tag, indépendamment de l'app.
- Kiosque : redémarre la machine pour valider la chaîne complète (autologin
  tty1 -> startx -> Chromium plein écran sur http://127.0.0.1:5000).
- Pour du débogage sans tout redémarrer : \`sudo -u ${APP_USER} startx\` depuis
  une session locale.
- PIN admin par défaut : 1234 (variable MALETA_ADMIN_PIN dans config.py) —
  à changer avant un événement, en ajoutant une ligne Environment= au service
  systemd (systemctl edit ${SERVICE_NAME}) puis systemctl restart.
- Pour la prochaine mise à jour : décompresse la nouvelle archive dans
  ${SOURCE_DIR}, en remplaçant l'ancienne (ou dans un nouveau dossier
  ~/maleta-occitana), puis relance \`sudo bash install.sh\` depuis là —
  exactement la même commande, aucun argument à changer. Le contenu déjà
  saisi dans l'admin (objets, tags, médias, base de données) n'est jamais
  touché.

EOF
