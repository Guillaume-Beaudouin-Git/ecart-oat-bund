"""Section 8 du README : prévoir le Bund, le niveau ou l'amplitude ? Applique une fois PLAN_PREVISION.md (commit
999b7cc, antérieur à ce script et à tout calcul sur les séries réelles).

    uv run python scripts/prevision.py

Lit les taux zéro-coupon quotidiens de la Bundesbank (10 ans et 2 ans), le 10 ans de la courbe AAA de la BCE et la
DV01 de resultats/stress.json. Écrit resultats/prevision.json, resultats/prevision_par_origine.csv,
figures/5_prevision_volatilite.png et figures/6_bandes.png, et affiche la sortie de l'outil : les bandes de
variation du Bund à 10 ans sur quatre trimestres et le choc à 99 % sur un trimestre.
"""
import json
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ecart_oat_bund import analyse, donnees, style
from ecart_oat_bund import prevision as pv

FIGURES, RESULTATS = Path("figures"), Path("resultats")
TELECHARGEMENT = "2026-11-23"        # jour du téléchargement des séries de la Bundesbank depuis août 1997
SOURCE = ("Source : Deutsche Bundesbank (taux zéro-coupon à 10 ans des titres fédéraux, méthode de Svensson) ; "
          "calculs de l'auteur.")
HORIZONS_TOUS = tuple(sorted(set(pv.HORIZONS) | set(pv.HORIZONS_BANDES)))
ANNEES_RETIREES = {"sans_2008_2009": (2008, 2009), "sans_2022_2023": (2022, 2023)}
NOMS = {"garch": "GARCH(1,1)", "hv252": "volatilité historique, 252 jours", "hv63": "volatilité historique, 63 jours",
        "ewma": "EWMA 0,94"}


def _fr(x: float, decimales: int = 1) -> str:
    return f"{x:.{decimales}f}".replace(".", ",").replace("-", "−")


def _jour(d) -> str:
    return pd.Timestamp(d).strftime("%Y-%m-%d")


def back_test(taux: pd.Series, fenetre_garch: int | None = None):
    """Variations, états aux origines (la dernière est le dernier jour publié) et prévisions à chaque horizon."""
    r = pv.variations_pb(taux)
    e = pv.etats(r, pv.origines(r.index), fenetre_garch)
    return r, e, {h: pv.prevoir(r, e, h) for h in HORIZONS_TOUS}


def decrire(taux: pd.Series, r: pd.Series, e: pd.DataFrame) -> dict:
    return {"premier_jour": _jour(taux.index[0]), "dernier_jour": _jour(taux.index[-1]),
            "premier_mois": taux.index[0].strftime("%Y-%m"), "jours_publies": int(len(taux)),
            "variations": int(len(r)), "ecart_type_des_variations_pb": float(r.std(ddof=0)),
            "plus_grande_variation_absolue_pb": float(r.abs().max()), "jour_de_la_plus_grande_variation": _jour(r.abs().idxmax()),
            "premiere_origine": _jour(e.index[0]), "variations_connues_a_la_premiere_origine": int(e["position"].iloc[0] + 1),
            "ajustements_garch": int(len(e)), "non_convergences_garch": int((~e["converge"]).sum())}


def evaluer_horizons(p: dict) -> dict:
    return {f"h{h}": pv.evaluer(p[h], h) for h in pv.HORIZONS}


def concentration(p: pd.DataFrame, h: int) -> dict:
    """Descriptif, sans test : d'où vient l'écart de perte entre la référence et la GARCH, année par année (date de
    fin de cible), et le gain recalculé sans les deux épisodes de forte volatilité."""
    d = pd.Series(pv.qlike(p["rv"], p[pv.REFERENCE]) - pv.qlike(p["rv"], p[pv.PRINCIPAL]), index=p.index)
    annees = p["fin_cible"].dt.year
    par_annee = d.groupby(annees.to_numpy()).sum()
    sortie = {"somme_des_ecarts_de_perte": float(d.sum()),
              "part_par_annee_de_fin_de_cible_pct": {str(a): float(100 * v / d.sum()) for a, v in par_annee.items()},
              "annees_ou_la_garch_fait_mieux": int((par_annee > 0).sum()), "annees": int(len(par_annee))}
    for nom, retirees in ANNEES_RETIREES.items():
        reste = p[~annees.isin(retirees).to_numpy()]
        c = pv.comparer(reste, pv.PRINCIPAL, pv.REFERENCE, h)
        sortie[nom] = {"origines": int(len(reste)), "gain_pct": c["gain_pct"],
                       "part_de_la_somme_retiree_pct": float(100 * par_annee.reindex(list(retirees)).fillna(0).sum() / d.sum())}
    return sortie


