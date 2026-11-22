"""Sections 3 à 9 du plan : la part propre à la France, les variantes, la règle de repli, le tableau sans modèle, les
épisodes de contrôle, le SovCISS et les faits à recalculer.

Écrit resultats/decomposition.json et trois figures : figures/1_ecart_depuis_1999.png,
figures/2_observe_contre_contrefactuel.png, figures/3_episodes.png.
"""
import json
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ecart_oat_bund import analyse, donnees, style
from ecart_oat_bund.decomposition import Z_95

FIGURES, RESULTATS = Path("figures"), Path("resultats")
SOURCE_EUROSTAT = "Source : Eurostat (irt_lt_mcby_m, nama_10_gdp), moyennes mensuelles ; calculs de l'auteur."
# Événements datés par une source primaire (Légifrance, Assemblée nationale) : voir le README.
EVENEMENTS = [("2024-06-09", "dissolution"), ("2024-12-04", "censure"), ("2025-09-08", "confiance\nrefusée")]


def _fr(x: float, decimales: int = 0) -> str:
    return f"{x:.{decimales}f}".replace(".", ",").replace("-", "−")


def _dates(index: pd.PeriodIndex):
    return index.to_timestamp(how="end").normalize()


def main() -> None:
    FIGURES.mkdir(exist_ok=True)
    RESULTATS.mkdir(exist_ok=True)
    style.appliquer()
    d = analyse.charger()

    # 1. Modèle principal (plan, section 4)
    est, chemin = analyse.principal(d)
    principal = {"estimation": est.resume(), "base": analyse.BASE, "fin": analyse.FIN,
                 "ecart_base_pb": float(d.ecarts["FR"].loc[analyse.BASE]),
                 "ecart_fin_pb": float(d.ecarts["FR"].loc[analyse.FIN]),
                 "P_G8_base_pb": float(d.P["G8"].loc[analyse.BASE]), "P_G8_fin_pb": float(d.P["G8"].loc[analyse.FIN]),
                 **analyse._resume_chemin(chemin)}
    h = principal["h_mois"]
    principal["diagnostic_derive"] = {"moyenne_residus_pb_par_mois": est.resume()["moyenne_residus_pb"],
                                      "derive_sur_h_mois_pb": est.resume()["moyenne_residus_pb"] * h,
                                      "note": "fixé dans le plan, sans décision qui en dépende"}
    principal["significative"] = bool(principal["ic95_pb"][0] > 0 or principal["ic95_pb"][1] < 0)
    principal["chemin"] = {str(m): {k: float(v) for k, v in ligne.items()} for m, ligne in chemin.iterrows()}

    # 2. Variantes et règle de repli (section 6)
    variantes = analyse.variantes(d)
    repli = analyse.regle_de_repli(principal["part_propre_pb"], variantes)

    # 3. Sans modèle (section 7), épisodes et SovCISS (section 8), faits (section 9)
    sans_modele = analyse.sans_modele(d)
    episodes = analyse.episodes(d, est)
    sov = analyse.sovciss(donnees.lire_sovciss())
    faits = analyse.faits(d)

    resultats = {
        "source": "Eurostat (irt_lt_mcby_m, nama_10_gdp) ; BCE (SovCISS de la France). Calculs de l'auteur.",
        "plan": "PLAN.md, commit f938339 ; calcul fait une fois, selon le plan",
        "donnees": {"premier_mois": str(d.taux.index[0]), "dernier_mois": str(d.taux.index[-1]),
                    "telechargement": "2026-11-22"},
        "poids_pib_2019": {g: {p: float(v) for p, v in w.items()} for g, w in d.poids.items()},
        "pib_2019_meur": {p: float(v) for p, v in d.pib.items()},
        "modele_principal": principal,
        "variantes": variantes,
        "regle_de_repli": repli,
        "sans_modele": sans_modele,
        "episodes": episodes,
        "sovciss": sov,
        "faits": faits,
        "decompte": {"decompositions": 1 + len(variantes), "episodes": len(episodes), "tableau_sans_modele": 1},
    }
    (RESULTATS / "decomposition.json").write_text(json.dumps(analyse.arrondir(resultats), indent=2,
                                                             ensure_ascii=False))

    # Figure 1 : l'écart depuis 1999
    fig, ax = plt.subplots(figsize=(11, 4.6))
    x = _dates(d.ecarts.index)
    for nom, e in analyse.EPISODES.items():
        ax.axvspan(pd.Period(e["base"], "M").start_time, pd.Period(e["fin"], "M").end_time, color=style.OMBRE, lw=0)
        ax.text(pd.Period(e["base"], "M").start_time, 1.0, nom, transform=ax.get_xaxis_transform(), fontsize=8,
                color=style.ENCRE_2, va="top")
    ax.plot(x, d.P["G8"], color=style.BLEU, lw=1.4, label="écart moyen des huit pairs à l'Allemagne (pondéré par le PIB de 2019)")
    ax.plot(x, d.ecarts["FR"], color=style.ENCRE, lw=1.8, label="écart France − Allemagne")
    ax.axvline(pd.Timestamp("2024-06-09"), color=style.ORANGE, lw=1, ls="--")
    ax.annotate("dissolution\n(9 juin 2024)", xy=(pd.Timestamp("2024-06-09"), 260), xytext=(pd.Timestamp("2019-06-01"), 280),
                fontsize=8, color=style.ORANGE, arrowprops={"arrowstyle": "->", "color": style.ORANGE, "lw": 0.8})
    ax.axhline(0, color=style.ENCRE_2, lw=0.6)
    ax.set_xlim(pd.Timestamp("1998-10-01"), pd.Timestamp("2027-03-01"))
    ax.set_ylabel("pb, en moyenne mensuelle")
    ax.set_title("Écart de taux à 10 ans avec l'Allemagne, 1999-2026", loc="left")
    ax.legend(loc="upper left", fontsize=8.5, bbox_to_anchor=(0.0, 0.93))
    fig.text(0.01, -0.02, "Les pairs : Italie, Espagne, Pays-Bas, Belgique, Autriche, Portugal, Finlande, Irlande. "
             "Zones grisées : les épisodes de contrôle E1 à E5. " + SOURCE_EUROSTAT, fontsize=7.5, color=style.ENCRE_2)
    fig.tight_layout()
    fig.savefig(FIGURES / "1_ecart_depuis_1999.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Figure 2 : observé contre contrefactuel, et les variantes
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.8), gridspec_kw={"width_ratios": [1.45, 1]})
    debut_fig = pd.Period("2023-01", "M")
    obs = d.ecarts["FR"].loc[debut_fig:]
    ax1.plot(_dates(obs.index), obs, color=style.ENCRE, lw=1.8, label="écart observé")
    contre = d.ecarts["FR"].loc[chemin.index] - chemin["propre"]
    base_val = d.ecarts["FR"].loc[analyse.BASE]
    xc = _dates(pd.PeriodIndex([pd.Period(analyse.BASE, "M")]).append(chemin.index))
    yc = np.concatenate([[base_val], contre.to_numpy()])
    sc = np.concatenate([[0.0], chemin["sigma"].to_numpy()])
    ax1.fill_between(xc, yc - Z_95 * sc, yc + Z_95 * sc, color=style.BLEU, alpha=0.15, lw=0,
                     label="intervalle à 95 %")
    ax1.plot(xc, yc, color=style.BLEU, lw=1.6, label="contrefactuel : la France suit les pairs (b × ΔP)")
    xf = _dates(pd.PeriodIndex([pd.Period(analyse.FIN, "M")]))[0]
    ax1.annotate("", xy=(xf, d.ecarts["FR"].loc[analyse.FIN]), xytext=(xf, contre.iloc[-1]),
                 arrowprops={"arrowstyle": "<->", "color": style.ORANGE, "lw": 1.2})
    ax1.text(xf + pd.Timedelta(days=14), (d.ecarts["FR"].loc[analyse.FIN] + contre.iloc[-1]) / 2,
             f"part propre\n{_fr(principal['part_propre_pb'])} pb\n[{_fr(principal['ic95_pb'][0])} ; "
             f"{_fr(principal['ic95_pb'][1])}]", ha="left", va="center", fontsize=8.5, color=style.ORANGE)
    for jour, texte in EVENEMENTS:
        ax1.axvline(pd.Timestamp(jour), color=style.GRIS, lw=0.8, ls=":")
        ax1.text(pd.Timestamp(jour) + pd.Timedelta(days=8), 0.98, texte, transform=ax1.get_xaxis_transform(),
                 fontsize=7, color=style.ENCRE_2, va="top")
    ax1.set_xlim(pd.Timestamp("2023-01-01"), pd.Timestamp("2027-05-01"))
    ax1.xaxis.set_major_locator(mdates.YearLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax1.set_ylabel("pb, en moyenne mensuelle")
    ax1.set_title("Écart France − Allemagne : observé et contrefactuel depuis mai 2024", loc="left")
    ax1.legend(loc="upper left", fontsize=8, bbox_to_anchor=(0.0, 0.86))
    noms = ["principal"] + list(variantes)
    etiquettes = ["modèle principal (G8, 60 mois)"] + [variantes[n]["libelle"] for n in variantes]
    valeurs = [principal] + [variantes[n] for n in variantes]
    yy = np.arange(len(noms))[::-1]
    xp = principal["part_propre_pb"]
    ax2.axvspan(xp - analyse.SEUIL_REPLI_PB, xp + analyse.SEUIL_REPLI_PB, color=style.OMBRE, lw=0,
                label="modèle principal ± 20 pb (règle de repli)")
    for y_, v, n in zip(yy, valeurs, noms):
        couleur = style.ENCRE if n == "principal" else style.BLEU
        ax2.errorbar(v["part_propre_pb"], y_, xerr=[[v["part_propre_pb"] - v["ic95_pb"][0]],
                                                   [v["ic95_pb"][1] - v["part_propre_pb"]]],
                     fmt="o", color=couleur, ecolor=couleur, capsize=3, ms=5)
        ax2.text(v["ic95_pb"][1] + 3, y_, _fr(v["part_propre_pb"]), va="center", fontsize=8, color=couleur)
    ax2.axvline(principal["variation_observee_pb"], color=style.ORANGE, lw=1, ls="--",
                label=f"hausse observée ({_fr(principal['variation_observee_pb'])} pb)")
    ax2.axvline(0, color=style.ENCRE_2, lw=0.6)
    ax2.set_yticks(yy, etiquettes, fontsize=8)
    ax2.set_xlabel("part propre à la France en octobre 2026 (pb), intervalle à 95 %")
    ax2.set_title("Modèle principal et cinq variantes", loc="left")
    ax2.legend(loc="upper left", fontsize=7.5, bbox_to_anchor=(-0.02, -0.13), ncol=2)
    fig.text(0.01, -0.1, "Contrefactuel : écart de mai 2024 plus b × variation de l'écart moyen des pairs, b estimé sur les "
             "60 mois jusqu'à mai 2024. Pointillés : dissolution (décret du 9 juin 2024), censure du gouvernement (scrutin "
             "n° 519 du 4 décembre 2024),\nconfiance refusée (scrutin n° 3054 du 8 septembre 2025). " + SOURCE_EUROSTAT,
             fontsize=7.5, color=style.ENCRE_2)
    fig.tight_layout()
    fig.savefig(FIGURES / "2_observe_contre_contrefactuel.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Figure 3 : les épisodes de contrôle, et le SovCISS de la France
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.6), gridspec_kw={"width_ratios": [1, 1.25]})
    xs = np.arange(len(episodes))
    largeur = 0.26
    obs_v = [e["variation_observee_pb"] for e in episodes.values()]
    com_v = [e["part_commune_pb"] for e in episodes.values()]
    pro_v = [e["part_propre_pb"] for e in episodes.values()]
    err = np.array([[e["part_propre_pb"] - e["ic95_pb"][0], e["ic95_pb"][1] - e["part_propre_pb"]]
                    for e in episodes.values()]).T
    ax1.bar(xs - largeur, obs_v, largeur, color=style.ENCRE, label="variation observée")
    ax1.bar(xs, com_v, largeur, color=style.BLEU, label="part commune (b × ΔP)")
    ax1.bar(xs + largeur, pro_v, largeur, color=style.ORANGE, label="part propre, intervalle à 95 %")
    ax1.errorbar(xs + largeur, pro_v, yerr=err, fmt="none", ecolor=style.ENCRE_2, capsize=3, lw=1)
    ax1.axhline(0, color=style.ENCRE_2, lw=0.6)
    ax1.set_xticks(xs, [f"{n}\n{e['base']}\n→ {e['fin']}" for n, e in episodes.items()], fontsize=8)
    ax1.set_ylabel("pb")
    ax1.set_ylim(min(-35, ax1.get_ylim()[0]), 135)
    ax1.set_title("Épisodes de contrôle : écart France − Allemagne", loc="left")
    ax1.legend(loc="upper right", fontsize=7.5)
    s = donnees.lire_sovciss()
    for nom, e in analyse.EPISODES.items():
        ax2.axvspan(pd.Period(e["base"], "M").start_time, pd.Period(e["fin"], "M").end_time, color=style.OMBRE, lw=0)
        ax2.text(pd.Period(e["base"], "M").start_time, 1.0, nom, transform=ax2.get_xaxis_transform(), fontsize=8,
                 color=style.ENCRE_2, va="top")
    ax2.plot(s.index, s, color=style.ENCRE, lw=0.7)
    ax2.axvline(pd.Timestamp("2024-06-09"), color=style.ORANGE, lw=1, ls="--")
    ax2.set_xlim(pd.Timestamp("1999-10-01"), pd.Timestamp("2027-03-01"))
    ax2.set_title("Tension souveraine de la France (SovCISS de la BCE), quotidien", loc="left")
    style.virgule(ax2, decimales=2)
    fig.text(0.01, -0.04, "Gauche : " + SOURCE_EUROSTAT + " Droite : Source : ECB statistics (CISS.D.FR.Z0Z.4F.EC.SOV_CIN.IDX). "
             "Tiret orange : 9 juin 2024.", fontsize=7.5, color=style.ENCRE_2)
    fig.tight_layout()
    fig.savefig(FIGURES / "3_episodes.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(json.dumps(analyse.arrondir({k: principal[k] for k in principal if k != "chemin"}, 2), indent=1,
                     ensure_ascii=False))
    print(json.dumps(analyse.arrondir({n: {k: v[k] for k in ("part_propre_pb", "ic95_pb", "part_commune_pb")}
                                       for n, v in variantes.items()}, 2), ensure_ascii=False))
    print(json.dumps(analyse.arrondir(repli, 2), ensure_ascii=False))


if __name__ == "__main__":
    main()
