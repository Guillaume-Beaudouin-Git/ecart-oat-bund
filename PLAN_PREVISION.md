# Plan : prévoir le Bund, le niveau ou l'amplitude ?

Écrit et commité seul le 23 novembre 2026, avant toute estimation sur les données. Il s'ajoute à `PLAN.md` (commit
`f938339`), qu'il ne modifie pas : `PLAN.md` écartait toute prévision (section 13), et les sections 1 à 7 du README,
publiées le 22 novembre 2026, ne changent pas. Ce plan fixe une section 8 du README : la question, les données, les
quatre règles de prévision, le back test, le seul test qui décide du titre, le repli, la règle de non-publication,
les variantes, la sortie de l'outil et les limites à écrire quel que soit le résultat. Tout calcul ajouté après ce
commit sera signalé comme tel dans le README et dans `resultats/prevision.json`.

Le plan est un engagement, pas une preuve : l'historique montre qu'il a été commité avant le code de la prévision et
avant les résultats ; il ne prouve pas l'ordre de ce qui a été regardé. Le « je » est l'agent qui écrit ce plan.

## 0. Ce qui a été vu avant ce plan

- Le cadrage, fait par un autre agent, a fixé le sujet, les séries, la méthode, le protocole et la règle de
  décision repris ici. Il déclare n'avoir fait aucun calcul pilote ; il a vérifié le 23 novembre 2026 que les
  séries s'ouvrent sans compte et depuis quand.
- Le 10 ans zéro-coupon de la Bundesbank sert déjà de contrôle dans le dépôt (`PLAN.md`, section 12) : sa moyenne
  mensuelle a été comparée à la série allemande d'Eurostat (corrélation des variations mensuelles 0,991, écart moyen
  12,5 pb, plus grand écart en mars 2009). Le fichier téléchargé le 22 novembre 2026 est sur le disque ; je ne l'ai
  pas ouvert. Aucune variation quotidienne, aucune variance, aucun paramètre de GARCH n'a été calculé sur une
  série réelle.
- J'ai lu le README en entier. Il donne des faits sur le niveau des taux : la courbe AAA à 10 ans en octobre 2026
  (3,45 %), la hausse du niveau de la courbe en 2022 (+218 pb), l'écart OAT-Bund. Je sais donc que 2022 est une
  année de fortes variations, comme 2008 et 2011.
- Le travail voisin non publié (courbe-taux-euro) a testé la prévision du niveau de la courbe AAA par un modèle de
  Nelson-Siegel dynamique : la marche aléatoire n'a pas été battue de 2010 à 2026 (RMSE plus élevée de 19 %, 21 % et
  30 % à 1, 6 et 12 mois). Le tableau du niveau de la section 7 de ce plan n'est donc pas un test à l'aveugle : son
  résultat est attendu.
- Que la volatilité des taux se regroupe dans le temps et qu'une GARCH la prévoie mieux qu'une moyenne longue est
  un résultat de manuel. L'hypothèse du titre vient de là, pas des données de ce dépôt.
- Le code (`src/ecart_oat_bund/prevision.py`, `scripts/prevision.py`, `tests/test_prevision.py`) a été mis au point
  avant ce commit sur des séries simulées seulement : des GARCH simulées dans les tests, et des fichiers simulés
  au format des sources pour le script. Le paquet `arch` (9.0.0) s'installe avec le Python 3.13 du projet.

## 1. Question

Pour un exercice trimestriel de prévision et de stress, que prévoit-on mieux qu'une règle simple sur le Bund : le
niveau, ou l'amplitude de ses variations ?

## 2. Données

| source | série | fréquence | fenêtre retenue | rôle |
|---|---|---|---|---|
| Bundesbank, `BBSIS/D.I.ZST.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A` | 10 ans zéro-coupon des titres fédéraux | quotidienne | août 1997 à octobre 2026 | série principale |
| Bundesbank, `BBSIS/D.I.ZST.ZI.EUR.S1311.B.A604.R02XX.R.A.A._Z._Z.A` | 2 ans zéro-coupon des titres fédéraux | quotidienne | août 1997 à octobre 2026 | robustesse |
| BCE, `YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y` | 10 ans de la courbe AAA de la zone euro | quotidienne | 6 septembre 2004 à octobre 2026 | robustesse |

