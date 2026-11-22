"""Tests repris de courbe-taux-euro : charges de Nelson-Siegel et formule de Svensson de la BCE."""
import numpy as np
import pandas as pd
import pytest

from ecart_oat_bund.nelson_siegel import (LAMBDA_DL, charges, courbe_ns, courbe_svensson, courbe_svensson_bce,
                                          estimer_facteurs)

TAUS = [0.25, 1, 2, 5, 10, 20, 30]
COLONNES = ["SR_3M", "SR_1Y", "SR_2Y", "SR_5Y", "SR_10Y", "SR_20Y", "SR_30Y"]


def test_charges_a_la_main():
    # en τ = 1/λ : pente (1 − e^−1) / 1 = 0,632121 ; courbure 0,632121 − e^−1 = 0,264241
    c = charges([1 / LAMBDA_DL])[0]
    assert c == pytest.approx([1.0, 0.6321206, 0.2642411], abs=1e-7)
    assert charges([0.0])[0] == pytest.approx([1.0, 1.0, 0.0])
    assert charges([1e4])[0] == pytest.approx([1.0, 0.0, 0.0], abs=1e-3)


def test_reconstruction_exacte_d_une_courbe_connue():
    # deux courbes construites avec des facteurs connus : les moindres carrés les retrouvent exactement
    connus = np.array([[4.0, -2.0, 1.5], [0.5, 1.2, -3.0]])
    taux = pd.DataFrame(courbe_ns(connus, TAUS), index=pd.to_datetime(["2010-01-29", "2023-12-29"]), columns=COLONNES)
    estimes = estimer_facteurs(taux, TAUS)
    assert estimes.to_numpy() == pytest.approx(connus, abs=1e-12)
    assert list(estimes.columns) == ["niveau", "pente", "courbure"]


def test_svensson_a_la_main():
    # β = (2, −1, 1, 0,5), τ1 = 1, τ2 = 10, à 1 an :
    # 2 − (1 − e^−1) + (1 − e^−1 − e^−1) + 0,5 × ((1 − e^−0,1) / 0,1 − e^−0,1) = 1,6555148
    assert courbe_svensson([1.0], 2, -1, 1, 0.5, 1, 10)[0] == pytest.approx(1.6555148, abs=1e-7)
    # avec β2 = β3 = 0 et τ1 = 1 / λ, Svensson se réduit à Nelson-Siegel
    assert courbe_svensson(TAUS, 3, -1, 0, 0, 1 / LAMBDA_DL, 5) == pytest.approx(courbe_ns([3, -1, 0], TAUS)[0])


def test_svensson_reproduit_les_taux_publies_par_la_bce():
    # le 19 novembre 2026, paramètres et taux publiés par la BCE (Source : ECB statistics, courbe AAA)
    parametres = pd.DataFrame({"BETA0": [1.638729467], "BETA1": [0.8111675364], "BETA2": [2.3808314672],
                               "BETA3": [6.6031998625], "TAU1": [1.0049189022], "TAU2": [14.0722799638]})
    publies = [2.6661574177, 3.004228815, 3.1250637519, 3.1883755314, 3.4415130227, 3.7294567235, 3.6923935442]
    assert courbe_svensson_bce(parametres, TAUS)[0] == pytest.approx(publies, abs=1e-8)
    # la version à une date redonne la même chose
    p = parametres.iloc[0].to_numpy()
    assert courbe_svensson(TAUS, *p) == pytest.approx(publies, abs=1e-8)
