"""La décomposition sur des cas calculables à la main."""
import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from ecart_oat_bund.decomposition import (Z_95, autocovariances, cumuler, decomposer, ecarts_pb, estimer,
                                          france_contre_pays, mois_au_dessus, moyenne_ponderee, plus_haut_depuis,
                                          poids_pib, retards_newey_west, variance_hac, variance_somme)


def _mois(debut, n):
    return pd.period_range(debut, periods=n, freq="M")


def test_ecarts_et_poids_a_la_main():
    taux = pd.DataFrame({"DE": [2.00, 2.10], "FR": [2.50, 2.75], "IT": [3.80, 3.70], "ES": [3.20, 3.30]},
                        index=_mois("2024-04", 2))
    s = ecarts_pb(taux)
    assert s.loc["2024-05", "FR"] == pytest.approx(65.0)          # 100 × (2,75 − 2,10)
    assert s.loc["2024-04", "IT"] == pytest.approx(180.0)
    assert (s["DE"] == 0).all()
    w = poids_pib(pd.Series({"IT": 300.0, "ES": 100.0, "FR": 999.0}), ["IT", "ES"])
    assert w.to_dict() == pytest.approx({"IT": 0.75, "ES": 0.25})
    # avril : 0,75 × 180 + 0,25 × 120 = 165 pb
    assert moyenne_ponderee(s, w).loc["2024-04"] == pytest.approx(165.0)


def test_retards_de_newey_west():
    assert [retards_newey_west(T) for T in (60, 120, 304)] == [3, 4, 5]


def test_moindres_carres_sans_constante_et_variances_a_la_main():
    # y = (1, 2, 3), x = (1, 1, 2) : b = Σxy / Σx² = 9 / 6 = 1,5 ; résidus (−0,5 ; 0,5 ; 0)
    index = _mois("2020-01", 3)
    est = estimer(pd.Series([1.0, 2.0, 3.0], index=index), pd.DataFrame({"x": [1.0, 1.0, 2.0]}, index=index),
                  fin="2020-03", n=3)
    assert est.coef[0] == pytest.approx(1.5)
    assert est.residus.tolist() == pytest.approx([-0.5, 0.5, 0.0])
    # γ0 = (0,25 + 0,25 + 0) / 3 = 1/6 ; γ1 = (0,5 × −0,5 + 0 × 0,5) / 3 = −1/12
    g = autocovariances(est.residus.to_numpy(), 1)
    assert g == pytest.approx([1 / 6, -1 / 12])
    # somme de 2 résidus, L = 1 : 2 γ0 + 2 × (1 − 1/2) × (2 − 1) × γ1 = 1/3 − 1/12 = 1/4
    assert variance_somme(g, 2, 1) == pytest.approx(0.25)
    # une somme d'un seul résidu : γ0
    assert variance_somme(g, 1, 1) == pytest.approx(1 / 6)
    # Var(b) de Newey-West, L = 1 : u = x ε = (−0,5 ; 0,5 ; 0) ;
    # S = 0,25 + 0,25 + 0,5 × 2 × (0,5 × −0,5) = 0,25 ; (X'X)⁻¹ S (X'X)⁻¹ = 0,25 / 36
    assert variance_hac(np.array([[1.0], [1.0], [2.0]]), est.residus.to_numpy(), 1)[0, 0] == pytest.approx(0.25 / 36)
    # R² non centré : 1 − 0,5 / 14
    assert est.r2_non_centre == pytest.approx(1 - 0.5 / 14)


def test_variance_hac_identique_a_statsmodels():
    rng = np.random.default_rng(3)
    x = rng.normal(size=(80, 2))
    e = rng.normal(size=80)
    e[1:] += 0.5 * e[:-1]                    # résidus autocorrélés, comme des variations de moyennes mensuelles
    y = x @ np.array([0.7, -0.2]) + e
    ajuste = sm.OLS(y, x).fit(cov_type="HAC", cov_kwds={"maxlags": 4, "use_correction": False})
    residus = y - x @ ajuste.params
    assert variance_hac(x, residus, 4) == pytest.approx(ajuste.cov_params(), rel=1e-10)


def _donnees_simulees(b=0.5, n=100, choc=None, bruit=0.0, graine=0):
    """Écart des pairs en marche aléatoire ; écart français = b × écart des pairs (+ bruit, + un choc propre)."""
    rng = np.random.default_rng(graine)
    index = _mois("2015-01", n)
    P = pd.Series(100 + np.cumsum(rng.normal(0, 5, n)), index=index)
    s_fr = 40 + b * (P - P.iloc[0]) + np.cumsum(rng.normal(0, bruit, n))
    if choc is not None:
        mois, taille = choc
        s_fr = s_fr + taille * (index >= pd.Period(mois, "M"))
    return s_fr, P.to_frame("P")


