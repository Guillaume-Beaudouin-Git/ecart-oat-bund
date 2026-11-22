# Plan : écart OAT-Bund, la part propre à la France

Écrit et commité le 22 novembre 2026, avant tout calcul sur les données. Ce qui suit fixe la question, les
données, les définitions, le modèle, l'intervalle, les variantes, la règle de repli, les épisodes de contrôle, le
stress et la comparaison avec l'ABE. Tout calcul ajouté après ce commit sera signalé comme tel dans le README et
dans les fichiers de `resultats/`.

Le plan est un engagement, pas une preuve : l'historique montre qu'il a été commité avant le code de la
décomposition et avant les résultats ; il ne prouve pas l'ordre de ce qui a été regardé.

## 0. Ce qui a été vu avant ce plan

- Le cadrage du projet, fait par un autre agent, a regardé les écarts bruts mensuels et donne des chiffres à
  vérifier : écart France-Allemagne à 10 ans de 51 pb en mai 2024 et de 147 pb en octobre 2026, soit 96 pb de
  hausse ; 147 pb serait le plus haut depuis novembre 2011 ; le taux français serait au-dessus de l'italien six mois
  depuis décembre 2025, une première depuis 1999 ; dans le scénario adverse de l'ABE de 2025, un écart de 157, 135
  et 117 pb en 2025, 2026 et 2027, et un choc de marché à 10 ans de +112 pb pour la France et +31 pb pour
  l'Allemagne. Aucun n'est repris sans être recalculé (section 9).
- Pendant l'exploration des sources, j'ai vu par mégarde les deux dernières valeurs du TEC 10 de la Banque de France
  dans les métadonnées de Webstat (un niveau de taux de novembre 2026), et, dans des extraits de recherche web, deux
  niveaux de taux d'une source non retenue (italien en novembre 2026, belge en février 2026). Le README du dépôt
  courbe-taux-euro, lu avant ce projet, donne la courbe AAA de la BCE jusqu'au 19 novembre 2026.
- L'exploration a porté sur l'accès, la couverture et la mise en page des sources : dates de début et de fin, mois
  manquants, codes des séries, intitulés des feuilles du CERS. Aucun écart, aucune régression, aucun résidu n'a été
  calculé.

## 1. Question

Dans la hausse de l'écart OAT-Bund à 10 ans depuis mai 2024, dernier mois avant la dissolution de l'Assemblée
nationale, combien de points de base sont propres à la France, et combien suivent les autres pays de la zone euro ?
Que coûte cette prime à un détenteur d'OAT sous des chocs calibrés sur l'histoire ? C'est une mesure, pas une
prévision ni une recommandation.

## 2. Données

| source | série | fréquence | fenêtre retenue |
|---|---|---|---|
| Eurostat, `irt_lt_mcby_m` | taux longs du critère de convergence, FR, DE, IT, ES, NL, BE, AT, PT, FI, IE | moyenne mensuelle | 1999-01 à 2026-10 |
| Eurostat, `nama_10_gdp` | PIB à prix courants (B1GQ, CP_MEUR), 2019 | annuelle | 2019 |
| BCE, `YC/B.U2.EUR.4F.G_N_A.SV_C_YM` | courbe AAA : 7 taux zéro-coupon, 6 paramètres de Svensson | quotidienne | 2004-09-06 à 2026-10-30 |
| BCE, `CISS/D.FR.Z0Z.4F.EC.SOV_CIN.IDX` | indicateur composite de tension souveraine de la France (SovCISS) | quotidienne | 2000-01-05 à 2026-10-30 |
| CERS, test de résistance de l'ABE de 2025 | scénario macrofinancier (feuille « Long-term rates ») et scénario de marché (feuilles « Credit spreads - Sovereign » et « IR ») | moyennes annuelles ; chocs instantanés | 2024 à 2027 |
| Bundesbank, `BBSIS/D.I.ZST.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A` | 10 ans zéro-coupon des titres fédéraux | quotidienne | contrôle seulement |
| Banco de España, `D_G0B1F0ZP` | 10 ans espagnol du marché secondaire | quotidienne | contrôle seulement |

- Les taux d'Eurostat sont des rendements du marché secondaire, bruts d'impôt, d'obligations d'État de durée
  résiduelle proche de 10 ans, remplacées régulièrement : ils ne sont pas à maturité constante. La BCE les collecte
  auprès des banques centrales nationales ; ce sont des moyennes mensuelles de données quotidiennes.
