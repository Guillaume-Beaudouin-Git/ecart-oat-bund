"""Téléchargement et lecture des données du projet. Toutes sont ouvertes, sans compte ; aucune n'est versionnée.

- Eurostat, `irt_lt_mcby_m` : les taux longs du critère de convergence (rendements sur le marché secondaire
  d'obligations d'État de durée résiduelle proche de 10 ans), en moyenne mensuelle, par pays. Ce sont les séries
  que la BCE collecte auprès des banques centrales nationales.
- Eurostat, `nama_10_gdp` : le PIB de 2019 à prix courants, qui pondère les pays pairs.
- BCE, jeu YC : la courbe zéro-coupon des obligations d'État de la zone euro notées AAA (sept taux et six
  paramètres de Svensson, chaque jour ouvré), qui sert de courbe sans risque dans le stress.
- BCE, jeu CISS : l'indicateur composite de tension souveraine (SovCISS) de la France, quotidien, qui date les
  épisodes.
- CERS (ESRB) : les scénarios macrofinancier et de marché du test de résistance de l'ABE de 2025.
- En contrôle seulement : le 10 ans zéro-coupon allemand de la Bundesbank et le 10 ans espagnol du Banco de
  España, quotidiens.

Les TEC de la Banque de France (indices Euronext, redistribution interdite) ne sont ni téléchargés ni utilisés.

La fenêtre est figée : de janvier 1999 au dernier mois complet disponible au téléchargement (octobre 2026). Pour
la prolonger, `scripts/tout.py --dernier-mois AAAA-MM` fixe la variable d'environnement
ECART_OAT_BUND_DERNIER_MOIS. Les fichiers bruts vont dans `data/`, non versionné.
"""
from __future__ import annotations

import itertools
import json
import os
import ssl
import time
import urllib.request
from pathlib import Path

import certifi
import numpy as np
import pandas as pd

DOSSIER = Path("data")

FRANCE, ALLEMAGNE = "FR", "DE"
PAIRS = ("IT", "ES", "NL", "BE", "AT", "PT", "FI", "IE")
COEUR = ("NL", "BE", "AT", "FI")
PERIPHERIE = ("IT", "ES", "PT", "IE")
PAYS = (FRANCE, ALLEMAGNE) + PAIRS
GRECE = "EL"                           # téléchargée pour documenter son exclusion, jamais dans une part propre
NOMS = {"FR": "France", "DE": "Allemagne", "IT": "Italie", "ES": "Espagne", "NL": "Pays-Bas", "BE": "Belgique",
        "AT": "Autriche", "PT": "Portugal", "FI": "Finlande", "IE": "Irlande", "EL": "Grèce"}

PREMIER_MOIS = "1999-01"
DERNIER_MOIS = os.environ.get("ECART_OAT_BUND_DERNIER_MOIS", "2026-10")
DEBUT_COURBE = "2004-09-06"            # première courbe AAA publiée par la BCE
DEBUT_SOVCISS = "2000-01-01"


def fin_quotidienne(dernier_mois: str = DERNIER_MOIS) -> str:
    """Dernier jour calendaire du dernier mois retenu, borne des séries quotidiennes."""
    return pd.Period(dernier_mois, "M").end_time.strftime("%Y-%m-%d")


# --- Adresses ----------------------------------------------------------------------------------------------------

EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
BCE = "https://data-api.ecb.europa.eu/service/data"
CERS = "https://www.esrb.europa.eu/mppa/stress/shared/pdf"
BUNDESBANK = "https://api.statistiken.bundesbank.de/rest/data"
BANCO_DE_ESPANA = "https://www.bde.es/webbe/es/estadisticas/compartido/datos/csv/ead002.csv"

CLE_COURBE = "YC/B.U2.EUR.4F.G_N_A.SV_C_YM"
MATURITES = {"SR_3M": 0.25, "SR_1Y": 1.0, "SR_2Y": 2.0, "SR_5Y": 5.0, "SR_10Y": 10.0, "SR_20Y": 20.0,
             "SR_30Y": 30.0}
