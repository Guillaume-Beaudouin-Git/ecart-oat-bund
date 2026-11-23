"""Prévoir le Bund : le niveau, ou l'amplitude de ses variations ? (PLAN_PREVISION.md, section 8 du README)

Le plan a été commité seul (commit 999b7cc), avant toute estimation sur les données ; ce module le traduit. Tout
ce qu'il contient a été mis au point sur des séries simulées (tests/test_prevision.py).

Notations. y(j) est un taux zéro-coupon publié le jour j, en % ; r(j) = 100 × (y(j) − y(j−1)) est sa variation en
pb entre deux jours publiés consécutifs. Une origine t est le dernier jour publié d'un mois ; à l'origine t, une
règle ne lit que r(j) pour j ≤ t.

- Cible : la variance réalisée sur les h jours publiés suivants, RV(t, h) = Σ_{i=1..h} r(t+i)², en pb².
- Quatre règles donnent F(t, h), la prévision de RV(t, h) :
  - `hv252` (la référence) et `hv63` : h fois la moyenne des 252 ou des 63 derniers carrés ;
  - `ewma` : h fois s², avec s²(t) = 0,94 s²(t−1) + 0,06 r(t)² (RiskMetrics) ;
  - `garch` : GARCH(1,1) à moyenne nulle, σ²(j+1) = ω + α r(j)² + β σ²(j), ajustée par quasi-vraisemblance
    normale (paquet `arch`) sur le seul passé ; F(t, h) = Σ_{i=1..h} E_t[σ²(t+i)].
- Perte : QLIKE(RV, F) = RV/F − ln(RV/F) − 1, nulle si F = RV, positive sinon.
- Test de Diebold-Mariano : d = perte de la référence − perte du modèle, moyenne testée contre 0 avec des
  erreurs-types de Newey-West ; les origines sont mensuelles, l'horizon de h jours compte m = h/21 mois, et le
  nombre de retards est 2m.

Le niveau du taux est prévu à part, en fin de mois : marche aléatoire contre AR(1) direct.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from arch import arch_model

# --- Constantes du plan --------------------------------------------------------------------------------------------

HORIZONS = (21, 63)                     # jours publiés : un mois, un trimestre
HORIZONS_BANDES = (63, 126, 189, 252)   # un à quatre trimestres
MOIS_PAR_HORIZON = {21: 1, 63: 3, 126: 6, 189: 9, 252: 12}
PREMIERE_ORIGINE = "2004-12"
MIN_VARIATIONS = 1000                   # variations connues à la première origine, au moins
REGLES = ("garch", "hv252", "hv63", "ewma")
PRINCIPAL, REFERENCE = "garch", "hv252"
REGLES_SIMPLES = ("hv252", "hv63", "ewma")
FENETRES_HISTORIQUES = {"hv252": 252, "hv63": 63}
LAMBDA_EWMA = 0.94
N_INIT_EWMA = 252
FENETRE_GLISSANTE = 2520                # dix ans de jours publiés
SEUIL = 0.05
SOUS_PERIODES = {"2005-2014": ("2005-01-01", "2014-12-31"), "2015-2021": ("2015-01-01", "2021-12-31"),
                 "2022-2026": ("2022-01-01", "2026-12-31")}
HORIZONS_NIVEAU = (3, 12)               # mois
Z_95 = 1.959963984540054                # quantile à 97,5 % de la loi normale : bande bilatérale à 95 %
Z_99 = 2.3263478740408408               # quantile à 99 % de la loi normale : choc unilatéral à 99 %
QUANTILE_EMPIRIQUE = 0.98               # quantile de |z| : 1 % dans chaque queue si la loi est symétrique


# --- Variations, origines, cible -----------------------------------------------------------------------------------

def variations_pb(taux: pd.Series) -> pd.Series:
    """r(j) = 100 × (y(j) − y(j−1)), en pb, entre deux jours publiés consécutifs ; indexée par le jour j."""
    return (100 * taux.astype(float).diff()).dropna()


def positions_fin_de_mois(index: pd.DatetimeIndex) -> np.ndarray:
    """Positions du dernier jour publié de chaque mois calendaire (la dernière position de la série comprise)."""
    mois = index.to_period("M")
    return np.flatnonzero(np.r_[mois[1:] != mois[:-1], True])


def origines(index: pd.DatetimeIndex, premiere_origine: str = PREMIERE_ORIGINE,
             min_variations: int = MIN_VARIATIONS) -> np.ndarray:
    """Positions des origines : le dernier jour publié de chaque mois à partir de `premiere_origine`, pourvu que
    `min_variations` variations au moins soient connues à cette date (elle comprise)."""
    pos = positions_fin_de_mois(index)
    garde = (index[pos].to_period("M") >= pd.Period(premiere_origine, "M")) & (pos + 1 >= min_variations)
    return pos[garde]


def variance_realisee(r: np.ndarray, t: int, h: int) -> float:
    """RV(t, h) = Σ_{i=1..h} r(t+i)² : la somme des carrés des h variations qui suivent l'origine t."""
    if t + h > len(r) - 1:
        raise ValueError("cible incomplète : il manque des jours après l'origine")
    return float(np.sum(np.asarray(r[t + 1: t + h + 1], dtype=float) ** 2))


