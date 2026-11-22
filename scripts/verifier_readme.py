"""Vérifie que chaque chiffre du README sort des JSON de resultats/.

1. Les chiffres attendus : recalculés depuis les JSON, mis en forme comme dans la page (virgule décimale, signe
   moins typographique), chacun avec un peu de contexte ; chacun doit figurer tel quel dans le README.
2. Les nombres de la page : hors blocs de code, liens et dates, chaque nombre du README doit apparaître dans l'un
   des chiffres attendus (ou être une année de 1999 à 2027).
3. Les dates : chaque « jour mois année » et chaque « mois année » du README doit être une date ou un mois présent
   dans les JSON (résultats, ou références écrites à la main avec leur source).

Sort avec le code 1 et la liste des écarts si un contrôle échoue.
"""
import json
import math
import re
import sys
from pathlib import Path

RESULTATS = Path("resultats")
MOIS = {"janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "août": 8,
        "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12}
NOMS_MOIS = {v: k for k, v in MOIS.items()}


def fr(x: float, d: int = 0) -> str:
    """Nombre à la française : virgule décimale, signe moins typographique ; milliers séparés par une espace."""
    texte = f"{abs(x):,.{d}f}".replace(",", " ").replace(".", ",")
    return ("−" if round(x, d) < 0 else "") + texte


def signe(x: float, d: int = 0) -> str:
    return ("+" if round(x, d) > 0 else "") + fr(x, d)


def ic(paire, d: int = 0) -> str:
    return f"[{fr(paire[0], d)} ; {fr(paire[1], d)}]"


def mois_fr(m: str) -> str:
    annee, mois = m.split("-")[:2]
    return f"{NOMS_MOIS[int(mois)]} {annee}"


def attendus(r: dict) -> dict[str, str]:
    dec, st, abe, ctl, ref = r["decomposition"], r["stress"], r["abe_2025"], r["controles"], r["references"]
    p = dec["modele_principal"]
    est = p["estimation"]
    var = dec["variantes"]
    f = dec["faits"]
    sm = dec["sans_modele"]
    ep = dec["episodes"]
    sov = dec["sovciss"]
    ch = p["chemin"]
    pos = st["positions"]
    A, B = pos["A_oat_seule"], pos["B_oat_contre_bund"]
    e = {}
    # Note et en-tête
    assert p["part_commune_pb"] < 0 < p["part_propre_pb"]
    e["en-tête"] = (f"Toute la hausse de l'écart OAT-Bund de mai 2024 à octobre 2026 ({signe(p['variation_observee_pb'])} pb, "
                    f"de {fr(p['ecart_base_pb'])} à {fr(p['ecart_fin_pb'])} pb en moyenne mensuelle) est propre à la France : "
                    f"{fr(p['part_propre_pb'])} pb {ic(p['ic95_pb'])} ; en suivant ses pairs, l'écart aurait baissé de "
                    f"{fr(-p['part_commune_pb'])} pb")
    e["arrondis"] = (f"Les arrondis expliquent que {fr(p['part_propre_pb'])} − {fr(-p['part_commune_pb'])} ne fasse pas "
                     f"{fr(p['variation_observee_pb'])} : la part propre vaut {fr(p['part_propre_pb'], 1)} pb, la part "
                     f"commune {fr(p['part_commune_pb'], 1)} pb et la hausse {fr(p['variation_observee_pb'], 1)} pb")
    e["baisse des pairs"] = f"a baissé de {fr(p['P_G8_base_pb'] - p['P_G8_fin_pb'])} pb"
    xs = sorted(round(v["part_propre_pb"]) for v in var.values())
    e["variantes"] = f"donnent toutes {xs[0]} ou {xs[-1]} pb"
    e["147"] = (f"l'écart OAT-Bund ({fr(f['ecart_fin_pb'])} pb en moyenne mensuelle) est au plus haut depuis "
                f"{mois_fr(f['plus_haut_depuis'])}")
    fi = f["france_au_dessus_de_l_italie"]
    nombres = {6: "sixième"}
    gaps = fi["ecarts_france_moins_italie_pb_ajout_apres_audit"]
    avant_sept = [g for m, g in gaps.items() if m < "2026-09"]
    e["italie"] = (f"et, en moyenne mensuelle, le taux français dépasse l'italien pour le {nombres[fi['nombre_de_mois']]} "
                   f"mois depuis {mois_fr(fi['premier_mois_depuis_1999'])} (de moins de {math.ceil(max(avant_sept))} pb "
                   "avant septembre 2026), une première depuis 1999")
    chemin_avant = {m: v for m, v in ch.items() if m <= "2026-08"}
    bas = min(chemin_avant.items(), key=lambda kv: kv[1]["propre"])
    haut = max(chemin_avant.items(), key=lambda kv: kv[1]["propre"])
    e["chemin, début"] = f"dès {mois_fr(bas[0]).split()[0]} {bas[0][:4]} ({fr(bas[1]['propre'])} pb)"
    e["chemin, plage"] = f"reste entre {fr(bas[1]['propre'])} et {fr(haut[1]['propre'])} pb jusqu'en {mois_fr(haut[0])}"
    e["chemin, septembre"] = f"à {fr(ch['2026-09']['propre'])} pb en septembre"
    e5 = ep["E5"]
    e["automne"] = f"{fr(e5['part_propre_pb'])} pb\n  {ic(e5['ic95_pb'])} en deux mois"
    e["b"] = (f"b = {fr(est['coefficients']['P'], 2)} ({fr(est['coefficients']['P'], 2)} pb d'écart français par pb "
              "d'écart moyen des pairs)")
    francais_contre = {k: v["variation_pb"] for k, v in sm.items() if k not in ("G8",)}
    mini = min(francais_contre, key=francais_contre.get)
    maxi = max(francais_contre, key=francais_contre.get)
    noms = {"BE": "Belgique", "IE": "Irlande"}
    e["sans modèle, plage"] = (f"de {fr(francais_contre[mini])} pb\n  ({noms[mini]}) à {fr(francais_contre[maxi])} pb "
                               f"({noms[maxi]})")
    derive = p["diagnostic_derive"]
    e["dérive"] = f"{fr(derive['moyenne_residus_pb_par_mois'], 2)} pb par mois de plus"
    e["dérive, total"] = f"ferait {fr(derive['derive_sur_h_mois_pb'])} pb des {fr(p['part_propre_pb'])}"
    e1, e2 = ep["E1"], ep["E2"]
    e["E1 note"] = f"{fr(e1['part_propre_pb'])} pb {ic(e1['ic95_pb'])} de juin à novembre 2011"
    e["E2 note"] = f"({fr(e2['part_propre_pb'])} pb, {ic(e2['ic95_pb'])})"
    assert round(A["dv01_taux_keur_par_pb"]) == round(A["sensibilite_ecart_keur_par_pb"])
    e["DV01 note"] = (f"la DV01 et la sensibilité à l'écart valent toutes deux {fr(A['dv01_taux_keur_par_pb'])} k€ "
                      "par pb")
    e["C1 note"] = f"rapporterait {fr(A['chocs']['C1_prime_resorbee']['variation_meur'], 1)} M€"
    e["C2 note"] = f"coûterait {fr(-A['chocs']['C2_choc_commun_2011']['variation_meur'], 1)} M€"
    obs = abe["ecart_observe_moyenne_annuelle_pb"]
    ea = abe["ecart_france_allemagne_abe_pb"]
    e["ABE note"] = f"({fr(obs['2025'])} pb en 2025, comme le\n  scénario)"
    e["ABE note 2"] = (f"Le niveau d'octobre 2026, {fr(f['ecart_fin_pb'])} pb sur un mois, approche l'écart adverse de 2025 "
                       f"({fr(ea['adverse_2025'])} pb) et dépasse celui de 2026 ({fr(ea['adverse_2026'])} pb) ; mais l'ABE "
                       "raisonne en moyenne annuelle")
    e["plan"] = f"commit `{ref['plan']['commit']}`"
    # Résumé anglais
    e["anglais 1"] = f"The whole {fr(p['variation_observee_pb'])} bp rise"
    e["anglais 2"] = f"is France-specific: {fr(p['part_propre_pb'])} bp [{fr(p['ic95_pb'][0])}; {fr(p['ic95_pb'][1])}]"
    e["anglais 2b"] = (f"(from {fr(p['ecart_base_pb'])} to {fr(p['ecart_fin_pb'])} bp, monthly averages)")
    e["anglais 2c"] = (f"the spread would have fallen by {fr(-p['part_commune_pb'])} bp ({fr(p['part_propre_pb'])} − "
                       f"{fr(-p['part_commune_pb'])} differs from {fr(p['variation_observee_pb'])} by rounding)")
    e["anglais 3"] = f"fell by {fr(p['P_G8_base_pb'] - p['P_G8_fin_pb'])} bp"
    e["anglais 4"] = f"give {xs[0]} or {xs[-1]} bp"
    e["anglais 5"] = f"EUR {fr(ref['plan']['nominal_oat_meur'])}m of {ref['plan']['maturite_ans']}-year OATs"
    e["anglais 6"] = f"worth EUR {fr(A['dv01_taux_keur_par_pb'])}k"
    # Section 2
    e["s2 147"] = (f"l'écart OAT-Bund est de {fr(f['ecart_fin_pb'])} pb en moyenne mensuelle, contre "
                   f"{fr(f['ecart_mai_2024_pb'])} pb en mai 2024")
    e["s2 2011"] = f"à novembre 2011 ({fr(f['ecart_au_plus_haut_depuis_pb'])} pb)"
    e["s2 italie"] = f"six mois, et aucun avant décembre 2025 depuis janvier 1999"
    e["s2 italie niveaux"] = f"le taux français était {fr(-sm['IT']['base_pb'])} pb en dessous de l'italien"
    e["s2 italie écarts"] = (f"L'écart est faible jusqu'en août 2026 (de {fr(min(avant_sept), 1)} à {fr(max(avant_sept), 1)} pb), "
                             f"puis de {fr(gaps['2026-09'], 1)} pb en septembre et de {fr(gaps['2026-10'])} pb en octobre "
                             "(écarts ajoutés après l'audit)")
    w = dec["poids_pib_2019"]["G8"]
    e["poids"] = (f"Italie {fr(100 * w['IT'])} %, Espagne {fr(100 * w['ES'])} %, Pays-Bas {fr(100 * w['NL'])} %, "
                  f"Belgique {fr(100 * w['BE'])} %, Autriche {fr(100 * w['AT'])} %,\n  Irlande {fr(100 * w['IE'])} %, "
                  f"Finlande {fr(100 * w['FI'])} %, Portugal {fr(100 * w['PT'])} %")
    e["pairs 80 72"] = f"passe de {fr(p['P_G8_base_pb'])} pb en mai 2024 à {fr(p['P_G8_fin_pb'])} pb en\n  octobre 2026"
    g = f["grece"]
    e["grèce"] = f"{fr(g['plus_grand_ecart_pb'])} pb en {mois_fr(g['mois'])}"
    e["grèce trou"] = f"en {mois_fr(g['mois_sans_valeur'][0])}"
    e["luxembourg"] = f"avant\n  {mois_fr(ref['exclusions']['luxembourg_taux_harmonise_depuis'])}"
    # Section 3
    e["s3 fenêtre"] = (f"sur les {est['variations']} variations de {mois_fr(est['fenetre'][0])} à "
                       f"{mois_fr(est['fenetre'][1])} : b = {fr(est['coefficients']['P'], 2)}")
    e["s3 erreur-type"] = f"(erreur-type de Newey-West {fr(est['erreurs_types_newey_west']['P'], 2)})"
    e["s3 R2"] = f"R² non\ncentré {fr(est['r2_non_centre'], 2)}"
    e["s3 sigma"] = f"écart-type des résidus {fr(est['ecart_type_residus_pb'], 1)} pb"
    e["s3 retards"] = f"Newey-West à\n{est['retards_newey_west']} retards"
    for m, texte in [("2024-06", "en juin 2024"), ("2024-12", "en décembre 2024"), ("2025-09", "en septembre\n2025"),
                     ("2026-08", "en août 2026"), ("2026-09", "en septembre 2026")]:
        e[f"chemin {m}"] = f"{fr(ch[m]['propre'])} pb {texte} {ic([ch[m]['bas'], ch[m]['haut']])}"
    e["chemin fin"] = f"{fr(p['part_propre_pb'])} pb en octobre 2026\n{ic(p['ic95_pb'])}"
    evs = {ev["date"]: ev for ev in ref["evenements"]}
    e["dissolution"] = f"JORF n° {evs['2024-06-09']['numero_jorf']:04d} du 10 juin\n2024"
    e["censure"] = (f"[scrutin n° {evs['2024-12-04']['numero_du_scrutin']}](https://www.assemblee-nationale.fr/dyn/17/"
                    f"scrutins/{evs['2024-12-04']['numero_du_scrutin']}), {evs['2024-12-04']['pour']} voix")
    v = evs["2025-09-08"]
    e["confiance"] = (f"[scrutin n° {v['numero_du_scrutin']}](https://www.assemblee-nationale.fr/dyn/17/scrutins/"
                      f"{v['numero_du_scrutin']}), {v['pour']} voix pour, {v['contre']} contre")
    lignes = [("**modèle principal** : huit pairs", "principal", None),
              ("fenêtre de 120 mois", "fenetre_120", None), ("fenêtre depuis 1999", "depuis_1999", None),
              ("pairs « cœur » : NL, BE, AT, FI", "coeur", None), ("pairs « périphérie » : IT, ES, PT, IE", "peripherie", None),
              ("taux et non écarts, coefficient libre sur le Bund", "taux_bund_libre", None)]
    for libelle, nom, _ in lignes:
        v = p if nom == "principal" else var[nom]
        c = v["estimation"]["coefficients"]
        coef = (f"Bund {fr(c['DE'], 2)} ; pairs {fr(c['pairs'], 2)}" if "DE" in c else f"b = {fr(c['P'], 2)}")
        if nom == "principal":
            e[f"variante {nom}"] = f"| {libelle} | 60 mois, juin 2019 à mai 2024 | {coef} | **{fr(v['part_propre_pb'])}** | **{ic(v['ic95_pb'])}** |"
        else:
            e[f"variante {nom}"] = f"| {coef} | {fr(v['part_propre_pb'])} | {ic(v['ic95_pb'])} |"
    e["fenêtre 1999"] = f"| {var['depuis_1999']['estimation']['variations']} mois, février 1999 à mai 2024 |"
    repli = dec["regle_de_repli"]
    e["repli"] = f"de plus de {fr(repli['seuil_pb'])} pb du modèle principal"
    e["repli écart"] = f"Le plus grand écart est de {fr(repli['plus_grand_ecart_pb'], 1)} pb : la règle ne joue pas"
    e["repli non appliqué"] = "la règle ne joue pas" if not repli["applique"] else "LA RÈGLE JOUE"
    cb = var["taux_bund_libre"]["estimation"]["coefficients"]
    bs = [v["estimation"]["coefficients"]["P"] for v in list(var.values()) + [p] if "P" in v["estimation"]["coefficients"]]
    e["b plage"] = f"b dépend de l'échelle du facteur ({fr(min(bs), 2)} à {fr(max(bs), 2)}), la part commune non"
    e["somme"] = f"la somme, {fr(cb['DE'] + cb['pairs'], 2)}, est proche de 1"
    e["dérive s3"] = f"le résidu moyen est de {fr(derive['moyenne_residus_pb_par_mois'], 2)} pb par mois"
    e["dérive s3 total"] = (f"soit {fr(derive['derive_sur_h_mois_pb'])} pb sur {p['h_mois']} mois : la part propre serait "
                            f"alors de l'ordre de\n  {fr(p['part_propre_pb'] - derive['derive_sur_h_mois_pb'])} pb")
    noms_pays = {"DE": "Allemagne", "IT": "Italie", "ES": "Espagne", "NL": "Pays-Bas", "BE": "Belgique",
                 "AT": "Autriche", "PT": "Portugal", "FI": "Finlande", "IE": "Irlande",
                 "G8": "moyenne des huit pairs (PIB de 2019)"}
    for k, v in sm.items():
        e[f"sans modèle {k}"] = f"| {noms_pays[k]} | {fr(v['base_pb'])} | {fr(v['fin_pb'])} | {signe(v['variation_pb'])} |"
    # Section 4
    libelles = {"E1": "juin à novembre 2011", "E2": "décembre 2016 à avril 2017", "E3": "février à avril 2020",
                "E4": "décembre 2021 à octobre 2022", "E5": "août à octobre 2026"}
    for n, v in ep.items():
        e[f"épisode {n}"] = (f"| {n} | {libelles[n]} | {signe(v['variation_observee_pb'])} | {signe(v['part_commune_pb'])} | "
                             f"{signe(v['part_propre_pb'])} {ic(v['ic95_pb'])} |")
        if v["lecture"] is not None:
            attente = {"E2": "positive, intervalle sans 0", "E3": "intervalle contenant 0", "E4": "intervalle contenant 0"}[n]
            verdict = "oui" if v["lecture"]["verifiee"] else "**non**"
            e[f"épisode {n} lecture"] = f"{ic(v['ic95_pb'])} | {attente} | {verdict} |"
    e["pepp"] = (f"le 18 mars un\n  programme d'achats d'urgence de {evs['2020-03-18']['montant_md_eur']} Md€")
    e["hausse bce"] = f"de {evs['2022-07-21']['hausse_pb']} pb le 21 juillet"
    e["élection"] = "les 22 et 23 avril 2017"
    e["décision"] = "décision n° 2017-169 PDR du 26 avril 2017"
    e["E2 texte"] = f"La part propre est positive ({signe(e2['part_propre_pb'])} pb)"
    e["E1 texte"] = (f"la part commune domine ({signe(e1['part_commune_pb'])} pb sur {signe(e1['variation_observee_pb'])}), "
                     f"et la France a aussi sa part propre ({signe(e1['part_propre_pb'])} pb)")
    e["E5 texte"] = f"{fr(e5['part_propre_pb'])} pb propres en deux mois"
    e["E5 pairs"] = f"L'écart moyen des pairs monte aussi de {fr(e5['variation_P_G8_pb'])} pb"
    for n, jour in [("E1", "le 1er novembre 2011"), ("E2", "le 16 mars 2017"), ("E3", "le\n  2 avril 2020"),
                    ("E4", "le 19 octobre 2022"), ("E5", "le 21 octobre 2026")]:
        e[f"sovciss {n}"] = f"{jour} ({fr(sov[n]['maximum'], 2)})"
    j = sov["juin_2024"]
    e["sovciss juin"] = f"le vendredi 14 juin, de {fr(j['valeur_jour_precedent'], 2)} à {fr(j['valeur_du_jour'], 2)}"
    # Section 5
    ca = st["courbe_aaa"]
    e["courbe"] = f"publiées les {ca['jours']}\n  jours ouvrés du mois ; {fr(ca['taux_zero_coupon_pct']['SR_10Y'], 2)} % à 10 ans"
    e["écart stress"] = f"plus l'écart d'octobre 2026, {fr(st['ecart_oat_pb'])} pb"
    e["oat"] = f"(coupon {fr(st['oat']['coupon_pct'], 2)} %, duration {fr(st['oat']['duration_ans'], 1)} ans)"
    e["bund"] = (f"la vente de {fr(-st['bund']['nominal_meur'], 1)} M€ de Bund à 10 ans au pair (coupon "
                 f"{fr(st['bund']['coupon_pct'], 2)} %, duration {fr(st['bund']['duration_ans'], 1)} ans)")
    e["sensibilités"] = (f"A : DV01 de taux {fr(A['dv01_taux_keur_par_pb'])} k€ par pb, sensibilité à l'écart "
                         f"{fr(A['sensibilite_ecart_keur_par_pb'])} k€ par pb")
    e["sensibilités B"] = f"sensibilité à l'écart {fr(B['sensibilite_ecart_keur_par_pb'])} k€ par pb"
    e["B dv01 nulle"] = "DV01 de taux nulle" if abs(B["dv01_taux_keur_par_pb"]) < 1e-6 else "DV01 NON NULLE"
    chocs = st["chocs"]
    e["C1 def"] = f"l'écart baisse de la part propre, {fr(-chocs['C1_prime_resorbee']['ecart_10_ans_pb'])} pb"
    ent = st["entrees"]
    e["C2 def"] = (f"{fr(ent['b'], 2)} × {fr(ent['variation_P_G8_2011_06_2011_11_pb'])} = "
                   f"{fr(chocs['C2_choc_commun_2011']['ecart_10_ans_pb'])} pb")
    fa = st["facteurs_2022"]["variation_pb"]
    e["C3 def"] = f"la courbe AAA monte de {fr(chocs['C3_niveau_2022']['aaa_10_ans_pb'])} pb"
    e["C4 def"] = (f"(niveau {signe(fa['niveau'])} pb, pente {signe(fa['pente'])} pb, courbure {signe(fa['courbure'])} pb) : "
                   f"{signe(chocs['C4_rejeu_2022']['aaa_10_ans_pb'])} pb à 10 ans")
    e["C5 def"] = (f"écart OAT-Bund {signe(chocs['C5_abe_2025_marche']['ecart_10_ans_pb'])} pb et Bund "
                   f"{signe(chocs['C5_abe_2025_marche']['aaa_10_ans_pb'])} pb à 10 ans")
    libs = {"C1_prime_resorbee": "C1 prime française résorbée", "C2_choc_commun_2011": "C2 choc commun de 2011",
            "C3_niveau_2022": "C3 niveau de 2022", "C4_rejeu_2022": "C4 rejeu des trois facteurs de 2022",
            "C5_abe_2025_marche": "C5 choc de marché de l'ABE 2025"}
    for c, lib in libs.items():
        va, vb = A["chocs"][c]["variation_meur"], B["chocs"][c]["variation_meur"]
        da = 2 if abs(va) < 0.5 else 1
        db = 2 if abs(vb) < 0.5 else 1
        ec = chocs[c]["ecart_10_ans_pb"]
        aa = chocs[c]["aaa_10_ans_pb"]
        cellule_ec = f"{signe(ec)} pb" if abs(ec) > 1e-9 else ""
        cellule_aa = f"{signe(aa)} pb" if abs(aa) > 1e-9 else ""
        gras = "**" if c == "C1_prime_resorbee" else ""
        cellules = [lib, cellule_ec, cellule_aa, f"{gras}{signe(va, da)} M€{gras}", f"{gras}{signe(vb, db)} M€{gras}"]
        e[f"stress {c}"] = ("| " + " | ".join(cellules) + " |").replace("|  |", "| |")
    c1 = A["chocs"]["C1_prime_resorbee"]
    e["prime en euros"] = (f"La prime mesurée vaut {fr(c1['variation_meur'], 1)} M€ pour {fr(ref['plan']['nominal_oat_meur'])} "
                           f"M€ d'OAT à {ref['plan']['maturite_ans']} ans")
    e["premier ordre"] = (f"contre\n  {fr(c1['premier_ordre_meur'], 1)} M€ au premier ordre ({fr(A['sensibilite_ecart_keur_par_pb'])} k€ × "
                          f"{fr(-chocs['C1_prime_resorbee']['ecart_10_ans_pb'])} pb)")
    e["B 2022"] = (f"B ne bouge\n  presque pas ({fr(B['chocs']['C3_niveau_2022']['variation_meur'], 2)} et "
                   f"{fr(B['chocs']['C4_rejeu_2022']['variation_meur'], 2)} M€)")
    e["2011 propre"] = f"la France a aussi eu sa part propre ({signe(e1['part_propre_pb'])} pb, section 4)"
    # Section 6
    e["abe lancement"] = "L'ABE a lancé le 20 janvier 2025 son test de résistance sur 2025-2027"
    e["abe mise à jour"] = "mis à jour le 12 février 2025"
    e["abe départ"] = f"| ABE, point de départ | {fr(ea['depart_moyenne_2024'])} | {fr(ea['depart_decembre_2024'])} | | | |"
    e["abe central"] = f"| ABE, scénario central | | | {fr(ea['central_2025'])} | {fr(ea['central_2026'])} | {fr(ea['central_2027'])} |"
    e["abe adverse"] = f"| ABE, scénario adverse | | | {fr(ea['adverse_2025'])} | {fr(ea['adverse_2026'])} | {fr(ea['adverse_2027'])} |"
    e["abe observé"] = (f"| observé (Eurostat), moyenne annuelle | {fr(obs['2024'])} | | {fr(obs['2025'])} | "
                        f"{fr(obs['2026_janvier_octobre'])} (janvier à octobre) | |")
    cd = abe["controle_depart_2024"]
    e["abe contrôle"] = (f"{fr(cd['abe_moyenne_2024_pct']['FR'], 2)} % pour\n  la France et {fr(cd['abe_moyenne_2024_pct']['DE'], 2)} % "
                         f"pour l'Allemagne, contre {fr(cd['eurostat_moyenne_2024_pct']['FR'], 2)} % et "
                         f"{fr(cd['eurostat_moyenne_2024_pct']['DE'], 2)} % chez Eurostat")
    e["abe suivi"] = (f"{fr(obs['2025'])} pb en 2025 pour {fr(ea['central_2025'])} dans le\n  scénario central et "
                      f"{fr(ea['adverse_2025'])} dans l'adverse")
    assert ea["adverse_2026"] < f["ecart_fin_pb"] < ea["adverse_2025"]
    e["abe octobre"] = (f"Le niveau d'octobre 2026 ({fr(f['ecart_fin_pb'])} pb en moyenne mensuelle) approche "
                        f"l'adverse de 2025 ({fr(ea['adverse_2025'])} pb) et dépasse celui de 2026 ({fr(ea['adverse_2026'])} pb), "
                        "mais c'est un mois contre des moyennes annuelles")
    ca2 = st["controle_ajoute_apres_coup"]["taux_eurostat_pct"]
    e["contrôle coupons"] = (f"Eurostat donne {fr(ca2['FR'], 2)} % pour la France et {fr(ca2['DE'], 2)} % pour\n  "
                             "l'Allemagne en octobre 2026")
    cm = abe["choc_de_marche_10_ans_pb"]
    e["abe marché"] = (f"monte le swap en euro de {fr(cm['swap_eur'])} pb, l'écart souverain français\n  contre swap de "
                       f"{fr(cm['france_contre_swap'])} pb et l'allemand de {fr(cm['allemagne_contre_swap'])} pb : "
                       f"{signe(cm['taux_france'])} pb pour le taux français, {signe(cm['taux_allemagne'])} pb pour "
                       f"l'allemand, {signe(cm['ecart_oat_bund'])} pb pour\n  l'écart OAT-Bund")
    # Section 7
    e["limite dérive"] = f"la part propre perd {fr(derive['derive_sur_h_mois_pb'])} pb"
    e["limite quotidien"] = (f"n'en confirme pas l'ampleur ({fr(sov['E5']['maximum'], 2)} au plus pendant l'automne 2026, "
                             f"contre {fr(sov['E1']['maximum'], 2)} en 2011)")
    e["plan avant décomposition"] = ("Le plan a été commité avant la décomposition (écarts bruts déjà vus : `PLAN.md`, "
                                     "section 0 ; commit `" + ref["plan"]["commit"] + "`) ; c'est un engagement, pas une preuve")
    e["IA"] = ("Le plan (son « je » est l'agent), le code et cette note ont été rédigés et relus par des agents d'IA "
               "(Claude Code), sous la direction de Guillaume Beaudouin ; il fixe l'objectif et les règles de validation, "
               "et décide de ce qui est gardé")
    e["IA anglais"] = ("The plan (its \"I\" is the agent), the code and this note were written and reviewed by AI agents "
                       "(Claude Code) under the direction of Guillaume Beaudouin; he sets the objective and the validation "
                       "rules, and decides what is kept")
    e["limite contagion"] = f"(par exemple de {fr(e5['variation_P_G8_pb'])} pb à l'automne 2026)"
    # Section 9
    al, es = ctl["allemagne_bundesbank_moins_eurostat"], ctl["espagne_banco_de_espana_moins_eurostat"]
    e["contrôle DE"] = f"(corrélation des variations mensuelles {fr(al['correlation_des_variations_mensuelles'], 3)})"
    e["contrôle DE niveau"] = f"plus haute de {fr(al['ecart_moyen_pb'], 1)} pb en moyenne"
    e["contrôle ES"] = (f"à\n  {fr(es['ecart_moyen_pb'], 2)} pb près en moyenne (corrélation "
                        f"{fr(es['correlation_des_variations_mensuelles'], 3)})")
    # Annexe
    an = ref["annexe_prevision"]
    h = an["horizons_mois"]
    rm = an["rmse_superieure_a_la_marche_aleatoire_pct"]
    e["annexe"] = (f"plus élevée de {rm[str(h[0])]} %, {rm[str(h[1])]} % et {rm[str(h[2])]} % à {h[0]}, {h[1]} et "
                   f"{h[2]} mois")
    # Constantes du plan citées dans le texte
    pl = ref["plan"]
    e["plan 60"] = f"sur les {pl['fenetre_principale_variations']} mois avant mai 2024"
    e["plan 95"] = f"intervalle à {pl['niveau_de_l_intervalle_pct']} %"
    e["plan 120"] = f"fenêtre de {pl['fenetre_longue_variations']} mois"
    e["plan 304"] = f"{pl['fenetre_depuis_1999_variations']} mois"
    e["plan 22 jours"] = f"{ca['jours']}\n  jours"
    return e


# Formulations corrigées par l'audit indépendant : elles ne doivent pas revenir.
INTERDITES = ["avant tout calcul", "before any computation", "CC BY", "d'indiquer les modifications", "bien connu",
              "sont propres à la France", "are specific to France"]


def normaliser(texte: str) -> str:
    """Sans les marques de citation en début de ligne, et avec un seul espace entre les mots : la vérification ne
    dépend pas de l'endroit où les lignes sont coupées."""
    texte = re.sub(r"^> ?", "", texte, flags=re.M)
    return re.sub(r"\s+", " ", texte)


def charger() -> dict:
    noms = ["decomposition", "stress", "abe_2025", "controles", "references"]
    return {n: json.loads((RESULTATS / f"{n}.json").read_text(encoding="utf-8")) for n in noms}


def dates_et_mois(r) -> tuple[set[str], set[str]]:
    """Toutes les dates (AAAA-MM-JJ) et tous les mois (AAAA-MM) qui apparaissent dans les JSON, clés comprises."""
    textes = []

    def parcourir(x):
        if isinstance(x, dict):
            for k, v in x.items():
                textes.append(str(k))
                parcourir(v)
        elif isinstance(x, list):
            for v in x:
                parcourir(v)
        elif isinstance(x, str):
            textes.append(x)
    parcourir(r)
    dates = set(re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", " ".join(textes)))
    mois = set(re.findall(r"\b(\d{4}-\d{2})\b", " ".join(textes))) | {d[:7] for d in dates}
    return dates, mois


def nettoyer(texte: str) -> str:
    """Retire ce qui n'est pas de la prose chiffrée : blocs de code, code en ligne, adresses des liens et images,
    numéros de section, nom de licence."""
    texte = re.sub(r"```.*?```", " ", texte, flags=re.S)
    texte = re.sub(r"`[^`]*`", " ", texte)
    texte = re.sub(r"\]\([^)]*\)", "] ", texte)
    texte = re.sub(r"!\[[^\]]*\]", " ", texte)
    texte = re.sub(r"^#+ \d+\.", "#", texte, flags=re.M)
    texte = texte.replace("CC BY 4.0", "CC BY")
    return texte


def main() -> int:
    r = charger()
    readme = Path("README.md").read_text(encoding="utf-8")
    erreurs = []
    e = attendus(r)
    page = normaliser(readme)
    for nom, chaine in e.items():
        if normaliser(chaine) not in page:
            erreurs.append(f"absent du README ({nom}) : {chaine!r}")
    for formule in INTERDITES:
        if normaliser(formule) in page:
            erreurs.append(f"formulation retirée après l'audit, de retour dans le README : {formule!r}")
    dates, mois = dates_et_mois(r)
    texte = nettoyer(readme)
    # dates « jour mois [année] »
    motif_date = re.compile(r"\b(1er|\d{1,2}) (" + "|".join(MOIS) + r")(?:\s+(\d{4}))?")
    jours_mois = {(int(d[5:7]), int(d[8:10])) for d in dates}
    for m in motif_date.finditer(texte):
        jour = 1 if m.group(1) == "1er" else int(m.group(1))
        num = MOIS[m.group(2)]
        if m.group(3):
            iso = f"{m.group(3)}-{num:02d}-{jour:02d}"
            if iso not in dates:
                erreurs.append(f"date absente des JSON : {m.group(0)!r}")
        elif (num, jour) not in jours_mois:
            erreurs.append(f"jour absent des JSON : {m.group(0)!r}")
    texte = motif_date.sub(" ", texte)
    motif_mois = re.compile(r"\b(" + "|".join(MOIS) + r")\s+(\d{4})\b")
    for m in motif_mois.finditer(texte):
        if f"{m.group(2)}-{MOIS[m.group(1)]:02d}" not in mois:
            erreurs.append(f"mois absent des JSON : {m.group(0)!r}")
    texte = motif_mois.sub(" ", texte)
    # nombres restants
    permis = set()
    motif_nombre = re.compile(r"(?<![\w.,])\d{1,3}(?: \d{3})+(?:,\d+)?(?![\w])|(?<![\w.,])\d+(?:,\d+)?")
    for chaine in e.values():
        permis.update(n.replace(" ", " ") for n in motif_nombre.findall(nettoyer(chaine)))
    for n in motif_nombre.findall(texte):
        n = n.replace(" ", " ")
        if n in permis:
            continue
        if re.fullmatch(r"(199\d|20[0-2]\d)", n):
            continue
        erreurs.append(f"nombre du README qui ne sort d'aucun chiffre attendu : {n!r}")
    if erreurs:
        print(f"{len(erreurs)} écart(s) :")
        for err in erreurs:
            print("  -", err)
        return 1
    print(f"README conforme : {len(e)} chiffres attendus trouvés, chaque nombre de la page sort des JSON.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