PARAMETRES = ("BETA0", "BETA1", "BETA2", "BETA3", "TAU1", "TAU2")
CLE_SOVCISS = "CISS/D.FR.Z0Z.4F.EC.SOV_CIN.IDX"
FICHIER_CERS_MACRO = "esrb.stress_test250120.macrofinancialscenario~1071d75da3.en.xlsx"
FICHIER_CERS_MARCHE = "esrb.stress_test250120.Marketriskscenario~c70aade892.en.xlsx"
CLE_BUND = "BBSIS/D.I.ZST.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A"
SERIE_ESPAGNE = "D_G0B1F0ZP"           # 10 ans, marché secondaire, obligations d'État non démembrées

FICHIERS = {
    "taux_longs": "eurostat_irt_lt_mcby_m.json",
    "pib": "eurostat_nama_10_gdp_2019.json",
    "courbe": "bce_courbe_aaa.csv",
    "sovciss": "bce_sovciss_france.csv",
    "cers_macro": "cers_scenario_macrofinancier_2025.xlsx",
    "cers_marche": "cers_scenario_marche_2025.xlsx",
    "bund": "bundesbank_bund_10_ans.csv",
    "espagne": "banco_de_espana_taux_quotidiens.csv",
}


def url_eurostat(jeu: str, filtres: dict[str, list[str] | str]) -> str:
    """Adresse de l'API d'Eurostat (statistiques 1.0, JSON-stat), un paramètre par valeur de filtre."""
    morceaux = ["format=JSON", "lang=EN"]
    for cle, valeurs in filtres.items():
        for v in [valeurs] if isinstance(valeurs, str) else valeurs:
            morceaux.append(f"{cle}={v}")
    return f"{EUROSTAT}/{jeu}?{'&'.join(morceaux)}"


def url_bce(cle: str, series: list[str] | tuple[str, ...] | None, debut: str, fin: str) -> str:
    """Adresse de l'API de la BCE au format CSV, sans métadonnées ; `series` ajoute le dernier élément de la clé."""
    complete = cle if not series else f"{cle}.{'+'.join(series)}"
    return f"{BCE}/{complete}?format=csvdata&detail=dataonly&startPeriod={debut}&endPeriod={fin}"


def url_bundesbank(cle: str, debut: str, fin: str) -> str:
    return f"{BUNDESBANK}/{cle}?format=csv&lang=en&startPeriod={debut}&endPeriod={fin}"


def _telecharger(url: str, chemin: Path, essais: int = 3, pause_s: float = 5.0) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    # L'API de la BCE remonte à une racine Sectigo récente, absente du magasin de certificats du Python d'uv sur
    # macOS : on vérifie les connexions avec le magasin de `certifi`.
    contexte = ssl.create_default_context(cafile=certifi.where())
    derniere_erreur: Exception | None = None
    for _ in range(essais):
        try:
            requete = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research script)"})
            with urllib.request.urlopen(requete, timeout=180, context=contexte) as reponse:
                chemin.write_bytes(reponse.read())
            return
        except Exception as erreur:  # réseau ou service momentanément indisponible
            derniere_erreur = erreur
            time.sleep(pause_s)
    raise RuntimeError(f"téléchargement impossible : {url}") from derniere_erreur


def telecharger_tout(dossier: Path = DOSSIER, dernier_mois: str = DERNIER_MOIS) -> None:
    """Toutes les sources, en neuf requêtes ; quelques secondes."""
    fin = fin_quotidienne(dernier_mois)
    _telecharger(url_eurostat("irt_lt_mcby_m", {"geo": list(PAYS) + [GRECE]}), dossier / FICHIERS["taux_longs"])
    _telecharger(url_eurostat("nama_10_gdp", {"unit": "CP_MEUR", "na_item": "B1GQ", "time": "2019",
                                              "geo": list(PAYS)}), dossier / FICHIERS["pib"])
    _telecharger(url_bce(CLE_COURBE, list(MATURITES) + list(PARAMETRES), DEBUT_COURBE, fin),
                 dossier / FICHIERS["courbe"])
    _telecharger(url_bce(CLE_SOVCISS, None, DEBUT_SOVCISS, fin), dossier / FICHIERS["sovciss"])
    _telecharger(f"{CERS}/{FICHIER_CERS_MACRO}", dossier / FICHIERS["cers_macro"])
    _telecharger(f"{CERS}/{FICHIER_CERS_MARCHE}", dossier / FICHIERS["cers_marche"])
    _telecharger(url_bundesbank(CLE_BUND, "1999-01-01", fin), dossier / FICHIERS["bund"])
    _telecharger(BANCO_DE_ESPANA, dossier / FICHIERS["espagne"])


