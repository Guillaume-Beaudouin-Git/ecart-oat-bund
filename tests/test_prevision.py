"""La prévision de volatilité sur des cas calculables à la main ou simulés ; aucune donnée réelle."""
import numpy as np
import pandas as pd
import pytest
from arch import arch_model

from ecart_oat_bund.prevision import (Z_95, ajuster_garch, bandes, comparer, comparer_niveau, couverture,
                                      decision_du_titre, diebold_mariano, erreur_vol_pb, etats, fin_de_mois,
                                      gain_significatif, origines, perte_premier_ordre_meur, positions_fin_de_mois,
                                      prevoir, prevoir_niveau, qlike, restreindre, retards_hac,
                                      somme_variances_garch, variance_historique, variance_realisee,
                                      variances_ewma, variations_pb, variations_standardisees)


def _garch_simulee(n, omega=0.5, alpha=0.08, beta=0.90, graine=0):
    """n variations d'une GARCH(1,1) normale à moyenne nulle, partie de sa variance de long terme."""
    rng = np.random.default_rng(graine)
    r, s2 = np.empty(n), omega / (1 - alpha - beta)
    for t in range(n):
        r[t] = np.sqrt(s2) * rng.normal()
        s2 = omega + alpha * r[t] ** 2 + beta * s2
    return r


def _serie(n=2400, graine=0, debut="1997-08-08"):
    """Variations simulées, datées sur des jours ouvrés à partir d'août 1997."""
    return pd.Series(_garch_simulee(n, graine=graine), index=pd.bdate_range(debut, periods=n))


def test_variations_et_variance_realisee_a_la_main():
    jours = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    r = variations_pb(pd.Series([1.00, 1.02, 1.01, 1.05], index=jours))
    # 100 × (1,02 − 1,00) = 2 pb ; puis −1 pb ; puis +4 pb, datées du jour d'arrivée
    assert r.index.tolist() == jours[1:].tolist()
    assert r.tolist() == pytest.approx([2.0, -1.0, 4.0])
    # après la première variation, les deux suivantes : (−1)² + 4² = 17 pb²
    assert variance_realisee(r.to_numpy(), 0, 2) == pytest.approx(17.0)
    with pytest.raises(ValueError):
        variance_realisee(r.to_numpy(), 1, 2)      # il ne reste qu'un jour après la position 1


def test_origines_en_fin_de_mois_depuis_decembre_2004():
    index = pd.bdate_range("2004-10-01", "2005-03-15")
    fins = index[positions_fin_de_mois(index)]
    # octobre 2004 finit le vendredi 29 ; la dernière position (15 mars) compte comme fin de la série
    assert fins.tolist() == pd.to_datetime(["2004-10-29", "2004-11-30", "2004-12-31", "2005-01-31", "2005-02-28",
                                            "2005-03-15"]).tolist()
    o = origines(index, premiere_origine="2004-12", min_variations=1)
    assert index[o].tolist() == pd.to_datetime(["2004-12-31", "2005-01-31", "2005-02-28", "2005-03-15"]).tolist()
    # avec au moins 100 variations connues : le 31 janvier 2005 est la 87e, le 28 février la 107e
    o = origines(index, premiere_origine="2004-12", min_variations=100)
    assert index[o[0]] == pd.Timestamp("2005-02-28") and o[0] + 1 == 107


def test_volatilite_historique_et_ewma_a_la_main():
    r = np.array([1.0, -2.0, 3.0, -4.0])
    # moyenne des deux derniers carrés connus en t = 3 : (9 + 16) / 2 ; des quatre : (1 + 4 + 9 + 16) / 4
    assert variance_historique(r, 3, 2) == pytest.approx(12.5)
    assert variance_historique(r, 3, 4) == pytest.approx(7.5)
    assert variance_historique(r, 2, 2) == pytest.approx(6.5)      # ne lit pas r[3]
    with pytest.raises(ValueError):
        variance_historique(r, 1, 4)
    # EWMA, départ sur les deux premiers carrés : s²(1) = 2,5 ; s²(2) = 0,94 × 2,5 + 0,06 × 9 = 2,89 ;
    # s²(3) = 0,94 × 2,89 + 0,06 × 16 = 3,6766
    s2 = variances_ewma(r, lam=0.94, n_init=2)
    assert np.isnan(s2[0]) and s2[1:].tolist() == pytest.approx([2.5, 2.89, 3.6766])


