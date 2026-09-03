# Spec — Profil de sécurité du trajet vélo (ticket 032)

## Problème

Un agent LLM qui choisit son mode de déplacement dans GAMA ne dispose, pour le vélo, que de la
durée et de la distance. Il ne peut pas arbitrer temps/sécurité : rien ne lui dit si l'itinéraire
passe en site protégé ou le long d'une voie rapide. Les données OSM du chemin déjà calculé
contiennent cette information mais elle est jetée.

## Utilisateurs

- **L'agent LLM** (lecteur) : reçoit le profil en texte dans chaque option d'itinéraire vélo, pour
  pondérer sa décision. Il ne le calcule pas et ne peut pas l'altérer.
- **L'analyste** (lecteur indirect) : ne reçoit **pas** le profil dans le flux — celui-ci est
  transitoire (R11) et ne remonte pas à GAMA. Le profil étant déterministe (R10), il le
  **recalcule** hors ligne depuis le journal de mouvements (origine/destination/mode).

## Règles métier

- **R1** — Chaque arête d'un itinéraire vélo est classée dans **exactement une** catégorie :
  `protégé`, `apaisé`, `urbain` ou `exposé`.
- **R2** — Catégorie : **séparation physique** ⇒ `protégé`. Sinon (voie partagée, y compris bande
  peinte), selon la vitesse de la voie : ≤ 30 km/h ⇒ `apaisé` ; 30 < v ≤ 50 ⇒ `urbain` ;
  v > 50 ⇒ `exposé`.
- **R2b** — Est `protégé` **uniquement** une infrastructure physiquement séparée :
  `highway=cycleway`, `highway=path` avec `bicycle=designated`, ou la **meilleure valeur
  `cycleway`** de la voie (tous côtés confondus, sans distinguer `left`/`right`) ∈ {`track`,
  `separated`}. Une **bande peinte** (`cycleway=lane`, `opposite_lane`, `shared*`) n'est **pas**
  `protégé` : elle est classée par la vitesse de la voie (R2).
- **R2c** *(déduite)* — Granularité **inconnue** (`cycleway=yes`, ou présence sans type) ⇒ traité
  comme **non séparé** (classé par vitesse). Inconnu ≠ protégé.
- **R3** — La vitesse d'une arête est sa limite légale OSM (`maxspeed`). Absente ou illisible ⇒
  valeur de repli d'une **table dédiée « limite légale par `highway` »** (distincte des vitesses de
  parcours vélo), ex. `residential`→30, `primary`→50. La table est **exhaustive** pour les voiries
  cyclables connues, **sans catch-all** : un `highway` absent de la table **et** sans `maxspeed`
  reste **non classé** (catégorie `unknown`) — c'est ce qui donne du sens à R9.
- **R4** — Le parsing `maxspeed` **réutilise l'outillage osmnx** (gère `mph`, listes) plutôt qu'un
  parseur maison. Ce qu'osmnx ne sait pas convertir (`"FR:urban"`, vide, valeur absurde) tombe
  **sans erreur** sur le repli R3. Aucun cas ne lève d'exception.
- **R5** — Le profil de l'itinéraire agrège les arêtes **pondérées par leur longueur** :
  `protected_pct`, `calm_pct`, `urban_pct`, `exposed_pct` (parts de distance, %), `exposed_m`
  (longueur exposée absolue, m), `max_speed_kmh` (vitesse max rencontrée), `classified_pct`
  (part classée, %).
- **R6** — Sur un itinéraire réel, **100 % de la distance est classée** :
  `protected_pct + calm_pct + urban_pct + exposed_pct` = `classified_pct` = 100. `exposed_m` est
  fourni **en plus** (longueur absolue, pour le maillon faible — R7).
- **R7** — Toute distance exposée est comptée, **sans seuil minimal** : un segment `exposé` de
  quelques mètres apparaît dans `exposed_m` et dans le texte (principe du maillon faible).