def _exiger(chemin: Path) -> Path:
    if not chemin.exists():
        raise FileNotFoundError(f"{chemin} absent : lancer d'abord `uv run python scripts/telecharger.py`")
    return chemin


# --- Eurostat ----------------------------------------------------------------------------------------------------

def lire_json_stat(chemin: Path) -> pd.DataFrame:
    """Un fichier JSON-stat 2.0 d'Eurostat en table longue : une colonne par dimension, plus `valeur`.

    Les valeurs sont rangées en ordre lexicographique des dimensions (la dernière varie le plus vite) ; une
    position absente de `value` est une valeur manquante."""
    d = json.loads(Path(chemin).read_text(encoding="utf-8"))
    ids = d["id"]
    codes = []
    for k in ids:
        index = d["dimension"][k]["category"]["index"]
        codes.append(sorted(index, key=index.get))
    valeurs = d["value"]
    if isinstance(valeurs, list):
        valeurs = {str(i): v for i, v in enumerate(valeurs) if v is not None}
    lignes = [(*coords, valeurs.get(str(pos), np.nan)) for pos, coords in enumerate(itertools.product(*codes))]
    return pd.DataFrame(lignes, columns=[*ids, "valeur"])


def lire_taux_longs(dossier: Path = DOSSIER, pays=PAYS, premier_mois: str = PREMIER_MOIS,
                    dernier_mois: str = DERNIER_MOIS, complet: bool = True) -> pd.DataFrame:
    """Taux longs en moyenne mensuelle (%), une colonne par pays, index mensuel (Period).

    Avec `complet` (par défaut), une valeur manquante est une erreur ; sans, elle reste NaN (la Grèce, juillet
    2015)."""
    df = lire_json_stat(_exiger(dossier / FICHIERS["taux_longs"]))
    df = df[df["int_rt"] == "MCBY"]
    large = df.pivot(index="time", columns="geo", values="valeur")
    large.index = pd.PeriodIndex(large.index, freq="M")
    large = large.sort_index().loc[premier_mois:dernier_mois, list(pays)]
    attendus = pd.period_range(premier_mois, dernier_mois, freq="M")
    if not large.index.equals(attendus):
        raise ValueError("des mois manquent dans les taux longs d'Eurostat")
    if complet and large.isna().any().any():
        manquants = large.columns[large.isna().any()].tolist()
        raise ValueError(f"valeurs manquantes dans les taux longs : {manquants}")
    large.columns.name = None
    return large.astype(float)


def lire_pib_2019(dossier: Path = DOSSIER, pays=PAYS) -> pd.Series:
    """PIB de 2019 à prix courants, en millions d'euros (Eurostat, nama_10_gdp, B1GQ, CP_MEUR)."""
    df = lire_json_stat(_exiger(dossier / FICHIERS["pib"]))
    df = df[(df["unit"] == "CP_MEUR") & (df["na_item"] == "B1GQ") & (df["time"] == "2019")]
    serie = df.set_index("geo")["valeur"].reindex(list(pays)).astype(float)
    if serie.isna().any():
        raise ValueError(f"PIB de 2019 absent pour {serie.index[serie.isna()].tolist()}")
    return serie.rename("pib_2019_meur")


# --- BCE ---------------------------------------------------------------------------------------------------------

def lire_csv_bce(chemin: Path) -> pd.DataFrame:
    """Un fichier CSV de l'API de la BCE (une ligne par série et par date) en tableau large : une colonne par série.

    Le nom de colonne est le dernier élément de la clé (« SR_10Y », « BETA0 », « IDX »)."""
    brut = pd.read_csv(chemin, usecols=["KEY", "TIME_PERIOD", "OBS_VALUE"])
    brut["serie"] = brut["KEY"].str.split(".").str[-1]
    brut["date"] = pd.to_datetime(brut["TIME_PERIOD"])
    large = brut.pivot(index="date", columns="serie", values="OBS_VALUE").sort_index()
    large.columns.name = None
    return large


