"""Télécharge toutes les sources dans data/ (quelques secondes) : Eurostat, BCE, CERS, Bundesbank, Banco de España.

    uv run python scripts/telecharger.py               # tout
    uv run python scripts/telecharger.py --prevision   # seulement les deux séries de la Bundesbank (10 ans et 2 ans,
                                                       # depuis août 1997), qui servent à la prévision de volatilité
"""
import argparse

from ecart_oat_bund.donnees import DERNIER_MOIS, DOSSIER, telecharger_prevision, telecharger_tout

if __name__ == "__main__":
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--prevision", action="store_true",
                         help="ne télécharger que les séries quotidiennes de la Bundesbank (section 8)")
    args = parseur.parse_args()
    (telecharger_prevision if args.prevision else telecharger_tout)(DOSSIER, DERNIER_MOIS)
    quoi = "Séries de la Bundesbank téléchargées" if args.prevision else "Données téléchargées"
    print(f"{quoi} dans {DOSSIER}/ (dernier mois retenu : {DERNIER_MOIS})")