def couvertures(p: dict) -> dict:
    """Part des origines où la variation réalisée du taux reste dans la bande à 95 % de chaque règle."""
    sortie = {}
    for h in HORIZONS_TOUS:
        sortie[f"h{h}"] = {"origines": int(len(p[h])), "trimestres_ou_mois_sans_chevauchement": int(len(p[h]) // pv.MOIS_PAR_HORIZON[h]),
                           **{regle: pv.couverture(p[h]["variation_pb"], p[h][regle]) for regle in pv.REGLES}}
    return sortie


def queues(p: pd.DataFrame) -> dict:
    """À 63 jours : fréquence des dépassements du choc normal à 99 %, vers le haut et vers le bas, et quantile
    empirique des variations standardisées par la GARCH."""
    sortie = {}
    for regle in (pv.PRINCIPAL, pv.REFERENCE):
        z = pv.variations_standardisees(p, regle)
        sortie[regle] = {"depassements_a_la_hausse_pct": float(100 * (z > pv.Z_99).mean()),
                         "depassements_a_la_baisse_pct": float(100 * (z < -pv.Z_99).mean()),
                         "nombre_a_la_hausse": int((z > pv.Z_99).sum()), "nombre_a_la_baisse": int((z < -pv.Z_99).sum()),
                         "quantile_98_de_z_absolu": float(np.quantile(np.abs(z), pv.QUANTILE_EMPIRIQUE)),
                         "plus_grand_z_absolu": float(np.abs(z).max()),
                         "origine_du_plus_grand_z": _jour(p.index[int(np.abs(z).argmax())]),
                         "ecart_type_de_z": float(z.std(ddof=0))}
    return sortie


def outil(taux: pd.Series, e: pd.DataFrame, quantile_empirique: float, dv01_keur: float) -> dict:
    """La sortie de l'outil au dernier jour publié : bandes à 95 % sur quatre trimestres, choc à 99 % sur un."""
    dernier = e.iloc[-1]
    niveau = float(taux.iloc[-1])
    sommes = {"garch": {h: pv.somme_variances_garch(dernier["omega"], dernier["alpha"], dernier["beta"], dernier["garch"], h)
                        for h in pv.HORIZONS_BANDES},
              "hv252": {h: h * float(dernier["hv252"]) for h in pv.HORIZONS_BANDES}}
    sigma_63 = float(np.sqrt(sommes["garch"][63]))
    choc_normal, choc_empirique = pv.Z_99 * sigma_63, quantile_empirique * sigma_63
    retenu = max(choc_normal, choc_empirique)
    futurs = pd.bdate_range(e.index[-1] + pd.offsets.BDay(1), periods=max(pv.HORIZONS_BANDES))
    return {
        "date": _jour(e.index[-1]), "niveau_pct": niveau,
        "garch": {"omega": float(dernier["omega"]), "alpha": float(dernier["alpha"]), "beta": float(dernier["beta"]),
                  "persistance": float(dernier["alpha"] + dernier["beta"]),
                  "ecart_type_du_lendemain_pb": float(np.sqrt(dernier["garch"])),
                  "ecart_type_de_long_terme_pb_par_jour": float(np.sqrt(dernier["omega"] / (1 - dernier["alpha"] - dernier["beta"]))),
                  "demi_vie_jours": float(np.log(0.5) / np.log(dernier["alpha"] + dernier["beta"]))},
        "ecart_type_hv252_pb_par_jour": float(np.sqrt(dernier["hv252"])),
        "dates_approchees": {str(h): _jour(futurs[h - 1]) for h in pv.HORIZONS_BANDES},
        "bandes_95": {regle: {str(h): v for h, v in pv.bandes(niveau, s).items()} for regle, s in sommes.items()},
        "choc_99_a_63_jours": {
            "ecart_type_63_jours_pb": sigma_63, "quantile_normal": pv.Z_99, "choc_normal_pb": choc_normal,
            "quantile_empirique_98_de_z_absolu": quantile_empirique, "choc_empirique_pb": choc_empirique,
            "choc_retenu_pb": retenu, "quantile_retenu": "empirique" if choc_empirique >= choc_normal else "normal",
            "dv01_keur_par_pb": dv01_keur, "perte_position_A_meur": pv.perte_premier_ordre_meur(retenu, dv01_keur),
            "perte_position_A_quantile_normal_meur": pv.perte_premier_ordre_meur(choc_normal, dv01_keur),
            "note": "premier ordre : choc × DV01 de taux de la position A (100 M€ d'OAT à 10 ans, resultats/stress.json) ; "
                    "écart OAT-Bund supposé inchangé"},
    }


def figure_volatilite(p: pd.DataFrame, h: int) -> None:
    vol, garch, hv = np.sqrt(p["rv"]), np.sqrt(p[pv.PRINCIPAL]), np.sqrt(p[pv.REFERENCE])
    d = pv.qlike(p["rv"], p[pv.REFERENCE]) - pv.qlike(p["rv"], p[pv.PRINCIPAL])
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10.5, 7), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    ax1.plot(p.index, vol, color=style.ENCRE, lw=1.1, label=f"réalisée sur les {h} jours suivants")
    ax1.plot(p.index, hv, color=style.ORANGE, lw=1.8, label="prévue par la volatilité historique d'un an (référence)")
    ax1.plot(p.index, garch, color=style.BLEU, lw=1.8, label="prévue par la GARCH(1,1), réestimée sur le seul passé")
    ax1.set_ylim(0, None)
    ax1.set_ylabel("pb sur un trimestre" if h == 63 else "pb sur un mois")
    ax1.set_title(f"Volatilité du Bund à 10 ans sur {h} jours, à la date de la prévision", loc="left")
    ax1.legend(loc="upper left", fontsize=8.5)
    style.virgule(ax1, decimales=0)
    ax2.axhline(0, color=style.ENCRE_2, lw=0.7)
    ax2.plot(p.index, np.cumsum(d), color=style.BLEU, lw=1.8)
    ax2.set_ylabel("somme cumulée")
    ax2.set_title("Somme cumulée de (QLIKE de la référence − QLIKE de la GARCH) : monte quand la GARCH fait mieux",
                  loc="left", fontsize=10)
    style.virgule(ax2, decimales=0)
    ax2.xaxis.set_major_locator(mdates.YearLocator(2))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    fig.text(0.01, -0.035, f"{len(p)} prévisions, une chaque fin de mois de {p.index[0]:%m/%Y} à {p.index[-1]:%m/%Y} ; "
             f"volatilité = racine de la somme des carrés des variations quotidiennes.\n{SOURCE}", fontsize=8,
             color=style.ENCRE_2)
    fig.savefig(FIGURES / "5_prevision_volatilite.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def figure_bandes(taux: pd.Series, o: dict) -> None:
    date = pd.Timestamp(o["date"])
    passe = taux.loc[date - pd.DateOffset(years=3):]
    futurs = pd.bdate_range(date + pd.offsets.BDay(1), periods=max(pv.HORIZONS_BANDES))
    x = [date] + [futurs[h - 1] for h in pv.HORIZONS_BANDES]
    niveau = o["niveau_pct"]
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    ax.plot(passe.index, passe, color=style.ENCRE, lw=1.3, label="Bund à 10 ans, taux zéro-coupon")
    for regle, couleur, etiquette in [("garch", style.BLEU, "bande à 95 %, GARCH(1,1)"),
                                      ("hv252", style.ORANGE, "bande à 95 %, volatilité historique d'un an")]:
        b = o["bandes_95"][regle]
        bas = [niveau] + [b[str(h)]["bas_pct"] for h in pv.HORIZONS_BANDES]
        haut = [niveau] + [b[str(h)]["haut_pct"] for h in pv.HORIZONS_BANDES]
        if regle == "garch":
            ax.fill_between(x, bas, haut, color=couleur, alpha=0.16, lw=0)
            ax.plot(x, haut, color=couleur, lw=1.8, marker="o", ms=4, label=etiquette)
            ax.plot(x, bas, color=couleur, lw=1.8, marker="o", ms=4)
            for xi, h in zip(x[1:], pv.HORIZONS_BANDES):
                ax.annotate(f"± {_fr(b[str(h)]['demi_largeur_pb'], 0)} pb", (xi, b[str(h)]["haut_pct"]),
                            textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8.5, color=style.ENCRE)
        else:
            ax.plot(x, haut, color=couleur, lw=1.5, ls="--", label=etiquette)
            ax.plot(x, bas, color=couleur, lw=1.5, ls="--")
    ax.plot([date, x[-1]], [niveau, niveau], color=style.ENCRE_2, lw=1, ls=":", label="prévision centrale : le dernier taux")
    ax.set_ylabel("%")
    ax.set_title(f"Bandes de variation du Bund à 10 ans sur quatre trimestres, au {date:%d/%m/%Y} "
                 f"({_fr(niveau, 2)} %)", loc="left")
    ax.legend(loc="lower left", fontsize=8.5)
    style.virgule(ax, decimales=1)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
    fig.tight_layout()
    fig.text(0.01, -0.06, "Bandes : dernier taux ± 1,96 × écart-type prévu de la variation sur 63, 126, 189 et 252 jours "
             "publiés ; elles ne disent rien du sens de la variation.\n" + SOURCE, fontsize=8, color=style.ENCRE_2)
    fig.savefig(FIGURES / "6_bandes.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def afficher(resultats: dict) -> None:
    o, dec = resultats["outil"], resultats["decision"]
    print(f"\nDécision du plan : {dec['titre']} "
          f"(63 jours : gain {_fr(dec['test_principal']['gain_pct'])} %, p = {_fr(dec['test_principal']['p'], 4)} ; "
          f"21 jours : gain {_fr(dec['test_de_repli']['gain_pct'])} %, p = {_fr(dec['test_de_repli']['p'], 4)})")
    print(f"\nBund à 10 ans au {o['date']} : {_fr(o['niveau_pct'], 2)} %. Bandes de variation à 95 % (GARCH ; référence) :")
    for h in pv.HORIZONS_BANDES:
        g, r = o["bandes_95"]["garch"][str(h)], o["bandes_95"]["hv252"][str(h)]
        print(f"  {h // 63} trimestre(s), {h:>3} jours (vers le {o['dates_approchees'][str(h)]}) : "
              f"± {_fr(g['demi_largeur_pb'], 0)} pb, de {_fr(g['bas_pct'], 2)} % à {_fr(g['haut_pct'], 2)} % ; "
              f"référence ± {_fr(r['demi_largeur_pb'], 0)} pb")
    c = o["choc_99_a_63_jours"]
    print(f"Choc à 99 % sur un trimestre : +{_fr(c['choc_retenu_pb'], 0)} pb (quantile {c['quantile_retenu']} ; "
          f"normal +{_fr(c['choc_normal_pb'], 0)} pb, empirique +{_fr(c['choc_empirique_pb'], 0)} pb), soit "
          f"−{_fr(c['perte_position_A_meur'], 1)} M€ pour 100 M€ d'OAT à 10 ans au premier ordre "
          f"(DV01 {_fr(c['dv01_keur_par_pb'], 0)} k€ par pb), écart OAT-Bund inchangé.")


def main() -> None:
    FIGURES.mkdir(exist_ok=True)
    RESULTATS.mkdir(exist_ok=True)
    style.appliquer()
    fin = donnees.fin_quotidienne()
    series = {"bund_10_ans": donnees.lire_bund_bundesbank().loc[:fin],
              "bund_2_ans": donnees.lire_bund_bundesbank(fichier="bund_2_ans").loc[:fin],
              "aaa_10_ans": donnees.lire_courbe()["SR_10Y"]}
    dv01 = json.loads((RESULTATS / "stress.json").read_text())["positions"]["A_oat_seule"]["dv01_taux_keur_par_pb"]

    # 1. Les trois séries, fenêtre croissante ; le Bund à 10 ans aussi en fenêtre glissante de dix ans
    calculs = {nom: back_test(taux) for nom, taux in series.items()}
    r10, e10, p10 = calculs["bund_10_ans"]
    _, e10_gl, p10_gl = back_test(series["bund_10_ans"], pv.FENETRE_GLISSANTE)

    # 2. Calcul principal et décision
    principal = evaluer_horizons(p10)
    test_63, test_21 = (principal[f"h{h}"]["comparaisons"]["garch_contre_hv252"] for h in (63, 21))
    decision = {"regle": "gain significatif si d moyen > 0 et p bilatéral < 0,05 ; 63 jours, sinon 21 jours, sinon "
                         "section non publiée",
                "test_principal": {"serie": "bund_10_ans", "horizon_jours": 63, **test_63,
                                   "significatif": pv.gain_significatif(test_63)},
                "test_de_repli": {"serie": "bund_10_ans", "horizon_jours": 21, **test_21,
                                  "significatif": pv.gain_significatif(test_21)},
                "titre": pv.decision_du_titre(test_63, test_21)}

    # 3. Variantes fixées d'avance
    mois_aaa = {h: calculs["aaa_10_ans"][2][h].index.to_period("M") for h in pv.HORIZONS}
    p10_aux_origines_aaa = {h: p10[h][p10[h].index.to_period("M").isin(mois_aaa[h])] for h in pv.HORIZONS}
    robustesse = {
        "bund_2_ans": evaluer_horizons(calculs["bund_2_ans"][2]),
        "aaa_10_ans": evaluer_horizons(calculs["aaa_10_ans"][2]),
        "bund_10_ans_aux_origines_de_la_courbe_aaa": evaluer_horizons(p10_aux_origines_aaa),
        "fenetre_glissante": evaluer_horizons(p10_gl),
        "sous_periodes": {nom: {f"h{h}": pv.evaluer(pv.restreindre(p10[h], debut, fin_), h) for h in pv.HORIZONS}
                          for nom, (debut, fin_) in pv.SOUS_PERIODES.items()},
    }
    cellules = [principal] + [robustesse[k] for k in ("bund_2_ans", "aaa_10_ans",
                                                      "bund_10_ans_aux_origines_de_la_courbe_aaa", "fenetre_glissante")]
    cellules += list(robustesse["sous_periodes"].values())
    tests = [c for cellule in cellules for h in cellule.values() for c in h["comparaisons"].values()]
    contre_reference = [h["comparaisons"]["garch_contre_hv252"] for cellule in cellules for h in cellule.values()]

    # 4. Couverture des bandes, queues, concentration
    couverture = {"bund_10_ans": couvertures(p10)}
    queues_63 = queues(p10[63])
    concentrations = {f"h{h}": concentration(p10[h], h) for h in pv.HORIZONS}

    # 5. Le niveau : marche aléatoire contre AR(1)
    mensuel = pv.fin_de_mois(series["bund_10_ans"])
    niveau = {f"h{h}": pv.comparer_niveau(mensuel, h) for h in pv.HORIZONS_NIVEAU}

    # 6. La sortie de l'outil
    sortie_outil = outil(series["bund_10_ans"], e10, queues_63["garch"]["quantile_98_de_z_absolu"], dv01)

    persistance = e10["alpha"] + e10["beta"]
    long_terme = np.sqrt(e10["omega"] / (1 - persistance).clip(lower=1e-12))   # borné si α + β touche 1
    resultats = {
        "source": "Deutsche Bundesbank (taux zéro-coupon à 10 ans et à 2 ans des titres fédéraux) ; ECB statistics "
                  "(courbe AAA, 10 ans). Calculs de l'auteur.",
        "plan": "PLAN_PREVISION.md, commit 999b7cc ; calcul fait une fois, selon le plan",
        "telechargement": TELECHARGEMENT,
        "constantes": {"horizons_jours": list(pv.HORIZONS), "horizons_des_bandes_jours": list(pv.HORIZONS_BANDES),
                       "premiere_origine": pv.PREMIERE_ORIGINE, "variations_minimales_a_la_premiere_origine": pv.MIN_VARIATIONS,
                       "fenetres_historiques_jours": pv.FENETRES_HISTORIQUES, "lambda_ewma": pv.LAMBDA_EWMA,
                       "fenetre_glissante_jours": pv.FENETRE_GLISSANTE, "seuil": pv.SEUIL,
                       "retards_newey_west": {f"h{h}": pv.retards_hac(h) for h in pv.HORIZONS},
                       "sous_periodes_par_fin_de_cible": {k: list(v) for k, v in pv.SOUS_PERIODES.items()},
                       "horizons_du_niveau_mois": list(pv.HORIZONS_NIVEAU), "quantile_bande_95": pv.Z_95,
                       "quantile_choc_99": pv.Z_99, "quantile_empirique": pv.QUANTILE_EMPIRIQUE},
        "donnees": {nom: decrire(series[nom], *calculs[nom][:2]) for nom in series},
        "decision": decision,
        "principal": principal,
        "robustesse": robustesse,
        "concentration": concentrations,
        "couverture_des_bandes_95": couverture,
        "queues_a_63_jours": queues_63,
        "niveau": niveau,
        "garch_bund_10_ans": {
            "premiere_origine": {"date": _jour(e10.index[0]), "omega": float(e10["omega"].iloc[0]),
                                 "alpha": float(e10["alpha"].iloc[0]), "beta": float(e10["beta"].iloc[0])},
            "persistance_min": float(persistance.min()), "persistance_max": float(persistance.max()),
            "ecart_type_de_long_terme_pb_par_jour": {"min": float(long_terme.min()), "max": float(long_terme.max()),
                                                      "fin_2014": float(long_terme.loc["2014-12"].iloc[0]),
                                                      "fin_2021": float(long_terme.loc["2021-12"].iloc[0])},
            "ecart_type_hv252_pb_par_jour": {"fin_2014": float(np.sqrt(e10["hv252"].loc["2014-12"].iloc[0])),
                                             "fin_2021": float(np.sqrt(e10["hv252"].loc["2021-12"].iloc[0]))},
            "fenetre_glissante": {"persistance_min": float((e10_gl["alpha"] + e10_gl["beta"]).min()),
                                  "persistance_max": float((e10_gl["alpha"] + e10_gl["beta"]).max()),
                                  "non_convergences": int((~e10_gl["converge"]).sum())},
        },
        "outil": sortie_outil,
        "decompte": {
            "series": len(series), "regles": len(pv.REGLES), "horizons": len(pv.HORIZONS),
            "cellules_serie_fenetre_echantillon": len(cellules),
            "tests_de_diebold_mariano_sur_la_volatilite": len(tests),
            "dont_test_decisif": 1, "dont_test_de_repli": 1,
            "garch_contre_reference": {
                "comparaisons": len(contre_reference),
                "gain_positif": sum(c["gain_pct"] > 0 for c in contre_reference),
                "gain_significatif": sum(pv.gain_significatif(c) for c in contre_reference),
                "perte_significative": sum(c["d_moyen"] < 0 and c["p"] < pv.SEUIL for c in contre_reference)},
            "tests_sur_le_niveau": len(niveau),
            "ajustements_garch": int(sum(len(c[1]) for c in calculs.values()) + len(e10_gl)),
        },
    }
    (RESULTATS / "prevision.json").write_text(json.dumps(analyse.arrondir(resultats), indent=2, ensure_ascii=False))

    # Détail par origine (Bund à 10 ans, 21 et 63 jours), pour refaire les tests sans relancer les estimations
    morceaux = []
    for h in pv.HORIZONS:
        t = p10[h].join(e10[["omega", "alpha", "beta", "converge"]]).reset_index()
        t.insert(1, "horizon_jours", h)
        t["garch_fenetre_glissante"] = p10_gl[h]["garch"].to_numpy()
        morceaux.append(t)
    detail = pd.concat(morceaux, ignore_index=True)
    for c in ("origine", "fin_cible"):
        detail[c] = detail[c].dt.strftime("%Y-%m-%d")
    detail.round(6).to_csv(RESULTATS / "prevision_par_origine.csv", index=False)

    h_figure = 21 if decision["titre"] == "21 jours" else 63
    figure_volatilite(p10[h_figure], h_figure)
    figure_bandes(series["bund_10_ans"], sortie_outil)

    for nom, cellule in [("Bund 10 ans", principal), ("Bund 2 ans", robustesse["bund_2_ans"]),
                         ("AAA 10 ans", robustesse["aaa_10_ans"]),
                         ("Bund 10 ans, origines AAA", robustesse["bund_10_ans_aux_origines_de_la_courbe_aaa"]),
                         ("Bund 10 ans, fenêtre glissante", robustesse["fenetre_glissante"])] + \
                        [(f"Bund 10 ans, {k}", v) for k, v in robustesse["sous_periodes"].items()]:
        for h in pv.HORIZONS:
            c = cellule[f"h{h}"]
            ligne = "  ".join(f"{regle} {c['regles'][regle]['qlike']:.4f}/{c['regles'][regle]['rmse_vol_pb']:.1f}"
                              for regle in pv.REGLES)
            t = c["comparaisons"]["garch_contre_hv252"]
            print(f"{nom:<32} h={h:>2} n={c['origines']:>3}  {ligne}  | gain {t['gain_pct']:+.1f} % p {t['p']:.4f}")
    print("Niveau :", json.dumps(analyse.arrondir(niveau, 3), ensure_ascii=False))
    print("Couverture :", json.dumps(analyse.arrondir(couverture, 3), ensure_ascii=False))
    print("Décompte :", json.dumps(resultats["decompte"], ensure_ascii=False))
    afficher(resultats)


if __name__ == "__main__":
    main()