- Les séries s'arrêtent au dernier jour publié d'octobre 2026, comme le reste du dépôt (`donnees.DERNIER_MOIS`) ;
  `scripts/tout.py --dernier-mois AAAA-MM` prolonge la fenêtre. Les séries de la Bundesbank sont téléchargées le
  23 novembre 2026 par `scripts/telecharger.py`, depuis août 1997 ; la courbe AAA est déjà dans `data/`.
- Aucune donnée brute n'est versionnée. Les conditions de réutilisation (politique du SEBC) sont dans le README.
- Un « jour » est un jour où la série a une valeur ; les jours sans valeur (fériés) sont sautés. Aucune variation
  n'est retirée ni écrêtée.
- Aucun taux OAT quotidien n'est ouvert (`PLAN.md`, section 2) : l'amplitude de l'écart OAT-Bund n'est pas prévue.

## 3. Définitions

- y(j) : le taux du jour publié j, en %. Variation quotidienne en points de base : r(j) = 100 × (y(j) − y(j−1)),
  entre deux jours publiés consécutifs.
- Origine t : le dernier jour publié d'un mois, chaque mois depuis décembre 2004, pourvu que 1 000 variations au
  moins soient connues à cette date (le Bund en a environ 1 850 en décembre 2004 ; la courbe AAA, qui commence en
  septembre 2004, n'en a 1 000 que vers l'été 2008). À l'origine t, une règle ne lit que r(j) pour j ≤ t.
- Horizons : h = 21 et h = 63 jours publiés, soit un mois et un trimestre.
- Cible : la variance réalisée RV(t, h) = Σ_{i=1..h} r(t+i)², la somme des carrés des variations des h jours
  suivants, en pb². Une origine n'entre dans le back test que si ses h jours existent.
- Volatilité de l'horizon, pour la lecture : √RV(t, h), en pb sur un mois ou sur un trimestre. C'est l'écart-type
  de la variation du taux sur l'horizon si les variations quotidiennes ne sont pas autocorrélées.

## 4. Les quatre règles

Chacune donne F(t, h), la prévision de RV(t, h) faite à l'origine t.

1. **GARCH(1,1) à moyenne nulle** : σ²(j+1) = ω + α r(j)² + β σ²(j). Ajustée à chaque origine par
   quasi-vraisemblance normale sur toutes les variations connues depuis le début de la série (fenêtre croissante),
   avec le paquet `arch` et ses réglages par défaut (ω > 0, α ≥ 0, β ≥ 0, α + β < 1 ; variance initiale par lissage
   exponentiel des premières observations). F(t, h) = Σ_{i=1..h} E_t[σ²(t+i)], par la récurrence
   E_t[σ²(t+i)] = ω + (α + β) E_t[σ²(t+i−1)] partie de σ²(t+1). Si l'optimiseur ne converge pas à une origine,
   les paramètres de l'origine précédente sont repris et filtrés sur les données connues ; le nombre de cas est
   rapporté.
2. **Volatilité historique sur 252 jours, la référence** : F(t, h) = h × la moyenne des 252 derniers r(j)²
   (moyenne des variations supposée nulle, comme pour la GARCH).
3. **Volatilité historique sur 63 jours** : la même sur 63 jours.
4. **Moyenne exponentielle (EWMA 0,94)** : s²(t) = 0,94 s²(t−1) + 0,06 r(t)², initialisée à la moyenne des 252
   premiers carrés de la série ; F(t, h) = h × s²(t).

## 5. Back test

- Une origine chaque fin de mois depuis décembre 2004 ; les quatre règles sont réestimées ou recalculées à chaque
  origine sur le seul passé. Un test brouille les données postérieures à une date et vérifie qu'aucune prévision
  faite avant ne change.
- Perte principale : QLIKE(RV, F) = RV/F − ln(RV/F) − 1, nulle si F = RV, positive sinon, moyenne sur les origines.
- Pour la lecture : l'erreur sur la volatilité √F − √RV, en pb, par son erreur quadratique moyenne (RMSE) et son
  biais.
- Gain de la GARCH face à une règle : G = 100 × (1 − QLIKE moyenne de la GARCH / QLIKE moyenne de la règle), en %.
- Test de Diebold-Mariano : d(t) = QLIKE de la règle − QLIKE de la GARCH, positif quand la GARCH fait mieux ;
  moyenne de d testée contre 0, erreurs-types de Newey-West (noyau de Bartlett, sans correction de petit
  échantillon), p bilatéral par la loi normale. Les origines sont mensuelles et les cibles se chevauchent : le
  nombre de retards est 2h avec h compté en mois, soit 2 retards à 21 jours et 6 retards à 63 jours.