def lire_courbe(dossier: Path = DOSSIER, debut: str = DEBUT_COURBE, fin: str | None = None) -> pd.DataFrame:
    """Courbe AAA quotidienne : les 7 taux spot puis les 6 paramètres de Svensson, du `debut` à la `fin` inclus."""
    fin = fin or fin_quotidienne()
    df = lire_csv_bce(_exiger(dossier / FICHIERS["courbe"]))
    colonnes = list(MATURITES) + list(PARAMETRES)
    manquantes = [c for c in colonnes if c not in df.columns]
    if manquantes:
        raise ValueError(f"séries absentes du fichier : {manquantes}")
    df = df.loc[debut:fin, colonnes]
    if df.isna().any().any():
        raise ValueError("valeurs manquantes dans la courbe : un jour publié sans toutes ses séries")
    return df


def fin_de_mois(quotidien: pd.DataFrame, dernier_mois: str = DERNIER_MOIS) -> pd.DataFrame:
    """La dernière observation de chaque mois calendaire, jusqu'à `dernier_mois` inclus.

    L'index garde la date réelle de l'observation (le dernier jour ouvré du mois). Un mois sans aucune
    observation interromprait la suite des mois : c'est une erreur, pas un trou à combler."""
    df = quotidien[quotidien.index.to_period("M") <= pd.Period(dernier_mois, "M")]
    mensuel = df.groupby(df.index.to_period("M")).tail(1)
    mois = mensuel.index.to_period("M")
    attendus = pd.period_range(mois.min(), mois.max(), freq="M")
    if len(mois) != len(attendus):
        raise ValueError("un mois sans observation dans la série")
    return mensuel


def lire_sovciss(dossier: Path = DOSSIER, fin: str | None = None) -> pd.Series:
    """Indicateur composite de tension souveraine de la France (SovCISS, BCE), chaque jour ouvré."""
    fin = fin or fin_quotidienne()
    return lire_csv_bce(_exiger(dossier / FICHIERS["sovciss"]))["IDX"].loc[:fin].rename("sovciss_fr")


# --- CERS : scénarios du test de résistance de l'ABE de 2025 -------------------------------------------------------

def _feuille(chemin: Path, nom: str):
    import openpyxl
    classeur = openpyxl.load_workbook(_exiger(chemin), read_only=False, data_only=True)
    return classeur[nom]


def lire_cers_taux_longs(dossier: Path = DOSSIER, pays=(FRANCE, ALLEMAGNE)) -> pd.DataFrame:
    """Feuille « Long-term rates » du scénario macrofinancier : taux longs en moyenne annuelle (%), par pays.

    Colonnes : départ (moyenne 2024 et moyenne de décembre 2024), scénario central et scénario adverse 2025-2027.
    Les colonnes sont repérées par leurs en-têtes (lignes 4 et 5 de la feuille), les pays par leur code."""
    ws = _feuille(dossier / FICHIERS["cers_macro"], "Long-term rates")
    entetes, annees = {}, {}
    courant = None
    for col in range(1, ws.max_column + 1):
        titre, annee = ws.cell(4, col).value, ws.cell(5, col).value
        if isinstance(titre, str):
            courant = titre
        if courant and isinstance(annee, int):
            entetes[col], annees[col] = courant, annee
    noms = {}
    for col, titre in entetes.items():
        if titre.startswith("Starting point rates") and "average" in titre:
            noms[col] = f"depart_moyenne_{annees[col]}"
        elif titre.startswith("Starting point rates") and "latest" in titre:
            noms[col] = f"depart_decembre_{annees[col]}"
        elif titre.startswith("Baseline"):
            noms[col] = f"central_{annees[col]}"
        elif titre.startswith("Adverse"):
            noms[col] = f"adverse_{annees[col]}"
    lignes = {}
    for r in range(6, ws.max_row + 1):
        code = ws.cell(r, 3).value
        if code in pays:
            lignes[code] = {nom: float(ws.cell(r, col).value) for col, nom in noms.items()}
    manquants = [p for p in pays if p not in lignes]
    if manquants:
        raise ValueError(f"pays absents de la feuille « Long-term rates » : {manquants}")
    return pd.DataFrame(lignes).T.loc[list(pays)]


