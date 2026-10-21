-- Maleta Occitana - schema SQLite
--
-- Etape 1 : uniquement ce dont a besoin le mode "Descobèrta d'objèctes".
-- Etape 2 : ajout de la table `media_items` pour le "Cadre fotó & vidèo"
-- (le jeu "Tròba l'objècte" n'a besoin d'aucune nouvelle table, il reutilise
-- `objects`/`tags`). Vertadièr o Occitan et le Quiz Calandreta restent pour
-- une étape ultérieure, une fois leur contenu vérifié avec une source fiable.
--
-- init_db() (db/database.py) rejoue ce fichier a chaque demarrage via
-- CREATE TABLE IF NOT EXISTS : ajouter une table ici suffit, aucune
-- migration a ecrire a la main pour une base existante.

CREATE TABLE IF NOT EXISTS objects (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name_oc       TEXT NOT NULL,              -- mot occitan (ex: "Fromatge")
    name_fr       TEXT NOT NULL,              -- traduction francaise (ex: "Fromage")
    category      TEXT,                       -- ex: "nourriture", "animaux", "nature", "familha"
    image_filename TEXT,                      -- nom de fichier dans media/objects/images/
    audio_filename TEXT,                      -- nom de fichier dans media/objects/audio/
    active        INTEGER NOT NULL DEFAULT 1, -- desactivable sans supprimer (cf. concept admin)
    sort_order    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Association objet <-> tag NFC. Un objet peut (temporairement) n'avoir aucun
-- tag associe -- utile pour préparer le contenu avant d'avoir les tags en main.
CREATE TABLE IF NOT EXISTS tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    uid         TEXT NOT NULL UNIQUE,   -- UID physique du tag NFC, lu via "Associer un tag"
    object_id   INTEGER,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (object_id) REFERENCES objects(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tags_object_id ON tags(object_id);

-- Etape 2 : bibliotheque de medias pour le mode "Cadre fotó & vidèo"
-- (diaporama / ecran de veille). Une entree = une photo ou une video.
CREATE TABLE IF NOT EXISTS media_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT NOT NULL,              -- nom de fichier dans media/library/
    media_type      TEXT NOT NULL,              -- 'image' ou 'video', deduit de l'extension a l'upload
    caption         TEXT,                       -- legende optionnelle affichee sur le diaporama
    display_seconds INTEGER,                    -- duree d'affichage (images uniquement) ; NULL = valeur par defaut (config.DIAPORAMA_DEFAULT_IMAGE_SECONDS)
    active          INTEGER NOT NULL DEFAULT 1, -- desactivable sans supprimer, meme principe que les objets
    sort_order      INTEGER NOT NULL DEFAULT 0, -- ordre d'affichage dans la boucle (modifiable via les fleches monter/descendre de l'admin)
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_media_items_sort_order ON media_items(sort_order);

-- v0.2 : reglages generaux modifiables depuis l'admin (Configuration), au
-- lieu de rester figes dans des variables d'environnement -- PIN admin,
-- theme de couleur, logo/croix personnalises, mapping manette. Simple table
-- cle/valeur (toutes les valeurs en TEXT, y compris les mappings serialises
-- en JSON) : voir managers/settings_manager.py pour les cles connues et
-- leurs valeurs par defaut.
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- v0.2 : jeu "Vertadièr o Occitan" -- un mot/une expression francaise est
-- proposee, le visiteur repond s'il pense qu'elle vient de l'occitan ou non.
-- Contenu volontairement VIDE a la livraison (voir concept-borne-interactive.md,
-- "Vertadièr o Occitan" : la liste doit etre construite avec une source
-- fiable, jamais improvisee au moment du developpement) -- a remplir depuis
-- l'admin, meme principe que les objets.
CREATE TABLE IF NOT EXISTS vertadier_words (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    word_fr     TEXT NOT NULL,               -- mot/expression francaise proposee au visiteur
    is_occitan  INTEGER NOT NULL,            -- 1 = vertadièr (vient de l'occitan), 0 = fals
    explanation TEXT,                        -- courte explication affichee apres la reponse
    source      TEXT,                        -- reference utilisee pour verifier (CNRTL, IEO...)
    active      INTEGER NOT NULL DEFAULT 1,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vertadier_sort_order ON vertadier_words(sort_order);

-- v0.7 : jeu "Duèl Occitan" -- 2 joueurs, une question de culture/langue
-- occitane avec 2 reponses possibles (choice_a / choice_b), chaque joueur
-- repond de son cote avec ses propres boutons manette. Meme principe de
-- contenu que vertadier_words : VOLONTAIREMENT VIDE a la livraison, a
-- construire avec une source fiable (CNRTL, Institut d'Estudis Occitan...),
-- jamais improvise au moment du developpement (voir
-- concept-borne-interactive.md, "Decisions de contenu et nouvelles
-- activites (15/09/2026)").
CREATE TABLE IF NOT EXISTS duel_questions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    question_fr    TEXT NOT NULL,               -- question posee (francais)
    choice_a       TEXT NOT NULL,                -- libelle de la reponse A
    choice_b       TEXT NOT NULL,                -- libelle de la reponse B
    correct_choice TEXT NOT NULL,                -- 'a' ou 'b'
    explanation    TEXT,                         -- courte explication affichee apres la reponse
    source         TEXT,                         -- reference utilisee pour verifier (CNRTL, IEO...)
    active         INTEGER NOT NULL DEFAULT 1,
    sort_order     INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_duel_questions_sort_order ON duel_questions(sort_order);

-- v0.8 : jeu "Memòria vilatge" -- meme mecanique que "Memòria" (voir
-- managers/game_controller.py, MEMORIA_VARIANTS) mais sur des noms de
-- villes/vilatges plutot que des objets : une carte montre le nom francais,
-- l'autre le nom occitan. Contenu volontairement VIDE a la livraison, meme
-- principe que vertadier_words/duel_questions : a construire avec une source
-- fiable (CNRTL, Institut d'Estudis Occitan...), jamais improvise.
CREATE TABLE IF NOT EXISTS villages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name_fr     TEXT NOT NULL,               -- nom francais (ex: "Toulouse")
    name_oc     TEXT NOT NULL,               -- nom occitan (ex: "Tolosa")
    source      TEXT,                        -- reference utilisee pour verifier (CNRTL, IEO...)
    active      INTEGER NOT NULL DEFAULT 1,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_villages_sort_order ON villages(sort_order);

-- v0.8 : jeu "Quiz Calandreta" -- question de culture/langue occitane avec
-- 3 reponses possibles (choice_a / choice_b / choice_c). Meme principe de
-- contenu que vertadier_words/duel_questions : VOLONTAIREMENT VIDE a la
-- livraison, a construire avec une source fiable (CNRTL, Institut d'Estudis
-- Occitan...), jamais improvise au moment du developpement.
CREATE TABLE IF NOT EXISTS quiz_questions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    question_fr    TEXT NOT NULL,               -- question posee (francais)
    choice_a       TEXT NOT NULL,                -- libelle de la reponse A
    choice_b       TEXT NOT NULL,                -- libelle de la reponse B
    choice_c       TEXT NOT NULL,                -- libelle de la reponse C
    correct_choice TEXT NOT NULL,                -- 'a', 'b' ou 'c'
    explanation    TEXT,                         -- courte explication affichee apres la reponse
    source         TEXT,                         -- reference utilisee pour verifier (CNRTL, IEO...)
    active         INTEGER NOT NULL DEFAULT 1,
    sort_order     INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quiz_questions_sort_order ON quiz_questions(sort_order);