- Calcul principal : Bund à 10 ans, les quatre règles, les deux horizons ; la GARCH est comparée à chacune des trois
  règles simples (trois tests par horizon).

## 6. Le seul test qui décide, le titre, le repli, la non-publication

**Un seul test décide** : Bund à 10 ans, 63 jours, GARCH contre volatilité historique sur 252 jours. Le gain est
dit significatif si la moyenne de d est positive et si p < 0,05.

| test principal (10 ans, 63 jours) | test de repli (10 ans, 21 jours) | conséquence |
|---|---|---|
| significatif | non consulté pour la décision | titre visé, à 63 jours |
| non significatif | significatif | titre de repli, à 21 jours ; le premier paragraphe dit que le gain à 63 jours n'est pas significatif et donne son chiffre |
| non significatif | non significatif | **la section n'est pas publiée** : arrêt, et rapport à Guillaume |

- Titre visé : « À un trimestre, la volatilité du Bund à 10 ans se prévoit : la GARCH réduit l'erreur de X % face à
  la volatilité historique d'un an. »
- Titre de repli : le même avec « À un mois » et le X de 21 jours.
- X est le gain G du test retenu, arrondi à l'unité : « l'erreur » est la perte QLIKE moyenne, celle du test. La
  phrase qui porte le titre nomme cette perte et donne, à côté, la RMSE de la volatilité en pb des deux règles, quel
  que soit son sens.
- Aucune variante ne peut changer cette décision, ni dans un sens ni dans l'autre. Si le test principal passe et
  que des variantes le contredisent, le titre reste et le texte le dit.
- Rien n'est relancé avec d'autres réglages après lecture des résultats.

## 7. Le niveau : marche aléatoire contre AR(1)

- Série : le Bund à 10 ans en fin de mois (dernier jour publié), depuis août 1997.
- Origines : chaque fin de mois depuis décembre 2004, tant que la cible existe. Horizons : 3 et 12 mois.
- Marche aléatoire : ŷ(t+h) = y(t). AR(1) : régression directe de y(s+h) sur une constante et y(s), sur les
  paires connues à l'origine (s + h ≤ t, fenêtre croissante), puis ŷ(t+h) = ĉ + γ̂ y(t).
- Rapportés : RMSE en pb des deux, leur rapport, et Diebold-Mariano sur les erreurs au carré (Newey-West, 2h
  retards avec h en mois : 6 et 24).
- Résultat attendu, et dit comme tel (section 0) : la marche aléatoire n'est pas battue. Si l'AR(1) la battait au
  seuil de 5 %, la section le dirait tel quel. Ce tableau ne décide de rien.

## 8. Variantes de robustesse, fixées d'avance

Toutes calculées, toutes rapportées (README pour la GARCH contre la référence, `resultats/prevision.json` pour le
reste). Chacune reprend les quatre règles, les deux horizons et les trois comparaisons de la section 5.

1. **Le Bund à 2 ans**, même protocole.
2. **Le 10 ans de la courbe AAA de la BCE**, même protocole ; ses origines ne commencent que lorsque 1 000
   variations sont connues. Pour comparer à dates égales, le Bund à 10 ans est aussi évalué sur les seuls mois
   d'origine de la courbe AAA (mêmes prévisions que le calcul principal, restreintes à ces mois).
3. **Une fenêtre glissante de 10 ans** pour la GARCH du Bund à 10 ans : les 2 520 dernières variations connues, ou
   toute l'histoire tant qu'elle est plus courte.
4. **Trois sous-périodes**, selon la date de fin de la cible : 2005-2014, 2015-2021, 2022-2026. Par sous-période :
   QLIKE, RMSE et biais de chaque règle, gain, et le test de Diebold-Mariano à titre descriptif.
