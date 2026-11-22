"""La décomposition de l'écart OAT-Bund, telle que fixée dans PLAN.md (sections 3 à 9), commité avant ce module.

Modèle principal, en variations mensuelles et sans constante :

    Δs_FR(t) = b × ΔP(t) + ε(t)

s_FR est l'écart de la France à l'Allemagne et P l'écart moyen des pairs à l'Allemagne, pondéré par le PIB de
2019, tous deux en pb et en moyenne mensuelle. b est estimé sur une fenêtre qui se termine au mois de base T0. Pour
t après T0, la part propre à la France est la somme des résidus depuis T0 :

    X(t) = Σ_{T0 < k ≤ t} (Δs_FR(k) − b̂ ΔP(k)) = s_FR(t) − [s_FR(T0) + b̂ (P(t) − P(T0))]

Son intervalle à 95 % est X(t) ± 1,96 σ(t), avec σ(t)² = V_h + g' Var(b̂) g : V_h est la variance d'une somme de
h résidus autocorrélés (h = t − T0 mois), g la somme des régresseurs depuis T0. Les deux termes sont estimés à la
Newey-West (noyau de Bartlett, L retards) sur la fenêtre d'estimation.

Le même code sert à la variante en taux (deux régresseurs, Δy_DE et Δȳ), aux épisodes de contrôle et au tableau
sans modèle.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

Z_95 = 1.959963984540054   # quantile à 97,5 % de la loi normale


# --- Écarts et pondérations --------------------------------------------------------------------------------------

def ecarts_pb(taux: pd.DataFrame, reference: str = "DE") -> pd.DataFrame:
    """Écart de chaque pays au pays de référence, en pb : 100 × (y_i − y_ref)."""
    return 100 * taux.sub(taux[reference], axis=0)


def poids_pib(pib: pd.Series, groupe) -> pd.Series:
    """Poids de chaque pays du groupe : son PIB divisé par la somme des PIB du groupe."""
    p = pib.loc[list(groupe)].astype(float)
    return p / p.sum()


def moyenne_ponderee(df: pd.DataFrame, poids: pd.Series) -> pd.Series:
    """Moyenne des colonnes de `df` pondérée par `poids` (dont les clés sont des colonnes de `df`)."""
    return (df[list(poids.index)] * poids).sum(axis=1)


# --- Estimation --------------------------------------------------------------------------------------------------

def retards_newey_west(T: int) -> int:
    """Nombre de retards : partie entière de 4 × (T / 100)^(2/9) (règle de Newey et West, 1994)."""
    return int(np.floor(4 * (T / 100) ** (2 / 9)))


def poids_bartlett(L: int) -> np.ndarray:
    """Poids du noyau de Bartlett pour les retards 0 … L : 1 − j / (L + 1)."""
    return 1 - np.arange(L + 1) / (L + 1)


def autocovariances(residus: np.ndarray, L: int) -> np.ndarray:
    """γ_j = (1/T) Σ_t ε(t) ε(t − j), j = 0 … L, non centrées (le modèle n'a pas de constante)."""
    e = np.asarray(residus, dtype=float)
    T = len(e)
    return np.array([(e[j:] * e[: T - j]).sum() / T for j in range(L + 1)])


def variance_somme(gammas: np.ndarray, h: int, L: int) -> float:
    """Variance d'une somme de h résidus : h γ0 + 2 Σ_{j=1}^{min(L, h−1)} (1 − j/(L+1)) (h − j) γ_j."""
    w = poids_bartlett(L)
    v = h * gammas[0]
    for j in range(1, min(L, h - 1) + 1):
        v += 2 * w[j] * (h - j) * gammas[j]
    return float(v)


def variance_hac(X: np.ndarray, residus: np.ndarray, L: int) -> np.ndarray:
    """Variance des coefficients des moindres carrés, à la Newey-West, sans correction de petit échantillon :
    (X'X)⁻¹ S (X'X)⁻¹, S = Σ_t u_t u_t' + Σ_{j=1}^{L} w_j Σ_t (u_t u_{t−j}' + u_{t−j} u_t'), u_t = x_t ε_t."""
    X = np.atleast_2d(np.asarray(X, dtype=float))
    if X.shape[0] != len(residus):
        X = X.T
    u = X * np.asarray(residus, dtype=float)[:, None]
    w = poids_bartlett(L)
    S = u.T @ u
    for j in range(1, L + 1):
        G = u[j:].T @ u[:-j]
        S += w[j] * (G + G.T)
    inv = np.linalg.inv(X.T @ X)
    return inv @ S @ inv


@dataclass
class Estimation:
    """Ce que l'estimation sur la fenêtre retient pour la suite."""
    noms: list[str]
    coef: np.ndarray
    variance: np.ndarray
    residus: pd.Series
    gammas: np.ndarray
    L: int
    r2_non_centre: float

    @property
    def T(self) -> int:
        return len(self.residus)

    @property
    def erreurs_types(self) -> np.ndarray:
        return np.sqrt(np.diag(self.variance))

    def resume(self) -> dict:
        return {"fenetre": [str(self.residus.index[0]), str(self.residus.index[-1])], "variations": self.T,
                "retards_newey_west": self.L,
                "coefficients": {n: float(c) for n, c in zip(self.noms, self.coef)},
                "erreurs_types_newey_west": {n: float(s) for n, s in zip(self.noms, self.erreurs_types)},
                "r2_non_centre": self.r2_non_centre,
                "ecart_type_residus_pb": float(np.sqrt(self.gammas[0])),
                "moyenne_residus_pb": float(self.residus.mean())}


def fenetre(index: pd.PeriodIndex, fin: str, n: int | None = None, debut: str | None = None) -> pd.PeriodIndex:
    """Les mois de la fenêtre d'estimation : les `n` mois qui se terminent à `fin`, ou de `debut` à `fin`."""
    fin_p = pd.Period(fin, "M")
    if (n is None) == (debut is None):
        raise ValueError("donner soit n, soit debut")
    debut_p = fin_p - (n - 1) if n is not None else pd.Period(debut, "M")
    mois = index[(index >= debut_p) & (index <= fin_p)]
    attendus = pd.period_range(debut_p, fin_p, freq="M")
    if not mois.equals(attendus):
        raise ValueError("la fenêtre d'estimation sort des données ou a un trou")
    return mois


def estimer(cible: pd.Series, regresseurs: pd.DataFrame, fin: str, n: int | None = None,
            debut: str | None = None) -> Estimation:
    """Moindres carrés sans constante de `cible` sur `regresseurs` (des variations mensuelles), sur la fenêtre."""
    mois = fenetre(cible.index, fin, n, debut)
    y = cible.loc[mois].to_numpy(dtype=float)
    X = regresseurs.loc[mois].to_numpy(dtype=float)
    if np.isnan(y).any() or np.isnan(X).any():
        raise ValueError("valeur manquante dans la fenêtre d'estimation")
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ coef
    L = retards_newey_west(len(y))
    return Estimation(noms=list(regresseurs.columns), coef=coef, variance=variance_hac(X, e, L),
                      residus=pd.Series(e, index=mois, name="residu"), gammas=autocovariances(e, L), L=L,
                      r2_non_centre=float(1 - (e ** 2).sum() / (y ** 2).sum()))


def cumuler(est: Estimation, cible: pd.Series, regresseurs: pd.DataFrame, base: str, fin: str) -> pd.DataFrame:
    """Le chemin de la part propre, mois par mois, de base + 1 à fin.

    Colonnes : h, observé (somme de la cible depuis la base), part commune (somme de coef · régresseurs), part
    propre X (leur différence), σ, et les bornes de l'intervalle à 95 %."""
    b, f = pd.Period(base, "M"), pd.Period(fin, "M")
    mois = cible.index[(cible.index > b) & (cible.index <= f)]
    if not mois.equals(pd.period_range(b + 1, f, freq="M")):
        raise ValueError("la période cumulée sort des données ou a un trou")
    y = cible.loc[mois].to_numpy(dtype=float)
    X = regresseurs.loc[mois].to_numpy(dtype=float)
    observe = np.cumsum(y)
    g = np.cumsum(X, axis=0)                      # somme des régresseurs depuis la base
    commune = g @ est.coef
    propre = observe - commune
    h = np.arange(1, len(mois) + 1)
    variance = np.array([variance_somme(est.gammas, int(k), est.L) + gk @ est.variance @ gk for k, gk in zip(h, g)])
    sigma = np.sqrt(variance)
    return pd.DataFrame({"h": h, "observe": observe, "commune": commune, "propre": propre, "sigma": sigma,
                         "bas": propre - Z_95 * sigma, "haut": propre + Z_95 * sigma}, index=mois)


def decomposer(cible_niveau: pd.Series, regresseurs_niveau: pd.DataFrame, base: str, fin: str,
               fin_estimation: str | None = None, n: int | None = None, debut_estimation: str | None = None,
               estimation: Estimation | None = None) -> tuple[Estimation, pd.DataFrame]:
    """Des niveaux mensuels aux variations, estimation (ou estimation donnée), puis chemin de la part propre."""
    cible = cible_niveau.diff().dropna()
    regresseurs = regresseurs_niveau.diff().dropna()
    if estimation is None:
        estimation = estimer(cible, regresseurs, fin_estimation or base, n=n, debut=debut_estimation)
    return estimation, cumuler(estimation, cible, regresseurs, base, fin)


# --- Sans modèle, et faits à recalculer --------------------------------------------------------------------------

def france_contre_pays(taux: pd.DataFrame, base: str, fin: str, pays, france: str = "FR",
                       moyennes: dict[str, pd.Series] | None = None) -> pd.DataFrame:
    """Écart y_FR − y_i (pb) au mois de base, au mois de fin, et sa variation, pour chaque pays i (et chaque série
    moyenne donnée dans `moyennes`, par exemple le taux moyen des pairs pondéré par le PIB)."""
    lignes = {}
    series = {p: taux[p] for p in pays}
    series.update(moyennes or {})
    for nom, y in series.items():
        e = 100 * (taux[france] - y)
        lignes[nom] = {"base_pb": float(e.loc[base]), "fin_pb": float(e.loc[fin]),
                       "variation_pb": float(e.loc[fin] - e.loc[base])}
    return pd.DataFrame(lignes).T


def plus_haut_depuis(serie: pd.Series, mois: str) -> str | None:
    """Le dernier mois avant `mois` où la série atteint ou dépasse sa valeur de `mois` ; None s'il n'y en a pas."""
    m = pd.Period(mois, "M")
    avant = serie[serie.index < m]
    atteint = avant[avant >= serie.loc[m]]
    return None if atteint.empty else str(atteint.index[-1])


def mois_au_dessus(a: pd.Series, b: pd.Series, debut: str | None = None, fin: str | None = None) -> list[str]:
    """Les mois (entre `debut` et `fin` inclus) où a > b, inégalité stricte."""
    d = (a - b).loc[debut:fin]
    return [str(p) for p in d.index[d > 0]]
