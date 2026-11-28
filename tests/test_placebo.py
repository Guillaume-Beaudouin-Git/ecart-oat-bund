"""Les placebos hors plan (section 3 du README) sur des cas construits à la main."""
import numpy as np
import pandas as pd
import pytest

from ecart_oat_bund.decomposition import Z_95, decomposer
from ecart_oat_bund.placebo import (depasse, etalonner, facteur_commun, intervalle_empirique, par_dates, par_pays,
                                    resume_dates)


def _mois(debut, n):
    return pd.period_range(debut, periods=n, freq="M")


def _ecarts(n=120, graine=0):
    """Trois pays dont l'écart à l'Allemagne suit un facteur commun et un bruit propre ; l'Allemagne à zéro."""
    rng = np.random.default_rng(graine)
    commun = np.cumsum(rng.normal(0, 3, n))
    index = _mois("2010-01", n)
    s = {"DE": np.zeros(n)}
    for i, c in enumerate(("AA", "BB", "CC")):
        s[c] = 50 + (0.5 + 0.25 * i) * commun + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame(s, index=index), pd.Series({"AA": 1.0, "BB": 2.0, "CC": 1.0})


def test_par_dates_ne_lit_rien_apres_la_fin_permise():
    ecarts, pib = _ecarts()
    P = facteur_commun(ecarts, pib, ["BB", "CC"])
    t = par_dates(ecarts["AA"], P, h=6, n=24, fin_max="2018-12")
    # première base : 24 variations avant elle (février 2010 à janvier 2012) ; dernière : six mois avant la fin
    assert t.index[0] == "2012-01" and t.index[-1] == "2018-06"
    assert (t["fin"] <= "2018-12").all() and len(t) == 78
    # chaque ligne est la décomposition du modèle, refaite à la main pour une base
    est, chemin = decomposer(ecarts["AA"], P, base="2015-03", fin="2015-09", n=24)
    assert t.loc["2015-03", "propre"] == pytest.approx(chemin.iloc[-1]["propre"])
    assert t.loc["2015-03", "b"] == pytest.approx(est.coef[0])
    assert t.loc["2015-03", "z"] == pytest.approx(chemin.iloc[-1]["propre"] / chemin.iloc[-1]["sigma"])


def test_par_pays_retire_le_pays_et_les_exclus_de_ses_pairs():
    ecarts, pib = _ecarts()
    r = par_pays(ecarts, pib, ("AA", "BB", "CC"), base="2015-12", fin="2017-12", n=36)
    assert r["AA"]["pairs"] == ["BB", "CC"] and r["CC"]["pairs"] == ["AA", "BB"]
    r2 = par_pays(ecarts, pib, ("AA", "BB", "CC"), base="2015-12", fin="2017-12", n=36, exclus=("CC",))
    assert r2["AA"]["pairs"] == ["BB"]
    # le facteur de AA est la moyenne de BB et CC pondérée par le PIB : 2/3 et 1/3
    P = facteur_commun(ecarts, pib, ["BB", "CC"])["P"]
    assert P.iloc[5] == pytest.approx((2 * ecarts["BB"].iloc[5] + ecarts["CC"].iloc[5]) / 3)


def test_resume_etalonnage_et_depassement_a_la_main():
    t = pd.DataFrame({"fin": ["2010-03", "2010-04", "2010-05", "2010-06"], "propre": [-30.0, 10.0, 5.0, 40.0],
                      "sigma": [10.0, 10.0, 10.0, 10.0]}, index=["2010-01", "2010-02", "2010-03", "2010-04"])
    t["bas"], t["haut"] = t["propre"] - Z_95 * t["sigma"], t["propre"] + Z_95 * t["sigma"]
    t["z"] = t["propre"] / t["sigma"]
    t["exclut_zero"] = (t["bas"] > 0) | (t["haut"] < 0)
    r = resume_dates(t, h=2)
    assert r["exclut_zero"] == 2 and r["part_exclut_zero"] == pytest.approx(0.5)
    assert r["bases_ou_l_intervalle_exclut_zero"] == ["2010-01", "2010-04"]
    assert r["max_abs_propre_pb"] == 40.0 and r["base_max_abs"] == "2010-04" and r["base_min"] == "2010-01"
    assert r["fenetres_sans_chevauchement"] == 2          # de janvier à juin 2010 : 5 mois, deux fenêtres de 2
    assert r["ecart_type_z"] == pytest.approx(np.std([-3.0, 1.0, 0.5, 4.0], ddof=1))
    assert r["max_abs_z"] == 4.0 and r["base_max_abs_z"] == "2010-04" and r["z_a_la_base_max_abs_z"] == 4.0
    assert r["centile_95_abs_z"] == pytest.approx(np.quantile([3.0, 1.0, 0.5, 4.0], 0.95))
    # seuil élargi : 1,96 × écart-type des z (2,87), soit 5,62 : plus aucun |z| ne le dépasse
    assert r["part_exclut_zero_apres_elargissement"] == 0.0
    assert r["propre_aux_bases_ou_l_intervalle_exclut_zero_pb"] == {"2010-01": -30.0, "2010-04": 40.0}
    assert etalonner(100.0, 10.0, 1.5) == pytest.approx([100 - Z_95 * 15, 100 + Z_95 * 15])
    assert intervalle_empirique(100.0, 10.0, 4.0) == pytest.approx([60.0, 140.0])
    assert depasse(t, 30.0) == 2 and depasse(t, -41.0) == 0
