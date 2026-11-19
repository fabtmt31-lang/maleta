# La Maleta Occitana × aprene — ce qu'il faut savoir côté aprene

La **Maleta Occitana** est une borne de stand (petit PC Debian, écran, manette USB, lecteur NFC) pour faire
découvrir l'occitan. Elle va proposer, depuis son administration, un accès à la **compétition d'aprene**
(`https://aprene.appsdoc.fr/competicion`, compte de rôle « compétition »). Détail complet côté borne :
[`cahier-des-charges-jocs-amagats.md`](cahier-des-charges-jocs-amagats.md).

## Comment la borne utilise aprene

- Le navigateur de la borne (Chromium plein écran, navigation privée) **va directement sur aprene** : pas
  d'affichage dans une autre page, l'en-tête `frame-ancestors 'none'` peut donc rester tel quel.
- Connexion automatique : `POST /connexion` avec `identifiant` / `mdp` du compte compétition, puis
  `/competicion`. La connexion est refaite à chaque lancement (navigation privée).
- Le maître du jeu règle la compétition au clavier et à la souris ; les joueurs répondent à la souris ou à
  la **manette**, que la borne convertit en touches (Tab / Maj+Tab pour passer d'une réponse à l'autre,
  Entrée pour valider).
- Sortie : double Échap sur la borne, qui se déconnecte (`POST /deconnexion`) puis revient à son menu.

## Rien d'obligatoire

**Aucune modification d'aprene n'est nécessaire** pour que la borne fonctionne avec la version actuelle.

## Recommandations

Par ordre d'importance :

1. **Mot de passe du compte `compet`** — il figure dans le README (comptes de test) : à changer avant
   l'ouverture au public. Idéalement, un compte compétition par borne, pour pouvoir en couper un sans
   toucher aux autres.
2. **Limiter les essais de connexion** sur `/connexion` (ex. pause croissante après quelques échecs par
   adresse IP et par identifiant) : aujourd'hui, rien ne limite les essais, et les comptes compétition sont
   partagés. Utile pour aprene en général, pas seulement pour la borne.
3. **Navigation au clavier sur les pages de compétition** (`play.html`, `turn.html`) :
   - boutons de réponse atteignables par Tab, dans l'ordre visuel, avec un **focus bien visible** ;
   - en plus, si possible, **raccourcis** : `1` `2` `3` `4` (ou `A` `B` `C` `D`) pour répondre, `Entrée`
     pour valider / passer au joueur suivant.
   C'est ce qui rend le jeu à la manette fiable sur la borne (et plus rapide au clavier pour tout le monde).
4. **Affichage sans défilement** en 1280×720 et 1920×1080 (écrans des bornes), avec des boutons de réponse
   assez grands pour être lus de loin.
5. **Optionnel — lien de connexion par jeton** pour les bornes, par exemple
   `GET /connexion/borne?jeton=…` (jeton long, un par borne, créé et révoqué dans l'admin d'aprene, qui
   connecte au compte compétition et ouvre `/competicion`). La borne n'aurait plus à garder de mot de passe,
   et un changement de la page de connexion ne la casserait plus.
6. **Optionnel — scores** : un moyen de récupérer le classement d'une partie terminée (ex. JSON), pour
   l'afficher sur la borne entre deux parties.

## Contact côté borne

Dépôt GitHub `fabtmt31-lang/maleta`.