def test_sans_choc_propre_la_part_propre_est_nulle():
    s_fr, P = _donnees_simulees()
    est, chemin = decomposer(s_fr, P, base="2020-12", fin="2023-04", n=60)
    assert est.coef[0] == pytest.approx(0.5)
    assert chemin["propre"].abs().max() == pytest.approx(0.0, abs=1e-9)
    # sans bruit, l'intervalle est réduit à un point
    assert chemin["sigma"].max() == pytest.approx(0.0, abs=1e-6)
    # l'observé est la part commune : b × (P(t) − P(base))
    assert chemin["observe"].iloc[-1] == pytest.approx(0.5 * (P["P"].loc["2023-04"] - P["P"].loc["2020-12"]))


def test_un_choc_propre_de_30_pb_est_retrouve():
    s_fr, P = _donnees_simulees(choc=("2021-06", 30.0))
    est, chemin = decomposer(s_fr, P, base="2020-12", fin="2023-04", n=60)
    assert est.coef[0] == pytest.approx(0.5)
    assert chemin.loc[:"2021-05", "propre"].abs().max() == pytest.approx(0.0, abs=1e-9)
    assert chemin.loc["2021-06":, "propre"].to_numpy() == pytest.approx(30.0)
    # X(t) = s_FR(t) − [s_FR(base) + b (P(t) − P(base))]
    fin = chemin.loc["2023-04"]
    attendu = s_fr.loc["2023-04"] - (s_fr.loc["2020-12"] + 0.5 * (P["P"].loc["2023-04"] - P["P"].loc["2020-12"]))
    assert fin["propre"] == pytest.approx(attendu)


def test_intervalle_avec_du_bruit():
    s_fr, P = _donnees_simulees(bruit=2.0, graine=5)
    est, chemin = decomposer(s_fr, P, base="2020-12", fin="2023-04", n=60)
    # σ(t)² = V_h + (P(t) − P(base))² Var(b), et les bornes sont à ± 1,96 σ
    dernier = chemin.iloc[-1]
    g = P["P"].loc["2023-04"] - P["P"].loc["2020-12"]
    attendu = variance_somme(est.gammas, int(dernier["h"]), est.L) + g ** 2 * est.variance[0, 0]
    assert dernier["sigma"] ** 2 == pytest.approx(attendu)
    assert dernier["haut"] - dernier["propre"] == pytest.approx(Z_95 * dernier["sigma"])
    # la fenêtre d'estimation : les 60 variations qui finissent au mois de base
    assert str(est.residus.index[0]) == "2016-01" and str(est.residus.index[-1]) == "2020-12"


def test_deux_regresseurs_dont_un_coefficient_libre_sur_le_bund():
    rng = np.random.default_rng(1)
    index = _mois("2015-01", 100)
    y_de = pd.Series(2 + np.cumsum(rng.normal(0, 0.1, 100)), index=index)
    y_p = pd.Series(3 + np.cumsum(rng.normal(0, 0.1, 100)), index=index)
    y_fr = 0.9 * y_de + 0.3 * y_p
    est, chemin = decomposer(100 * y_fr, 100 * pd.DataFrame({"DE": y_de, "pairs": y_p}), base="2020-12",
                             fin="2022-12", n=60)
    assert est.coef == pytest.approx([0.9, 0.3])
    assert chemin["propre"].abs().max() == pytest.approx(0.0, abs=1e-8)


def test_cumuler_avec_une_estimation_donnee():
    # l'épisode E5 réutilise l'estimation du modèle principal : la part propre ne compte que depuis sa base
    s_fr, P = _donnees_simulees(choc=("2022-03", 12.0))
    est, _ = decomposer(s_fr, P, base="2020-12", fin="2023-04", n=60)
    chemin = cumuler(est, s_fr.diff().dropna(), P.diff().dropna(), base="2022-01", fin="2022-04")
    assert chemin["propre"].tolist() == pytest.approx([0.0, 12.0, 12.0])
    assert chemin["h"].tolist() == [1, 2, 3]


def test_la_france_contre_chaque_pays_a_la_main():
    taux = pd.DataFrame({"FR": [3.00, 3.50], "DE": [2.50, 2.60], "IT": [3.90, 3.40]}, index=_mois("2024-05", 2))
    t = france_contre_pays(taux, "2024-05", "2024-06", ["DE", "IT"])
    assert t.loc["DE"].to_dict() == pytest.approx({"base_pb": 50.0, "fin_pb": 90.0, "variation_pb": 40.0})
    assert t.loc["IT"].to_dict() == pytest.approx({"base_pb": -90.0, "fin_pb": 10.0, "variation_pb": 100.0})


def test_plus_haut_depuis_et_mois_au_dessus():
    index = _mois("2011-01", 6)
    s = pd.Series([150.0, 190.0, 120.0, 100.0, 140.0, 147.0], index=index)
    assert plus_haut_depuis(s, "2011-06") == "2011-02"
    assert plus_haut_depuis(s, "2011-02") is None
    a = pd.Series([3.0, 3.2, 3.5, 3.6, 3.4, 3.5], index=index)
    b = pd.Series([3.1, 3.2, 3.4, 3.5, 3.5, 3.4], index=index)
    assert mois_au_dessus(a, b) == ["2011-03", "2011-04", "2011-06"]      # 3,2 contre 3,2 : pas au-dessus
    assert mois_au_dessus(a, b, "2011-05", "2011-06") == ["2011-06"]
