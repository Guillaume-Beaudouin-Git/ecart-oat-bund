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


def jour_fr(d: str) -> str:
    """« 2026-10-30 » -> « 30 octobre 2026 » ; le premier du mois s'écrit « 1er »."""
    annee, mois, jour = d.split("-")
    return f"{'1er' if int(jour) == 1 else int(jour)} {NOMS_MOIS[int(mois)]} {annee}"


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
                             "(écarts ajoutés après l'audit d'une session de relecture distincte, par IA)")
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
    # Le rôle de l'IA : la phrase du profil, traduite (décision du 28 novembre 2026), puis ce qu'elle ne dit pas.
    e["IA"] = ("Je crée et gère des agents de programmation IA qui écrivent et relisent le code ; je fixe "
               "l'objectif et les règles de validation, et je décide de ce qui est retenu. Ces agents (Claude Code) "
               "ont aussi rédigé et "
               "relu les deux plans et cette note ; le « je » des plans est l'agent")
    e["IA anglais"] = ("I create and manage AI coding agents that write and review the code; I set the objective and "
                       "the validation rules, and decide what is kept. These agents (Claude Code) also wrote and "
                       "reviewed the two plans and this note; the plans' \"I\" is the agent")
    e["limite contagion"] = f"(par exemple de {fr(e5['variation_P_G8_pb'])} pb à l'automne 2026)"
    # Section 9
    al, es = ctl["allemagne_bundesbank_moins_eurostat"], ctl["espagne_banco_de_espana_moins_eurostat"]
    e["contrôle DE"] = f"(corrélation des variations mensuelles {fr(al['correlation_des_variations_mensuelles'], 3)})"
    e["contrôle DE niveau"] = f"plus haute de {fr(al['ecart_moyen_pb'], 1)} pb en moyenne"
    e["contrôle ES"] = (f"à\n  {fr(es['ecart_moyen_pb'], 2)} pb près en moyenne (corrélation "
                        f"{fr(es['correlation_des_variations_mensuelles'], 3)})")
    # Le travail voisin, cité dans la section 8 (l'ancienne annexe)
    an = ref["annexe_prevision"]
    h = an["horizons_mois"]
    rm = an["rmse_superieure_a_la_marche_aleatoire_pct"]
    e["annexe"] = (f"plus élevée de {rm[str(h[0])]} %, {rm[str(h[1])]} % et {rm[str(h[2])]} % à {h[0]}, {h[1]} et "
                   f"{h[2]} mois")
    e.update(attendus_prevision(r))
    e.update(attendus_placebo(r))
    # Constantes du plan citées dans le texte
    pl = ref["plan"]
    e["plan 60"] = f"sur les {pl['fenetre_principale_variations']} mois avant mai 2024"
    e["plan 95"] = f"intervalle à {pl['niveau_de_l_intervalle_pct']} %"
    e["plan 120"] = f"fenêtre de {pl['fenetre_longue_variations']} mois"
    e["plan 304"] = f"{pl['fenetre_depuis_1999_variations']} mois"
    e["plan 22 jours"] = f"{ca['jours']}\n  jours"
    return e


