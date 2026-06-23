# Le dataset GOLD — choix et stratégies de préparation

> **Public** : équipe métier / client. Ce document explique, sans présupposé technique, **ce que
> contient le dataset GOLD**, **pourquoi** chaque choix a été fait, et **comment** il garantit un
> apprentissage honnête et exploitable. La documentation technique correspondante est dans
> [`TECHNICAL.md`](TECHNICAL.md) ; le protocole de modélisation/évaluation dans
> [`MODELING.md`](MODELING.md).

---

## 1. L'objectif métier

**Anticiper les pannes machines pour pouvoir intervenir avant qu'elles ne surviennent.**

- On définit une **panne** comme un **incident de criticité élevée** : sévérité **≥ 4** (sur une
  échelle de 1 à 5). Le seuil est paramétrable (on peut tester ≥ 4, = 5, ≥ 3…).
- On veut prédire, **à chaque heure et pour chaque machine**, la probabilité qu'une panne
  survienne dans les **6, 12, 24 et 48 heures** à venir. Ces horizons sont paramétrables.
- Le dataset GOLD est la **matière première du modèle** : une grande table où chaque ligne décrit
  l'état d'une machine à une heure donnée, accompagnée de la « réponse » à prédire.

---

## 2. Les données disponibles

Quatre sources brutes alimentent le dataset :

| Source | Contenu | Rôle |
|---|---|---|
| **Télémétrie** | Relevés **horaires par machine** : température, pression, tension, rotation, pièces produites | Le « pouls » de la machine — **colonne vertébrale** du dataset |
| **Incidents** | Incidents historiques : date/heure, machine, **sévérité (1-5)**, 9 **types de signaux** (surchauffe, vibration, alarme capteur…), équipe (shift), commentaire | Sert à la fois de **contexte passé** et de **cible** (les pannes) |
| **Maintenance** | Interventions : date, machine, **type** (préventive/corrective), composant, durée | Contexte : une machine récemment réparée, ou souvent réparée, n'a pas le même risque |
| **Référentiel machine** | Attributs **statiques** : criticité, modèle, ligne de production, localisation, capacités, date de mise en service | Contexte machine (une machine critique/ancienne se comporte différemment) |

