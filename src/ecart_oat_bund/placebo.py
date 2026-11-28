"""Placebos de la décomposition : d'autres pays, d'autres dates. Hors plan, ajoutés le 28 novembre 2026.

Ces calculs ne sont pas dans PLAN.md ; ils ont été demandés après une seconde relecture de la page par une session
de relecture distincte, par IA, qui les avait faits avec son propre script. Ils ne changent ni le titre ni les
chiffres de tête. Ils reprennent la méthode du modèle principal telle quelle (`decomposition.decomposer` : b estimé
sans constante sur les 60 variations qui finissent au mois de base, intervalle de Newey-West), et posent deux
questions :

- **par pays** : appliquée à chacun des huit pairs contre l'écart moyen des sept autres (pondéré par le PIB de 2019,
  France exclue), sur la même période que la France, la méthode trouve-t-elle aussi une part propre ?
- **par dates** : appliquée à la France à toutes les dates de base possibles avant la période étudiée, chaque
  fenêtre cumulée finissant au plus tard au mois de base du modèle principal, combien de fois l'intervalle à 95 %
  exclut-il zéro ? Sous les hypothèses du modèle, 5 % des fois.
"""
from __future__ import annotations

import pandas as pd

from ecart_oat_bund.decomposition import Z_95, decomposer, moyenne_ponderee, poids_pib


def facteur_commun(ecarts: pd.DataFrame, pib: pd.Series, groupe) -> pd.DataFrame:
    """L'écart moyen du groupe à l'Allemagne, pondéré par le PIB de 2019, en colonne « P »."""
    return moyenne_ponderee(ecarts, poids_pib(pib, groupe)).to_frame("P")


def par_pays(ecarts: pd.DataFrame, pib: pd.Series, pays, base: str, fin: str, n: int,
             exclus=()) -> dict[str, dict]:
    """Pour chaque pays de `pays`, sa part propre de `base` à `fin` contre l'écart moyen des autres pays de `pays`
    (hors `exclus`), estimée comme le modèle principal."""
    sortie = {}
    for c in pays:
        autres = [p for p in pays if p != c and p not in exclus]
        est, chemin = decomposer(ecarts[c], facteur_commun(ecarts, pib, autres), base=base, fin=fin, n=n)
        f = chemin.iloc[-1]
        sortie[c] = {"pairs": autres, "b": float(est.coef[0]), "variation_observee_pb": float(f["observe"]),
                     "part_propre_pb": float(f["propre"]), "sigma_pb": float(f["sigma"]),
                     "ic95_pb": [float(f["bas"]), float(f["haut"])], "z": float(f["propre"] / f["sigma"]),
                     "exclut_zero": bool(f["bas"] > 0 or f["haut"] < 0)}
    return sortie


def par_dates(cible_niveau: pd.Series, facteur_niveau: pd.DataFrame, h: int, n: int, fin_max: str) -> pd.DataFrame:
    """La part propre à h mois pour chaque mois de base possible : au moins n variations avant la base pour estimer
    b, et une fin (base + h) au plus tard en `fin_max`. Une ligne par base."""
    lignes = []
    limite = pd.Period(fin_max, "M")
    for base in cible_niveau.index[n:]:
        fin = base + h
        if fin > limite:
            break
        est, chemin = decomposer(cible_niveau, facteur_niveau, base=str(base), fin=str(fin), n=n)
        f = chemin.iloc[-1]
        lignes.append({"base": str(base), "fin": str(fin), "b": float(est.coef[0]), "propre": float(f["propre"]),
                       "sigma": float(f["sigma"]), "bas": float(f["bas"]), "haut": float(f["haut"])})
    t = pd.DataFrame(lignes).set_index("base")
    t["z"] = t["propre"] / t["sigma"]
    t["exclut_zero"] = (t["bas"] > 0) | (t["haut"] < 0)
    return t


def resume_dates(t: pd.DataFrame, h: int) -> dict:
    """Ce que la page cite d'un placebo par dates : couverture de l'intervalle nominal, dispersion des z et des parts
    propres, et le nombre de fenêtres de h mois sans chevauchement que la période contient."""
    a = t["propre"].abs()
    premiere, derniere = pd.Period(t.index[0], "M"), pd.Period(t["fin"].iloc[-1], "M")
    mois_couverts = (derniere - premiere).n
    rejets = t.index[t["exclut_zero"]]
    return {"horizon_mois": h, "bases": int(len(t)), "premiere_base": t.index[0], "derniere_base": t.index[-1],
            "derniere_fin": t["fin"].iloc[-1], "fenetres_sans_chevauchement": int(mois_couverts // h),
            "exclut_zero": int(t["exclut_zero"].sum()), "part_exclut_zero": float(t["exclut_zero"].mean()),
            "ecart_type_z": float(t["z"].std()), "sigma_median_pb": float(t["sigma"].median()),
            "mediane_abs_propre_pb": float(a.median()), "centile_95_abs_propre_pb": float(a.quantile(0.95)),
            "max_abs_propre_pb": float(a.max()), "base_max_abs": a.idxmax(),
            "propre_a_la_base_max_abs_pb": float(t.loc[a.idxmax(), "propre"]),
            "min_propre_pb": float(t["propre"].min()), "base_min": t["propre"].idxmin(),
            "max_propre_pb": float(t["propre"].max()), "base_max": t["propre"].idxmax(),
            "max_abs_z": float(t["z"].abs().max()), "base_max_abs_z": t["z"].abs().idxmax(),
            "z_a_la_base_max_abs_z": float(t.loc[t["z"].abs().idxmax(), "z"]),
            "max_z_positif": float(t["z"].max()), "base_max_z_positif": t["z"].idxmax(),
            "centile_95_abs_z": float(t["z"].abs().quantile(0.95)),
            "part_exclut_zero_apres_elargissement": float((t["z"].abs() > Z_95 * t["z"].std()).mean()),
            "bases_ou_l_intervalle_exclut_zero": [str(b) for b in rejets],
            "propre_aux_bases_ou_l_intervalle_exclut_zero_pb": {str(b): float(t.loc[b, "propre"]) for b in rejets},
            "par_annee_de_base": {str(k): int(v) for k, v in
                                  pd.Series(1, index=[b[:4] for b in rejets]).groupby(level=0).sum().items()}}


def etalonner(part_propre: float, sigma: float, ecart_type_z: float) -> list[float]:
    """L'intervalle nominal élargi du facteur que le placebo mesure : part ± 1,96 σ × écart-type des z."""
    demi = Z_95 * sigma * ecart_type_z
    return [float(part_propre - demi), float(part_propre + demi)]


def intervalle_empirique(part_propre: float, sigma: float, centile_95_abs_z: float) -> list[float]:
    """L'intervalle qui prend, au lieu de 1,96, le 95e centile des |z| du placebo : part ± centile × σ."""
    demi = centile_95_abs_z * sigma
    return [float(part_propre - demi), float(part_propre + demi)]


def depasse(t: pd.DataFrame, valeur: float) -> int:
    """Le nombre de bases placebo dont la part propre atteint `valeur` en valeur absolue."""
    return int((t["propre"].abs() >= abs(valeur)).sum())


__all__ = ["facteur_commun", "par_pays", "par_dates", "resume_dates", "etalonner", "intervalle_empirique",
           "depasse"]
