"""Télécharge toutes les sources dans data/ (quelques secondes) : Eurostat, BCE, CERS, Bundesbank, Banco de España."""
from ecart_oat_bund.donnees import DERNIER_MOIS, DOSSIER, telecharger_tout

if __name__ == "__main__":
    telecharger_tout(DOSSIER, DERNIER_MOIS)
    print(f"Données téléchargées dans {DOSSIER}/ (dernier mois retenu : {DERNIER_MOIS})")