def lire_cers_chocs_marche(dossier: Path = DOSSIER) -> dict:
    """Chocs instantanés du scénario de marché (en pb) : écarts souverains contre swap, France et Allemagne, et
    taux de swap en euro, par maturité (feuilles « Credit spreads - Sovereign » et « IR »)."""
    chemin = dossier / FICHIERS["cers_marche"]
    ws = _feuille(chemin, "Credit spreads - Sovereign")
    maturites = {col: ws.cell(5, col).value for col in range(5, ws.max_column + 1) if ws.cell(5, col).value}
    ecarts = {}
    for r in range(6, ws.max_row + 1):
        pays = ws.cell(r, 3).value
        if pays in ("France", "Germany"):
            ecarts[pays] = {"swap_de_reference": ws.cell(r, 4).value,
                            **{m: float(ws.cell(r, col).value) for col, m in maturites.items()}}
    ws = _feuille(chemin, "IR")
    maturites_ir = {col: ws.cell(5, col).value for col in range(5, ws.max_column + 1) if ws.cell(5, col).value}
    swap = None
    for r in range(6, ws.max_row + 1):
        if ws.cell(r, 3).value == "Euro Area":
            swap = {"description": ws.cell(r, 4).value,
                    **{m: float(ws.cell(r, col).value) for col, m in maturites_ir.items()}}
    if set(ecarts) != {"France", "Germany"} or swap is None:
        raise ValueError("chocs de marché introuvables dans le fichier du CERS")
    return {"ecarts_souverains_contre_swap_pb": ecarts, "swap_eur_pb": swap}


# --- Contrôles : Bundesbank et Banco de España --------------------------------------------------------------------

def lire_bund_bundesbank(dossier: Path = DOSSIER) -> pd.Series:
    """10 ans zéro-coupon des titres fédéraux (méthode de Svensson, Bundesbank), en %, chaque jour publié."""
    lignes = _exiger(dossier / FICHIERS["bund"]).read_text(encoding="utf-8-sig").splitlines()
    dates, valeurs = [], []
    for ligne in lignes:
        morceaux = ligne.split(",")
        if len(morceaux) >= 2 and len(morceaux[0]) == 10 and morceaux[0][4] == "-":
            try:
                valeurs.append(float(morceaux[1]))
            except ValueError:
                continue
            dates.append(pd.Timestamp(morceaux[0]))
    return pd.Series(valeurs, index=pd.DatetimeIndex(dates), name="bund_10_ans_zero_coupon").sort_index()


MOIS_ESPAGNOLS = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AGO": 8, "SEP": 9,
                  "OCT": 10, "NOV": 11, "DIC": 12}


def date_espagnole(texte: str) -> pd.Timestamp:
    """« 02 ENE 1979 » -> 1979-01-02."""
    jour, mois, annee = texte.strip().strip('"').split()
    return pd.Timestamp(int(annee), MOIS_ESPAGNOLS[mois.upper()], int(jour))


def lire_espagne_bde(dossier: Path = DOSSIER, serie: str = SERIE_ESPAGNE) -> pd.Series:
    """10 ans espagnol du marché secondaire (Banco de España, série D_G0B1F0ZP), en %, chaque jour publié."""
    import csv
    import io
    brut = _exiger(dossier / FICHIERS["espagne"]).read_bytes().decode("latin-1")
    lignes = list(csv.reader(io.StringIO(brut)))
    try:
        col = lignes[0].index(serie)
    except ValueError as erreur:
        raise ValueError(f"série {serie} absente du fichier du Banco de España") from erreur
    dates, valeurs = [], []
    for ligne in lignes[6:]:
        if len(ligne) <= col or not ligne[0].strip():
            continue
        try:
            v = float(ligne[col].replace(",", "."))
        except ValueError:
            continue
        dates.append(date_espagnole(ligne[0]))
        valeurs.append(v)
    return pd.Series(valeurs, index=pd.DatetimeIndex(dates), name="espagne_10_ans").sort_index()