def test_somme_des_variances_garch_a_la_main():
    # ω = 1, α = 0,1, β = 0,8, σ²(t+1) = 20 : les jours suivants valent 1 + 0,9 × 20 = 19, puis 1 + 0,9 × 19 = 18,1
    assert somme_variances_garch(1.0, 0.1, 0.8, 20.0, 1) == pytest.approx(20.0)
    assert somme_variances_garch(1.0, 0.1, 0.8, 20.0, 2) == pytest.approx(39.0)
    assert somme_variances_garch(1.0, 0.1, 0.8, 20.0, 3) == pytest.approx(57.1)
    # forme fermée : h σ̄² + (σ²(t+1) − σ̄²)(1 − φ^h)/(1 − φ), σ̄² = ω/(1 − φ) = 10, φ = 0,9
    assert somme_variances_garch(1.0, 0.1, 0.8, 20.0, 63) == pytest.approx(63 * 10 + 10 * (1 - 0.9 ** 63) / 0.1)
    # partie de la variance de long terme, la prévision y reste : h × 10
    assert somme_variances_garch(1.0, 0.1, 0.8, 10.0, 63) == pytest.approx(630.0)


def test_garch_retrouvee_sur_donnees_simulees():
    r = _garch_simulee(20000, omega=0.5, alpha=0.08, beta=0.90, graine=1)
    g = ajuster_garch(r)
    assert g.converge
    assert g.alpha == pytest.approx(0.08, abs=0.015)
    assert g.beta == pytest.approx(0.90, abs=0.02)
    assert g.variance_de_long_terme == pytest.approx(0.5 / 0.02, rel=0.15)
    # σ²(t+1) et la somme sur 63 jours redonnent la prévision analytique du paquet arch
    reference = arch_model(r, mean="Zero", vol="GARCH", p=1, q=1, rescale=False).fit(disp="off")
    variances = reference.forecast(horizon=63, reindex=False).variance.to_numpy()[-1]
    assert g.variance_suivante == pytest.approx(variances[0], rel=1e-10)
    assert somme_variances_garch(g.omega, g.alpha, g.beta, g.variance_suivante, 63) == pytest.approx(variances.sum(),
                                                                                                    rel=1e-10)


def test_garch_sans_convergence_reprend_les_parametres_precedents(monkeypatch):
    from ecart_oat_bund import prevision
    r = _garch_simulee(1500, graine=2)
    precedente = ajuster_garch(r[:1400])
    vrai_modele = prevision.arch_model

    def modele_qui_ne_converge_pas(*args, **kwargs):
        m = vrai_modele(*args, **kwargs)
        fit = m.fit

        def fit_rate(*a, **k):
            resultat = fit(*a, **k)
            resultat._optim_output.status = 9      # l'optimiseur signale un échec
            return resultat
        m.fit = fit_rate
        return m
    monkeypatch.setattr(prevision, "arch_model", modele_qui_ne_converge_pas)
    g = ajuster_garch(r, repli=precedente)
    assert not g.converge
    assert (g.omega, g.alpha, g.beta) == pytest.approx((precedente.omega, precedente.alpha, precedente.beta))
    # les paramètres repris sont filtrés sur toutes les données connues : σ²(t+1) n'est pas celle de l'origine d'avant
    assert g.variance_suivante != pytest.approx(precedente.variance_suivante)


def test_qlike_a_la_main():
    assert qlike(100.0, 100.0) == pytest.approx(0.0)
    # prévision deux fois trop basse : 2 − ln 2 − 1 = 0,3069 ; deux fois trop haute : 0,5 + ln 2 − 1 = 0,1931
    assert qlike(200.0, 100.0) == pytest.approx(0.306853, abs=1e-6)
    assert qlike(100.0, 200.0) == pytest.approx(0.193147, abs=1e-6)
    assert qlike(200.0, 100.0) > qlike(100.0, 200.0)
    # erreur sur la volatilité : √400 − √100 = +10 pb quand la règle prévoit trop
    assert erreur_vol_pb(100.0, 400.0) == pytest.approx(10.0)


def test_diebold_mariano_a_la_main():
    # d = (1, 3, 1, 3) : moyenne 2, écarts (−1, 1, −1, 1). Sans retard, Var(moyenne) = Σe²/n² = 4/16 : t = 2/0,5 = 4.
    sans_retard = diebold_mariano([1.0, 3.0, 1.0, 3.0], 0)
    assert sans_retard["d_moyen"] == pytest.approx(2.0) and sans_retard["t"] == pytest.approx(4.0)
    # un retard, poids de Bartlett 1/2 : S = 4 + 2 × 0,5 × (−3) = 1, Var(moyenne) = 1/16 : t = 2/0,25 = 8
    assert diebold_mariano([1.0, 3.0, 1.0, 3.0], 1)["t"] == pytest.approx(8.0)
    # 2m retards, m le nombre de mois de l'horizon
    assert (retards_hac(21), retards_hac(63)) == (2, 6)