- La fenêtre mensuelle s'arrête en octobre 2026, dernier mois publié au téléchargement du 22 novembre 2026.
- Ne sont pas utilisés : les TEC de la Banque de France (indices calculés par Euronext, dont la redistribution est
  interdite sans autorisation écrite) ; l'API Webstat (compte obligatoire) ; le site de l'AFT (fermé aux scripts) ;
  la série quotidienne d'Eurostat (retirée). Il n'y a donc ni taux français quotidien, ni marché primaire.
- Pays exclus : la Grèce, parce que sa série a un trou (juillet 2015, marché fermé selon Eurostat) et que son écart,
  porté par une histoire propre, dominerait une moyenne pondérée même avec un faible poids (son plus grand écart est
  recalculé, section 9) ; le Luxembourg (pas de taux harmonisé avant mai 2010) ; les pays entrés dans l'euro après
  2001, aux marchés plus petits. La série grecque est téléchargée pour documenter l'exclusion, jamais utilisée
  dans un calcul de part propre.

## 3. Définitions

- Écart du pays i à l'Allemagne : s_i(t) = 100 × (y_i(t) − y_DE(t)), en pb, en moyenne mensuelle.
- Pairs : G8 = IT, ES, NL, BE, AT, PT, FI, IE (principal) ; cœur = NL, BE, AT, FI ; périphérie = IT, ES, PT, IE.
- Poids : w_i = PIB_i(2019) / somme des PIB(2019) des pays du groupe. Écart moyen des pairs : P(t) = Σ w_i s_i(t).
  Taux moyen des pairs : ȳ(t) = Σ w_i y_i(t).
- Mois de base T0 = mai 2024. Hausse observée : R = s_FR(2026-10) − s_FR(2024-05).

## 4. Modèle principal

    Δs_FR(t) = b × ΔP(t) + ε(t)          (variations mensuelles, sans constante, P sur le G8)

- b est estimé par moindres carrés sur les 60 variations mensuelles de juin 2019 à mai 2024 : elles se terminent
  avec le mois de base et précèdent toutes la dissolution (le cadrage dit « les 60 mois qui précèdent mai 2024 » ;
  la fenêtre retenue garde la variation d'avril à mai 2024, antérieure à la dissolution, pour n'oublier aucun mois).
- Contrefactuel, pour t après mai 2024 : ŝ_FR(t) = s_FR(T0) + b̂ × (P(t) − P(T0)).
- Part propre à la France : X(t) = s_FR(t) − ŝ_FR(t), la somme des résidus depuis T0. Part commune :
  b̂ × (P(t) − P(T0)).
- Intervalle à 95 % : X(t) ± 1,96 σ(t), avec σ(t)² = V_h + (P(t) − P(T0))² × Var(b̂) et h = t − T0 en mois.
  - V_h est la variance d'une somme de h résidus, estimée comme Newey-West : V_h = h γ0 + 2 Σ_{j=1}^{min(L, h−1)}
    (1 − j/(L+1)) (h − j) γ_j, où γ_j = (1/T) Σ ε̂(t) ε̂(t−j) sur la fenêtre d'estimation. Les moyennes
    mensuelles rendent les variations autocorrélées : c'est ce que les γ_j prennent en compte.
  - Var(b̂) : Newey-West, noyau de Bartlett, L retards, sans correction de petit échantillon.
  - L = partie entière de 4 × (T/100)^(2/9), T le nombre de variations d'estimation : 3 pour 60, 4 pour 120,
    5 pour 304.
- Diagnostic fixé d'avance, sans décision qui en dépende : la moyenne des résidus sur la fenêtre d'estimation et la
  dérive qu'elle donnerait sur h mois (un modèle sans constante ne prolonge pas une dérive propre à la France).
- Rapportés : b̂ et son erreur-type, R², écart-type des résidus, part commune, part propre, intervalle, et le
  chemin mensuel de X(t) et de son intervalle de juin 2024 à octobre 2026 (pour la figure).

## 5. Résultat d'en-tête