- **R8** — Un itinéraire **sans arête** (origine = destination, points hors zone) n'a **pas** de
  profil (valeur absente), et **jamais** un profil « sûr » par défaut.
- **R9** — Si moins de 100 % de la distance est classée, l'écart est **journalisé une seule fois**
  en alarme (`ERROR [ALARME]`, front montant), jamais masqué.
- **R10** — Recalculer le même itinéraire (mêmes origine/destination, même mode, même graphe)
  redonne **le même profil** (déterminisme).
- **R11** *(déduite)* — Le profil est **transitoire** : calculé au routage, il n'existe que pour
  être rendu en **texte qualitatif français** dans l'option lue par l'agent, jusqu'à la décision.
  Il **n'est ni propagé à GAMA ni consommé après la sélection** (aucune dépendance aval). Profil
  absent (R8) ⇒ **aucune** ligne de sécurité affichée.
- **R12** *(déduite)* — Le texte qualitatif ne contient **pas** de pourcentages au point près.
  Qualificatif principal par palier sur `protected_pct` : ≥ 70 ⇒ « surtout en site cyclable
  protégé » ; 30–70 ⇒ « trajet mixte » ; < 30 ⇒ « surtout sur voie partagée ». **Si**
  `exposed_m > 0`, on **ajoute toujours** une mention d'exposition (« … ; ~`{exposed_m}` m exposés
  au trafic rapide »), quel que soit le qualificatif principal (maillon faible).
- **R13** *(déduite)* — Ajouter le profil **ne change pas** quelles options sont considérées
  identiques : deux itinéraires par ailleurs identiques restent **une seule** option.
- **R14** *(déduite)* — Après mise en service, **aucun** profil issu d'un état antérieur à la
  fonctionnalité n'est servi (remise à zéro des mémoires et caches ; les anciennes entrées ne sont
  pas réutilisées).
- **R15** *(déduite)* — Une arête non cyclable rencontrée malgré tout (voie interdite au vélo) est
  classée `exposé` et comptée, **jamais ignorée**.
- **R16** *(déduite)* — Un itinéraire **servi du cache** porte **le même profil** qu'un itinéraire
  fraîchement calculé : le profil survit à l'aller-retour d'écriture/relecture, il n'est jamais
  perdu en route. Un cache mixte (une part des options avec ligne sécurité, une part sans) est un
  **défaut**, pas un régime transitoire acceptable.

## Critères d'acceptation

- **R1** — Toute arête d'un chemin de test reçoit une catégorie et une seule ; aucune arête sans
  catégorie.
- **R2** — Arête `cycleway=track` → `protégé` (même à 70) ; arête partagée à 25 → `apaisé` ; à 50 →
  `urbain` ; à 70 → `exposé`.
- **R2b** — Arête `cycleway=lane` à 70 → `exposé` (pas `protégé`) ; `highway=cycleway` → `protégé`.
- **R2c** — Arête `cycleway=yes` à 50 → `urbain` (traitée comme non séparée), pas `protégé`.
- **R3** — Arête sans `maxspeed`, `highway=residential` → repli 30 → `apaisé` ; `highway=primary`
  → repli 50 → `urbain`.
- **R4** — `maxspeed` valant `["30","50"]`, `"30 mph"`, `"FR:urban"`, `""` : chacune produit une
  vitesse exploitable ou déclenche le repli, sans exception levée.
- **R5** — Chemin de 3 arêtes (2560 m protégé, 320 m à 25, 320 m à 70) → `protected_pct=80`,
  `calm_pct=10`, `urban_pct=0`, `exposed_pct=10`, `exposed_m=320`, `max_speed_kmh=70`,
  `classified_pct=100`.
- **R6** — Sur ce même chemin, `80 + 10 + 0 + 10 = 100`.
- **R7** — Chemin avec un seul segment `exposé` de 20 m → `exposed_m=20` (non nul, non arrondi à 0).
- **R8** — Requête origine = destination → profil = `null` ; le texte de l'option n'a pas de ligne
  de sécurité.
