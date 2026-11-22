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


# --- Ajouté pour ce projet (PLAN.md, section 10) : OAT = courbe AAA + écart, positions et sensibilités -----------

def courbe_moyenne(parametres) -> Courbe:
    """La moyenne, maturité par maturité, des courbes de Svensson de plusieurs jours (une ligne de paramètres BETA0 …
    TAU2 par jour) : la courbe AAA « en moyenne du mois »."""
    from ecart_oat_bund.nelson_siegel import courbe_svensson_bce
    return lambda tau: courbe_svensson_bce(parametres, np.atleast_1d(tau)).mean(axis=0)


def courbe_oat(courbe_aaa: Courbe, ecart_pb: float) -> Courbe:
    """La courbe des OAT : la courbe AAA plus un écart constant à toutes les maturités (en pb)."""
    return lambda tau: courbe_aaa(tau) + ecart_pb / 100


def choc_interpole(maturites, chocs_pb) -> Courbe:
    """Un choc publié à quelques maturités (en années, en pb), interpolé linéairement entre elles et constant
    au-delà ; renvoyé en points de %, comme les autres chocs."""
    m = np.asarray(maturites, dtype=float)
    c = np.asarray(chocs_pb, dtype=float) / 100
    ordre = np.argsort(m)
    return lambda tau: np.interp(np.atleast_1d(np.asarray(tau, dtype=float)), m[ordre], c[ordre])


AUCUN_CHOC: Courbe = choc_niveau(0.0)


def valeur_position(lignes: list[dict], courbe_aaa: Courbe, ecart_pb: float, choc_aaa: Courbe = AUCUN_CHOC,
                    choc_ecart: Courbe = AUCUN_CHOC) -> float:
    """Valeur d'une position (dans l'unité des nominaux) : chaque ligne est un titre, `emetteur` « FR » (actualisé
    sur la courbe AAA + écart) ou « DE » (sur la courbe AAA), `nominal` signé (négatif pour une vente), `dates` et
    `flux` pour 100 de nominal. Les chocs s'ajoutent à la courbe AAA et, pour les OAT seulement, à l'écart."""
    aaa = deplacer(courbe_aaa, choc_aaa)
    oat = deplacer(courbe_oat(aaa, ecart_pb), choc_ecart)
    total = 0.0
    for ligne in lignes:
        courbe = oat if ligne["emetteur"] == "FR" else aaa
        total += ligne["nominal"] * prix(courbe, ligne["dates"], ligne["flux"]) / 100
    return total


def titre_au_pair(courbe: Courbe, maturite: int, emetteur: str, nominal: float) -> dict:
    """Une ligne de position : un titre émis au pair sur `courbe` (coupon annuel égal au taux au pair)."""
    coupon = taux_au_pair(courbe, maturite)
    dates, flux = flux_obligation(maturite, coupon)
    return {"emetteur": emetteur, "maturite": maturite, "coupon_pct": coupon, "nominal": nominal, "dates": dates,
            "flux": flux}


def dv01_taux(lignes: list[dict], courbe_aaa: Courbe, ecart_pb: float) -> float:
    """Gain de la position pour une baisse parallèle de 1 pb de la courbe AAA, écart fixe (différence centrée)."""
    bas = valeur_position(lignes, courbe_aaa, ecart_pb, choc_aaa=choc_niveau(-0.005))
    haut = valeur_position(lignes, courbe_aaa, ecart_pb, choc_aaa=choc_niveau(0.005))
    return bas - haut


def sensibilite_ecart(lignes: list[dict], courbe_aaa: Courbe, ecart_pb: float) -> float:
    """Perte de la position pour une hausse de 1 pb de l'écart OAT-Bund, courbe AAA fixe (différence centrée)."""
    return (valeur_position(lignes, courbe_aaa, ecart_pb - 0.5)
            - valeur_position(lignes, courbe_aaa, ecart_pb + 0.5))


def nominal_de_couverture(oat: dict, courbe_aaa: Courbe, ecart_pb: float, maturite_bund: int = 10) -> dict:
    """La ligne de Bund au pair à vendre pour annuler la DV01 de taux d'une ligne d'OAT : son nominal vaut
    −DV01(ligne d'OAT) / DV01(Bund pour 1 de nominal)."""
    bund_unitaire = titre_au_pair(courbe_aaa, maturite_bund, "DE", 1.0)
    rapport = dv01_taux([oat], courbe_aaa, ecart_pb) / dv01_taux([bund_unitaire], courbe_aaa, ecart_pb)
    return {**bund_unitaire, "nominal": -rapport}


def pb_en_euros(pb: float, sensibilite_par_pb: float) -> float:
    """Variation de valeur au premier ordre : nombre de pb × sensibilité par pb (même unité que la sensibilité)."""
    return pb * sensibilite_par_pb
