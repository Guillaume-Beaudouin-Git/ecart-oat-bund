"""Section 11 du plan : l'écart France-Allemagne dans les scénarios de l'ABE de 2025, face à l'écart observé.

Écrit resultats/abe_2025.json. Les scénarios sont des moyennes annuelles ; les chocs de marché sont mesurés contre
le swap en euro.
"""
import json
from pathlib import Path

from ecart_oat_bund import analyse, donnees

RESULTATS = Path("resultats")


def main() -> None:
    taux = donnees.lire_cers_taux_longs()
    ecart_abe = {col: float(100 * (taux.loc["FR", col] - taux.loc["DE", col])) for col in taux.columns}
    marche = donnees.lire_cers_chocs_marche()
    fr = marche["ecarts_souverains_contre_swap_pb"]["France"]
    de = marche["ecarts_souverains_contre_swap_pb"]["Germany"]
    swap = marche["swap_eur_pb"]

    d = analyse.charger()
    s = d.ecarts["FR"]
    observe = {"2024": float(s.loc["2024-01":"2024-12"].mean()), "2025": float(s.loc["2025-01":"2025-12"].mean()),
               "2026_janvier_octobre": float(s.loc["2026-01":"2026-10"].mean()),
               "mois_2026": int(len(s.loc["2026-01":"2026-10"]))}
    taux_moyens_2024 = {p: float(d.taux[p].loc["2024-01":"2024-12"].mean()) for p in ("FR", "DE")}

    resultats = {
        "source": "CERS (ESRB), scénarios du test de résistance de l'ABE de 2025 (publiés le 20 janvier 2025, scénario "
                  "de marché mis à jour le 12 février 2025) ; Eurostat (écart observé). Calculs de l'auteur.",
        "plan": "PLAN.md, section 11, commit f938339",
        "taux_longs_abe_pct": {p: {c: float(v) for c, v in taux.loc[p].items()} for p in taux.index},
        "ecart_france_allemagne_abe_pb": ecart_abe,
        "ecart_observe_moyenne_annuelle_pb": observe,
        "choc_de_marche_10_ans_pb": {"france_contre_swap": fr["10Y"], "allemagne_contre_swap": de["10Y"],
                                     "swap_eur": swap["10Y"], "taux_france": swap["10Y"] + fr["10Y"],
                                     "taux_allemagne": swap["10Y"] + de["10Y"], "ecart_oat_bund": fr["10Y"] - de["10Y"]},
        "controle_depart_2024": {"abe_moyenne_2024_pct": {p: float(taux.loc[p, "depart_moyenne_2024"]) for p in ("FR", "DE")},
                                 "eurostat_moyenne_2024_pct": taux_moyens_2024,
                                 "ecart_abe_moins_eurostat_pb": {p: 100 * (float(taux.loc[p, "depart_moyenne_2024"])
                                                                           - taux_moyens_2024[p]) for p in ("FR", "DE")}},
    }
    (RESULTATS / "abe_2025.json").write_text(json.dumps(analyse.arrondir(resultats), indent=2, ensure_ascii=False))
    print(json.dumps(analyse.arrondir(resultats, 2), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