def test_comparaison_et_decision_a_la_main():
    origines_ = pd.date_range("2005-01-31", periods=4, freq="ME")
    p = pd.DataFrame({"fin_cible": origines_ + pd.Timedelta(days=90), "rv": [100.0, 100.0, 100.0, 100.0],
                      "garch": [100.0, 100.0, 200.0, 100.0], "hv252": [200.0, 50.0, 200.0, 50.0]}, index=origines_)
    c = comparer(p, "garch", "hv252", 63)
    # référence : (0,1931 + 0,3069 + 0,1931 + 0,3069) / 4 = 0,25 ; modèle : 0,1931 / 4
    assert c["qlike_reference"] == pytest.approx(0.25)
    assert c["qlike_modele"] == pytest.approx(0.193147 / 4, abs=1e-6)
    assert c["gain_pct"] == pytest.approx(100 * (1 - 0.193147 / 4 / 0.25), abs=1e-3)
    assert c["d_moyen"] == pytest.approx(0.25 - 0.193147 / 4, abs=1e-6) and c["retards"] == 6
    # la table de décision : 63 jours d'abord, 21 jours en repli, sinon pas de section
    oui, non, pire = {"d_moyen": 0.1, "p": 0.01}, {"d_moyen": 0.1, "p": 0.20}, {"d_moyen": -0.1, "p": 0.01}
    assert gain_significatif(oui) and not gain_significatif(non) and not gain_significatif(pire)
    assert decision_du_titre(oui, non) == "63 jours"
    assert decision_du_titre(non, oui) == "21 jours"
    assert decision_du_titre(pire, oui) == "21 jours"
    assert decision_du_titre(non, pire) == "section non publiée"
    # sous-période : seules les cibles qui finissent dans l'intervalle, bornes comprises (les cibles finissent les
    # 1er mai, 29 mai, 29 juin et 29 juillet 2005)
    assert len(restreindre(p, "2005-05-02", "2005-06-30")) == 2
    assert len(restreindre(p, "2005-05-01", "2005-06-29")) == 3


def test_previsions_a_la_main_et_cibles_completes():
    r = _serie(1400)
    positions = origines(r.index, premiere_origine="2002-01", min_variations=1000)
    e = etats(r, positions)
    p = prevoir(r, e, 21)
    x = r.to_numpy()
    t = int(e["position"].iloc[0])
    assert e.index[0] == r.index[t] and t + 1 >= 1000
    # cible et règles simples recalculées à la main à la première origine
    assert p["rv"].iloc[0] == pytest.approx((x[t + 1: t + 22] ** 2).sum())
    assert p["variation_pb"].iloc[0] == pytest.approx(x[t + 1: t + 22].sum())
    assert p["fin_cible"].iloc[0] == r.index[t + 21]
    assert p["hv252"].iloc[0] == pytest.approx(21 * (x[t - 251: t + 1] ** 2).mean())
    assert p["hv63"].iloc[0] == pytest.approx(21 * (x[t - 62: t + 1] ** 2).mean())
    assert p["garch"].iloc[0] == pytest.approx(somme_variances_garch(e["omega"].iloc[0], e["alpha"].iloc[0],
                                                                     e["beta"].iloc[0], e["garch"].iloc[0], 21))
    # une origine sans 21 jours après elle n'a pas de cible : elle garde son état (pour l'outil), pas de prévision
    assert len(p) < len(e) and (e.loc[p.index, "position"] + 21 <= len(x) - 1).all()
    assert e["position"].iloc[-1] == len(x) - 1


@pytest.mark.parametrize("fenetre", [None, 600])
def test_aucune_regle_ne_lit_l_avenir(fenetre):
    # on brouille toutes les variations après le 30 juin 2005 : ce que chaque règle sait et prévoit aux origines
    # antérieures ne doit pas changer, même quand la cible tombe après ; les origines suivantes, elles, changent
    r = _serie(2400)
    coupure = pd.Timestamp("2005-06-30")
    autre = r.copy()
    futur = r.index > coupure
    autre[futur] = np.random.default_rng(7).normal(0, 25, futur.sum())
    positions = origines(r.index, premiere_origine="2004-12", min_variations=1000)
    e, e_autre = etats(r, positions, fenetre), etats(autre, positions, fenetre)
    passe = e.index <= coupure
    assert passe.sum() == 7                                    # origines de décembre 2004 à juin 2005
    pd.testing.assert_frame_equal(e[passe], e_autre[passe])
    assert not np.allclose(e.loc[~passe, "garch"], e_autre.loc[~passe, "garch"])
    for h in (21, 63):
        p, p_autre = prevoir(r, e, h), prevoir(autre, e_autre, h)
        avant = p.index <= coupure
        regles = ["garch", "hv252", "hv63", "ewma"]
        pd.testing.assert_frame_equal(p.loc[avant, regles], p_autre.loc[avant, regles])
        assert not np.allclose(p.loc[~avant, regles], p_autre.loc[~avant, regles])
        # la cible de la dernière origine d'avant la coupure, elle, a changé : elle est bien dans le futur
        assert p["rv"][avant].iloc[-1] != pytest.approx(p_autre["rv"][avant].iloc[-1])


