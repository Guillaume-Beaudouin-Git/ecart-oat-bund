"""Nelson-Siegel à λ fixé (Diebold et Li, 2006), et la courbe de Svensson publiée par la BCE.

Repris du dépôt courbe-taux-euro de l'auteur, sans la partie prévision. Sert ici à deux choses : calculer la
courbe AAA de la BCE à toute maturité (formule de Svensson appliquée aux paramètres publiés), et rejouer la
variation des facteurs de 2022 dans le scénario de stress.

Taux zéro-coupon à la maturité τ (en années), en % :

    y(τ) = L + S · [(1 − e^(−λτ)) / (λτ)] + C · [(1 − e^(−λτ)) / (λτ) − e^(−λτ)]

L est le niveau (charge 1 à toutes les maturités), S la pente (charge 1 en τ = 0, puis décroissante), C la
courbure (charge nulle aux deux bouts). λ est fixé à 0,0609 par mois, comme dans Diebold et Li (2006). Avec λ
fixé, les trois facteurs d'une date sont les coefficients des moindres carrés des taux de cette date sur les
trois charges.

La BCE estime chaque jour le modèle de Svensson (1994), qui ajoute une seconde bosse :

    z(τ) = β0 + β1 · [(1 − e^(−τ/τ1)) / (τ/τ1)] + β2 · [(1 − e^(−τ/τ1)) / (τ/τ1) − e^(−τ/τ1)]
              + β3 · [(1 − e^(−τ/τ2)) / (τ/τ2) − e^(−τ/τ2)]

Les taux sont en composition continue : le facteur d'actualisation à τ ans vaut e^(−z(τ) · τ / 100).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LAMBDA_DL = 0.0609 * 12  # par an ; 0,0609 par mois dans Diebold et Li (2006)
FACTEURS = ("niveau", "pente", "courbure")


def _forme(x: np.ndarray) -> np.ndarray:
    """(1 − e^(−x)) / x, qui tend vers 1 quand x tend vers 0 (calcul exact près de 0 grâce à expm1)."""
    x = np.asarray(x, dtype=float)
    sortie = np.ones_like(x)
    non_nul = x != 0
    sortie[non_nul] = -np.expm1(-x[non_nul]) / x[non_nul]
    return sortie


def charges(maturites, lam: float = LAMBDA_DL) -> np.ndarray:
    """Matrice des charges, une ligne par maturité (en années) : [1, pente, courbure]."""
    tau = np.atleast_1d(np.asarray(maturites, dtype=float))
    pente = _forme(lam * tau)
    courbure = pente - np.exp(-lam * tau)
    return np.column_stack([np.ones_like(tau), pente, courbure])


def estimer_facteurs(taux: pd.DataFrame, maturites, lam: float = LAMBDA_DL) -> pd.DataFrame:
    """Les trois facteurs de chaque date : moindres carrés des taux de la date sur les charges.

    `taux` : une ligne par date, une colonne par maturité, dans l'ordre de `maturites` (en années)."""
    X = charges(maturites, lam)
    beta, *_ = np.linalg.lstsq(X, taux.to_numpy(dtype=float).T, rcond=None)
    return pd.DataFrame(beta.T, index=taux.index, columns=list(FACTEURS))


def courbe_ns(facteurs: pd.DataFrame | np.ndarray, maturites, lam: float = LAMBDA_DL) -> np.ndarray:
    """Taux de la courbe de Nelson-Siegel, une ligne par jeu de facteurs, une colonne par maturité."""
    f = np.atleast_2d(np.asarray(facteurs, dtype=float))
    return f @ charges(maturites, lam).T


def courbe_svensson(maturites, b0: float, b1: float, b2: float, b3: float, t1: float, t2: float) -> np.ndarray:
    """Taux de la courbe de Svensson aux maturités données (en années), formule des notes techniques de la BCE."""
    tau = np.atleast_1d(np.asarray(maturites, dtype=float))
    f1, f2 = _forme(tau / t1), _forme(tau / t2)
    return b0 + b1 * f1 + b2 * (f1 - np.exp(-tau / t1)) + b3 * (f2 - np.exp(-tau / t2))


def courbe_svensson_bce(parametres: pd.DataFrame, maturites) -> np.ndarray:
    """La courbe de Svensson de chaque date, à partir des paramètres publiés (colonnes BETA0 … TAU2)."""
    p = {c: parametres[c].to_numpy(dtype=float)[:, None] for c in ("BETA0", "BETA1", "BETA2", "BETA3", "TAU1", "TAU2")}
    tau = np.atleast_1d(np.asarray(maturites, dtype=float))[None, :]
    f1, f2 = _forme(tau / p["TAU1"]), _forme(tau / p["TAU2"])
    return (p["BETA0"] + p["BETA1"] * f1 + p["BETA2"] * (f1 - np.exp(-tau / p["TAU1"]))
            + p["BETA3"] * (f2 - np.exp(-tau / p["TAU2"])))