# --- Les trois règles simples --------------------------------------------------------------------------------------

def variance_historique(r: np.ndarray, t: int, n: int) -> float:
    """Variance par jour : la moyenne des n derniers carrés connus en t, moyenne des variations supposée nulle."""
    if t + 1 < n:
        raise ValueError(f"moins de {n} variations connues à l'origine")
    return float(np.mean(np.asarray(r[t - n + 1: t + 1], dtype=float) ** 2))


def variances_ewma(r: np.ndarray, lam: float = LAMBDA_EWMA, n_init: int = N_INIT_EWMA) -> np.ndarray:
    """s²(t), variance par jour prévue pour t+1 et connue en t : s²(n_init − 1) est la moyenne des n_init premiers
    carrés, puis s²(t) = λ s²(t−1) + (1 − λ) r(t)². Non définie (NaN) avant."""
    r = np.asarray(r, dtype=float)
    s2 = np.full(len(r), np.nan)
    if len(r) < n_init:
        return s2
    s2[n_init - 1] = np.mean(r[:n_init] ** 2)
    for t in range(n_init, len(r)):
        s2[t] = lam * s2[t - 1] + (1 - lam) * r[t] ** 2
    return s2


# --- GARCH(1,1) ----------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Garch:
    """Une GARCH(1,1) ajustée à une origine t : σ²(j+1) = ω + α r(j)² + β σ²(j)."""
    omega: float
    alpha: float
    beta: float
    variance_suivante: float    # σ²(t+1), connue en t
    converge: bool              # faux si l'optimiseur n'a pas convergé (les paramètres sont alors ceux du repli)

    @property
    def persistance(self) -> float:
        return self.alpha + self.beta

    @property
    def variance_de_long_terme(self) -> float:
        return self.omega / (1 - self.persistance) if self.persistance < 1 else float("inf")


