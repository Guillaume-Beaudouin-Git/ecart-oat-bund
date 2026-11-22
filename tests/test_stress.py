"""Tests repris de courbe-taux-euro pour le moteur de stress : des cas calculables à la main."""
import numpy as np
import pytest

from ecart_oat_bund.nelson_siegel import LAMBDA_DL
from ecart_oat_bund.stress import (choc_facteurs, choc_niveau, convexite, deplacer, duration, dv01, flux_obligation,
                                   prix, taux_au_pair)


def plate(niveau):
    """Une courbe plate : le même taux zéro-coupon (en %) à toutes les maturités."""
    return lambda tau: np.full(np.shape(np.atleast_1d(tau)), float(niveau))


def test_zero_coupon_sous_un_choc_de_100_pb():
    # zéro-coupon à 10 ans, courbe plate à 3 % : 100 e^−0,3 = 74,0818 ; après +100 pb, 100 e^−0,4 = 67,0320,
    # soit e^−0,1 − 1 = −9,516 % ; sa duration vaut sa maturité, 10 ans
    dates, flux = np.array([10.0]), np.array([100.0])
    avant = prix(plate(3), dates, flux)
    apres = prix(deplacer(plate(3), choc_niveau(1.0)), dates, flux)
    assert avant == pytest.approx(74.0818, abs=1e-4)
    assert apres == pytest.approx(67.0320, abs=1e-4)
    assert 100 * (apres / avant - 1) == pytest.approx(-9.5163, abs=1e-4)
    assert duration(plate(3), dates, flux) == pytest.approx(10.0)


def test_obligation_au_pair_a_deux_ans_a_la_main():
    # courbe plate à 3 % : D(1) = e^−0,03 = 0,970446, D(2) = e^−0,06 = 0,941765
    # coupon au pair = 100 × (1 − 0,9417645) / (0,9704455 + 0,9417645) = 3,045453 %
    c = taux_au_pair(plate(3), 2)
    assert c == pytest.approx(3.045453, abs=1e-6)
    dates, flux = flux_obligation(2, c)
    assert flux.tolist() == pytest.approx([c, 100 + c])
    assert prix(plate(3), dates, flux) == pytest.approx(100.0)
    # duration = (1 × 3,045453 × 0,9704455 + 2 × 103,045453 × 0,9417645) / 100 = 1,970446 an
    assert duration(plate(3), dates, flux) == pytest.approx(1.970446, abs=1e-6)
    # après +100 pb : 3,045453 × (e^−0,04 + e^−0,08) + 100 × e^−0,08 = 98,04898
    assert prix(deplacer(plate(3), choc_niveau(1.0)), dates, flux) == pytest.approx(98.04898, abs=1e-5)


def test_la_duration_donne_le_premier_ordre_et_la_convexite_le_second():
    courbe = lambda tau: 2.0 + 0.05 * np.atleast_1d(tau)  # noqa: E731  une courbe qui monte
    dates, flux = flux_obligation(10, taux_au_pair(courbe, 10))
    d, cx = duration(courbe, dates, flux), convexite(courbe, dates, flux)
    for delta in (0.01, 1.0):  # 1 pb, puis 100 pb
        exact = prix(deplacer(courbe, choc_niveau(delta)), dates, flux) / 100 - 1
        assert exact == pytest.approx(-d * delta / 100 + 0.5 * cx * (delta / 100) ** 2, abs=2e-4 * delta ** 3 + 1e-9)
    # au premier ordre seul, l'écart est la convexité : la perte exacte est plus faible
    exact = prix(deplacer(courbe, choc_niveau(1.0)), dates, flux) / 100 - 1
    assert exact > -d / 100


def test_le_choc_des_trois_facteurs_contient_le_choc_de_niveau():
    tau = np.array([0.25, 2.0, 10.0, 30.0])
    assert choc_facteurs([0.7, 0.0, 0.0])(tau) == pytest.approx(choc_niveau(0.7)(tau))
    # la pente seule : −100 pb sur S font −91,40 pb à 3 mois, −4,56 pb à 30 ans
    x3m, x30 = LAMBDA_DL * 0.25, LAMBDA_DL * 30
    assert choc_facteurs([0.0, -1.0, 0.0])([0.25])[0] == pytest.approx(-(1 - np.exp(-x3m)) / x3m)
    assert 100 * choc_facteurs([0.0, -1.0, 0.0])([30.0])[0] == pytest.approx(-4.56, abs=0.01)
    # la courbure seule ne bouge ni le très court terme ni le très long terme
    assert choc_facteurs([0.0, 0.0, 1.0])([0.0, 1e4]) == pytest.approx([0.0, 0.0], abs=1e-3)


