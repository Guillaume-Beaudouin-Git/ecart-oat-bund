"""Tout le projet en une commande : téléchargement, calculs, figures, puis vérification du README.

    uv run python scripts/tout.py                          # fenêtre figée : janvier 1999 à octobre 2026
    uv run python scripts/tout.py --dernier-mois 2026-11   # mise à jour : prolonge la fenêtre
    uv run python scripts/tout.py --sans-telechargement    # recalcule sur les données déjà dans data/

Avec une fenêtre prolongée, les résultats changent ; la vérification dit alors quels chiffres du README ne
correspondent plus.
"""
import argparse
import os
import subprocess
import sys

ETAPES = ["decomposition.py", "stress.py", "abe.py", "controles.py", "verifier_readme.py"]


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--dernier-mois", help="dernier mois retenu, au format AAAA-MM (par défaut 2026-10)")
    parseur.add_argument("--sans-telechargement", action="store_true", help="ne pas retélécharger les données")
    args = parseur.parse_args()
    env = dict(os.environ)
    if args.dernier_mois:
        env["ECART_OAT_BUND_DERNIER_MOIS"] = args.dernier_mois
    etapes = ([] if args.sans_telechargement else ["telecharger.py"]) + ETAPES
    for etape in etapes:
        print(f"== {etape}", flush=True)
        code = subprocess.call([sys.executable, f"scripts/{etape}"], env=env,
                               stdout=None if etape in ("telecharger.py", "verifier_readme.py") else subprocess.DEVNULL)
        if code != 0:
            print(f"échec de {etape} (code {code})")
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