« Sur R pb de hausse depuis mai 2024, X pb [borne basse ; borne haute] sont propres à la France », valeurs
arrondies au pb, en octobre 2026, modèle principal. Si la part commune est négative, la phrase le dit : la part
propre dépasse alors la hausse observée. La part propre est significative si l'intervalle exclut 0.

## 6. Variantes et règle de repli

Cinq variantes, toutes calculées et toutes rapportées, avec la même base, la même fin et le même intervalle :

1. fenêtre de 120 variations (juin 2014 à mai 2024) ;
2. fenêtre depuis 1999 (février 1999 à mai 2024, 304 variations) ;
3. pairs « cœur » NL, BE, AT, FI ;
4. pairs « périphérie » IT, ES, PT, IE ;
5. taux plutôt qu'écarts, avec un coefficient libre sur le Bund : Δy_FR(t) = c Δy_DE(t) + d Δȳ(t) + ε(t), sans
   constante, 60 variations, ȳ sur le G8. « En niveaux de taux » s'entend des taux eux-mêmes et non de leurs
   écarts à l'Allemagne ; on reste en variations mensuelles, comme le modèle principal, pour ne pas régresser des
   séries non stationnaires l'une sur l'autre. La part propre est la somme des résidus ; le terme de paramètres de
   l'intervalle devient g' V g, g la somme des régresseurs depuis T0 et V la matrice de Newey-West.

Règle de repli : si l'une des cinq variantes s'écarte de plus de 20 pb du modèle principal (|X_variante − X_principal|
en octobre 2026, valeurs non arrondies), l'en-tête devient le tableau sans modèle de la section 7. Le modèle
principal et les variantes restent rapportés, comme lecture par modèle.

## 7. Tableau sans modèle : la France contre chaque pays

Pour l'Allemagne, chacun des huit pairs et la moyenne pondérée du G8 : l'écart y_FR − y_i en mai 2024, en octobre
2026, et sa variation, en pb, en moyenne mensuelle. Toujours calculé ; en tête si la règle de repli joue.

## 8. Épisodes de contrôle

| épisode | mois de base | fin | estimation de b |
|---|---|---|---|
| E1 | 2011-06 | 2011-11 | 60 variations jusqu'à 2011-06 |
| E2 | 2016-12 | 2017-04 | 60 variations jusqu'à 2016-12 |
| E3 | 2020-02 | 2020-04 | 60 variations jusqu'à 2020-02 |
| E4 | 2021-12 | 2022-10 | 60 variations jusqu'à 2021-12 |
| E5 | 2026-08 | 2026-10 | modèle principal (b de la section 4) : les 60 mois avant août 2026 contiennent la période étudiée |

Pour chacun : variation observée de s_FR, part commune, part propre et son intervalle (pour E5, l'accroissement de
X entre août et octobre 2026, h = 2).

Lecture fixée d'avance :
- E3 (pandémie) et E4 (resserrement monétaire) sont des chocs communs : l'intervalle de la part propre doit
  contenir 0 ;
- E2 (élection présidentielle française de 2017) : la part propre doit être positive et son intervalle exclure 0 ;
- E1 et E5 : pas d'attente écrite ; E1 donne la taille d'un choc commun, E5 n'a pas de cause établie ici.
Si E2, E3 ou E4 ne vérifient pas leur attente, le README le dit et la lecture de la méthode en est affaiblie.

SovCISS de la France (descriptif) : pour chaque épisode, la date et la valeur de son maximum entre le premier jour du
mois de base et le dernier jour du mois de fin ; en juin 2024, le jour de sa plus forte hausse sur un jour.

Aucun événement n'est cité sans source primaire (décret, Assemblée nationale, communiqué de la BCE ou du
Conseil constitutionnel). Les causes de l'automne 2026 ne sont pas établies par le cadrage : faute de source
primaire, le README le dit.

## 9. Faits à recalculer

- s_FR en mai 2024 et en octobre 2026, et R.
- Le dernier mois avant octobre 2026 où s_FR atteint ou dépasse sa valeur d'octobre 2026 (« plus haut depuis »).
- Les mois de décembre 2025 à octobre 2026 où y_FR > y_IT (inégalité stricte sur les valeurs publiées), et le
  premier mois depuis janvier 1999 où y_FR > y_IT.
- Le plus grand écart mensuel de la Grèce à l'Allemagne depuis 1999 et son mois (justification de l'exclusion).
- Les chiffres de l'ABE de la section 11.
Seuls les faits que les données confirment entrent dans le README.

