"""Importe sur la borne un export de contenu (.zip) fait depuis la version de
demo (ou une autre borne), et/ou des fichiers CSV ecrits dans un tableur --
en ligne de commande, sans passer par l'admin.

Meme import que la page Admin > Exportar / Importar (v1.2, CSV depuis la
v1.21), voir managers/content_transfer.py. Utile aussi sur une borne restee
en v1.11 : il suffit d'y ajouter ce fichier et managers/content_transfer.py
(detail dans docs/import-contenu-version-prod.md a la racine du depot).

Usage, sur la borne (en tant qu'utilisateur "maleta", pour que les fichiers
medias copies lui appartiennent) :

    sudo -u maleta /opt/maleta-occitana/.venv/bin/python \\
        /opt/maleta-occitana/importer_contenu.py /tmp/maleta-demo-contenu-XXXX.zip

    sudo -u maleta /opt/maleta-occitana/.venv/bin/python \\
        /opt/maleta-occitana/importer_contenu.py /tmp/quiz.csv /tmp/duel.csv

Options :
    --apercu       affiche le contenu des fichiers sans rien importer
    --remplacer    efface d'abord le contenu des sections importees
                   (par defaut : ajoute, doublons ignores)
    --sections     liste separee par des virgules (par defaut : toutes)
                   objects,vertadier_words,duel_questions,quiz_questions,villages,media_items
    --type         type de contenu des fichiers .csv, si leur nom ne le dit
                   pas (memes noms que --sections)
    --reglages     importe aussi l'apparence et les textes de la borne
    --sans-tags    n'importe pas les tags NFC reels associes aux objets
    --modeles DOSSIER
                   ecrit les modeles CSV vides (et leur notice) dans DOSSIER

Pas besoin d'arreter le service : le kiosque relit la base a chaque partie.
Recharger l'ecran (F5) si --reglages a ete utilise.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask  # noqa: E402

from db.database import close_db, init_db  # noqa: E402
from managers import content_transfer  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Importe un export de contenu ou des CSV dans la Maleta Occitana.")
    parser.add_argument("fichiers", nargs="*", help="export .zip / .json, ou fichiers .csv")
    parser.add_argument("--apercu", action="store_true", help="affiche le contenu sans rien importer")
    parser.add_argument("--remplacer", action="store_true", help="efface d'abord les sections importees")
    parser.add_argument("--sections", default="", help="sections a importer, separees par des virgules")
    parser.add_argument("--type", default=None, help="type de contenu des fichiers .csv")
    parser.add_argument("--reglages", action="store_true", help="importe aussi apparence et textes")
    parser.add_argument("--sans-tags", action="store_true", help="n'importe pas les tags NFC")
    parser.add_argument("--modeles", metavar="DOSSIER", help="ecrit les modeles CSV dans DOSSIER")
    args = parser.parse_args()

    all_sections = [s["name"] for s in content_transfer.SECTIONS]
    if args.modeles:
        os.makedirs(args.modeles, exist_ok=True)
        for name, content in content_transfer.csv_template_files().items():
            with open(os.path.join(args.modeles, name), "w", encoding="utf-8", newline="") as f:
                f.write(content)
        print(f"Modeles CSV ecrits dans {args.modeles}")
        if not args.fichiers:
            return 0
    if not args.fichiers:
        parser.error("indique au moins un fichier a importer")
    sections = [s.strip() for s in args.sections.split(",") if s.strip()] or all_sections
    unknown = [s for s in sections + ([args.type] if args.type else []) if s not in all_sections]
    if unknown:
        parser.error(f"section(s) inconnue(s) : {', '.join(unknown)} (possibles : {', '.join(all_sections)})")

    app = Flask(__name__)
    app.teardown_appcontext(close_db)
    init_db()
    status = 0
    total = {"sections": {}, "files": 0, "warnings": []}
    with app.app_context():
        for path in args.fichiers:
            try:
                with open(path, "rb") as f:
                    data, archive = content_transfer.read_upload(os.path.basename(path), f.read(), args.type)
            except (OSError, content_transfer.ImportError_) as exc:
                print(f"Erreur : {exc}", file=sys.stderr)
                status = 1
                continue

            if data.get("source") == "csv":
                print(f"{path} : fichier CSV")
            else:
                print(f"{path} : export de la version {data.get('app_version', '?')} "
                      f"({data.get('source', '?')}), du {data.get('exported_at', '?')}")
            for entry in content_transfer.summarize(data):
                if entry["count"] or data.get("source") != "csv":
                    print(f"  - {entry['label']} : {entry['count']}")
            if args.apercu:
                continue

            report = content_transfer.import_bundle(
                data, archive, sections,
                mode="replace" if args.remplacer else "merge",
                import_settings=args.reglages and data.get("source") != "csv",
                import_tags=not args.sans_tags,
            )
            content_transfer.merge_reports(total, report)

    if args.apercu:
        return status
    print("\nImport termine :")
    for result in total["sections"].values():
        if result["added"] or result["skipped"]:
            print(f"  - {result['label']} : {result['added']} ajoute(s), {result['skipped']} ignore(s)")
    print(f"  - {total['files']} fichier(s) media copie(s)")
    for warning in total["warnings"]:
        print(f"  ! {warning}")
    return status


if __name__ == "__main__":
    sys.exit(main())