5. **La couverture des bandes à 95 %** du Bund à 10 ans : la part des origines où la variation réalisée du taux sur
   h jours reste dans ± 1,96 √F(t, h), pour les quatre règles, à 21 et 63 jours (horizons testés) et à 126, 189 et
   252 jours (horizons des bandes de l'outil). Fréquences descriptives, sans test : les fenêtres se chevauchent.

Diagnostics descriptifs, sans test, sur le calcul principal :
- concentration : la part de chaque année civile (date de fin de cible) dans la somme des d, et le gain recalculé
  en retirant les cibles qui finissent en 2008-2009, puis en 2022-2023 ;
- queues : à 63 jours, la fréquence des variations au-delà de ± 2,326 √F (le quantile normal à 99 % d'un côté),
  et le quantile à 98 % de |z|, z = variation réalisée / √F de la GARCH ;
- GARCH : paramètres à la première et à la dernière origine, étendue de α + β, écart-type de long terme à la fin
  de 2014 et de 2021, nombre de non-convergences.

## 9. Sortie de l'outil, en une commande

`uv run python scripts/prevision.py` (enchaîné par `scripts/tout.py`) affiche, au dernier jour publié :

- **les bandes de variation du Bund à 10 ans sur quatre trimestres** : dernier taux ± 1,96 √F(h) pour h = 63, 126,
  189 et 252 jours, F(h) venant de la GARCH ajustée sur toute l'histoire ; à côté, les mêmes bandes avec la
  volatilité historique sur 252 jours. La prévision centrale est le dernier taux (marche aléatoire, section 7) ;
- **un choc à 99 % sur un trimestre**, à la hausse : quantile × √F(63). Deux quantiles sont donnés : celui de la loi
  normale (2,326) et le quantile empirique à 98 % de |z| du back test à 63 jours (il suppose des queues
  symétriques). Le choc retenu est le plus grand des deux. Il est appliqué au premier ordre à la DV01 de taux de la
  position A de la section 5 du README (100 M€ d'OAT à 10 ans, `resultats/stress.json`) : perte = choc × DV01,
  écart OAT-Bund inchangé.

Deux figures : (5) la volatilité réalisée et les prévisions de la GARCH et de la référence à l'horizon du titre,
avec la somme cumulée des d ; (6) les bandes sur quatre trimestres.

## 10. Limites à écrire quel que soit le résultat

- Prévoir l'amplitude ne dit rien du sens des variations.
- Un taux zéro-coupon lissé (Svensson) n'est pas le rendement d'un titre.
- En 2015-2021 la volatilité est écrasée près de zéro, et une fenêtre croissante gonfle la variance de long terme
  de la GARCH : le biais par sous-période et la variante en fenêtre glissante le chiffrent.
- La variance réalisée sur des variations quotidiennes est une mesure bruitée de la variance vraie.
- Les fenêtres se chevauchent : environ 85 trimestres effectifs, où 2008 et 2022 pèsent lourd (diagnostic de
  concentration).
- Un quantile de loi normale sous-estime les queues (couverture, quantile empirique).
- L'amplitude de l'écart OAT-Bund n'est pas prévue, faute de taux OAT quotidien ouvert.
- La mention « ni une prévision » de la note du README vaut pour la décomposition : elle sera reformulée pour
  rester vraie.
- Aucune comparaison avec les prévisions d'une banque.

## 11. Ce qui n'est pas fait

Ni prévision du sens, ni prévision de l'écart OAT-Bund, ni modèle à plusieurs variables, ni autre forme de GARCH
(asymétrique, à queues épaisses), ni autre perte pour décider, ni mesure intrajournalière de la variance, ni
recommandation de position.

## 12. Décompte des calculs prévus

- 3 séries (Bund à 10 ans, Bund à 2 ans, 10 ans AAA), 4 règles, 2 horizons testés.
- 8 cellules (série, fenêtre, échantillon) : le calcul principal ; le Bund à 2 ans ; la courbe AAA ; le Bund à 10
  ans aux origines de la courbe AAA ; la fenêtre glissante ; trois sous-périodes. Dans chacune, 2 horizons × 3
  comparaisons : **48 tests de Diebold-Mariano sur la volatilité, dont 1 décide et 1 sert de repli** ; les 46
  autres sont descriptifs.
- 2 tests sur le niveau (3 et 12 mois), descriptifs.
- 20 fréquences de couverture (5 horizons × 4 règles) ; les diagnostics de la section 8.
- Environ 1 000 ajustements de GARCH : une par origine, pour trois séries, plus la fenêtre glissante.

Rien d'autre n'est prévu ; tout ajout sera signalé comme fait après coup.
