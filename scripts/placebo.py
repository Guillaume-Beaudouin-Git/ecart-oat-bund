"""Placebos de la décomposition, hors plan, ajoutés le 28 novembre 2026 : d'autres pays, d'autres dates.

Écrit resultats/placebo.json. Ces calculs ne sont pas dans PLAN.md et ne changent ni le titre ni les chiffres de
tête ; le README les présente à la fin de sa section 3, comme une analyse ajoutée après coup.
"""
import json
from pathlib import Path

from ecart_oat_bund import analyse, donnees, placebo

RESULTATS = Path("resultats")
DATE_AJOUT = "2026-11-28"
HORIZONS = (2, 29)          # deux mois, comme l'automne 2026 (E5) ; 29 mois, comme le modèle principal


def main() -> None:
    RESULTATS.mkdir(exist_ok=True)
    d = analyse.charger()
    n = analyse.N_PRINCIPAL
    est, chemin = analyse.principal(d)
    f = chemin.iloc[-1]
    h_principal = int(f["h"])
    assert h_principal in HORIZONS

    # 1. Par pays : chaque pair contre les sept autres, France exclue ; puis avec la France parmi les pairs.
    pays = placebo.par_pays(d.ecarts, d.pib, donnees.PAIRS, analyse.BASE, analyse.FIN, n)
    avec_france = placebo.par_pays(d.ecarts, d.pib, ("FR",) + donnees.PAIRS, analyse.BASE, analyse.FIN, n)

    # 2. Par dates : la France, toutes les bases dont la fenêtre cumulée finit au plus tard au mois de base du
    #    modèle principal ; les pairs de même, contre les sept autres pairs.
    dates, tables = {}, {}
    for h in HORIZONS:
        t = placebo.par_dates(d.ecarts["FR"], d.P["G8"].to_frame("P"), h, n, analyse.BASE)
        tables[h] = t
        dates[f"h{h}"] = placebo.resume_dates(t, h)
    pairs_dates = {}
    for c in donnees.PAIRS:
        autres = [p for p in donnees.PAIRS if p != c]
        t = placebo.par_dates(d.ecarts[c], placebo.facteur_commun(d.ecarts, d.pib, autres), h_principal, n,
                              analyse.BASE)
        r = placebo.resume_dates(t, h_principal)
        pairs_dates[c] = {k: r[k] for k in ("bases", "exclut_zero", "part_exclut_zero", "ecart_type_z",
                                            "max_abs_propre_pb")}
        # la part propre de 2024-2026 de ce pair, élargie de l'écart-type des z de son propre placebo par dates
        v = pays[c]
        v["ecart_type_z_placebo_par_dates"] = r["ecart_type_z"]
        v["ic95_elargi_pb"] = placebo.etalonner(v["part_propre_pb"], v["sigma_pb"], r["ecart_type_z"])
        v["exclut_zero_apres_elargissement"] = bool(v["ic95_elargi_pb"][0] > 0 or v["ic95_elargi_pb"][1] < 0)

    # 3. Étalonnage : l'intervalle du modèle principal (29 mois) et celui de l'automne 2026 (E5, 2 mois), élargis
    #    de l'écart-type des z du placebo par dates au même horizon.
    _, chemin_e5 = analyse.modele(d, base=analyse.EPISODES["E5"]["base"], fin=analyse.EPISODES["E5"]["fin"],
                                  estimation=est)
    e5 = chemin_e5.iloc[-1]
    etalonnage = {
        "principal": {"h_mois": h_principal, "part_propre_pb": float(f["propre"]), "sigma_pb": float(f["sigma"]),
                      "ic95_nominal_pb": [float(f["bas"]), float(f["haut"])],
                      "ecart_type_z_placebo": dates[f"h{h_principal}"]["ecart_type_z"],
                      "ic95_etalonne_pb": placebo.etalonner(f["propre"], f["sigma"],
                                                            dates[f"h{h_principal}"]["ecart_type_z"]),
                      "bases_placebo_au_moins_aussi_grandes": placebo.depasse(tables[h_principal], f["propre"]),
                      "z": float(f["propre"] / f["sigma"]),
                      "ic95_centile_empirique_pb": placebo.intervalle_empirique(
                          f["propre"], f["sigma"], dates[f"h{h_principal}"]["centile_95_abs_z"])},
        "E5": {"h_mois": int(e5["h"]), "part_propre_pb": float(e5["propre"]), "sigma_pb": float(e5["sigma"]),
               "ic95_nominal_pb": [float(e5["bas"]), float(e5["haut"])],
               "ecart_type_z_placebo": dates[f"h{int(e5['h'])}"]["ecart_type_z"],
               "ic95_etalonne_pb": placebo.etalonner(e5["propre"], e5["sigma"],
                                                     dates[f"h{int(e5['h'])}"]["ecart_type_z"]),
               "bases_placebo_au_moins_aussi_grandes": placebo.depasse(tables[int(e5["h"])], e5["propre"]),
               "ic95_centile_empirique_pb": placebo.intervalle_empirique(
                   e5["propre"], e5["sigma"], dates[f"h{int(e5['h'])}"]["centile_95_abs_z"]),
               "note_b": "le placebo réestime b à chaque base ; l'automne 2026 garde le b du modèle principal"},
        "note": ("élargissement de l'intervalle nominal par l'écart-type des z du placebo par dates ; les fenêtres "
                 "placebo se chevauchent, et la période n'en contient qu'une poignée sans chevauchement"),
    }

    sortie = {
        "note": ("Hors plan, ajouté le 28 novembre 2026, après la seconde relecture de la page par une session de "
                 "relecture distincte, par IA : ces calculs ne sont pas dans PLAN.md et ne changent ni le titre ni "
                 "les chiffres de tête. Même méthode que le modèle principal (b sur les 60 variations qui finissent "
                 "au mois de base, intervalle de Newey-West)."),
        "date_ajout": DATE_AJOUT, "base": analyse.BASE, "fin": analyse.FIN, "n_mois_estimation": n,
        "par_pays_contre_les_sept_autres_pairs": pays,
        "par_pays_avec_la_france_parmi_les_pairs": avec_france,
        "par_dates_france": dates,
        "par_dates_pairs_h29": pairs_dates,
        "etalonnage": etalonnage,
    }
    (RESULTATS / "placebo.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