def test_couverture_bandes_et_choc_a_la_main():
    # bandes à ± 1,96 √F : 19,6 pb pour F = 100, 39,2 pb pour F = 400 ; 10 et 5 dedans, −30 et 50 dehors
    assert couverture([10.0, -30.0, 5.0, 50.0], [100.0, 100.0, 100.0, 400.0]) == pytest.approx(0.5)
    b = bandes(2.50, {63: 400.0})
    assert b[63]["ecart_type_pb"] == pytest.approx(20.0)
    assert b[63]["demi_largeur_pb"] == pytest.approx(Z_95 * 20)
    assert (b[63]["bas_pct"], b[63]["haut_pct"]) == pytest.approx((2.50 - 0.392, 2.50 + 0.392), abs=1e-4)
    # 46,5 pb de hausse sur une DV01 de 81 k€ par pb : 3,7665 M€ au premier ordre
    assert perte_premier_ordre_meur(46.5, 81.0) == pytest.approx(3.7665)
    p = pd.DataFrame({"variation_pb": [10.0, -30.0], "garch": [100.0, 400.0]})
    assert variations_standardisees(p).tolist() == pytest.approx([1.0, -1.5])


def test_niveau_ar1_direct_et_marche_aleatoire_a_la_main():
    # taux déterministe y(s+1) = c + γ y(s) : la régression directe retrouve c et γ, et à 2 mois c(1 + γ) + γ² y
    c, gamma = 0.3, 0.9
    y = np.empty(120)
    y[0] = 6.0
    for s in range(1, 120):
        y[s] = c + gamma * y[s - 1]
    mensuel = pd.Series(y, index=pd.date_range("1997-08-31", periods=120, freq="ME"))
    ar1 = prevoir_niveau(mensuel, 1, "ar1", premiere_origine="2004-12")
    assert ar1["origine"].iloc[0] == pd.Timestamp("2004-12-31") and ar1.index[0] == pd.Timestamp("2005-01-31")
    assert ar1["prevu"].to_numpy() == pytest.approx(ar1["realise"].to_numpy(), abs=1e-9)
    ar2 = prevoir_niveau(mensuel, 2, "ar1", premiere_origine="2004-12")
    t = mensuel.index.get_loc(pd.Timestamp("2004-12-31"))
    assert ar2["prevu"].iloc[0] == pytest.approx(c * (1 + gamma) + gamma ** 2 * y[t], abs=1e-9)
    ma = prevoir_niveau(mensuel, 3, "marche_aleatoire", premiere_origine="2004-12")
    assert ma["prevu"].iloc[0] == y[t] and ma["realise"].iloc[0] == y[t + 3]
    assert len(ma) == 120 - 3 - t
    # sur ce taux sans bruit, l'AR(1) ne fait aucune erreur : rapport des RMSE nul, d moyen positif
    r = comparer_niveau(mensuel, 3, premiere_origine="2004-12")
    assert r["rapport"] == pytest.approx(0.0, abs=1e-6) and r["d_moyen"] > 0 and r["retards"] == 6


def test_le_niveau_ne_lit_pas_l_avenir():
    rng = np.random.default_rng(3)
    mensuel = pd.Series(3 + np.cumsum(rng.normal(0, 0.2, 160)), index=pd.date_range("1997-08-31", periods=160, freq="ME"))
    autre = mensuel.copy()
    futur = mensuel.index > pd.Timestamp("2007-06-30")
    autre[futur] = rng.uniform(-5, 10, futur.sum())
    for modele in ("ar1", "marche_aleatoire"):
        for h in (3, 12):
            a = prevoir_niveau(mensuel, h, modele, "2004-12")
            b = prevoir_niveau(autre, h, modele, "2004-12")
            passe = a["origine"] <= pd.Timestamp("2007-06-30")
            assert passe.sum() == 31                               # origines de décembre 2004 à juin 2007
            assert a.loc[passe, "prevu"].tolist() == b.loc[passe, "prevu"].tolist()
            assert a.loc[~passe, "prevu"].tolist() != b.loc[~passe, "prevu"].tolist()


def test_fin_de_mois_garde_la_date_reelle():
    jours = pd.to_datetime(["2024-03-27", "2024-03-28", "2024-04-29", "2024-04-30"])
    m = fin_de_mois(pd.Series([1.0, 2.0, 3.0, 4.0], index=jours))
    assert m.index.tolist() == pd.to_datetime(["2024-03-28", "2024-04-30"]).tolist() and m.tolist() == [2.0, 4.0]