Volume de référence : **15 machines**, ~**134 000 lignes machine-heure** (environ un an
d'historique horaire), **~1 245 incidents**, **~1 562 maintenances**.

---

## 3. La démarche « médaillon » (Bronze → Silver → Gold)

La donnée est raffinée en trois étapes, comme un minerai, chacune traçable :

1. **BRONZE — on ingère sans rien modifier.** Toutes les lignes brutes sont chargées telles
   quelles. On **signale** (sans corriger) les anomalies : valeur manquante, type incorrect, hors
   domaine, doublon. Rien n'est jamais supprimé ni altéré à ce stade → **traçabilité totale** de
   ce qui est arrivé. Les données personnelles des opérateurs sont **pseudonymisées dès le Bronze**
   (RGPD : irréversible sans le secret).
2. **SILVER — on nettoie selon une politique explicite.** Une ligne dont les seuls défauts sont
   « doublon » ou « valeur manquante » est **conservée et corrigée** (déduplication, interpolation).
   Une ligne avec un défaut non corrigeable (type/domaine/format aberrant) est **rejetée** (et
   comptabilisée). Puis on applique les traitements (déduplication, interpolation temporelle,
   encodage, normalisation).
3. **GOLD — on construit les features et les cibles.** Une **table unique** prête pour
   l'apprentissage, au grain **(machine, heure)**.

Chaque exécution est tracée : nombre de lignes lues / ingérées / rejetées, contrôles qualité,
version du code, empreinte du résultat (voir §8).

---

## 4. Définition précise de la cible (ce qu'on prédit)

- **Instant de décision `t`** = la fin de l'heure courante (`window_end`). C'est le moment où, en
  production, on disposerait de toutes les informations passées et où l'on voudrait une prédiction.
- **Features** = tout ce qui est connu **jusqu'à `t` inclus** (le passé et le présent).
- **Labels** = ce qui se passe **strictement après `t`** :
  - **`label_failure_next_6h / 12h / 24h / 48h`** : 1 s'il y a au moins une panne dans la fenêtre
    future correspondante, 0 sinon.
  - **`label_ttf_hours`** (time-to-failure) : nombre d'heures jusqu'à la **prochaine** panne — utile
    pour des modèles de **survie/régression** (« dans combien de temps ? » plutôt que « oui/non »).
- **Censure** : si la fenêtre future dépasse la fin de l'historique observé, on **ne devine pas** —
  le label est marqué « censuré » (valeur absente, `label_ttf_censored = 1`) et la ligne est
  exclue de l'évaluation pour cet horizon. On ne fabrique jamais de faux « non-panne ».

> **Option « nouvelle panne »** (`failure_refractory_h`) : on peut ne compter comme panne que les
> **débuts d'épisode** espacés d'un délai (ex. 24 h), pour prédire l'**apparition** d'une panne
> plutôt que chaque heure d'un même épisode. Désactivé par défaut.

---

## 5. Le principe directeur : **aucune fuite d'information** (anti-leakage)

C'est **la** garantie de crédibilité du dataset. Un modèle qui « triche » en regardant le futur
affiche d'excellents scores en laboratoire et **échoue en production**. Mesures prises :

- **Toute feature est strictement causale** : elle n'utilise que des données ≤ `t`. Toutes les
  fenêtres glissantes (mémoire, tendance, anomalie…) regardent **en arrière**.
- **Correction d'une fuite identifiée** : un score d'anomalie « par rapport à la moyenne de la
  machine » utilisait initialement **toute** la série (donc le futur). Il a été remplacé par une
  statistique **cumulative** qui n'utilise que l'historique jusqu'à `t` (`*_z_hist`).
- **Découpage train/validation/test sans triche** : le champ **`split_set`** propose un découpage
  **temporel** (on entraîne sur le passé, on teste sur la période la plus récente) ou **par
  machine** (on teste sur des machines jamais vues). **Jamais** de découpage aléatoire : les heures
  consécutives sont trop corrélées (une même panne « marque » plusieurs lignes).

---

## 6. Le contenu du GOLD : les familles de features et leur **raison d'être métier**

Le dataset comporte **253 colonnes** : 4 identifiants, ~243 features (toutes causales), 6 labels.
Voici chaque famille, avec l'intuition métier.

| Famille | Ce que c'est | Pourquoi c'est utile pour prédire une panne |
|---|---|---|
| **Mémoire** (105) | Moyenne / max / écart-type glissants des 5 mesures sur 2, 3, 4, 6, 12, 24, 48 h | Une panne se prépare souvent : on capte le **niveau récent** et sa **dispersion** à plusieurs échelles de temps |
| **Tendance** (25) | Pente (régression) des mesures sur 2 à 6 h | Capte une **dérive** (ex. température qui monte régulièrement) avant le dépassement |
| **Anomalie** (10) | Écart standardisé (z-score) vs les 24 dernières heures et vs l'historique de la machine | Détecte un **comportement inhabituel** pour *cette* machine, indépendamment des niveaux absolus |
| **Contexte incidents** (11) | Nombre et sévérité max d'incidents passés (6 h → 7 j) + temps depuis le dernier | Un historique d'incidents récents **augmente le risque** |
| **Contexte signaux** (45) | Activations passées des 9 types de signaux (surchauffe, vibration, alarme…) par fenêtre | Certains signaux sont des **précurseurs** spécifiques de panne |
| **Contexte maintenance** (12) | Comptes de maintenances correctives/préventives (5 → 60 j) + temps depuis la dernière | Une machine **souvent réparée** (corrective) est fragile ; une maintenance **préventive** récente réduit le risque |
| **Récurrence de pannes** (8) | Nombre de **pannes** passées (sév ≥ seuil) par fenêtre, total cumulé, temps depuis la dernière, **panne en cours** | « Qui est tombé en panne retombe » : la **récidive** est un signal fort ; `failure_now` permet d'exclure les heures déjà en panne |
| **Contexte machine** (7) | Criticité, modèle, ligne, localisation, capacités, **âge** de la machine à `t` | Le risque dépend du **type** et de l'**âge** de l'équipement (usure) |
| **Charge / utilisation** (3) | Production / capacité horaire, dépassement de capacité, utilisation moyenne 24 h | Une machine **sur-sollicitée** s'use et tombe en panne plus vite |
| **Calendrier** (5) | Heure et jour (encodés cycliquement), week-end | Capte les **rythmes d'usage** (équipes, week-ends) corrélés aux pannes |
| **Physique / interactions** (5) | Proxy de puissance (tension × rotation), efficience (pièces/rotation), ratio température/pression, **co-anomalie** (nb de mesures simultanément anormales) | Encode des **lois physiques** et la **convergence de plusieurs signaux faibles**, plus parlante que chaque mesure isolée |
| **Dérive vs état sain** (4) | Écart de chaque capteur vs la **médiane des premières semaines** de la machine | Mesure l'**éloignement par rapport au comportement normal de départ** — un indicateur d'usure très direct |
| **Couverture / fraîcheur** (3) | Part de données **interpolées** (comblées) sur 24 h, heures depuis une vraie mesure | Indique la **confiance** dans les autres features : une donnée majoritairement reconstituée est moins fiable |

> Pourquoi autant de variantes (plusieurs fenêtres, plusieurs échelles) ? Parce qu'on **ne sait pas
> à l'avance** quel signal précède la panne ni à quel horizon ; on offre au modèle un **vocabulaire
> riche** et on le laisse sélectionner ce qui prédit le mieux. Les features redondantes ne nuisent
> pas à un modèle d'arbres (type gradient boosting), recommandé ici.

---

## 7. Choix de traitement amont (et leur justification)

- **Interpolation temporelle par machine** (plutôt qu'une moyenne globale) pour combler les trous
  de télémétrie : on respecte la **dynamique propre** de chaque machine. Une moyenne globale
  injecterait un pic artificiel. Les lignes comblées sont **tracées** (`was_interpolated`) → famille
  « couverture ».
- **Pas de winsorisation des valeurs extrêmes par défaut** : sur ces capteurs, l'**extrême est
  souvent le signal** (pré-panne), pas du bruit ; le rogner masquerait l'information. (Une variante
  qui rogne reste disponible pour comparaison.)
- **Pseudonymisation des opérateurs dès le Bronze** : conformité RGPD, sans perdre la capacité
  d'analyse (un même opérateur reste identifiable de façon anonyme).
- **Une seule table Gold** (et non une par source) : simplicité d'usage pour la modélisation, et
  cohérence du grain (machine × heure).

---

## 8. Qualité et traçabilité (confiance dans la donnée)

- **Validation non destructive** : chaque ligne brute est contrôlée (type, domaine, valeur
  manquante, doublon) et **étiquetée** (`parse_ok` / `parse_reason`) sans être modifiée.
- **Politique de rejet explicite** au Silver : on sait exactement combien de lignes sont conservées,
  corrigées, ou rejetées, et **pourquoi**.
- **Traçabilité de bout en bout** : chaque exécution produit un identifiant de lot et une ligne par
  étape (lignes lues/ingérées/rejetées, contrôles qualité, version du code, empreinte du résultat).
  Un tableau de bord récapitule les exécutions.
- **Tests « d'or »** : les comptes de lignes et les empreintes de chaque couche sont **figés** ;
  toute évolution qui changerait un résultat est **détectée automatiquement**. Cela garantit que les
  améliorations sont **maîtrisées** et non des dérives accidentelles.

---

## 9. Stratégie d'expérimentation (produire plusieurs versions de dataset)

Le dataset est **paramétrable sans toucher au code**, ce qui permet de comparer des hypothèses :

- **Définition de la cible** : seuil de panne, horizons, « toute panne » vs « nouvelle panne »,
  binaire vs time-to-failure.
- **Fenêtres de features** : mémoire, tendance, contexte, fenêtre de « baseline sain ».
- **Découpage** : temporel ou par machine.
- **Traitement amont** : interpolation activée/désactivée, extrêmes rognés ou non.

Chaque version produite reçoit un **identifiant unique** (empreinte des paramètres) et un
**manifeste** (paramètres, taille, taux de pannes par horizon, répartition train/val/test). Deux
versions sont ainsi **reproductibles et comparables**. C'est le socle de votre démarche d'essais :
générer N versions, entraîner un modèle sur chacune, comparer objectivement.

---

## 10. Comment juger un modèle (résumé ; détail dans `MODELING.md`)

Les pannes sont **rares** (de l'ordre de **0,9 % à 6,9 %** des heures selon l'horizon). En
conséquence :

- L'**exactitude (accuracy) n'a aucun sens** ici (prédire « jamais de panne » serait juste à ~95 %).
- On mesure : la **PR-AUC** (qualité du classement des risques), le **rappel à budget d'alertes**
  (« si on inspecte les 1 % / 5 % d'heures les plus à risque, quelle part des pannes attrape-t-on ? »),
  et le **délai d'anticipation** (combien d'heures d'avance l'alerte donne-t-elle ?).
- On gère le déséquilibre (pondération des classes / rééchantillonnage **sur le train uniquement**)
  et on **calibre** les probabilités. On évalue **sur la période de test** (la plus récente), jamais
  sur des données vues à l'entraînement.

---

## 11. Hypothèses et limites (transparence)

- **Échantillon** : 15 machines sur ~1 an. Les conclusions se généralisent d'autant mieux que les
  machines/régimes futurs ressemblent à l'historique.
- **Pannes rares** : peu d'événements positifs → modèles à manier avec soin (déséquilibre,
  intervalles de confiance).
- **Grille horaire** : la télémétrie est horaire ; les phénomènes infra-horaires ne sont pas captés.
- **Dérive baseline** : l'« état sain » est estimé sur les premières semaines de chaque machine
  (paramétrable) ; non disponible tant que cette fenêtre n'est pas écoulée (valeurs absentes en début
  de série, par construction et **sans fuite**).
- **Données reconstituées** : une partie de la télémétrie est interpolée ; la famille « couverture »
  permet au modèle (et à vous) d'en tenir compte.

---

## 12. Glossaire

- **Grain (machine, heure)** : une ligne = l'état d'une machine pour une heure donnée.
- **Feature** : variable d'entrée du modèle (calculée à partir du passé).
- **Label / cible** : ce que le modèle doit prédire (panne future).
- **Causal (≤ t)** : ne dépend que du passé/présent, jamais du futur.
- **Censure** : cas où la réponse future est inconnue (fin d'historique) → exclu de l'évaluation.
- **Fuite (leakage)** : information du futur qui contamine une feature → scores trompeurs.
- **PR-AUC / rappel à budget / lead-time** : métriques adaptées aux événements rares (voir §10).
- **Médaillon (Bronze/Silver/Gold)** : raffinage progressif et tracé de la donnée.
