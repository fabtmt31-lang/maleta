# Utiliser sur la borne l'export fait avec la version démo

Ce document explique ce qu'il faut **ajouter à la version de production**
(la borne : petit PC Debian, installée par `install.sh`) pour réimplanter le
fichier créé par **Admin > Exportar / Importar > Telecargar l'export** dans
la version démo (`maleta-demo-contenu-AAAAMMJJ-HHMM.zip`).

Trois cas, du plus simple au plus manuel :

| Situation de la borne | Ce qu'il faut ajouter | Section |
|---|---|---|
| Mise à jour en **v1.2** (ce dépôt) | Rien : la page d'import est déjà là | [1](#1-borne-en-v12--rien-à-ajouter) |
| Restée en **v1.11**, import en ligne de commande | 2 fichiers, aucun fichier existant modifié | [2](#2-borne-en-v111--import-en-ligne-de-commande-2-fichiers) |
| Restée en **v1.11**, import depuis l'admin | 3 fichiers + 2 fichiers modifiés (patch fourni) | [3](#3-borne-en-v111--page-exportar--importar-dans-ladmin) |
| Autre version de prod / code réécrit | Lire le format du fichier | [4](#4-format-du-fichier-dexport-pour-réimplémenter-limport) |

---

## 0. Amener le fichier sur la borne

Le `.zip` s'utilise **tel quel, sans le décompresser**.

- Clé USB, ou depuis un autre PC : `scp maleta-demo-contenu-*.zip <utilisateur>@<borne>:/tmp/`
- Le rendre lisible par l'utilisateur de l'appli : `chmod 644 /tmp/maleta-demo-contenu-*.zip`

---

## 1. Borne en v1.2 : rien à ajouter

1. Mettre la borne à jour comme d'habitude : copier le dossier
   `maleta-occitana/` de ce dépôt dans `~/maleta-occitana`, puis
   `sudo bash install.sh`.
2. Sur la borne : **Admin > Exportar / Importar** (barre latérale, section
   Sistèma) > **Importar** > choisir le `.zip`.
   - **Ajouter** (par défaut) : garde ce qui est déjà sur la borne, ignore les
     doublons.
   - **Remplacer** : efface d'abord le contenu des sections cochées.
   - Case « Apparence et textes de la borne » : cochée seulement pour
     reprendre aussi le modèle d'interface, la bannière et les textes choisis
     dans la démo.
3. Associer les tags NFC aux objets importés (voir [Après l'import](#après-limport)).

L'import en ligne de commande de la section 2 est aussi disponible en v1.2.

---

## 2. Borne en v1.11 : import en ligne de commande (2 fichiers)

Rien n'est modifié dans l'appli existante : on **ajoute** deux fichiers qui
ne sont utilisés que lorsqu'on les lance.

| Fichier à ajouter (copier depuis ce dépôt) | Rôle |
|---|---|
| `maleta-occitana/managers/content_transfer.py` → `managers/content_transfer.py` | Lecture du .zip et écriture en base / dans `media/` |
| `maleta-occitana/importer_contenu.py` → `importer_contenu.py` (racine de l'appli) | Commande d'import |

Les deux ne dépendent que de `config.py`, `db/database.py` et
`managers/upload_utils.py`, présents depuis la v1.03.

**Installation** — toujours dans le dossier source, jamais directement dans
`/opt` (`install.sh` synchronise `/opt/maleta-occitana` sur `~/maleta-occitana`
avec `rsync --delete` : un fichier ajouté uniquement dans `/opt` serait
supprimé à la mise à jour suivante) :

```bash
cp content_transfer.py ~/maleta-occitana/managers/
cp importer_contenu.py ~/maleta-occitana/
cd ~/maleta-occitana && sudo bash install.sh
```

**Utilisation** — en tant qu'utilisateur `maleta`, pour que les images et
sons copiés lui appartiennent :

```bash
# 1. voir ce que contient le fichier, sans rien importer
sudo -u maleta /opt/maleta-occitana/.venv/bin/python /opt/maleta-occitana/importer_contenu.py \
    /tmp/maleta-demo-contenu-XXXX.zip --apercu

# 2. importer (ajoute, doublons ignorés)
sudo -u maleta /opt/maleta-occitana/.venv/bin/python /opt/maleta-occitana/importer_contenu.py \
    /tmp/maleta-demo-contenu-XXXX.zip
```

| Option | Effet |
|---|---|
| `--apercu` | Affiche le nombre d'éléments par section, n'importe rien |
| `--remplacer` | Efface d'abord le contenu des sections importées |
| `--sections objects,quiz_questions` | N'importe que ces sections (`objects`, `vertadier_words`, `duel_questions`, `quiz_questions`, `villages`, `media_items`) |
| `--reglages` | Importe aussi l'apparence et les textes de la borne |
| `--sans-tags` | N'importe pas les tags NFC réels (un export de démo n'en contient pas) |

Le service n'a pas besoin d'être redémarré : le kiosque relit la base à
chaque partie. Recharger l'écran (F5) si `--reglages` a été utilisé.

---

## 3. Borne en v1.11 : page « Exportar / Importar » dans l'admin

Même import qu'en v1.2, depuis l'admin, sans passer à la v1.2 complète
(ni mode démo, ni autres changements).

### Méthode rapide : appliquer le patch fourni

`docs/prod-v1.11-import-contenu.patch` (ce dossier) contient exactement les
changements ci-dessous, testés sur l'archive v1.11 d'origine :

```bash
cp prod-v1.11-import-contenu.patch ~/            # copié sur la borne, ex. depuis une clé USB
cd ~/maleta-occitana
patch -p1 --dry-run < ~/prod-v1.11-import-contenu.patch   # vérification, ne modifie rien
patch -p1 < ~/prod-v1.11-import-contenu.patch
sudo bash install.sh
```

### Détail, pour le faire à la main

**Fichiers à ajouter** (copier depuis `maleta-occitana/` de ce dépôt) :

| Fichier | Rôle |
|---|---|
| `managers/content_transfer.py` | Export et import du contenu |
| `templates/admin/transfer.html` | Page Admin > Exportar / Importar |
| `importer_contenu.py` | Facultatif : import en ligne de commande (section 2) |

**`blueprints/admin.py`** — 3 imports à compléter en tête de fichier :

```python
import io                                   # nouvelle ligne, avant « import time »
import time

from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash,
    current_app, jsonify, send_file,        # + send_file
)

from managers import (
    content_transfer, duel_manager, ...     # + content_transfer
)
```

puis ajouter les 3 routes à la fin du fichier (à copier depuis la fin de
`maleta-occitana/blueprints/admin.py`, bloc « Exportar / Importar (v1.2) ») :

| Route | Fonction | Rôle |
|---|---|---|
| `GET /admin/transfer` | `transfer()` | Affiche la page |
| `GET /admin/transfer/export` | `transfer_export()` | Télécharge l'export (.zip) de la borne |
| `POST /admin/transfer/import` | `transfer_import()` | Importe le fichier envoyé, affiche le rapport |

**`templates/admin/base.html`** — une ligne dans la barre latérale, juste
après le lien « Configuracion » :

```html
<a class="sidebar-link {{ 'active' if request.endpoint in ('admin.transfer', 'admin.transfer_import') }}" href="{{ url_for('admin.transfer') }}">{{ m.icon('database', sw=2) }}<span>Exportar / Importar</span></a>
```

Aucun changement de base de données : l'import écrit dans les tables
existantes (`objects`, `tags`, `vertadier_words`, `duel_questions`,
`quiz_questions`, `villages`, `media_items`, `settings`).

---

## 4. Format du fichier d'export (pour réimplémenter l'import)

Le `.zip` contient :

```
maleta-contenu.json          <- seul fichier lu à l'import
media/objects/images/...     <- images des objets
media/objects/audio/...      <- prononciations
media/library/...            <- photos / vidéos du diaporama
media/branding/...           <- logo d'école, croix
tableur/*.csv                <- même contenu en CSV (relecture), jamais lu à l'import
LISEZMOI.txt
```

`maleta-contenu.json` :

```json
{
  "format": "maleta-occitana-contenu",
  "format_version": 1,
  "app_version": "1.2",
  "exported_at": "2026-10-21T10:15:00",
  "source": "demo",
  "objects":         [{"name_oc": "...", "name_fr": "...", "category": null, "image_filename": "a1b2_x.png", "audio_filename": null, "active": 1, "sort_order": 0, "tags": []}],
  "vertadier_words": [{"word_fr": "...", "is_occitan": 1, "explanation": "...", "source": "...", "active": 1, "sort_order": 1}],
  "duel_questions":  [{"question_fr": "...", "choice_a": "...", "choice_b": "...", "correct_choice": "a", "explanation": "...", "source": "...", "active": 1, "sort_order": 1}],
  "quiz_questions":  [{"question_fr": "...", "choice_a": "...", "choice_b": "...", "choice_c": "...", "correct_choice": "c", "explanation": "...", "source": "...", "active": 1, "sort_order": 1}],
  "villages":        [{"name_fr": "...", "name_oc": "...", "source": "...", "active": 1, "sort_order": 1}],
  "media_items":     [{"filename": "photo.jpg", "media_type": "image", "caption": null, "display_seconds": null, "active": 1, "sort_order": 1}],
  "settings":        {"theme": "senhal", "kiosk_texts": "{...json...}", "action_label_overrides": "{...}", "logo_filename": "logo.png", "crotz_filename": "..."},
  "media_included": true,
  "missing_media": []
}
```

- Chaque section correspond **colonne pour colonne** à la table du même nom
  (`db/schema.sql`), sans `id` ni `created_at`.
- Noms de fichiers médias → fichier `media/<dossier>/<nom>` de l'archive :
  `image_filename` → `media/objects/images/`, `audio_filename` →
  `media/objects/audio/`, `media_items.filename` → `media/library/`,
  `logo_filename` / `crotz_filename` → `media/branding/`.
- `settings` : valeurs brutes de la table `settings` (texte, JSON sérialisé
  pour `kiosk_texts` / `action_label_overrides`). Jamais `admin_pin` ni les
  mappings manette/clavier.
- `objects[].tags` : UID des tags NFC **réels** seulement ; un export de
  démo n'en contient pas.

Règles appliquées par l'import de référence (`content_transfer.import_bundle`) :

1. Refuser un fichier dont `format` n'est pas `maleta-occitana-contenu`, ou
   dont `format_version` est plus grand que celui connu.
2. Mode « ajouter » : une entrée est un doublon si sa clé existe déjà
   (comparaison sans tenir compte de la casse ni des espaces autour) —
   objets : `name_oc` + `name_fr` ; Ven de l'occitan : `word_fr` ; Duèl et
   Quiz : `question_fr` ; vilatges : `name_fr` + `name_oc` ; diaporama :
   `filename`. Mode « remplacer » : vider la table avant.
3. `correct_choice` en minuscules, `a`/`b` (Duèl) ou `a`/`b`/`c` (Quiz),
   sinon entrée ignorée ; champs obligatoires vides → entrée ignorée.
4. `sort_order` importé = plus grand `sort_order` existant + valeur
   d'origine + 1 (le contenu importé se range après l'existant, dans le même
   ordre).
5. Fichiers médias : extension vérifiée (mêmes listes que `config.py`) ;
   fichier identique déjà présent → réutilisé ; même nom mais contenu
   différent → renommé `<8 premiers caractères du sha256>_<nom>`.
6. Tags commençant par `DEMO-` ou `SIMU-` (simulés) : jamais importés.

---

## Après l'import

- **Tags NFC** : les objets venant de la démo n'ont aucun tag. Pour chacun :
  Admin > Objèctes & tags > fiche de l'objet > « Associer un nouveau tag »,
  puis poser le tag physique sur le lecteur.
- **Tableau de bord** : vérifier que les jeux passent en « Jogable ».
- **Sauvegarde** : avant un import en mode « Remplacer », faire d'abord un
  export de la borne (même page, ou copier `/opt/maleta-occitana/maleta.db`
  et `/opt/maleta-occitana/media/`).