## 10. Stress

- Courbe sans risque : la courbe AAA de la BCE en moyenne d'octobre 2026 (moyenne, maturité par maturité, des
  courbes de Svensson publiées chaque jour ouvré du mois), qui tient lieu de courbe du Bund. Courbe des OAT : la
  courbe AAA plus un écart constant à toutes les maturités, égal à s_FR d'octobre 2026.
- Titres : une OAT et un Bund à 10 ans émis au pair sur leur courbe, coupon annuel.
- Positions : (A) 100 M€ de nominal d'OAT 10 ans ; (B) la même OAT contre une vente de Bund 10 ans dont le nominal
  annule la DV01 de taux de la position.
- Sensibilités : DV01 de taux (gain pour une baisse parallèle de 1 pb de la courbe AAA, écart fixe) et sensibilité à
  l'écart (perte pour une hausse de 1 pb de l'écart, courbe AAA fixe), par différences centrées de ±0,5 pb.
- Chocs instantanés, réévaluation complète, sans portage, sans plancher, sans probabilité :
  - C1, la prime française résorbée : l'écart baisse de X (modèle principal, octobre 2026) ;
  - C2, le choc commun de 2011 : l'écart monte de b̂ × (P(2011-11) − P(2011-06)), b̂ du modèle principal ;
  - C3, le niveau de 2022 : la courbe AAA monte partout de la variation du niveau de Nelson-Siegel entre les fins de
    décembre 2021 et de décembre 2022 (λ de Diebold et Li, sept maturités publiées) ;
  - C4, le rejeu des trois facteurs de 2022 : même période, niveau, pente et courbure ensemble ;
  - C5, le choc de marché de l'ABE de 2025 : la courbe AAA monte du choc de swap en euro plus le choc d'écart de
    l'Allemagne, l'écart OAT-Bund du choc d'écart de la France moins celui de l'Allemagne, maturité par maturité
    (interpolation linéaire entre les maturités publiées, constante au-delà).
- Résultats : variation de valeur en M€ (et en % pour A) sous chaque choc ; DV01 et sensibilité à l'écart en k€ par pb.

## 11. Comparaison avec l'ABE de 2025

- Scénario macrofinancier : taux longs de la France et de l'Allemagne au départ (moyenne 2024, moyenne de décembre
  2024), dans le scénario central et dans le scénario adverse (2025, 2026, 2027), en moyenne annuelle ; l'écart
  France-Allemagne de chaque colonne, en pb.
- Scénario de marché : chocs instantanés à 10 ans des écarts souverains de la France et de l'Allemagne, mesurés
  contre le swap en euro, et choc du swap en euro à 10 ans.
- Comparaison : l'écart observé en moyenne annuelle 2024, 2025 et sur janvier-octobre 2026 (Eurostat), face aux
  colonnes de l'ABE. Les moyennes annuelles de l'ABE ne se comparent pas à un mois ; ses chocs de marché sont
  mesurés contre swap, pas contre le Bund.

## 12. Contrôles des données

- Allemagne : moyenne mensuelle du 10 ans zéro-coupon de la Bundesbank contre la série d'Eurostat (écart moyen,
  corrélation des variations mensuelles, plus grand écart), 1999-01 à 2026-10.
- Espagne : moyenne mensuelle du 10 ans du Banco de España contre Eurostat, mêmes mesures.
- ABE : le point de départ « moyenne 2024 » de la France et de l'Allemagne contre la moyenne 2024 d'Eurostat.
Ils sont descriptifs ; un écart important serait examiné avant toute lecture.

## 13. Ce qui n'est pas fait

Ni prévision, ni recommandation de position, ni juste valeur absolue : la « juste valeur » est relative aux pairs.
Ni taux quotidien français, ni marché primaire, ni CDS, ni coût budgétaire (le programme de financement de l'AFT n'a
pas pu être lu par script).

## 14. Décompte des calculs prévus

6 décompositions (le modèle principal et 5 variantes) ; 1 tableau sans modèle ; 5 épisodes ; 4 faits ; 5 chocs
appliqués à 2 positions, avec leurs sensibilités ; 2 lectures de l'ABE ; 3 contrôles des données. Rien d'autre
n'est prévu ; tout ajout sera signalé comme fait après coup.
