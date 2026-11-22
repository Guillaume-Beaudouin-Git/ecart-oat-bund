"""Les calculs du plan (PLAN.md, commit f938339), dans l'ordre où le plan les écrit.

Ce module ne fait que brancher les données sur `decomposition` : fenêtres, groupes de pairs, variantes et épisodes
sont des constantes recopiées du plan. Les scripts de `scripts/` l'appellent et écrivent `resultats/` et
`figures/`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ecart_oat_bund import donnees
from ecart_oat_bund.decomposition import (Estimation, decomposer, ecarts_pb, france_contre_pays, mois_au_dessus,
                                          moyenne_ponderee, plus_haut_depuis, poids_pib)

BASE = "2024-05"                     # dernier mois avant la dissolution (plan, section 3)
FIN = donnees.DERNIER_MOIS           # octobre 2026 à la date du plan
N_PRINCIPAL = 60
SEUIL_REPLI_PB = 20.0
GROUPES = {"G8": donnees.PAIRS, "coeur": donnees.COEUR, "peripherie": donnees.PERIPHERIE}
VARIANTES = {
    "fenetre_120": {"libelle": "fenêtre de 120 mois", "groupe": "G8", "n": 120},
    "depuis_1999": {"libelle": "fenêtre depuis 1999", "groupe": "G8", "debut": "1999-02"},
    "coeur": {"libelle": "pairs « cœur » NL, BE, AT, FI", "groupe": "coeur", "n": 60},
    "peripherie": {"libelle": "pairs « périphérie » IT, ES, PT, IE", "groupe": "peripherie", "n": 60},
    "taux_bund_libre": {"libelle": "taux, coefficient libre sur le Bund", "groupe": "G8", "n": 60, "taux": True},
}
EPISODES = {
    "E1": {"base": "2011-06", "fin": "2011-11", "libelle": "crise des dettes souveraines"},
    "E2": {"base": "2016-12", "fin": "2017-04", "libelle": "élection présidentielle de 2017"},
    "E3": {"base": "2020-02", "fin": "2020-04", "libelle": "pandémie"},
    "E4": {"base": "2021-12", "fin": "2022-10", "libelle": "resserrement monétaire"},
    "E5": {"base": "2026-08", "fin": "2026-10", "libelle": "automne 2026"},
}
ATTENTES = {"E2": "positive, intervalle sans 0", "E3": "intervalle contenant 0", "E4": "intervalle contenant 0"}


@dataclass
class Donnees:
    taux: pd.DataFrame          # %, moyenne mensuelle, une colonne par pays
    ecarts: pd.DataFrame        # pb, à l'Allemagne
    pib: pd.Series
    poids: dict[str, pd.Series]
    P: dict[str, pd.Series]     # écart moyen des pairs, pb
    ybar: dict[str, pd.Series]  # taux moyen des pairs, %


def charger() -> Donnees:
    taux = donnees.lire_taux_longs()
    ecarts = ecarts_pb(taux)
    pib = donnees.lire_pib_2019()
    poids = {g: poids_pib(pib, pays) for g, pays in GROUPES.items()}
    P = {g: moyenne_ponderee(ecarts, w).rename(f"P_{g}") for g, w in poids.items()}
    ybar = {g: moyenne_ponderee(taux, w).rename(f"ybar_{g}") for g, w in poids.items()}
    return Donnees(taux, ecarts, pib, poids, P, ybar)


def _resume_chemin(chemin: pd.DataFrame) -> dict:
    fin = chemin.iloc[-1]
    return {"mois": str(chemin.index[-1]), "h_mois": int(fin["h"]), "variation_observee_pb": float(fin["observe"]),
            "part_commune_pb": float(fin["commune"]), "part_propre_pb": float(fin["propre"]),
            "sigma_pb": float(fin["sigma"]), "ic95_pb": [float(fin["bas"]), float(fin["haut"])]}


def modele(d: Donnees, groupe: str = "G8", n: int | None = N_PRINCIPAL, debut: str | None = None,
           taux: bool = False, base: str = BASE, fin: str = FIN,
           estimation: Estimation | None = None, fin_estimation: str | None = None):
    """Une décomposition du plan : en écarts (b × ΔP) ou en taux (c Δy_DE + d Δȳ), base, fin, fenêtre."""
    if taux:
        cible = 100 * d.taux["FR"]
        regresseurs = 100 * pd.DataFrame({"DE": d.taux["DE"], "pairs": d.ybar[groupe]})
    else:
        cible = d.ecarts["FR"]
        regresseurs = d.P[groupe].to_frame("P")
    est, chemin = decomposer(cible, regresseurs, base=base, fin=fin, fin_estimation=fin_estimation or base,
                             n=n if debut is None else None, debut_estimation=debut, estimation=estimation)
    return est, chemin


def principal(d: Donnees):
    return modele(d)


def variantes(d: Donnees) -> dict:
    sortie = {}
    for nom, v in VARIANTES.items():
        est, chemin = modele(d, groupe=v["groupe"], n=v.get("n"), debut=v.get("debut"), taux=v.get("taux", False))
        sortie[nom] = {"libelle": v["libelle"], "estimation": est.resume(), **_resume_chemin(chemin)}
    return sortie


def regle_de_repli(x_principal: float, var: dict, seuil: float = SEUIL_REPLI_PB) -> dict:
    ecarts = {nom: v["part_propre_pb"] - x_principal for nom, v in var.items()}
    pire = max(ecarts, key=lambda k: abs(ecarts[k]))
    return {"seuil_pb": seuil, "ecarts_au_principal_pb": ecarts, "plus_grand_ecart_pb": abs(ecarts[pire]),
            "variante_la_plus_eloignee": pire, "applique": bool(abs(ecarts[pire]) > seuil)}


def sans_modele(d: Donnees, base: str = BASE, fin: str = FIN) -> dict:
    t = france_contre_pays(d.taux, base, fin, ("DE",) + donnees.PAIRS, moyennes={"G8": d.ybar["G8"]})
    return {k: {c: float(v) for c, v in ligne.items()} for k, ligne in t.iterrows()}


def episodes(d: Donnees, est_principal: Estimation) -> dict:
    sortie = {}
    for nom, e in EPISODES.items():
        if nom == "E5":   # plan, section 8 : le b du modèle principal
            est, chemin = modele(d, base=e["base"], fin=e["fin"], estimation=est_principal)
        else:
            est, chemin = modele(d, base=e["base"], fin=e["fin"], n=N_PRINCIPAL)
        r = _resume_chemin(chemin)
        bas, haut = r["ic95_pb"]
        lecture = None
        if nom in ("E3", "E4"):
            lecture = {"attente": ATTENTES[nom], "verifiee": bool(bas <= 0 <= haut)}
        elif nom == "E2":
            lecture = {"attente": ATTENTES[nom], "verifiee": bool(r["part_propre_pb"] > 0 and bas > 0)}
        sortie[nom] = {"libelle": e["libelle"], "base": e["base"], "fin": e["fin"], "estimation": est.resume(),
                       "ecart_base_pb": float(d.ecarts["FR"].loc[e["base"]]),
                       "ecart_fin_pb": float(d.ecarts["FR"].loc[e["fin"]]),
                       "variation_P_G8_pb": float(d.P["G8"].loc[e["fin"]] - d.P["G8"].loc[e["base"]]),
                       **r, "lecture": lecture}
    return sortie


def sovciss(s: pd.Series) -> dict:
    """Maximum du SovCISS de la France dans chaque épisode ; plus forte hausse sur un jour en juin 2024."""
    sortie = {}
    for nom, e in EPISODES.items():
        debut = pd.Period(e["base"], "M").start_time
        fin = pd.Period(e["fin"], "M").end_time
        fenetre = s.loc[debut:fin]
        sortie[nom] = {"date_du_maximum": fenetre.idxmax().strftime("%Y-%m-%d"), "maximum": float(fenetre.max())}
    variation = s.diff().loc["2024-06-01":"2024-06-30"]
    jour = variation.idxmax()
    veille = s.index[s.index.get_loc(jour) - 1]
    sortie["juin_2024"] = {"jour_de_la_plus_forte_hausse": jour.strftime("%Y-%m-%d"),
                           "jour_precedent": veille.strftime("%Y-%m-%d"),
                           "valeur_jour_precedent": float(s.loc[veille]), "valeur_du_jour": float(s.loc[jour]),
                           "hausse": float(variation.max())}
    return sortie


def faits(d: Donnees) -> dict:
    s_fr = d.ecarts["FR"]
    grece = donnees.lire_taux_longs(pays=(donnees.GRECE, "DE"), complet=False)
    s_el = 100 * (grece["EL"] - grece["DE"])
    au_dessus_recents = mois_au_dessus(d.taux["FR"], d.taux["IT"], "2025-12", FIN)
    au_dessus_tous = mois_au_dessus(d.taux["FR"], d.taux["IT"])
    return {
        "ecart_mai_2024_pb": float(s_fr.loc[BASE]), "ecart_fin_pb": float(s_fr.loc[FIN]),
        "hausse_pb": float(s_fr.loc[FIN] - s_fr.loc[BASE]),
        "plus_haut_depuis": plus_haut_depuis(s_fr, FIN),
        "ecart_au_plus_haut_depuis_pb": (float(s_fr.loc[plus_haut_depuis(s_fr, FIN)])
                                         if plus_haut_depuis(s_fr, FIN) else None),
        "france_au_dessus_de_l_italie": {"de_2025_12_a_la_fin": au_dessus_recents,
                                          "nombre_de_mois": len(au_dessus_recents),
                                          "premier_mois_depuis_1999": au_dessus_tous[0] if au_dessus_tous else None,
                                          "tous_les_mois_depuis_1999": au_dessus_tous},
        "grece": {"plus_grand_ecart_pb": float(s_el.max()), "mois": str(s_el.idxmax()),
                  "mois_sans_valeur": [str(p) for p in s_el.index[s_el.isna()]]},
    }


def arrondir(x, decimales: int = 6):
    """Arrondit récursivement les nombres d'une structure (pour des JSON lisibles et stables)."""
    if isinstance(x, dict):
        return {str(k): arrondir(v, decimales) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [arrondir(v, decimales) for v in x]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (float, np.floating)):
        return round(float(x), decimales)
    if isinstance(x, np.integer):
        return int(x)
    return x
