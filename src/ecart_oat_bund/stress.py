"""Prix, duration, DV01 et chocs de courbe : le moteur de stress repris de courbe-taux-euro.

Conventions :

- Une courbe est une fonction des maturités (en années) vers les taux zéro-coupon (en %), en composition
  continue : un flux reçu dans t ans vaut aujourd'hui flux × e^(−z(t) · t / 100).
- Les obligations paient un coupon annuel et remboursent 100 à l'échéance ; une obligation « au pair » a le coupon
  qui la fait valoir 100 sur la courbe de départ.
- Un choc est lui aussi une fonction des maturités vers une variation des taux (en points de %) ; la courbe
  choquée est la courbe de départ plus le choc. La réévaluation est complète : chaque flux est actualisé au taux
  de sa date, avant et après le choc.
- Choc de niveau : la même variation à toutes les maturités. Choc des trois facteurs : la variation des facteurs
  de Nelson-Siegel (niveau, pente, courbure) répartie selon leurs charges ; c'est ce qui sert à rejouer 2022.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ecart_oat_bund.nelson_siegel import LAMBDA_DL, charges

Courbe = Callable[[np.ndarray], np.ndarray]  # maturités en années -> taux zéro-coupon en %


def actualisation(courbe: Courbe, t) -> np.ndarray:
    """Facteurs d'actualisation e^(−z(t) · t / 100) aux dates t (en années)."""
    t = np.atleast_1d(np.asarray(t, dtype=float))
    return np.exp(-courbe(t) / 100 * t)


def flux_obligation(maturite: int, coupon: float, nominal: float = 100.0) -> tuple[np.ndarray, np.ndarray]:
    """Dates (1, 2, …, maturité ans) et flux d'une obligation à coupon annuel `coupon` (en % du nominal)."""
    dates = np.arange(1, maturite + 1, dtype=float)
    flux = np.full(maturite, coupon / 100 * nominal)
    flux[-1] += nominal
    return dates, flux


def taux_au_pair(courbe: Courbe, maturite: int) -> float:
    """Coupon annuel (en %) qui fait valoir 100 à l'obligation : 100 × (1 − D(T)) / (D(1) + … + D(T))."""
    d = actualisation(courbe, np.arange(1, maturite + 1))
    return float(100 * (1 - d[-1]) / d.sum())


def prix(courbe: Courbe, dates: np.ndarray, flux: np.ndarray) -> float:
    """Somme des flux actualisés, chacun au taux zéro-coupon de sa date."""
    return float((flux * actualisation(courbe, dates)).sum())


def duration(courbe: Courbe, dates: np.ndarray, flux: np.ndarray) -> float:
    """Duration de Fisher-Weil, en années : moyenne des dates pondérée par la valeur actuelle des flux.

    Pour un déplacement parallèle Δ (en points), la valeur varie au premier ordre de −duration × Δ / 100."""
    va = flux * actualisation(courbe, dates)
    return float((dates * va).sum() / va.sum())


def convexite(courbe: Courbe, dates: np.ndarray, flux: np.ndarray) -> float:
    """Convexité : moyenne des dates au carré pondérée par la valeur actuelle des flux."""
    va = flux * actualisation(courbe, dates)
    return float((dates ** 2 * va).sum() / va.sum())


def choc_niveau(delta: float) -> Courbe:
    """Variation des taux (en points de %) pour un choc `delta` sur le niveau : la même à toutes les maturités."""
    return lambda tau: np.full(np.shape(np.atleast_1d(tau)), float(delta))


def choc_facteurs(delta, lam: float = LAMBDA_DL) -> Courbe:
    """Variation des taux pour des variations simultanées (niveau, pente, courbure) : Λ(τ) · delta."""
    d = np.asarray(delta, dtype=float)
    return lambda tau: charges(tau, lam) @ d


def deplacer(courbe: Courbe, choc: Courbe) -> Courbe:
    """La courbe de départ plus le choc."""
    return lambda tau: courbe(tau) + choc(tau)


def dv01(courbe: Courbe, maturites: list[int], nominal: float) -> float:
    """Gain de valeur d'un portefeuille d'obligations émises au pair (`nominal` chacune) pour une baisse parallèle de
    1 pb, par différence centrée entre −0,5 pb et +0,5 pb, dans l'unité du nominal."""
    total = 0.0
    for m in maturites:
        dates, flux = flux_obligation(m, taux_au_pair(courbe, m))
        bas, haut = deplacer(courbe, choc_niveau(-0.005)), deplacer(courbe, choc_niveau(0.005))
        total += nominal * (prix(bas, dates, flux) - prix(haut, dates, flux)) / 100
    return total