def ajuster_garch(r_passe: np.ndarray, repli: Garch | None = None) -> Garch:
    """GARCH(1,1) à moyenne nulle, quasi-vraisemblance normale, sur les variations `r_passe` (toutes connues à
    l'origine). Réglages par défaut du paquet `arch` : ω > 0, α ≥ 0, β ≥ 0, α + β < 1, variance initiale par
    lissage exponentiel des premières observations. Si l'optimiseur ne converge pas et qu'un `repli` est donné (la
    GARCH de l'origine précédente), ses paramètres sont repris et filtrés sur `r_passe`."""
    r_passe = np.asarray(r_passe, dtype=float)
    modele = arch_model(r_passe, mean="Zero", vol="GARCH", p=1, q=1, dist="normal", rescale=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ajustement = modele.fit(disp="off", show_warning=False)
    converge = ajustement.convergence_flag == 0
    if not converge and repli is not None:
        ajustement = modele.fix([repli.omega, repli.alpha, repli.beta])
    omega, alpha, beta = (float(x) for x in np.asarray(ajustement.params))
    variance_du_jour = float(np.asarray(ajustement.conditional_volatility)[-1]) ** 2
    return Garch(omega, alpha, beta, omega + alpha * r_passe[-1] ** 2 + beta * variance_du_jour, converge)


def somme_variances_garch(omega: float, alpha: float, beta: float, variance_suivante: float, h: int) -> float:
    """Σ_{i=1..h} E_t[σ²(t+i)] par la récurrence E_t[σ²(t+i)] = ω + (α + β) E_t[σ²(t+i−1)], partie de σ²(t+1)."""
    total, v = 0.0, float(variance_suivante)
    for _ in range(h):
        total += v
        v = omega + (alpha + beta) * v
    return total


# --- Ce que chaque règle sait à chaque origine, puis les prévisions ------------------------------------------------

def etats(r: pd.Series, positions: np.ndarray, fenetre_garch: int | None = None) -> pd.DataFrame:
    """À chaque origine (une ligne, indexée par sa date) : la variance par jour des trois règles simples et la
    GARCH ajustée sur le seul passé : toute l'histoire, ou les `fenetre_garch` dernières variations (fenêtre
    glissante). Aucune ligne ne dépend d'une variation postérieure à son origine."""
    x = r.to_numpy(dtype=float)
    ewma = variances_ewma(x)
    lignes, precedente = [], None
    for t in positions:
        debut = 0 if fenetre_garch is None else max(0, t + 1 - fenetre_garch)
        g = ajuster_garch(x[debut: t + 1], repli=precedente)
        precedente = g
        lignes.append({"position": int(t),
                       **{regle: variance_historique(x, t, n) for regle, n in FENETRES_HISTORIQUES.items()},
                       "ewma": float(ewma[t]),
                       "omega": g.omega, "alpha": g.alpha, "beta": g.beta, "garch": g.variance_suivante,
                       "converge": g.converge, "variations_garch": int(t + 1 - debut)})
    return pd.DataFrame(lignes, index=pd.DatetimeIndex(r.index[positions], name="origine"))


def prevoir(r: pd.Series, etats_: pd.DataFrame, h: int) -> pd.DataFrame:
    """Pour chaque origine dont la cible est complète : la date de fin de cible, RV(t, h), la variation cumulée du
    taux sur les h jours (en pb) et F(t, h) pour les quatre règles (en pb²)."""
    x = r.to_numpy(dtype=float)
    garde = etats_[etats_["position"] + h <= len(x) - 1]
    lignes = []
    for origine, e in garde.iterrows():
        t = int(e["position"])
        lignes.append({"fin_cible": r.index[t + h], "rv": variance_realisee(x, t, h),
                       "variation_pb": float(x[t + 1: t + h + 1].sum()),
                       "garch": somme_variances_garch(e["omega"], e["alpha"], e["beta"], e["garch"], h),
                       "hv252": h * e["hv252"], "hv63": h * e["hv63"], "ewma": h * e["ewma"]})
    return pd.DataFrame(lignes, index=garde.index)


# --- Pertes et tests -----------------------------------------------------------------------------------------------

def qlike(rv, f):
    """QLIKE(RV, F) = RV/F − ln(RV/F) − 1 : nulle si F = RV ; une prévision trop basse coûte plus qu'une prévision
    trop haute du même facteur."""
    x = np.asarray(rv, dtype=float) / np.asarray(f, dtype=float)
    return x - np.log(x) - 1


def erreur_vol_pb(rv, f):
    """Erreur sur la volatilité de l'horizon, en pb : √F − √RV (positive quand la règle prévoit trop)."""
    return np.sqrt(np.asarray(f, dtype=float)) - np.sqrt(np.asarray(rv, dtype=float))


def retards_hac(h: int) -> int:
    """2m retards, m le nombre de mois de l'horizon : les cibles d'origines mensuelles se chevauchent sur m − 1."""
    return 2 * MOIS_PAR_HORIZON[h]


def diebold_mariano(d: np.ndarray, retards: int) -> dict:
    """Moyenne de d = perte de la référence − perte du modèle, et son test (Newey-West, noyau de Bartlett,
    `retards` retards, sans correction de petit échantillon ; p bilatéral, loi normale)."""
    d = np.asarray(d, dtype=float)
    ajustement = sm.OLS(d, np.ones(len(d))).fit(cov_type="HAC", cov_kwds={"maxlags": retards})
    return {"n": int(len(d)), "retards": int(retards), "d_moyen": float(ajustement.params[0]),
            "t": float(ajustement.tvalues[0]), "p": float(ajustement.pvalues[0])}


def comparer(p: pd.DataFrame, modele: str, reference: str, h: int) -> dict:
    """Le modèle contre la référence sur les mêmes origines : QLIKE moyennes, gain en % (positif quand le modèle
    fait mieux) et test de Diebold-Mariano."""
    perte_ref, perte_mod = qlike(p["rv"], p[reference]), qlike(p["rv"], p[modele])
    return {"qlike_reference": float(perte_ref.mean()), "qlike_modele": float(perte_mod.mean()),
            "gain_pct": float(100 * (1 - perte_mod.mean() / perte_ref.mean())),
            **diebold_mariano(perte_ref - perte_mod, retards_hac(h))}


def resumer(p: pd.DataFrame) -> dict:
    """Par règle : QLIKE moyenne, erreur quadratique moyenne et biais sur la volatilité (pb) ; volatilité réalisée."""
    vol = np.sqrt(p["rv"])
    sortie = {"origines": int(len(p)), "premiere_origine": p.index[0].strftime("%Y-%m-%d"),
              "derniere_origine": p.index[-1].strftime("%Y-%m-%d"),
              "derniere_fin_de_cible": p["fin_cible"].iloc[-1].strftime("%Y-%m-%d"),
              "vol_realisee_moyenne_pb": float(vol.mean()), "vol_realisee_mediane_pb": float(vol.median()),
              "regles": {}}
    for regle in REGLES:
        e = erreur_vol_pb(p["rv"], p[regle])
        sortie["regles"][regle] = {"qlike": float(qlike(p["rv"], p[regle]).mean()),
                                   "rmse_vol_pb": float(np.sqrt((e ** 2).mean())), "biais_vol_pb": float(e.mean())}
    return sortie


def evaluer(p: pd.DataFrame, h: int) -> dict:
    """Le résumé des quatre règles et la GARCH contre chacune des trois règles simples."""
    return {**resumer(p), "comparaisons": {f"garch_contre_{ref}": comparer(p, PRINCIPAL, ref, h)
                                          for ref in REGLES_SIMPLES}}


def gain_significatif(test: dict, seuil: float = SEUIL) -> bool:
    """La décision écrite d'avance : la GARCH fait mieux (d moyen positif) et p bilatéral sous le seuil."""
    return bool(test["d_moyen"] > 0 and test["p"] < seuil)


def decision_du_titre(test_63: dict, test_21: dict) -> str:
    """La table de décision du plan : « 63 jours », sinon « 21 jours », sinon « section non publiée »."""
    if gain_significatif(test_63):
        return "63 jours"
    if gain_significatif(test_21):
        return "21 jours"
    return "section non publiée"


def restreindre(p: pd.DataFrame, debut: str, fin: str) -> pd.DataFrame:
    """Les origines dont la cible finit entre `debut` et `fin` inclus."""
    return p[(p["fin_cible"] >= pd.Timestamp(debut)) & (p["fin_cible"] <= pd.Timestamp(fin))]


# --- Bandes, couverture, choc --------------------------------------------------------------------------------------

def couverture(variation_pb, somme_variances, z: float = Z_95) -> float:
    """Part des origines où la variation réalisée du taux reste dans la bande ± z √F."""
    dans = np.abs(np.asarray(variation_pb, dtype=float)) <= z * np.sqrt(np.asarray(somme_variances, dtype=float))
    return float(dans.mean())


def variations_standardisees(p: pd.DataFrame, regle: str = PRINCIPAL) -> np.ndarray:
    """z = variation réalisée du taux sur l'horizon / √F : de l'ordre de 1 si la règle prévoit bien l'amplitude."""
    return (p["variation_pb"] / np.sqrt(p[regle])).to_numpy(dtype=float)


def bandes(niveau_pct: float, sommes_par_horizon: dict[int, float], z: float = Z_95) -> dict:
    """Bandes autour du dernier niveau (pas de dérive : la prévision centrale est la marche aléatoire) :
    niveau ± z √F(h), F(h) la variance prévue de la variation sur h jours."""
    sortie = {}
    for h, f in sommes_par_horizon.items():
        demi = z * float(np.sqrt(f))
        sortie[int(h)] = {"ecart_type_pb": float(np.sqrt(f)), "demi_largeur_pb": demi,
                          "bas_pct": niveau_pct - demi / 100, "haut_pct": niveau_pct + demi / 100}
    return sortie


def perte_premier_ordre_meur(choc_pb: float, dv01_keur_par_pb: float) -> float:
    """Perte au premier ordre d'une position de DV01 donnée (k€ par pb) pour une hausse de `choc_pb` : en M€."""
    return choc_pb * dv01_keur_par_pb / 1e3


# --- Le niveau : marche aléatoire contre AR(1) ---------------------------------------------------------------------

def fin_de_mois(taux: pd.Series) -> pd.Series:
    """La dernière valeur publiée de chaque mois ; l'index garde la date réelle."""
    return taux.iloc[positions_fin_de_mois(taux.index)]


def prevoir_niveau(mensuel: pd.Series, h: int, modele: str, premiere_origine: str = PREMIERE_ORIGINE) -> pd.DataFrame:
    """Le taux prévu h mois après chaque origine mensuelle, à partir de `premiere_origine` et tant que la cible
    existe. `marche_aleatoire` : le taux de l'origine. `ar1` : régression directe de y(s+h) sur une constante et
    y(s), sur les paires connues à l'origine (s + h ≤ t, fenêtre croissante), puis ĉ + γ̂ y(t)."""
    y = mensuel.to_numpy(dtype=float)
    mois = mensuel.index.to_period("M")
    t0 = int(np.flatnonzero(mois >= pd.Period(premiere_origine, "M"))[0])
    lignes = []
    for t in range(t0, len(y) - h):
        if modele == "marche_aleatoire":
            prevu = y[t]
        elif modele == "ar1":
            s = np.arange(0, t - h + 1)
            X = np.column_stack([np.ones(len(s)), y[s]])
            coef, *_ = np.linalg.lstsq(X, y[s + h], rcond=None)
            prevu = coef[0] + coef[1] * y[t]
        else:
            raise ValueError(f"modèle inconnu : {modele}")
        lignes.append({"origine": mensuel.index[t], "prevu": float(prevu), "realise": float(y[t + h])})
    return pd.DataFrame(lignes, index=pd.DatetimeIndex(mensuel.index[t0 + h: len(y)], name="cible"))


def comparer_niveau(mensuel: pd.Series, h: int, premiere_origine: str = PREMIERE_ORIGINE) -> dict:
    """AR(1) contre marche aléatoire à h mois : RMSE en pb, rapport, et Diebold-Mariano sur les erreurs au carré
    (d = e_marche² − e_AR(1)², 2h retards)."""
    ma = prevoir_niveau(mensuel, h, "marche_aleatoire", premiere_origine)
    ar = prevoir_niveau(mensuel, h, "ar1", premiere_origine)
    e_ma, e_ar = 100 * (ma["realise"] - ma["prevu"]), 100 * (ar["realise"] - ar["prevu"])
    rmse_ma, rmse_ar = float(np.sqrt((e_ma ** 2).mean())), float(np.sqrt((e_ar ** 2).mean()))
    return {"previsions": int(len(ma)), "premiere_origine": ma["origine"].iloc[0].strftime("%Y-%m-%d"),
            "derniere_origine": ma["origine"].iloc[-1].strftime("%Y-%m-%d"),
            "rmse_marche_aleatoire_pb": rmse_ma, "rmse_ar1_pb": rmse_ar, "rapport": rmse_ar / rmse_ma,
            **diebold_mariano((e_ma ** 2 - e_ar ** 2).to_numpy(), 2 * h)}
