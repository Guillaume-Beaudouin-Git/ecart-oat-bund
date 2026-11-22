"""Lecture des formats des sources, sur de petits fichiers construits à la main."""
import json

import openpyxl
import pandas as pd
import pytest

from ecart_oat_bund import donnees
from ecart_oat_bund.donnees import (date_espagnole, fin_de_mois, fin_quotidienne, lire_cers_chocs_marche,
                                    lire_cers_taux_longs, lire_csv_bce, lire_json_stat, lire_taux_longs, url_bce,
                                    url_eurostat)

ENTETE_BCE = "KEY,FREQ,REF_AREA,CURRENCY,PROVIDER_FM,INSTRUMENT_FM,PROVIDER_FM_ID,DATA_TYPE_FM,TIME_PERIOD,OBS_VALUE\n"


def _ligne(serie, date, valeur):
    return f"YC.B.U2.EUR.4F.G_N_A.SV_C_YM.{serie},B,U2,EUR,4F,G_N_A,SV_C_YM,{serie},{date},{valeur}\n"


def test_lecture_d_un_fichier_de_la_bce(tmp_path):
    texte = ENTETE_BCE + "".join([_ligne("SR_10Y", "2024-05-30", 2.5), _ligne("SR_10Y", "2024-05-31", 2.6),
                                  _ligne("SR_3M", "2024-05-31", 3.6), _ligne("SR_3M", "2024-05-30", 3.7)])
    chemin = tmp_path / "bce.csv"
    chemin.write_text(texte)
    df = lire_csv_bce(chemin)
    assert list(df.columns) == ["SR_10Y", "SR_3M"]
    assert df.index.tolist() == [pd.Timestamp("2024-05-30"), pd.Timestamp("2024-05-31")]
    assert df.loc["2024-05-31", "SR_3M"] == 3.6


def test_fin_de_mois_prend_le_dernier_jour_publie():
    # le 31 août 2024 est un samedi : la fin du mois est le vendredi 30 ; mars 2024 finit le jeudi 28 (Pâques)
    jours = pd.to_datetime(["2024-03-27", "2024-03-28", "2024-04-29", "2024-04-30", "2024-05-31",
                            "2024-06-28", "2024-07-31", "2024-08-29", "2024-08-30"])
    df = pd.DataFrame({"SR_10Y": range(len(jours))}, index=jours)
    m = fin_de_mois(df, dernier_mois="2024-08")
    assert m.index.tolist() == pd.to_datetime(["2024-03-28", "2024-04-30", "2024-05-31", "2024-06-28",
                                               "2024-07-31", "2024-08-30"]).tolist()
    assert m["SR_10Y"].tolist() == [1, 3, 4, 5, 6, 8]


def test_adresses():
    assert url_bce("YC/B.U2.EUR.4F.G_N_A.SV_C_YM", ["SR_3M", "SR_10Y"], "2004-09-06", "2026-10-31") == (
        "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M+SR_10Y"
        "?format=csvdata&detail=dataonly&startPeriod=2004-09-06&endPeriod=2026-10-31")
    assert url_eurostat("irt_lt_mcby_m", {"geo": ["FR", "DE"]}) == (
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/irt_lt_mcby_m"
        "?format=JSON&lang=EN&geo=FR&geo=DE")
    assert fin_quotidienne("2026-10") == "2026-10-31"
    assert fin_quotidienne("2024-02") == "2024-02-29"


def _json_stat(pays, mois, valeurs, absentes=()):
    """Un petit fichier JSON-stat au format d'Eurostat : dimensions freq, int_rt, geo, time ; `value` creux."""
    valeur, pos = {}, 0
    for p in pays:
        for m in mois:
            if (p, m) not in absentes:
                valeur[str(pos)] = valeurs[(p, m)]
            pos += 1
    return {"id": ["freq", "int_rt", "geo", "time"], "size": [1, 1, len(pays), len(mois)],
            "dimension": {"freq": {"category": {"index": {"M": 0}}},
                          "int_rt": {"category": {"index": {"MCBY": 0}}},
                          "geo": {"category": {"index": {p: i for i, p in enumerate(pays)}}},
                          "time": {"category": {"index": {m: i for i, m in enumerate(mois)}}}},
            "value": valeur}