def attendus_prevision(r: dict) -> dict[str, str]:
    """Les chiffres de la section 8 (PLAN_PREVISION.md), de sa puce dans la note et de sa phrase en anglais : tous
    viennent de resultats/prevision.json, sauf la DV01 (stress.json) et les références (references.json)."""
    pv, st, ref = r["prevision"], r["stress"], r["references"]
    cst, dec, P, R = pv["constantes"], pv["decision"], pv["principal"], pv["robustesse"]
    h63, h21 = P["h63"], P["h21"]
    t63, t21 = dec["test_principal"], dec["test_de_repli"]
    o, bib, plan = pv["outil"], ref["bibliographie"], ref["plan_prevision"]
    choc = o["choc_99_a_63_jours"]
    b_garch, b_ref = o["bandes_95"]["garch"], o["bandes_95"]["hv252"]
    H, H21 = cst["horizons_jours"][1], cst["horizons_jours"][0]
    n_long, n_court = cst["fenetres_historiques_jours"]["hv252"], cst["fenetres_historiques_jours"]["hv63"]
    seuil = fr(100 * cst["seuil"])
    A = st["positions"]["A_oat_seule"]
    e = {}
    # Le titre est celui que la table de décision du plan autorise
    assert dec["titre"] == f"{H} jours" and t63["significatif"] and t63["horizon_jours"] == H
    assert round(100 * cst["seuil"]) == 5 and plan["nombre_de_tests_sur_la_volatilite"] == 48
    X = fr(t63["gain_pct"])
    g, q = h63["regles"], h21["regles"]
    c63, c21 = h63["comparaisons"], h21["comparaisons"]
    # Depuis l'audit, le titre nomme la perte : le plan le demandait pour la phrase qui porte le titre
    e["p8 titre"] = (f"**À un trimestre, la volatilité du Bund à 10 ans se prévoit : la GARCH réduit l'erreur (perte "
                     f"QLIKE) de {X} % face à la volatilité historique d'un an.**")
    e["p8 qlike"] = (f"vaut en moyenne {fr(t63['qlike_modele'], 3)} pour la GARCH(1,1) et "
                     f"{fr(t63['qlike_reference'], 3)} pour la référence (test de Diebold-Mariano, p = {fr(t63['p'], 3)}, "
                     f"{t63['n']} prévisions)")
    assert g["garch"]["rmse_vol_pb"] / h63["vol_realisee_moyenne_pb"] > 0.25
    e["p8 rmse"] = (f"passe de {fr(g['hv252']['rmse_vol_pb'], 1)} à {fr(g['garch']['rmse_vol_pb'], 1)} pb, soit encore "
                    f"plus du quart d'une volatilité réalisée de {fr(h63['vol_realisee_moyenne_pb'])} pb en moyenne")
    e["p8 ajout"] = f"Section ajoutée le {jour_fr(plan['date'])}, après les sections 1 à 7, qu'elle ne modifie pas"
    e["p8 plan"] = ("Elle suit un second plan, commité seul avant toute estimation sur les données (`PLAN_PREVISION.md`, "
                    f"commit `{plan['commit']}` ; ce qui avait été vu est dans sa section 0) ; c'est un engagement, pas "
                    "une preuve")
    e["p8 non prévu"] = "aucun taux OAT quotidien n'est ouvert (section 7)"
    # Protocole
    d10 = pv["donnees"]["bund_10_ans"]
    e["p8 série"] = (f"du {jour_fr(d10['premier_jour'])} au {jour_fr(d10['dernier_jour'])} ({fr(d10['jours_publies'])} "
                     "jours)")
    e["p8 origines"] = f"Une prévision chaque fin de mois depuis {mois_fr(cst['premiere_origine'])}"
    assert d10["premiere_origine"][:7] == cst["premiere_origine"]
    e["p8 cible"] = (f"des {H} jours publiés suivants (un trimestre) ou des {H21} suivants (un mois)")
    assert d10["non_convergences_garch"] == 0
    e["p8 garch"] = (f"Une GARCH(1,1) à moyenne nulle (Bollerslev, {bib['bollerslev']['annee']}), réestimée à chaque "
                     f"origine sur tout le passé (paquet `arch` ; {d10['ajustements_garch']} ajustements, tous convergés)")
    e["p8 règles simples"] = (f"la volatilité historique sur {n_long} jours, qui sert de référence ; la volatilité "
                              f"historique sur {n_court} jours ; une moyenne exponentielle de paramètre "
                              f"{fr(cst['lambda_ewma'], 2)} (EWMA ; RiskMetrics, {bib['riskmetrics']['annee']})")
    e["p8 patton"] = f"(Patton, {bib['patton']['annee']})"
    e["p8 test"] = (f"Diebold et Mariano ({bib['diebold_mariano']['annee']}), erreurs-types de Newey-West à "
                    f"{cst['retards_newey_west'][f'h{H}']} retards à un trimestre et "
                    f"{cst['retards_newey_west'][f'h{H21}']} retards à un mois")
    assert t63["retards"] == cst["retards_newey_west"][f"h{H}"] and t21["retards"] == cst["retards_newey_west"][f"h{H21}"]
    e["p8 décision"] = (f"Un seul test décide du titre : 10 ans, {H} jours, GARCH contre référence, seuil de {seuil} %. "
                        f"En cas d'échec, le titre aurait porté sur {H21} jours")
    e["p8 repli"] = "Le test passe : le repli ne joue pas"
    # Tableau des quatre règles et tableau des gains
    libelles = {"garch": "GARCH(1,1)", "hv252": f"volatilité historique, {n_long} jours (référence)",
                "hv63": f"volatilité historique, {n_court} jours", "ewma": f"EWMA {fr(cst['lambda_ewma'], 2)}"}
    for regle, lib in libelles.items():
        gras = "**" if regle in ("garch", "hv252") else ""
        a, b = g[regle], q[regle]
        e[f"p8 règle {regle}"] = (f"| {lib} | {gras}{fr(a['qlike'], 3)}{gras} | {fr(a['rmse_vol_pb'], 1)} | "
                                  f"{signe(a['biais_vol_pb'], 1)} | {fr(b['qlike'], 3)} | {fr(b['rmse_vol_pb'], 1)} | "
                                  f"{signe(b['biais_vol_pb'], 1)} |")
    faces = {"hv252": f"la volatilité historique, {n_long} jours", "hv63": f"la volatilité historique, {n_court} jours",
             "ewma": f"l'EWMA {fr(cst['lambda_ewma'], 2)}"}
    for regle, lib in faces.items():
        a, b = c63[f"garch_contre_{regle}"], c21[f"garch_contre_{regle}"]
        gras = "**" if regle == "hv252" else ""
        e[f"p8 gain {regle}"] = (f"| {lib} | {gras}{fr(a['gain_pct'])} %{gras} | {gras}{fr(a['p'], 3)}{gras} | "
                                 f"{fr(b['gain_pct'])} % | {fr(b['p'], 3)} |")
    e["p8 montre"] = (f"à un trimestre ({X} %) comme à un mois ({fr(t21['gain_pct'])} %, p = {fr(t21['p'], 3)})")
    a63, w63 = c63["garch_contre_hv63"], c63["garch_contre_ewma"]
    assert a63["p"] > cst["seuil"] and w63["p"] > cst["seuil"] and a63["gain_pct"] > 0 and w63["gain_pct"] > 0
    # La part de l'écart de QLIKE entre la référence et la GARCH que capte chacune des deux règles réactives
    capte = {k: (g["hv252"]["qlike"] - g[k]["qlike"]) / (g["hv252"]["qlike"] - g["garch"]["qlike"])
             for k in ("hv63", "ewma")}
    assert capte["hv63"] > 2 / 3 and capte["ewma"] > 0.5
    e["p8 essentiel"] = (f"Une moyenne des {n_court} derniers jours capte déjà l'essentiel du gain : "
                         f"{fr(100 * capte['hv63'])} % de l'écart de perte entre la référence et la GARCH ; l'EWMA, "
                         f"{fr(100 * capte['ewma'])} %")
    e["p8 ne montre pas"] = (f"son gain est de {fr(a63['gain_pct'])} % face à la volatilité sur {n_court} jours "
                             f"(p = {fr(a63['p'], 3)}) et de {fr(w63['gain_pct'])} % face à l'EWMA (p = {fr(w63['p'], 3)}) : "
                             "ni l'un ni l'autre n'est significatif")
    # Concentration
    sans = h63["origines"] // 3
    assert sans == pv["couverture_des_bandes_95"]["bund_10_ans"][f"h{H}"]["trimestres_ou_mois_sans_chevauchement"]
    e["p8 trimestres"] = f"{h63['origines']} prévisions mensuelles ne font que {sans} trimestres sans chevauchement"
    conc = pv["concentration"][f"h{H}"]
    parts = conc["part_par_annee_de_fin_de_cible_pct"]
    trois = sorted(parts, key=parts.get, reverse=True)[:3]
    assert sorted(trois) == ["2015", "2020", "2022"] and trois[0] == "2022"
    e["p8 trois années"] = (f"Trois années, 2015, 2020 et 2022, font {fr(sum(parts[a] for a in trois))} % de l'écart de "
                            f"perte cumulé (figure, panneau du bas), dont {fr(parts['2022'])} % pour 2022 seule")
    # Les deux fragilités, dites dès le premier paragraphe (correction de l'audit)
    e["p8 fragile"] = (f"Le résultat est fragile sur deux points : la GARCH ne bat de façon significative ni une moyenne "
                       f"des {n_court} derniers jours (gain de {fr(a63['gain_pct'])} %, p = {fr(a63['p'], 3)}) ni l'EWMA "
                       f"({fr(w63['gain_pct'])} %, p = {fr(w63['p'], 3)}), qui captent chacune plus de la moitié du gain ; "
                       f"et trois années, 2015, 2020 et 2022, font {fr(sum(parts[a] for a in trois))} % de l'écart de "
                       "perte cumulé")
    # Hors plan, ajouté après l'audit : le test sans une seule des trois années, puis en erreur au carré
    audit = pv["hors_plan_apres_audit"]
    retire = audit["sans_une_annee_de_fin_de_cible"]
    assert sorted(retire) == sorted(trois) and audit["horizon_jours"] == H
    assert all(v["gain_pct"] > 0 and v["p"] > cst["seuil"] for v in retire.values())
    e["p8 audit années"] = (f"p = {fr(retire['2015']['p'], 3)} sans 2015, {fr(retire['2020']['p'], 3)} sans 2020, "
                            f"{fr(retire['2022']['p'], 3)} sans 2022. Le gain reste positif "
                            f"({fr(retire['2015']['gain_pct'])} %, {fr(retire['2020']['gain_pct'])} % et "
                            f"{fr(retire['2022']['gain_pct'])} %), mais aucune des trois versions ne passe le seuil de "
                            f"{seuil} %")
    eq = audit["erreur_au_carre_sur_la_variance"]
    assert eq["n"] == h63["origines"] and eq["retards"] == t63["retards"]
    e["p8 audit erreur au carré"] = (f"Avec l'erreur au carré sur la variance à la place de la QLIKE, le gain est de "
                                     f"{fr(eq['gain_pct'])} % (p = {fr(eq['p'], 3)})")
    e["p8 audit marque"] = "**Hors plan, ajouté après l'audit d'une session de relecture distincte, par IA.**"
    e["p8 sans épisodes"] = (f"Sans les cibles qui finissent en 2022 ou 2023, le gain tombe à "
                             f"{fr(conc['sans_2022_2023']['gain_pct'])} % ; sans celles de 2008 et 2009, il reste de "
                             f"{fr(conc['sans_2008_2009']['gain_pct'])} %")
    e["p8 années"] = (f"La GARCH fait mieux que la référence {conc['annees_ou_la_garch_fait_mieux']} années sur "
                      f"{conc['annees']}")
    sp = R["sous_periodes"]
    creux = sp["2015-2021"][f"h{H}"]
    e["p8 biais"] = (f"Son biais est de {signe(g['garch']['biais_vol_pb'], 1)} pb à un trimestre, et de "
                     f"{signe(creux['regles']['garch']['biais_vol_pb'], 1)} pb sur 2015-2021")
    # Le niveau
    niv = pv["niveau"]
    for h in cst["horizons_du_niveau_mois"]:
        n = niv[f"h{h}"]
        assert n["rapport"] > 1 and n["d_moyen"] < 0
        e[f"p8 niveau {h}"] = (f"| {h} mois | {n['previsions']} | {fr(n['rmse_marche_aleatoire_pb'])} pb | "
                               f"{fr(n['rmse_ar1_pb'])} pb | {fr(n['rapport'], 2)} | {fr(n['p'], 3)} |")
    e["p8 niveau lecture"] = "La marche aléatoire n'est pas battue, et l'AR(1) fait moins bien aux deux horizons"
    e["p8 niveau ordre"] = (f"L'erreur de la marche aléatoire à 3 mois, {fr(niv['h3']['rmse_marche_aleatoire_pb'])} pb, "
                            f"est du même ordre que la volatilité d'un trimestre ({fr(h63['vol_realisee_moyenne_pb'])} pb "
                            "en moyenne)")
    # Robustesse
    aaa = R["aaa_10_ans"]
    variantes = [("**calcul principal** : Bund à 10 ans", P, True), ("Bund à 2 ans", R["bund_2_ans"], False),
                 (f"10 ans de la courbe AAA de la BCE (origines depuis "
                  f"{mois_fr(pv['donnees']['aaa_10_ans']['premiere_origine'])})", aaa, False),
                 ("Bund à 10 ans, mêmes origines que la courbe AAA", R["bund_10_ans_aux_origines_de_la_courbe_aaa"], False),
                 ("GARCH en fenêtre glissante de 10 ans", R["fenetre_glissante"], False)]
    variantes += [(f"cibles qui finissent en {nom}", cellule, False) for nom, cellule in sp.items()]
    assert cst["fenetre_glissante_jours"] == 10 * n_long
    tests = []
    for lib, cellule, gras in variantes:
        a = cellule[f"h{H}"]["comparaisons"]["garch_contre_hv252"]
        b = cellule[f"h{H21}"]["comparaisons"]["garch_contre_hv252"]
        tests += [a, b]
        m = "**" if gras else ""
        e[f"p8 variante {lib}"] = (f"| {lib} | {cellule[f'h{H}']['origines']} | {m}{fr(a['gain_pct'])} %{m} | "
                                   f"{m}{fr(a['p'], 3)}{m} | {fr(b['gain_pct'])} % | {fr(b['p'], 3)} |")
    dc = pv["decompte"]
    positifs = sum(t["gain_pct"] > 0 for t in tests)
    significatifs = sum(t["d_moyen"] > 0 and t["p"] < cst["seuil"] for t in tests)
    pertes = sum(t["d_moyen"] < 0 and t["p"] < cst["seuil"] for t in tests)
    assert (len(tests), positifs, significatifs, pertes) == (
        dc["garch_contre_reference"]["comparaisons"], dc["garch_contre_reference"]["gain_positif"],
        dc["garch_contre_reference"]["gain_significatif"], dc["garch_contre_reference"]["perte_significative"])
    assert positifs == len(tests) and pertes == 0
    e["p8 décompte"] = (f"Les {len(tests)} comparaisons du tableau donnent un gain positif, mais elles portent sur les "
                        f"mêmes années et, pour la plupart, sur la même série ; {significatifs} passent le seuil de "
                        f"{seuil} %, aucune ne donne une perte significative")
    assert dc["tests_de_diebold_mariano_sur_la_volatilite"] == plan["nombre_de_tests_sur_la_volatilite"]
    e["p8 tests"] = f"Le plan compte {dc['tests_de_diebold_mariano_sur_la_volatilite']} tests sur la volatilité, dont un seul décide"
    deux = R["bund_2_ans"][f"h{H}"]
    assert deux["regles"]["garch"]["qlike"] > 2 * g["garch"]["qlike"] and deux["regles"]["hv252"]["qlike"] > 2 * g["hv252"]["qlike"]
    assert deux["comparaisons"]["garch_contre_hv252"]["p"] > cst["seuil"]
    e["p8 deux ans"] = (f"({fr(deux['regles']['garch']['qlike'], 3)} pour la GARCH, {fr(deux['regles']['hv252']['qlike'], 3)} "
                        "pour la référence, à un trimestre)")
    p_aaa = aaa[f"h{H}"]["comparaisons"]["garch_contre_hv252"]["p"]
    assert p_aaa > cst["seuil"]
    e["p8 aaa"] = f"À un trimestre, p = {fr(p_aaa, 4)} : juste au-dessus du seuil"
    memes = R["bund_10_ans_aux_origines_de_la_courbe_aaa"][f"h{H}"]["comparaisons"]["garch_contre_hv252"]
    assert 0 < aaa[f"h{H}"]["comparaisons"]["garch_contre_hv252"]["gain_pct"] < memes["gain_pct"]
    e["p8 aaa bund"] = (f"le Bund donne {fr(memes['gain_pct'])} % (p = {fr(memes['p'], 3)}) : sur une courbe estimée à "
                        "part, par la BCE, le gain est de même signe mais plus faible")
    gl = R["fenetre_glissante"][f"h{H}"]["regles"]
    assert 0.4 < gl["garch"]["biais_vol_pb"] / g["garch"]["biais_vol_pb"] < 0.6
    assert fr(gl["garch"]["qlike"], 3) == fr(g["hv63"]["qlike"], 3)
    e["p8 glissante"] = (f"({signe(gl['garch']['biais_vol_pb'], 1)} pb à un trimestre), mais sa perte monte à "
                         f"{fr(gl['garch']['qlike'], 3)}, au niveau de la volatilité sur {n_court} jours")
    for cellule in sp.values():
        t = cellule[f"h{H}"]["comparaisons"]["garch_contre_hv252"]
        assert t["gain_pct"] > 0 and t["p"] > cst["seuil"]
    e["p8 sous-périodes"] = "Le gain est positif dans les trois ; à un trimestre, il n'est significatif dans aucune"
    e["p8 creux"] = (f"tombe à {fr(creux['vol_realisee_moyenne_pb'])} pb par trimestre en moyenne, et la GARCH prévoit "
                     f"{fr(creux['regles']['garch']['biais_vol_pb'], 1)} pb de trop, contre "
                     f"{fr(creux['regles']['hv252']['biais_vol_pb'], 1)} pour la référence")
    lt, hv = (pv["garch_bund_10_ans"][k] for k in ("ecart_type_de_long_terme_pb_par_jour", "ecart_type_hv252_pb_par_jour"))
    e["p8 long terme"] = (f"volatilité de long terme de {fr(lt['fin_2014'], 1)} pb par jour à la fin de 2014 et de "
                          f"{fr(lt['fin_2021'], 1)} à la fin de 2021, quand la volatilité d'un an est de "
                          f"{fr(hv['fin_2014'], 1)} puis de {fr(hv['fin_2021'], 1)} pb par jour")
    e["p8 creux qlike"] = (f"({fr(creux['regles']['garch']['qlike'], 3)} contre {fr(creux['regles']['hv252']['qlike'], 3)})")
    # Couverture et queues
    e["p8 bande"] = f"(dernier taux ± {fr(cst['quantile_bande_95'], 2)} fois l'écart-type prévu)"
    couv = pv["couverture_des_bandes_95"]["bund_10_ans"]
    for h in [H21] + cst["horizons_des_bandes_jours"]:
        c = couv[f"h{h}"]
        e[f"p8 couverture {h}"] = (f"| {h} jours | {c['trimestres_ou_mois_sans_chevauchement']} | {fr(100 * c['garch'], 1)} % | "
                                   f"{fr(100 * c['hv252'], 1)} % |")
    # « dans le bruit » : chaque couverture est à moins de deux écarts-types binomiaux de 95 %, l'écart-type étant
    # compté sur les seules fenêtres sans chevauchement
    for c in couv.values():
        ecart_type = math.sqrt(0.95 * 0.05 / c["trimestres_ou_mois_sans_chevauchement"])
        assert abs(c["garch"] - 0.95) < 2 * ecart_type and abs(c["hv252"] - 0.95) < 2 * ecart_type
    independantes = [couv[f"h{h}"]["trimestres_ou_mois_sans_chevauchement"] for h in cst["horizons_des_bandes_jours"]]
    e["p8 couverture lecture"] = (f"les écarts sont dans le bruit de {min(independantes)} à {max(independantes)} fenêtres "
                                  f"indépendantes ({couv[f'h{H21}']['trimestres_ou_mois_sans_chevauchement']} à un mois)")
    zq = pv["queues_a_63_jours"]
    hausses, baisses = zq["garch"]["nombre_a_la_hausse"], zq["garch"]["nombre_a_la_baisse"]
    assert baisses == 1 and hausses > 1
    e["p8 queues"] = (f"dépassé {fr(cst['quantile_choc_99'], 3)} écarts-types prévus par la GARCH {hausses + baisses} fois "
                      f"sur {h63['origines']} ({hausses} hausses, {baisses} baisse), pour {fr(0.02 * h63['origines'])} "
                      f"attendues sous une loi normale, et {zq['hv252']['nombre_a_la_hausse'] + zq['hv252']['nombre_a_la_baisse']} "
                      "fois avec la référence")
    e["p8 plus grand z"] = (f"Mais le plus grand écart, {fr(zq['garch']['plus_grand_z_absolu'], 1)} écarts-types, vient de "
                            f"la prévision de fin {mois_fr(zq['garch']['origine_du_plus_grand_z'])}")
    e["p8 quantile"] = f"{sans} trimestres ne suffisent pas à estimer un quantile à 99 %"
    # La sortie de l'outil
    e["p8 outil date"] = (f"Au {jour_fr(o['date'])}, dernier jour retenu, le taux zéro-coupon est de "
                          f"{fr(o['niveau_pct'], 2)} %")
    e["p8 bandes en-tête"] = (f"| intervalle autour du taux du {jour_fr(o['date']).rsplit(' ', 1)[0]}, sans sens prévu |")
    for k, h in enumerate(cst["horizons_des_bandes_jours"], start=1):
        bg, br = b_garch[str(h)], b_ref[str(h)]
        e[f"p8 bande {h}"] = (f"| {k} trimestre{'s' if k > 1 else ''} ({h} jours) | ± {fr(bg['demi_largeur_pb'])} pb | de "
                              f"{fr(bg['bas_pct'], 2)} % à {fr(bg['haut_pct'], 2)} % | ± {fr(br['demi_largeur_pb'])} pb |")
        assert bg["demi_largeur_pb"] > br["demi_largeur_pb"]
    og = o["garch"]
    e["p8 mécanisme"] = (f"un écart-type de {fr(og['ecart_type_du_lendemain_pb'], 1)} pb pour le lendemain, puis revient "
                         f"vers son niveau de long terme, {fr(og['ecart_type_de_long_terme_pb_par_jour'], 1)} pb par jour "
                         f"(α + β = {fr(og['persistance'], 3)}, soit une demi-vie de {fr(og['demi_vie_jours'])} jours). La "
                         f"volatilité d'un an est de {fr(o['ecart_type_hv252_pb_par_jour'], 1)} pb par jour")
    e["p8 choc"] = (f"**Choc à 99 % sur un trimestre : {signe(choc['choc_retenu_pb'])} pb**, à la hausse, soit "
                    f"{fr(choc['quantile_normal'], 3)} fois l'écart-type prévu ({fr(choc['ecart_type_63_jours_pb'])} pb)")
    assert abs(choc["dv01_keur_par_pb"] - A["dv01_taux_keur_par_pb"]) < 1e-6
    e["p8 perte"] = (f"({fr(choc['dv01_keur_par_pb'])} k€ par pb pour {fr(ref['plan']['nominal_oat_meur'])} M€ d'OAT à "
                     f"{ref['plan']['maturite_ans']} ans), il coûte {fr(choc['perte_position_A_meur'], 1)} M€ au premier ordre")
    abe = st["chocs"]["C5_abe_2025_marche"]["aaa_10_ans_pb"]
    assert abe > choc["choc_retenu_pb"]
    e["p8 échelle"] = f"le choc de marché de l'ABE 2025 monte le Bund de {fr(abe)} pb (section 5)"
    assert choc["quantile_retenu"] == "normal"
    e["p8 quantiles"] = (f"celui de la loi normale ({fr(choc['quantile_normal'], 3)}) et le quantile empirique des "
                         f"variations standardisées du back test ({fr(choc['quantile_empirique_98_de_z_absolu'], 2)}). Le "
                         "quantile normal l'emporte")
    # Limites
    e["p8 limite cible"] = f"{H} carrés de variations quotidiennes mesurent la variance avec bruit"
    e["p8 limite épisodes"] = (f"{sans} trimestres sans chevauchement, et trois années qui font "
                               f"{fr(sum(parts[a] for a in trois))} % du gain : la valeur p de {fr(t63['p'], 3)} repose sur eux")
    e["p8 limite queues"] = f"que {sans} trimestres ne peuvent ni valider ni réfuter"
    fenetres = [couv[f"h{h}"]["trimestres_ou_mois_sans_chevauchement"] for h in cst["horizons_des_bandes_jours"][1:]]
    e["p8 limite bandes"] = f"mesurée que sur {min(fenetres)} à {max(fenetres)} fenêtres sans chevauchement"
    # La puce de la note et la phrase en anglais
    e["note prévision"] = (f"À un trimestre, une GARCH réduit l'erreur de prévision de la volatilité de {X} % face à la "
                           f"volatilité historique d'un an (perte QLIKE, p = {fr(t63['p'], 3)}), sans battre de façon "
                           f"significative une moyenne sur {n_court} jours ni l'EWMA ; trois années (2015, 2020, 2022) "
                           f"font {fr(sum(parts[a] for a in trois))} % du gain")
    e["note outil"] = (f"(± {fr(b_garch[str(H)]['demi_largeur_pb'])} pb à un trimestre, au {jour_fr(o['date'])}) et un choc "
                       f"à 99 % : {signe(choc['choc_retenu_pb'])} pb, soit {fr(choc['perte_position_A_meur'], 1)} M€ pour "
                       f"{fr(ref['plan']['nominal_oat_meur'])} M€ d'OAT à {ref['plan']['maturite_ans']} ans")
    e["note section 8"] = f"**Prévision** (section 8, ajoutée le {jour_fr(plan['date'])})"
    e["note mesure"] = ("La décomposition est une mesure, ni une prévision ni une recommandation de position ; la section "
                        "8, ajoutée ensuite, prévoit l'amplitude des variations du Bund, pas leur sens, et ne recommande "
                        "rien non plus")
    e["note second plan"] = ("La section 8 suit un second plan, commité seul avant toute estimation sur les données "
                             f"(`PLAN_PREVISION.md`, commit `{plan['commit']}`)")
    jour, mois_anglais = int(plan["date"][8:]), {11: "November"}[int(plan["date"][5:7])]
    e["anglais prévision 1"] = (f"Section 8, added on {jour} {mois_anglais} {plan['date'][:4]} under a second plan committed "
                                "before any estimation on the data")
    e["anglais prévision 2"] = (f"a GARCH(1,1) cuts the volatility forecast loss (QLIKE) by {X}% against one-year "
                                f"historical volatility (Diebold-Mariano p = {t63['p']:.3f}), but not significantly "
                                f"against a {n_court}-day average or an EWMA, with {fr(sum(parts[a] for a in trois))}% of "
                                "the gain from 2015, 2020 and 2022; the random walk is not beaten on the level")
    e["reproduire dates"] = (f"téléchargées le 22 novembre 2026, et le {jour_fr(pv['telechargement']).rsplit(' ', 1)[0]} "
                             "pour les séries de la Bundesbank depuis 1997")
    return e