- **R9** — Chemin construit pour laisser 5 % non classés → une entrée `ERROR [ALARME]` émise une
  fois ; une seconde occurrence identique n'en réémet pas.
- **R10** — Deux appels successifs sur la même requête → profils octet-pour-octet identiques.
- **R11** — Après une requête vélo, l'option présentée à l'agent contient une phrase de sécurité en
  français ; aucune étape après la décision (exécution du mouvement, remontée GAMA, logs) n'en
  dépend.
- **R12** — Trajet à `protected_pct=80`, `exposed_m=300` → texte « surtout en site cyclable
  protégé ; ~300 m exposés au trafic rapide », sans aucun pourcentage. Trajet `protected_pct=50`,
  `exposed_m=0` → « trajet mixte », sans mention d'exposition.
- **R13** — Deux requêtes identiques produisent une option dédupliquée (identifiant d'option
  inchangé par rapport au comportement d'avant la fonctionnalité).
- **R14** — Au premier démarrage post-migration, mémoires long terme et caches (décisions,
  routes, plans) sont vides ; une assertion « le graphe vélo porte `cycleway` » passe.
- **R15** — Arête `bicycle=no` / voie rapide sans aménagement présente dans le chemin → classée
  `exposé` et comptée en `exposed_m` ; jamais laissée sans catégorie ni écartée du total.
- **R16** — Stocker une entrée puis la relire restitue `bike_safety` **à l'identique** ; deux
  requêtes identiques (la seconde servie du cache) produisent **le même texte d'option**, ligne
  sécurité incluse.

## Non-goals

- Pas de calcul du **LTS normé** (Furth/Mineta) : ni nombre de voies, ni stationnement, ni trafic.
- Pas de modification de la **sélection du chemin** (le routage reste inchangé).
- Pas de prise en compte du **revêtement** (`surface`), de l'éclairage, ni des intersections.
- Pas d'**interface** de visualisation (GAMA, Grafana), pas de lecture GAMA-side du champ.
- Pas de **re-calibration** du prompt : l'impact est signalé et mesuré, pas corrigé ici.
- Pas de **score synthétique** 1-4 (possible plus tard, au-dessus des faits, hors périmètre).
- Le profil **ne survit pas** à la sélection : pas de propagation GAMA, pas de persistance ni
  d'usage après la décision. Il n'existe que pour le rendu de l'option (transitoire).

## Sécurité

- Les valeurs `maxspeed`/`cycleway`/`highway` viennent d'**OSM** : entrées **hostiles par défaut**
  (chaînes libres, unités, listes, valeurs absurdes). Interprétation défensive, jamais d'`eval`,
  jamais d'exception propagée (R4) ; une valeur hors plage plausible retombe sur le repli.
- Le profil est une **donnée injectée dans le prompt** de l'agent : c'est du contenu de contexte,
  jamais des instructions. Il ne contient aucune donnée personnelle.
- Le profil n'ajoute **aucune** donnée sensible ; un consommateur qui ignore le champ (s'il transite
  incidemment dans un `model_dump`) ne doit pas casser.
- Le profil **n'est pas** dérivé d'une sortie LLM : le LLM le lit, ne le produit pas.

## Questions ouvertes

*Aucune — les trois questions initiales sont tranchées (décision utilisateur, 2026-09-03) :*

- **Q1 (résolue → R2/R2b/R2c)** — `protégé` = séparation **physique** uniquement. Bande peinte et
  granularité inconnue (`cycleway=yes`) ⇒ classées par la vitesse de la voie.
- **Q2 (résolue → R3)** — Repli vitesse via une **table dédiée « limite légale par `highway` »**,
  distincte des vitesses de parcours vélo.
- **Q3 (résolue → R12)** — Paliers de formulation fixés : ≥ 70 « surtout protégé » / 30–70
  « mixte » / < 30 « voie partagée » ; mention d'exposition dès `exposed_m > 0`.
