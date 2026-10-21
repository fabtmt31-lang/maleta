"""Importe sur la borne un export de contenu (.zip) fait depuis la version de
demo (ou une autre borne) -- en ligne de commande, sans passer par l'admin.

Meme import que la page Admin > Exportar / Importar (v1.2), voir
managers/content_transfer.py. Utile aussi sur une borne restee en v1.11 :
il suffit d'y ajouter ce fichier et managers/content_transfer.py (detail
dans docs/import-contenu-version-prod.md a la racine du depot).

Usage, sur la borne (en tant qu'utilisateur "maleta", pour que les fichiers
medias copies lui appartiennent) :

    sudo -u maleta /opt/maleta-occitana/.venv/bin/python \\
        /opt/maleta-occitana/importer_contenu.py /tmp/maleta-demo-contenu-XXXX.zip

Options :
    --apercu       affiche le contenu du fichier sans rien importer
    --remplacer    efface d'abord le contenu des sections importees
                   (par defaut : ajoute, doublons ignores)
    --sections     liste separee par des virgules (par defaut : toutes)
                   objects,vertadier_words,duel_questions,quiz_questions,villages,media_items
    --reglages     importe aussi l'apparence et les textes de la borne
    --sans-tags    n'importe pas les tags NFC reels associes aux objets

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


class _File:
    """Interface minimale attendue par content_transfer.read_bundle()."""

    def __init__(self, path):
        self.path = path

    def read(self):
        with open(self.path, "rb") as f:
            return f.read()


def main():
    parser = argparse.ArgumentParser(description="Importe un export de contenu de la Maleta Occitana.")
    parser.add_argument("fichier", help="export .zip (ou .json)")
    parser.add_argument("--apercu", action="store_true", help="affiche le contenu sans rien importer")
    parser.add_argument("--remplacer", action="store_true", help="efface d'abord les sections importees")
    parser.add_argument("--sections", default="", help="sections a importer, separees par des virgules")
    parser.add_argument("--reglages", action="store_true", help="importe aussi apparence et textes")
    parser.add_argument("--sans-tags", action="store_true", help="n'importe pas les tags NFC")
    args = parser.parse_args()

    all_sections = [s["name"] for s in content_transfer.SECTIONS]
    sections = [s.strip() for s in args.sections.split(",") if s.strip()] or all_sections
    unknown = [s for s in sections if s not in all_sections]
    if unknown:
        parser.error(f"section(s) inconnue(s) : {', '.join(unknown)} (possibles : {', '.join(all_sections)})")

    app = Flask(__name__)
    app.teardown_appcontext(close_db)
    init_db()
    with app.app_context():
        try:
            data, archive = content_transfer.read_bundle(_File(args.fichier))
        except (OSError, content_transfer.ImportError_) as exc:
            print(f"Erreur : {exc}", file=sys.stderr)
            return 1

        print(f"Export de la version {data.get('app_version', '?')} ({data.get('source', '?')}), "
              f"du {data.get('exported_at', '?')}")
        for entry in content_transfer.summarize(data):
            print(f"  - {entry['label']} : {entry['count']}")
        if args.apercu:
            return 0

        report = content_transfer.import_bundle(
            data, archive, sections,
            mode="replace" if args.remplacer else "merge",
            import_settings=args.reglages,
            import_tags=not args.sans_tags,
        )

    print("\nImport termine :")
    for result in report["sections"].values():
        print(f"  - {result['label']} : {result['added']} ajoute(s), {result['skipped']} ignore(s)")
    print(f"  - {report['files']} fichier(s) media copie(s)")
    for warning in report["warnings"]:
        print(f"  ! {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