def attendus_placebo(r: dict) -> dict[str, str]:
    """Les chiffres de la sous-section « Placebos » de la section 3 (hors plan, ajoutée le 28 novembre 2026) : tous
    viennent de resultats/placebo.json, sauf ceux qu'elle rappelle de decomposition.json."""
    pl, dec = r["placebo"], r["decomposition"]
    p, var, sm, e5d = dec["modele_principal"], dec["variantes"], dec["sans_modele"], dec["episodes"]["E5"]
    pays, avec = pl["par_pays_contre_les_sept_autres_pairs"], pl["par_pays_avec_la_france_parmi_les_pairs"]
    h29, h2 = pl["par_dates_france"]["h29"], pl["par_dates_france"]["h2"]
    et, et5 = pl["etalonnage"]["principal"], pl["etalonnage"]["E5"]
    assert pl["base"] == p["base"] and pl["fin"] == p["mois"] and h29["horizon_mois"] == p["h_mois"]
    assert h29["derniere_fin"] == p["base"]                    # les fenêtres placebo finissent avant la période
    assert abs(et["part_propre_pb"] - p["part_propre_pb"]) < 1e-3
    assert abs(et5["part_propre_pb"] - e5d["part_propre_pb"]) < 1e-3
    e = {}
    e["placebo titre"] = f"Placebos : d'autres pays, d'autres dates (hors plan, ajouté le {jour_fr(pl['date_ajout'])})"
    e["placebo hors plan"] = ("**Cette sous-section est hors du plan d'origine et a été ajoutée après coup**, une fois "
                              "tous les résultats connus")
    e["placebo méthode"] = (f"(b sur les {pl['n_mois_estimation']} variations qui finissent au mois de base, intervalle "
                            "de Newey-West)")
    noms = {"IT": "Italie", "ES": "Espagne", "NL": "Pays-Bas", "BE": "Belgique", "AT": "Autriche", "PT": "Portugal",
            "FI": "Finlande", "IE": "Irlande"}
    nominaux = [c for c, v in pays.items() if v["exclut_zero"]]
    assert nominaux == ["BE"] and len(pays) == 8
    e["placebo sept sur huit"] = "Sept pairs sur huit n'ont pas de part propre dont l'intervalle nominal exclut 0"
    for c, v in pays.items():
        x, i = signe(v["part_propre_pb"]), ic(v["ic95_pb"])
        if v["exclut_zero"]:
            x, i = f"**{x}**", f"**{i}**"
        e[f"placebo {c}"] = f"| {noms[c]} | {fr(v['b'], 2)} | {x} | {i} |"
    e["placebo France"] = (f"| France (modèle principal, contre les huit pairs) | "
                           f"{fr(p['estimation']['coefficients']['P'], 2)} | **{signe(p['part_propre_pb'])}** | "
                           f"**{ic(p['ic95_pb'])}** |")
    be = pays["BE"]
    assert 0.4 < be["part_propre_pb"] / p["part_propre_pb"] < 0.6   # « moitié moins grande »
    assert not be["exclut_zero_apres_elargissement"]
    e["placebo Belgique"] = (f"moitié moins grande que celle de la France** : {signe(be['part_propre_pb'])} pb "
                             f"{ic(be['ic95_pb'])}")
    e["placebo Belgique élargie"] = (f"l'écart-type des z de son propre placebo par dates "
                                     f"({fr(be['ecart_type_z_placebo_par_dates'], 2)}), son intervalle devient "
                                     f"{ic(be['ic95_elargi_pb'])} et contient 0")
    e["placebo sans modèle"] = (f"contre la Belgique, l'écart de la France ne monte que de "
                                f"{fr(sm['BE']['variation_pb'])} pb")
    e["placebo avec la France"] = (f"la Belgique tombe à {signe(avec['BE']['part_propre_pb'])} pb "
                                   f"{ic(avec['BE']['ic95_pb'])} et l'Autriche passe à "
                                   f"{signe(avec['AT']['part_propre_pb'])} pb {ic(avec['AT']['ic95_pb'])}")
    e["placebo dates"] = (f"La France, à chaque mois de base de {mois_fr(h29['premiere_base'])} à "
                          f"{mois_fr(h29['derniere_base'])} ({h29['bases']} bases), avec le b des "
                          f"{pl['n_mois_estimation']} variations qui finissent à la base et une part propre cumulée "
                          f"sur {h29['horizon_mois']} mois")
    e["placebo fin"] = f"finissent au plus tard en {mois_fr(h29['derniere_fin'])}, avant la période étudiée"
    assert h29["max_abs_propre_pb"] < p["part_propre_pb"] and et["bases_placebo_au_moins_aussi_grandes"] == 0
    e["placebo 100"] = f"Aucune base n'atteint {fr(p['part_propre_pb'])} pb"
    e["placebo plage"] = (f"La part propre va de {signe(h29['min_propre_pb'])} pb (base {mois_fr(h29['base_min'])}) à "
                          f"{signe(h29['max_propre_pb'])} pb (base {mois_fr(h29['base_max'])}) ; en valeur absolue, "
                          f"sa médiane est de {fr(h29['mediane_abs_propre_pb'])} pb et son 95e centile de "
                          f"{fr(h29['centile_95_abs_propre_pb'])} pb")
    assert et["z"] > h29["max_abs_z"]
    assert h29["z_a_la_base_max_abs_z"] < 0 < h29["max_z_positif"]
    e["placebo z marge"] = (f"le z de 2024-2026 vaut {fr(et['z'], 2)}, le plus grand z placebo "
                            f"{fr(h29['max_abs_z'], 2)} en valeur absolue (base {mois_fr(h29['base_max_abs_z'])}, un z "
                            f"négatif) ; du côté positif, le plus grand ne vaut que {fr(h29['max_z_positif'], 2)} (base "
                            f"{mois_fr(h29['base_max_z_positif'])})")
    assert h2["propre_a_la_base_max_abs_pb"] > 0 and h2["max_abs_propre_pb"] < e5d["part_propre_pb"]
    e["placebo deux mois"] = (f"deux\n  mois ({h2['bases']} bases), la plus grande part propre est de "
                              f"{fr(h2['max_abs_propre_pb'])} pb (base {mois_fr(h2['base_max_abs'])}), contre "
                              f"{fr(e5d['part_propre_pb'])} pb à l'automne 2026")
    e["placebo nominal"] = "À 95 %, il l'exclurait dans 5 % des bases"
    rejets = h29["propre_aux_bases_ou_l_intervalle_exclut_zero_pb"]
    episode = {b: x for b, x in rejets.items() if "2007" <= b[:4] <= "2010"}
    assert len(rejets) == h29["exclut_zero"] and len(episode) >= len(rejets) - 1    # « presque tous »
    assert all(x < 0 for x in episode.values())                                     # « toutes négatives »
    e["placebo rejets"] = (f"il l'exclut dans {fr(100 * h29['part_exclut_zero'])} % des cas à {h29['horizon_mois']} "
                           f"mois ({h29['exclut_zero']} bases, dont {len(episode)} prises de {mois_fr(min(episode))} à "
                           f"{mois_fr(max(episode))}, toutes négatives")
    e["placebo rejets deux mois"] = f"et dans {fr(100 * h2['part_exclut_zero'])} % à deux mois"
    e["placebo z"] = (f"devrait avoir un écart-type de 1 sur l'ensemble des bases ; il a "
                      f"{fr(h29['ecart_type_z'], 2)} à {h29['horizon_mois']} mois et {fr(h2['ecart_type_z'], 2)} à "
                      "deux mois")
    parts = sorted(100 * v["part_exclut_zero"] for v in pl["par_dates_pairs_h29"].values())
    e["placebo pairs"] = f"voit son intervalle exclure 0 dans {fr(parts[0])} % à {fr(parts[-1])} % des bases"
    assert et["ic95_etalonne_pb"][0] > 0 and et5["ic95_etalonne_pb"][0] > 0 and et["ic95_centile_empirique_pb"][0] > 0
    assert all(abs(a - b) < 1e-3 for a, b in zip(et5["ic95_nominal_pb"], e5d["ic95_pb"]))
    e["placebo élargi"] = (f"Élargi de l'écart-type des z du placebo ({fr(et['ecart_type_z_placebo'], 2)}), "
                           f"l'intervalle de tête devient {ic(et['ic95_etalonne_pb'])}**, proche de ceux des fenêtres "
                           f"longues ({ic(var['fenetre_120']['ic95_pb'])} et {ic(var['depuis_1999']['ic95_pb'])}), et "
                           f"celui de l'automne 2026 {ic(et5['ic95_etalonne_pb'])} au lieu de "
                           f"{ic(et5['ic95_nominal_pb'])}")
    assert h29["part_exclut_zero_apres_elargissement"] > 0.05
    e["placebo encore étroit"] = (f"même élargi, l'intervalle exclut 0 dans "
                                  f"{fr(100 * h29['part_exclut_zero_apres_elargissement'])} % des bases placebo. Avec "
                                  f"le 95e centile des |z| du placebo, {fr(h29['centile_95_abs_z'], 2)} au lieu de "
                                  f"1,96, l'intervalle de tête serait {ic(et['ic95_centile_empirique_pb'])}. 0 reste "
                                  "exclu dans tous les cas")
    e["placebo chevauchement"] = (f"les {h29['bases']} fenêtres de {h29['horizon_mois']} mois se chevauchent, la "
                                  f"période n'en contient que {h29['fenetres_sans_chevauchement']} sans chevauchement")
    return e

# Formulations corrigées après les audits : elles ne doivent pas revenir. « Indépendant » désignait des agents
# d'IA (décision du 28 novembre 2026), comme l'ancienne phrase sur leur rôle.
INTERDITES = ["audit indépendant", "relecture indépendante", "independent audit", "independent review",
              "independent pass", "sous la direction de Guillaume Beaudouin",
              "under the direction of Guillaume Beaudouin", "dépasse tout ce que", "Étalonné sur ce placebo",
              "avant tout calcul", "before any computation", "CC BY", "d'indiquer les modifications", "bien connu",
              "sont propres à la France", "are specific to France"]


def normaliser(texte: str) -> str:
    """Sans les marques de citation en début de ligne, et avec un seul espace entre les mots : la vérification ne
    dépend pas de l'endroit où les lignes sont coupées."""
    texte = re.sub(r"^> ?", "", texte, flags=re.M)
    return re.sub(r"\s+", " ", texte)


def charger() -> dict:
    noms = ["decomposition", "stress", "abe_2025", "controles", "prevision", "references", "placebo"]
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