def test_lecture_json_stat_et_taux_longs(tmp_path, monkeypatch):
    pays, mois = ["DE", "FR"], ["1999-01", "1999-02", "1999-03"]
    valeurs = {(p, m): (1.0 if p == "DE" else 1.5) + 0.1 * i for p in pays for i, m in enumerate(mois)}
    chemin = tmp_path / donnees.FICHIERS["taux_longs"]
    chemin.write_text(json.dumps(_json_stat(pays, mois, valeurs)))
    longue = lire_json_stat(chemin)
    assert len(longue) == 6 and list(longue.columns) == ["freq", "int_rt", "geo", "time", "valeur"]
    # l'ordre des valeurs : la dernière dimension (time) varie le plus vite
    assert longue.iloc[1].to_dict() == {"freq": "M", "int_rt": "MCBY", "geo": "DE", "time": "1999-02", "valeur": 1.1}
    taux = lire_taux_longs(tmp_path, pays=("FR", "DE"), premier_mois="1999-01", dernier_mois="1999-03")
    assert list(taux.columns) == ["FR", "DE"]
    assert taux.loc["1999-03", "FR"] == pytest.approx(1.7)
    # un mois manquant est une erreur, pas un trou à combler
    chemin.write_text(json.dumps(_json_stat(pays, mois, valeurs, absentes={("FR", "1999-02")})))
    with pytest.raises(ValueError):
        lire_taux_longs(tmp_path, pays=("FR", "DE"), premier_mois="1999-01", dernier_mois="1999-03")


def test_dates_du_banco_de_espana():
    assert date_espagnole('"02 ENE 1979"') == pd.Timestamp("1979-01-02")
    assert date_espagnole("31 DIC 2025") == pd.Timestamp("2025-12-31")
    assert date_espagnole("18 AGO 2026") == pd.Timestamp("2026-08-18")


def _classeurs_cers(dossier):
    """Deux petits classeurs à la mise en page des fichiers du CERS (mêmes feuilles, mêmes lignes d'en-tête)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Long-term rates"
    ws.cell(4, 4, "Starting point rates (%) – average")
    ws.cell(4, 5, "Starting point rates (%) – latest")
    ws.cell(4, 6, "Baseline rates (%)")
    ws.cell(4, 9, "Adverse rates (%)")
    for col, annee in zip(range(4, 12), [2024, 2024, 2025, 2026, 2027, 2025, 2026, 2027]):
        ws.cell(5, col, annee)
    for r, (nom, code, base) in enumerate([("Germany", "DE", 2.0), ("France", "FR", 3.0)], start=6):
        ws.cell(r, 2, nom)
        ws.cell(r, 3, code)
        for col in range(4, 12):
            ws.cell(r, col, base + 0.1 * (col - 4))
    wb.save(dossier / donnees.FICHIERS["cers_macro"])
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Credit spreads - Sovereign"
    for col, m in zip(range(3, 10), ["Country", "Reference swap rate", "3M", "1Y", "5Y", "10Y", "15Y"]):
        ws.cell(5, col, m)
    for r, (nom, choc) in enumerate([("France", 100.0), ("Germany", 30.0)], start=6):
        ws.cell(r, 3, nom)
        ws.cell(r, 4, "EUR")
        for col in range(5, 10):
            ws.cell(r, col, choc + col)
    ws = wb.create_sheet("IR")
    for col, m in zip(range(3, 9), ["Country", "Description", "3M", "1Y", "5Y", "10Y"]):
        ws.cell(5, col, m)
    ws.cell(6, 3, "Euro Area")
    ws.cell(6, 4, "Interest rate SWAP on the EUR (Euro)")
    for col in range(5, 9):
        ws.cell(6, col, 50.0 + col)
    wb.save(dossier / donnees.FICHIERS["cers_marche"])


def test_lecture_des_scenarios_du_cers(tmp_path):
    _classeurs_cers(tmp_path)
    taux = lire_cers_taux_longs(tmp_path)
    assert list(taux.index) == ["FR", "DE"]
    assert list(taux.columns) == ["depart_moyenne_2024", "depart_decembre_2024", "central_2025", "central_2026",
                                  "central_2027", "adverse_2025", "adverse_2026", "adverse_2027"]
    assert taux.loc["FR", "adverse_2025"] == pytest.approx(3.5)   # colonne I = 9 : 3,0 + 0,1 × 5
    chocs = lire_cers_chocs_marche(tmp_path)
    assert chocs["ecarts_souverains_contre_swap_pb"]["France"]["10Y"] == pytest.approx(108.0)  # colonne H = 8
    assert chocs["ecarts_souverains_contre_swap_pb"]["Germany"]["swap_de_reference"] == "EUR"
    assert chocs["swap_eur_pb"]["10Y"] == pytest.approx(58.0)
