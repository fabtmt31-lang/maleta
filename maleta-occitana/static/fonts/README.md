# Polices vendorées localement (v1.1)

Depuis la v1.1, l'interface (borne et admin) se décline en **3 modèles**
choisis dans Configuration : **Senhal**, **Mercat** et **Nuèch** (maquettes
« La Maleta Occitana — 3 directions » fournies par Fabien). Chaque modèle a
ses deux polices, toutes présentes dans ce dossier pour un rendu identique
**sans aucune connexion réseau** (même principe que `static/js/socket.io.min.js`).

| Modèle | Titres          | Texte courant    |
|--------|-----------------|------------------|
| Senhal | Unbounded       | Manrope          |
| Mercat | Bagel Fat One   | Lexend           |
| Nuèch  | Young Serif     | Instrument Sans  |

Les fichiers `.woff2` ont été extraits tels quels des maquettes (polices
Google Fonts). Deux fichiers par famille : `-latin` (lettres accentuées
occitanes et françaises) et `-latinext` (compléments). Unbounded, Manrope,
Lexend et Instrument Sans sont des polices « variables » : un seul fichier
couvre toutes les graisses. Les déclarations `@font-face` sont dans
`static/css/fonts.css`, chargé par la borne et par l'admin.

Licences : toutes ces familles sont sous **SIL Open Font License 1.1**
(fichiers `OFL-*.txt`, à conserver avec les polices — exigé par la licence).

Les anciennes polices (Caprasimo, Figtree, v0.71) ont été retirées en v1.1 :
plus aucun écran ne les utilisait.