def test_dv01_a_la_main():
    # obligation au pair à 2 ans, courbe plate à 3 %, 25 de nominal : DV01 ≈ 25 × 1,970446 × 0,0001 = 0,004926
    d = dv01(plate(3), [2], nominal=25.0)
    assert d == pytest.approx(25 * 1.970446e-4, rel=1e-6)
    # elle s'additionne sur les obligations
    assert dv01(plate(3), [2, 10], nominal=25.0) == pytest.approx(d + dv01(plate(3), [10], nominal=25.0))


# --- Positions OAT contre Bund (PLAN.md, section 10) ---------------------------------------------------------

import pandas as pd  # noqa: E402

from ecart_oat_bund.stress import (choc_interpole, courbe_moyenne, courbe_oat, dv01_taux,  # noqa: E402
                                   nominal_de_couverture, pb_en_euros, sensibilite_ecart, titre_au_pair,
                                   valeur_position)


def test_courbe_moyenne_et_courbe_des_oat():
    # deux jours de courbes plates à 2 % et 4 % : la moyenne vaut 3 % partout ; l'OAT à +150 pb vaut 4,5 %
    p = pd.DataFrame({"BETA0": [2.0, 4.0], "BETA1": [0.0, 0.0], "BETA2": [0.0, 0.0], "BETA3": [0.0, 0.0],
                      "TAU1": [1.0, 2.0], "TAU2": [5.0, 9.0]})
    moyenne = courbe_moyenne(p)
    assert moyenne([0.5, 10.0, 30.0]) == pytest.approx([3.0, 3.0, 3.0])
    assert courbe_oat(moyenne, 150)([10.0])[0] == pytest.approx(4.5)


def test_choc_interpole_a_la_main():
    choc = choc_interpole([0.25, 1, 5, 10, 15], [10, 20, 60, 110, 120])
    # 7,5 ans : à mi-chemin entre 60 et 110 pb, soit 85 pb = 0,85 point ; constant au-delà des bouts
    assert choc([7.5])[0] == pytest.approx(0.85)
    assert choc([0.1, 30.0]) == pytest.approx([0.10, 1.20])


def test_dv01_d_un_zero_coupon_et_conversion_en_euros():
    # 100 M€ de zéro-coupon à 10 ans, courbe plate à 3 % : valeur 74,0818 M€, DV01 ≈ 74,0818 × 10 × 1 pb
    ligne = {"emetteur": "DE", "nominal": 100.0, "dates": np.array([10.0]), "flux": np.array([100.0])}
    assert valeur_position([ligne], plate(3), 0.0) == pytest.approx(74.0818, abs=1e-4)
    d = dv01_taux([ligne], plate(3), 0.0)
    assert d == pytest.approx(74.0818 * 10 * 1e-4, rel=1e-6)          # 0,0741 M€, soit 74 082 € par pb
    assert 1e6 * d == pytest.approx(74_082, abs=1)
    # 20 pb à 85 000 € par pb : 1,7 M€
    assert pb_en_euros(20, 85_000) == pytest.approx(1_700_000)


def test_position_neutre_en_dv01():
    aaa = lambda tau: 2.0 + 0.08 * np.atleast_1d(tau)  # noqa: E731
    ecart = 120.0
    oat = titre_au_pair(courbe_oat(aaa, ecart), 10, "FR", 100.0)
    assert valeur_position([oat], aaa, ecart) == pytest.approx(100.0)
    # pour l'OAT seule, la DV01 de taux et la sensibilité à l'écart sont égales (deux déplacements parallèles)
    assert dv01_taux([oat], aaa, ecart) == pytest.approx(sensibilite_ecart([oat], aaa, ecart), rel=1e-9)
    bund = nominal_de_couverture(oat, aaa, ecart)
    assert bund["nominal"] < 0 and bund["emetteur"] == "DE"
    position = [oat, bund]
    assert dv01_taux(position, aaa, ecart) == pytest.approx(0.0, abs=1e-12)
    # la couverture ne touche pas la sensibilité à l'écart : le Bund ne dépend pas de l'écart
    assert sensibilite_ecart(position, aaa, ecart) == pytest.approx(sensibilite_ecart([oat], aaa, ecart))
    # +1 pb d'écart : perte au premier ordre égale à la sensibilité
    perte = valeur_position(position, aaa, ecart) - valeur_position(position, aaa, ecart + 1)
    assert perte == pytest.approx(sensibilite_ecart(position, aaa, ecart), rel=1e-3)
    # un choc parallèle de la courbe AAA ne bouge presque pas la position (seule reste la convexité)
    avant = valeur_position(position, aaa, ecart)
    apres = valeur_position(position, aaa, ecart, choc_aaa=choc_niveau(1.0))
    assert abs(apres - avant) < 0.02 * abs(valeur_position([oat], aaa, ecart, choc_aaa=choc_niveau(1.0)) - 100)
