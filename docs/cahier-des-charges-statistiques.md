# Statistiques d'utilisation de la borne — proposition (avant développement)

Statut : **proposition, rien n'est développé**. Maquettes (données fictives) dans
[`docs/maquettes/statistiques/`](maquettes/statistiques/).

## 1. Ce qu'on veut savoir

- **Heure par heure**, ce qui a été joué sur la borne.
- Le **temps passé** sur chaque jeu.
- Le **nombre de parties finies** (et donc abandonnées).

En plus, si utile :

- le nombre de **visites** ;
- les **heures creuses / pleines** de la semaine ;
- pour la classe, les **questions les plus ratées** ;
- les **objets les plus posés** sur la borne.

**Aucune donnée personnelle** : la borne ne sait pas qui joue. On n'enregistre
ni nom, ni photo, ni son, seulement des évènements anonymes (heure, jeu, durée,
fin, score).

## 2. Définitions (à valider)

| Terme | Définition proposée |
|---|---|
| **Visite** | La borne sort de veille (objet posé, bouton) jusqu'à son retour en veille. |
| **Partie lancée** | Un jeu démarre (Troba, Ven de l'occitan, Duèl, Memòria, Vilatges, Quiz). |
| **Partie finie** | L'écran de fin du jeu est atteint (avec son score). |
| **Partie abandonnée** | Retour au menu, Échap ou mise en veille (inactivité) avant l'écran de fin. |
| **Temps de jeu** | Du début de la partie à sa fin ou à son abandon (le temps d'inactivité avant une mise en veille automatique n'est pas compté). |
| **Descoberta** | Chaque objet posé compte comme une « consultation » : quel objet, combien de temps sa fiche reste affichée. |
| **Jòcs amagats** | aprene et chaque jeu rétro : nombre de lancements et temps. Pas de notion de « partie finie » : l'émulateur ne sait pas si le jeu est terminé. |
| **Diaporama** | Temps d'affichage seulement (pas un jeu). |

## 3. Écrans proposés (maquettes)

1. **Vue d'ensemble** (`1-vue-ensemble.png`) — *Admin > Estadísticas*.
   - Choix de la période : aujourd'hui, 7 jours, 30 jours, tout, ou dates au choix.
   - 5 chiffres clés : visites, parties lancées, parties finies (en %), temps de
     jeu, durée d'une visite.
   - **Heure par heure** : barres empilées, en minutes de jeu par heure, une
     couleur par jeu.
   - **Quand la borne sert-elle ?** : grille jour × heure, plus c'est foncé plus
     elle a servi.
   - **Tableau par jeu** : temps, parties lancées, finies (en %), durée moyenne,
     score moyen.
2. **Journée heure par heure** (`2-journee-heure-par-heure.png`).
   - Navigation d'un jour à l'autre.
   - **Frise de la journée** : chaque partie dessinée de son début à sa fin, une
     ligne par jeu. Plein = finie, hachuré = abandonnée. Au survol : heures, durée,
     score.
   - Tableau **heure par heure** : visites, parties, finies, temps, jeu le plus
     joué.
   - **Journal** des parties, une par une, filtrable par jeu.
3. **Détail par jeu** (`3-detail-par-jeu.png`).
   - Pour le jeu choisi : chiffres clés et répartition des scores.
   - **Questions / mots les plus ratés** (Quiz, Ven de l'occitan, Duèl), pour
     travailler en classe.
   - **Objets les plus posés** (Descoberta).
   - **Centre de jòcs et aprene** : temps et lancements par jeu rétro.
4. **Tableau de bord** (`4-tableau-de-bord.png`) : encart « Aujourd'hui sur la
   borne », avec visites, parties, temps de jeu et les 3 jeux les plus joués, plus
   un lien vers les statistiques.

Partout : **export CSV**, à ouvrir dans un tableur (journal des parties et
tableaux), et un tableau sous chaque graphique, pour la lisibilité.

## 4. Fonctionnement technique (prévu)

- **Enregistrement automatique** au fil des changements d'écran de la borne
  (`game_controller`), sans rien changer aux jeux. La borne enregistre :
  - début et fin de chaque visite et de chaque partie ;
  - comment la partie s'est terminée (finie / abandonnée) ;
  - le score (bonnes réponses / total) ;
  - pour les questions, juste / faux par question.

  Le centre de jòcs est enregistré par ses pages (lancement d'un jeu, retour au
  centre).
- **Base de la borne** (SQLite), trois petites tables :
  - `stats_visites` ;
  - `stats_parties` (jeu, détail, début, fin, fin de partie, score) ;
  - `stats_reponses` (jeu, question, juste/faux, heure).

  Volume négligeable : une école chargée ≈ 100 000 lignes par an.
- **Heure de la borne** : la borne doit être à l'heure. Le petit PC garde l'heure
  hors réseau ; une fois le Wi-Fi connecté, elle se règle automatiquement.
- **Robustesse** : une partie en cours lors d'une coupure de courant est close
  au redémarrage suivant. Elle est comptée comme abandonnée, avec sa durée
  jusqu'au dernier signe de vie connu.
- **Pages admin** : calculs faits à l'affichage (requêtes SQL simples), graphiques
  dessinés en local, sans bibliothèque ni Internet.
- **Démo (Windows / Linux)** : fonctionne aussi, ses statistiques restent sur le
  PC.

## 5. Questions à trancher avant le développement

1. **Définitions** du §2 : OK telles quelles ? En particulier, une mise en veille
   pendant une partie = abandon.
2. **Durée de conservation** : proposé **2 ans** de détail (journal et réponses),
   puis effacement automatique. Les totaux par jour sont gardés.
3. **Plage horaire** affichée : proposé **8 h – 19 h**, réglable (une borne en
   salle des fêtes le soir ?).
4. **Questions les plus ratées** : à garder ? Utile pour la classe, mais ça
   multiplie les lignes enregistrées.
5. **Export du contenu** (*Exportar / Importar*) : inclure les statistiques ?
   Proposé **non** : elles ont leur propre export CSV.
6. **Remise à zéro** : un bouton « Effacer les statistiques », avec confirmation
   et sauvegarde CSV avant (utile après une semaine de tests) ?
7. **Visites** : à garder dans les chiffres clés, ou seulement les parties ?
