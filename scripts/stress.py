"""Section 10 du plan : cinq chocs instantanés sur une OAT à 10 ans et sur une position OAT contre Bund neutre en DV01.

Lit resultats/decomposition.json (part propre, b, variation de l'écart moyen des pairs en 2011) ; écrit
resultats/stress.json et figures/4_stress.png.
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ecart_oat_bund import analyse, donnees, style
from ecart_oat_bund.nelson_siegel import estimer_facteurs
from ecart_oat_bund.stress import (AUCUN_CHOC, choc_facteurs, choc_interpole, choc_niveau, courbe_moyenne, courbe_oat,
                                   duration, dv01_taux, nominal_de_couverture, sensibilite_ecart, titre_au_pair,
                                   valeur_position)

FIGURES, RESULTATS = Path("figures"), Path("resultats")
NOMINAL = 100.0                      # M€
MATURITES_ABE = {"3M": 0.25, "1Y": 1.0, "5Y": 5.0, "10Y": 10.0, "15Y": 15.0}


def _fr(x: float, decimales: int = 1) -> str:
    return f"{x:.{decimales}f}".replace(".", ",").replace("-", "−")


def _signe(x: float) -> str:
    """Un nombre arrondi au pb avec son signe : « +218 », « −100 »."""
    return ("+" if round(x) > 0 else "") + _fr(x, 0)


def main() -> None:
    FIGURES.mkdir(exist_ok=True)
    style.appliquer()
    dec = json.loads((RESULTATS / "decomposition.json").read_text())
    principal = dec["modele_principal"]
    x_propre = principal["part_propre_pb"]
    b = principal["estimation"]["coefficients"]["P"]
    dP_2011 = dec["episodes"]["E1"]["variation_P_G8_pb"]
    ecart = principal["ecart_fin_pb"]

    # Courbe AAA en moyenne d'octobre 2026 ; courbe des OAT = AAA + écart d'octobre 2026
    quotidien = donnees.lire_courbe()
    mois = quotidien[quotidien.index.to_period("M") == pd.Period(analyse.FIN, "M")]
    aaa = courbe_moyenne(mois[list(donnees.PARAMETRES)])
    taus = list(donnees.MATURITES.values())
    controle = float(np.abs(aaa(taus) - mois[list(donnees.MATURITES)].mean().to_numpy()).max())

    # Rejeu de 2022 : facteurs de Nelson-Siegel en fin de mois, décembre 2021 et décembre 2022
    mensuel = donnees.fin_de_mois(quotidien)
    facteurs = estimer_facteurs(mensuel[list(donnees.MATURITES)], taus)
    f21, f22 = facteurs.loc["2021-12"].iloc[0], facteurs.loc["2022-12"].iloc[0]
    d_facteurs = (f22 - f21).to_numpy()

    # Chocs de marché de l'ABE 2025 (en pb), par maturité
    abe = donnees.lire_cers_chocs_marche()
    fr, de, swap = (abe["ecarts_souverains_contre_swap_pb"]["France"], abe["ecarts_souverains_contre_swap_pb"]["Germany"],
                    abe["swap_eur_pb"])
    m_swap = [MATURITES_ABE[m] for m in ("3M", "1Y", "5Y", "10Y")]
    m_sov = [MATURITES_ABE[m] for m in ("3M", "1Y", "5Y", "10Y", "15Y")]
    swap_c = choc_interpole(m_swap, [swap[m] for m in ("3M", "1Y", "5Y", "10Y")])
    de_c = choc_interpole(m_sov, [de[m] for m in ("3M", "1Y", "5Y", "10Y", "15Y")])
    fr_c = choc_interpole(m_sov, [fr[m] for m in ("3M", "1Y", "5Y", "10Y", "15Y")])
    abe_aaa = lambda tau: swap_c(tau) + de_c(tau)  # noqa: E731
    abe_ecart = lambda tau: fr_c(tau) - de_c(tau)  # noqa: E731

    chocs = {
        "C1_prime_resorbee": {"libelle": "prime française résorbée", "aaa": AUCUN_CHOC,
                              "ecart": choc_niveau(-x_propre / 100), "ecart_10_ans_pb": -x_propre, "aaa_10_ans_pb": 0.0},
        "C2_choc_commun_2011": {"libelle": "choc commun de 2011", "aaa": AUCUN_CHOC,
                                "ecart": choc_niveau(b * dP_2011 / 100), "ecart_10_ans_pb": b * dP_2011,
                                "aaa_10_ans_pb": 0.0},
        "C3_niveau_2022": {"libelle": "niveau de 2022", "aaa": choc_niveau(d_facteurs[0]), "ecart": AUCUN_CHOC,
                           "ecart_10_ans_pb": 0.0, "aaa_10_ans_pb": 100 * d_facteurs[0]},
        "C4_rejeu_2022": {"libelle": "rejeu des trois facteurs de 2022", "aaa": choc_facteurs(d_facteurs),
                          "ecart": AUCUN_CHOC, "ecart_10_ans_pb": 0.0,
                          "aaa_10_ans_pb": float(100 * choc_facteurs(d_facteurs)([10.0])[0])},
        "C5_abe_2025_marche": {"libelle": "choc de marché de l'ABE 2025", "aaa": abe_aaa, "ecart": abe_ecart,
                               "ecart_10_ans_pb": float(100 * abe_ecart([10.0])[0]),
                               "aaa_10_ans_pb": float(100 * abe_aaa([10.0])[0])},
    }

    # Positions : (A) 100 M€ d'OAT 10 ans au pair ; (B) la même OAT contre une vente de Bund neutre en DV01
    oat = titre_au_pair(courbe_oat(aaa, ecart), 10, "FR", NOMINAL)
    bund = nominal_de_couverture(oat, aaa, ecart)
    positions = {"A_oat_seule": [oat], "B_oat_contre_bund": [oat, bund]}
    sortie_positions = {}
    for nom, lignes in positions.items():
        v0 = valeur_position(lignes, aaa, ecart)
        r = {"valeur_depart_meur": v0, "dv01_taux_keur_par_pb": 1e3 * dv01_taux(lignes, aaa, ecart),
             "sensibilite_ecart_keur_par_pb": 1e3 * sensibilite_ecart(lignes, aaa, ecart), "chocs": {}}
        for c, spec in chocs.items():
            v1 = valeur_position(lignes, aaa, ecart, choc_aaa=spec["aaa"], choc_ecart=spec["ecart"])
            r["chocs"][c] = {"variation_meur": v1 - v0, "variation_pct_du_nominal_oat": 100 * (v1 - v0) / NOMINAL,
                             "premier_ordre_meur": -(r["dv01_taux_keur_par_pb"] * spec["aaa_10_ans_pb"]
                                                     + r["sensibilite_ecart_keur_par_pb"] * spec["ecart_10_ans_pb"]) / 1e3}
        sortie_positions[nom] = r

    resultats = {
        "source": "ECB statistics (courbe AAA) ; Eurostat (écart d'octobre 2026) ; CERS (scénario de marché de l'ABE "
                  "2025). Calculs de l'auteur.",
        "plan": "PLAN.md, section 10, commit f938339",
        "courbe_aaa": {"mois": analyse.FIN, "jours": int(len(mois)),
                       "taux_zero_coupon_pct": {s: float(v) for s, v in zip(donnees.MATURITES, aaa(taus))},
                       "controle_moyenne_des_courbes_contre_moyenne_des_taux_publies_point": controle},
        "ecart_oat_pb": ecart,
        "oat": {"coupon_pct": oat["coupon_pct"], "duration_ans": duration(courbe_oat(aaa, ecart), oat["dates"], oat["flux"])},
        "bund": {"coupon_pct": bund["coupon_pct"], "nominal_meur": bund["nominal"],
                 "duration_ans": duration(aaa, bund["dates"], bund["flux"])},
        "facteurs_2022": {"decembre_2021": {k: float(v) for k, v in f21.items()},
                          "decembre_2022": {k: float(v) for k, v in f22.items()},
                          "variation_pb": {k: float(100 * v) for k, v in zip(f21.index, d_facteurs)},
                          "dates": [mensuel.loc["2021-12"].index[0].strftime("%Y-%m-%d"),
                                    mensuel.loc["2022-12"].index[0].strftime("%Y-%m-%d")]},
        "abe_2025_marche_pb": {"france_contre_swap": fr, "allemagne_contre_swap": de, "swap_eur": swap},
        "chocs": {c: {"libelle": s["libelle"], "ecart_10_ans_pb": s["ecart_10_ans_pb"], "aaa_10_ans_pb": s["aaa_10_ans_pb"]}
                  for c, s in chocs.items()},
        "entrees": {"part_propre_pb": x_propre, "b": b, "variation_P_G8_2011_06_2011_11_pb": dP_2011},
        "controle_ajoute_apres_coup": {
            "note": "ajouté après le premier calcul, hors plan : les coupons construits face aux taux d'Eurostat du même mois",
            "taux_eurostat_pct": {p: float(donnees.lire_taux_longs().loc[analyse.FIN, p]) for p in ("FR", "DE")}},
        "positions": sortie_positions,
    }
    (RESULTATS / "stress.json").write_text(json.dumps(analyse.arrondir(resultats), indent=2, ensure_ascii=False))

    # Figure 4
    fig, ax = plt.subplots(figsize=(11, 4.6))
    noms = list(chocs)
    x = np.arange(len(noms))
    largeur = 0.36
    for decalage, (pos, couleur, etiquette) in zip((-largeur / 2, largeur / 2), [
            ("A_oat_seule", style.ENCRE, f"A : 100 M€ d'OAT 10 ans (DV01 {_fr(sortie_positions['A_oat_seule']['dv01_taux_keur_par_pb'], 0)} k€ par pb)"),
            ("B_oat_contre_bund", style.ORANGE, f"B : la même OAT contre {_fr(-bund['nominal'], 1)} M€ de Bund 10 ans, neutre en DV01")]):
        valeurs = [sortie_positions[pos]["chocs"][c]["variation_meur"] for c in noms]
        barres = ax.bar(x + decalage, valeurs, largeur, color=couleur, label=etiquette)
        for barre, v in zip(barres, valeurs):
            ax.text(barre.get_x() + barre.get_width() / 2, v + (0.25 if v >= 0 else -0.25),
                    _fr(v, 2 if abs(v) < 0.5 else 1),
                    ha="center", va="bottom" if v >= 0 else "top", fontsize=8)
    etiquettes = []
    for c in noms:
        s = chocs[c]
        morceaux = []
        if abs(s["ecart_10_ans_pb"]) > 1e-9:
            morceaux.append(f"écart {_signe(s['ecart_10_ans_pb'])} pb")
        if abs(s["aaa_10_ans_pb"]) > 1e-9:
            morceaux.append(f"AAA 10 ans {_signe(s['aaa_10_ans_pb'])} pb")
        etiquettes.append(f"{s['libelle']}\n" + "\n".join(morceaux))
    ax.set_xticks(x, etiquettes, fontsize=8)
    ax.axhline(0, color=style.ENCRE_2, lw=0.7)
    ax.set_ylabel("variation de valeur (M€)")
    ax.set_title(f"Chocs instantanés ; départ : courbe AAA et écart OAT-Bund ({_fr(ecart, 0)} pb) en moyenne d'octobre 2026",
                 loc="left")
    ax.legend(loc="lower left", fontsize=8)
    style.virgule(ax, decimales=0)
    fig.text(0.01, -0.06, "Réévaluation complète, sans portage. OAT = courbe AAA + écart constant ; Bund = courbe AAA. "
             "Sources : ECB statistics (courbe AAA), Eurostat (écart), CERS (choc de l'ABE 2025) ; calculs de l'auteur.",
             fontsize=7.5, color=style.ENCRE_2)
    fig.tight_layout()
    fig.savefig(FIGURES / "4_stress.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(json.dumps(analyse.arrondir({k: resultats[k] for k in ("courbe_aaa", "ecart_oat_pb", "oat", "bund", "facteurs_2022",
                                                                 "chocs", "positions")}, 3), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
