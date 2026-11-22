"""Section 12 du plan : les séries d'Eurostat contre les séries quotidiennes de la Bundesbank et du Banco de España.

Écrit resultats/controles.json. Le contrôle du point de départ de l'ABE est dans resultats/abe_2025.json.
"""
import json
from pathlib import Path

import numpy as np

from ecart_oat_bund import analyse, donnees

RESULTATS = Path("resultats")


def comparer(eurostat, quotidien) -> dict:
    mensuel = quotidien.groupby(quotidien.index.to_period("M")).mean()
    commun = eurostat.index.intersection(mensuel.index)
    a, b = eurostat.loc[commun], mensuel.loc[commun]
    ecart = 100 * (b - a)
    return {"mois": [str(commun[0]), str(commun[-1])], "nombre_de_mois": int(len(commun)),
            "ecart_moyen_pb": float(ecart.mean()), "plus_grand_ecart_absolu_pb": float(ecart.abs().max()),
            "mois_du_plus_grand_ecart": str(ecart.abs().idxmax()),
            "correlation_des_variations_mensuelles": float(np.corrcoef(a.diff().dropna(), b.diff().dropna())[0, 1])}


def main() -> None:
    d = analyse.charger()
    fin = donnees.fin_quotidienne()
    bund = donnees.lire_bund_bundesbank().loc["1999-01-01":fin]
    espagne = donnees.lire_espagne_bde().loc["1999-01-01":fin]
    resultats = {
        "source": "Eurostat ; Deutsche Bundesbank (10 ans zéro-coupon, Svensson) ; Banco de España (10 ans, marché "
                  "secondaire). Calculs de l'auteur.",
        "plan": "PLAN.md, section 12, commit f938339",
        "allemagne_bundesbank_moins_eurostat": comparer(d.taux["DE"], bund),
        "espagne_banco_de_espana_moins_eurostat": comparer(d.taux["ES"], espagne),
        "note": "La Bundesbank publie un taux zéro-coupon, Eurostat des rendements d'obligations proches de 10 ans : "
                "un écart de niveau est attendu, les variations doivent se suivre.",
    }
    (RESULTATS / "controles.json").write_text(json.dumps(analyse.arrondir(resultats), indent=2, ensure_ascii=False))
    print(json.dumps(analyse.arrondir(resultats, 3), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
