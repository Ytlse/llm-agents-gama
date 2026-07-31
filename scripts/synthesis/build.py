"""Construit la page de synthèse des scores.

    python -m scripts.synthesis.build [--config …] [--run …] [--out …]

Rien n'échoue sur une donnée absente : chaque source manquante devient une carte
« Données manquantes » assortie de l'action qui la produirait.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import frames, heldout_eval, render
from .frames import DIMENSIONS, MODES
from .sources import REPO_ROOT, import_calibration, load_manifest

# Actions pour remplir la page. Affichées telles quelles en bas de page : une
# seule source de vérité entre la doc et le rendu. Les identifiants ne sont
# jamais recyclés — une action faite reste dans la liste, marquée `done`, parce
# que les avertissements du code et les tickets y renvoient par numéro.
ACTIONS = [
    {"id": "A1", "title": "Figer le run servant de jeu commun",
     "detail": "Remplacer experiments/current par un chemin d'archive explicite dans "
               "sources.yaml, pour que la page reste reproductible quand le symlink bouge.",
     "cost": "5 min", "unlocks": "Reproductibilité de toute la page",
     "done": "Le manifeste épingle experiments/archive/2026-07-29_18_34. La page ne "
             "suit plus le symlink : elle décrit le même run à chaque régénération, "
             "et l'empreinte de moves.csv le vérifie."},
    {"id": "A2", "title": "Renseigner le type de logement dans moves.csv",
     "detail": "La colonne est écrite vide (move_logger.py) alors que la référence EMC² "
               "porte une ventilation par type de logement. Le trait n'existe pas non "
               "plus dans traits_json : il faut le produire à la génération de population.",
     "cost": "1/2 j", "unlocks": "Dimension type de logement, volet 1",
     "progress": {
         "acquis":
             "Le trait est produit et journalisé. Aucune source de la chaîne ne le "
             "portait — ni eqasim, ni les tables INSEE de l'étape 3bis du notebook : "
             "vérifié, ce n'est pas un branchement mais une création. La seule source "
             "qui le porte pour Toulouse est l'enquête elle-même (variable M1 du "
             "fichier ménages, « Type d'habitat », dont les cinq modalités sont "
             "exactement celles de la ventilation publiée). Le trait est donc IMPUTÉ, "
             "et la page doit le dire : make housing-type exporte la loi du type de "
             "logement par zone fine (pondérée par les coefficients de redressement "
             "des PERSONNES — 41,7 % des personnes en individuel isolé contre 34,7 % "
             "des ménages, les foyers en individuel étant plus grands), lissée zone → "
             "secteur de tirage → périmètre parce qu'une zone fine ne compte que 18 "
             "personnes enquêtées en médiane. L'imputation est conditionnée à la zone "
             "fine du domicile via le résolveur de l'action A7 : un tirage indépendant "
             "de la géographie aurait mis des tours en périphérie rurale et faussé "
             "l'axe même qu'on cherche à mesurer. Elle est déterministe (hachage "
             "SHA-256 de l'adresse, pas d'un RNG) et porte sur l'ADRESSE, pour que deux "
             "personas d'un même foyer — 930 personas pour 498 domiciles sur le run — "
             "ne se retrouvent pas l'un en maison et l'autre en tour. Hors couche, rien "
             "n'est deviné : 4,4 % des personas n'ont pas de trait, et la colonne reste "
             "vide. La distribution obtenue est vérifiable : sur la population de "
             "10 000, elle s'écarte de 2,9 points L1 cumulés de la loi de l'enquête, "
             "l'écart résiduel diminuant avec la taille comme du bruit de tirage. Côté "
             "journal, move_logger.py écrit le libellé porté par le persona et vide "
             "quand il n'y en a pas ; les modalités sont déclarées EN UN SEUL POINT "
             "(llm_module/core/housing_type.py), partagé par la génération, le journal "
             "et la page.",
         "reste":
             "L'axe lui-même. Comme pour l'action A9, le changement ne touche que les "
             "runs FUTURS : le moves.csv du run épinglé est déjà écrit, sa colonne est "
             "vide, et la page la relit telle quelle. La ventilation par type de "
             "logement restera donc à zéro jusqu'à ce qu'un nouveau run soit produit et "
             "épinglé. Elle n'a pas été reconstruite à la volée depuis "
             "population_1000.json, et ce n'était pas possible sans tricher : la "
             "population du run ne porte pas le trait (il n'existait pas), le "
             "recalculer à la génération de la page supposerait de rejouer "
             "l'imputation, donc d'exiger deux ressources d'accès restreint (couche de "
             "zones, table du type de logement) au moment de bâtir la page — la page "
             "cesserait d'être reproductible sur un poste sans les données PROGEDO, ce "
             "que l'action A1 a précisément acquis."}},
    {"id": "A3", "title": "Ré-évaluer graine et meilleur prompt sur le jeu commun",
     "detail": "Rejouer deux prompts sur un échantillon du run (viser ~400 décisions) "
               "avec le modèle d'évaluation épinglé, et écrire le résultat au format "
               "décisions attendu par la page.",
     "cost": "175 appels LLM", "unlocks": "Volet 2 dans la comparaison finale",
     "done": "scripts/synthesis/common_set_eval.py (make common-set-eval) a rejoué la "
             "graine 4c2ea894 et la feuille 0fc427e7 sur 509 décisions du run épinglé, "
             "sous le régime épinglé, avec 100 % de couverture (80/80 personnes). "
             "L'échantillon est gelé : tirage PAR PERSONNE sur "
             "sha256(\"common_set_v1:\" + agent_id) % 1000 < 99 — même famille de règle "
             "que les jeux gelés du moteur, mais dans un espace de hachage DISTINCT, "
             "sans quoi l'échantillon aurait été un préfixe de l'intervalle train et "
             "n'aurait contenu que des personas ayant servi à optimiser la lignée. Le "
             "seuil 99 n'est pas rond : c'est le plus petit dont le rapport de "
             "couverture du moteur est propre (à 424 décisions, la tranche 70-74 est "
             "vide et la dimension « âge » ne porterait plus sur le même support que le "
             "volet 1). Le lotissement et le rattrapage sont ceux de l'action A10, non "
             "réécrits : bien leur en a pris, 29 lots sur 128 sont revenus amputés de "
             "personas (jusqu'à 2 rendus sur 8) et ont tous été re-tirés par moitiés — "
             "un découpage maison aurait scoré sur une sous-population sans le dire. "
             "RÉSULTAT : le gain de la lignée se transporte presque à l'identique "
             "(+2,13 points sur le jeu commun contre +2,12 sur les personas gelés), "
             "mais le NIVEAU ne se transporte pas du tout — 38,53 et 36,41 sur le jeu "
             "commun contre 24,35 et 22,24 sur les personas gelés, soit +14,2 points "
             "pour les deux prompts. Une part de ce décalage est un artefact "
             "d'effectif, et elle est désormais chiffrée plutôt que supposée : la "
             "colonne « Sim. (éch. V2) » restreint le volet 1 aux 81 mêmes personnes et "
             "montre que la seule réduction d'effectif coûte +5,02 points (24,37 → "
             "29,39), les divergences par strate étant biaisées vers le haut à petits "
             "effectifs. C'est donc à 29,39 que les colonnes de calibration se "
             "comparent, pas à 24,37 — et le volet 2 reste au-dessus, donc moins fidèle "
             "à l'enquête que la simulation sur son propre substrat. Quota : 175 appels "
             "sur la seconde clé Google (la première était encore épuisée, le seau free "
             "tier se réinitialisant à minuit PACIFIC et non UTC — une sonde de 4 "
             "appels a réussi avant que le compteur ne rattrape, l'application du RPD "
             "n'étant pas exacte à la frontière). La page regroupant les régimes par "
             "modèle · politique et non par clé, le libellé produit reste le régime "
             "épinglé."},
    {"id": "A4", "title": "Évaluer sur le jeu de test gelé",
     "detail": "Aucun nœud du store n'a d'évaluation sur le split test : seuls train et "
               "screen sont peuplés. Le chiffre publiable de la calibration n'existe pas.",
     "cost": "~2 h de quota", "unlocks": "Score de généralisation, volet 2",
     "done": "Le constat était exact et il a été revérifié avant de payer quoi que ce "
             "soit : zéro éval sur « test » dans les deux stores, et les 3 évals « val » "
             "n'existaient que sous mistral-small — donc inutilisables sous le régime "
             "épinglé. scripts/synthesis/heldout_eval.py (make heldout-eval) a mesuré la "
             "lignée ENTIÈRE — 6 nœuds sur 6, pas seulement ses extrémités — sur les 106 "
             "décisions du jeu test, sous gemini-3.1-flash-lite-preview · masse de "
             "probabilité, en déléguant le lotissement et le rattrapage à l'évaluateur du "
             "moteur (défenses de l'action A10) : 7 lots amputés de personas sur 84, tous "
             "re-tirés par moitiés. 98 appels sur la seconde clé Google. "
             "NATURE DE LA GÉNÉRALISATION, établie sur les fichiers et non sur la règle "
             "déclarée : le découpage est PAR PERSONNE — les 66 personnes du test "
             "n'apparaissent dans aucun des 298 personas du train (intersection vide, "
             "vérifiée ; val de même ; screen au contraire entièrement inclus dans le "
             "train, ce qui lui interdit ce rôle). Ce sont donc des individus jamais vus, "
             "pas d'autres trajets des mêmes individus. "
             "RÉSULTAT. Lu brut, l'écart ressemble à du surapprentissage : la graine passe "
             "de 24,35 à 31,60 et la feuille de 22,24 à 24,06. Il n'en est rien, et le "
             "témoin le montre sans un seul appel LLM — rééchantillonner les décisions "
             "train DÉJÀ STOCKÉES à 66 personnes (200 tirages appariés, par personne, "
             "graine fixée) donne 29,84 pour la graine et 26,90 pour la feuille. La seule "
             "réduction d'effectif coûte donc +5,49 et +4,66 points, du même ordre que les "
             "+5,02 mesurés par l'action A3 sur la simulation. À effectif neutralisé la "
             "feuille est MEILLEURE sur le test que sur le train (-2,84), et les six nœuds "
             "tombent dans la bande du témoin : aucun surapprentissage détectable. "
             "Le gain de la lignée survit : +2,12 sur le train, +7,54 sur le test. "
             "L'amplification, elle, n'est PAS démontrée et la page ne la revendique pas — "
             "le témoin apparié du gain vaut +2,94 sur une bande de -1,84 à +8,24, et 7,54 "
             "y tombe. 66 personnes ne permettent pas de trancher plus finement. "
             "UNE CONFUSION RÉSIDUELLE EST PUBLIÉE PLUTÔT QUE TUE : le moteur retire la "
             "section « Historique » (mémoire STM/LTM, non reproductible) des jeux val et "
             "test et la garde dans le train, où elle couvre 86 % des records. Le prompt de "
             "test n'est donc pas seulement adressé à d'autres personnes, il est aussi plus "
             "court d'une section — les deux effets sont mêlés et rien dans les données ne "
             "les sépare. Ces évals ne rejoignent ni la trajectoire, ni la lignée, ni la "
             "matrice de synthèse : le jeu de retenue est un troisième substrat, et l'y "
             "coller rejouerait la confusion que l'action A3 a corrigée."},
    {"id": "A5", "title": "Rejouer une lignée sous un modèle d'évaluation unique",
     "detail": "L'historique mélange mistral-small, gemini-3.1-flash-lite et des imports "
               "hérités. Les niveaux de score ne sont pas comparables entre eux.",
     "cost": "variable", "unlocks": "Trajectoire lisible bout à bout, volet 2",
     "done": "La page distingue les régimes de mesure (modèle ET politique de décision, la "
             "seconde changeant les décisions elles-mêmes) au lieu du seul modèle, et "
             "affiche la lignée épinglée dans sources.yaml : 6 nœuds, de la graine à "
             "0fc427e7. La chaîne est reconstruite par les arêtes de mutation, sans quoi "
             "elle perdait sa graine — le deuxième nœud, dédoublonné depuis la branche "
             "main, a un parent vide. Le rejeu est produit : calibrate reeval a mesuré les "
             "6 nœuds sur le jeu train sous le régime ÉPINGLÉ "
             "(gemini-3.1-flash-lite-preview · masse de probabilité), une fois l'éval "
             "débloquée par l'action A10 ; le repli sur mistral-small-latest · mode élu a "
             "disparu. La lignée se lit maintenant sous DEUX régimes en regard, et ils "
             "s'accordent : la calibration gagne 7,60 points sous l'ancien instrument "
             "(24,9 % du niveau de la graine) et 2,12 sous celui de la production (8,7 %) "
             "— près de trois fois moins en part, mais dans le même sens. Le gain n'est "
             "donc pas un artefact de l'instrument qui a guidé l'optimisation ; son "
             "ampleur, elle, ne se transporte pas d'un régime à l'autre."},
    {"id": "A6", "title": "Entraîner la politique LightGBM PROGEDO",
     "detail": "Le parquet et feature_spec.json existent ; il manque le notebook "
               "d'entraînement et le modèle sérialisé mode_choice_policy.json.",
     "cost": "1 j", "unlocks": "Volet 3",
     "done": "scripts/progedo_logit/fit_mode_choice_policy.py (make policy) entraîne un "
             "booster LightGBM multiclasse sur les 21 variables du spec — pondéré par "
             "les coefficients de redressement de l'enquête, split train/test lu dans le "
             "parquet donc étanche au ménage, arrêt anticipé sur une validation "
             "redécoupée dans le train et jamais sur le test, graine fixée et résultat "
             "reproductible à l'octet. Les trois variables marquées diagnostic_only "
             "(distance_km, crow_km, duration_min) sont refusées par un contrôle "
             "explicite : ce sont elles qui donnaient une PR-AUC marche de 0,985, "
             "c'est-à-dire une fuite. Sur le split test, pondéré : log-loss 0,5363, "
             "accuracy 79,5 %, et 2,1 points d'écart cumulé sur les parts modales en "
             "masse de probabilité (8,7 points en mode élu). L'artefact "
             "mode_choice_policy.json est autoportant — ordre des variables, encodage "
             "des modalités, ordre des classes, version du contrat, métriques, et le "
             "booster sous deux formes (dump_model pour l'évaluateur pur Python, texte "
             "natif pour un rechargement exact) : un consommateur prédit sans relire le "
             "parquet. Le modèle est depuis appliqué au jeu commun (A8), et les écarts "
             "mesurés ici sur le split test se retrouvent sur le run : la masse de "
             "probabilité reste nettement mieux calibrée que le mode élu."},
    {"id": "A7", "title": "Construire le résolveur de zone fine",
     "detail": "Les variables géographiques du modèle (od_km, densités, distances au "
               "centre) exigent un point → zone fine. La couche ZF existe dans les "
               "données PROGEDO mais n'est pas exploitable à l'exécution.",
     "cost": "1 j", "unlocks": "Variables géo du volet 3",
     "done": "llm_module/core/zone_resolver.py rattache un point à sa zone par jointure "
             "point-dans-polygone, et en dérive les six variables géo à la formule de "
             "l'entraînement — distance entre centroïdes, imputation intra-zone — et non "
             "à vol d'oiseau, qui donnait un facteur 2 sur les trajets intra-zone. La "
             "couche servie est exportée en réutilisant le build_geo() du jeu "
             "d'entraînement (make zones), donc identique par construction ; le "
             "résolveur refuse de démarrer si elle et feature_spec.json ne décrivent pas "
             "le même hypercentre. Couverture mesurée sur la population de référence : "
             "95,1 % des paires origine-destination, 95,5 % des localisations ; hors "
             "couche, il renvoie « pas de zone » au lieu de deviner. Le run épinglé, "
             "lui, est intégralement couvert : sa population est un autre tirage que "
             "celle sur laquelle les 95 % ont été mesurés (toulouse_population_1000.json, "
             "4,5 % hors couche), et aucune de ses 11 890 localisations n'échappe au "
             "périmètre d'enquête. Le repli reste posé et testé — il n'a simplement pas "
             "eu à servir sur ce run."},
    {"id": "A8", "title": "Prédire sur le jeu commun et renormaliser sur l'offre OTP",
     "detail": "Appliquer le modèle aux personas du run, en renormalisant sur les modes "
               "réellement proposés par OTP, puis écrire les probabilités attendues.",
     "cost": "1/2 j", "unlocks": "Volet 3 dans la comparaison finale",
     "done": "scripts/synthesis/model_on_common_set.py (make common-set-predict) applique "
             "la politique aux 5 945 décisions du run épinglé — le périmètre du volet 1 "
             "lui-même, construit par le même frames.read_moves et les mêmes exclusions, "
             "sans quoi les colonnes ne seraient pas comparables. Aucun appel LLM, aucun "
             "réseau, résultat déterministe. La correspondance des modes est établie en "
             "UN point et testée : train tombe dans les transports collectifs des deux "
             "côtés, mais le deux-roues motorisé diverge (voiture pour la politique, "
             "« autres » pour la page) — il est donc retiré de l'offre plutôt que compté "
             "comme une offre de voiture, faute de quoi le seul volet 3 verrait sa part "
             "voiture gonflée. La renormalisation sur l'offre OTP n'est pas cosmétique : "
             "96,6 % de la masse prédite tombe en moyenne sur des modes réellement "
             "proposés (médiane 99,8 %, minimum 0,8 %), la correction déplace le mode le "
             "plus probable sur 142 décisions, et rapproche les parts modales de la "
             "référence de 17,9 à 14,1 points d'écart cumulé. Aucune décision n'a été "
             "écartée : les trois causes prévues (zone inconnue, offre sans mode "
             "prédictible, persona introuvable) sont codées et testées, mais la "
             "population de ce run tombe entièrement dans la couche de zones. Deux "
             "lectures sont publiées, comme pour le volet 1 — masse de probabilité "
             "(composite 4,66) et mode élu (5,98) — parce que l'écart entre les deux est "
             "structurel : le modèle n'élit presque jamais le vélo alors qu'il le calibre "
             "bien. Le volet 3 écrase les deux autres (24,37 pour la simulation, 22,92 "
             "pour le meilleur prompt) et c'est attendu : entraîné sur l'enquête qui sert "
             "de cible, il borne ce qu'un modèle statistique atteint. La page le dit au "
             "lecteur au-dessus de la matrice, pas trois sections plus loin. Une surprise "
             "reste ouverte : 919 décisions (15,5 %) n'ont pas de "
             "socioprofessional_class, la population synthétique portant « Retired », "
             "modalité que le recodage de l'enquête ne produit jamais. Elle est rendue "
             "manquante par le contrat du spec plutôt que remappée à l'aveugle — "
             "main_occupation = « Retraité » porte la même information."},
    {"id": "A9", "title": "Unifier l'hypercentre",
     "detail": "43.597347/1.444997 dans feature_spec.json contre 43.6047/1.4442 dans "
               "move_logger.py : 820 m d'écart, qui déplacent les couronnes de résidence.",
     "cost": "15 min", "unlocks": "Cohérence lieu de résidence entre volets 1 et 3",
     "done": "move_logger.py ne déclare plus de centre : il lit celui de "
             "feature_spec.json via llm_module/core/geo_reference.py, unique point de "
             "lecture du bloc geo_reference — le même que celui sur lequel le résolveur "
             "de zone fine (A7) refuse de démarrer en cas de divergence. Le spec étant "
             "produit depuis des données d'accès restreint, son absence est prévue : le "
             "repli est la valeur publiée recopiée en constante, et un test échoue si "
             "les deux se mettent à diverger. Les couronnes de résidence des futurs runs "
             "sont donc mesurées depuis 43.597347/1.444997, comme les dist_center_* du "
             "modèle. Le volet 1 de cette page ne bouge pas pour autant : il relit la "
             "colonne « Lieu de résidence » déjà écrite dans le moves.csv du run "
             "épinglé, calculée sous l'ancien centre."},
    {"id": "A10", "title": "Débloquer l'éval sous la politique pondérée, puis porter la "
                           "lignée sur le modèle épinglé",
     "detail": "La lignée se lit bout à bout (A5), mais sous mistral-small-latest et la "
               "politique « mode élu » — pas sous le modèle qu'utilise la campagne. "
               "calibrate reeval fait la mesure, mais aucune éval n'aboutit : les lots "
               "dépassent le timeout de 240 s de l'adaptateur Google et sont retentés 5 "
               "fois, sans qu'aucune erreur ne remonte. Réduire le lot de 15 à 8 n'a pas "
               "suffi. À instrumenter avant de corriger : tokens de complétion, "
               "finishReason, nombre de décisions rendues. Bloque aussi la boucle — "
               "aucune campagne n'a encore tourné sous cette politique.",
     "cost": "diagnostic + ~372 appels", "unlocks": "Trajectoire sous le modèle de "
                                                    "production, et reprise de la campagne",
     "done": "Le diagnostic a écarté la cause supposée. Instrumenté sur des lots réels : "
             "3,6 à 8,8 s par appel pour un timeout de 240 s, finishReason=STOP partout, "
             "2 742 tokens de complétion au pire pour un plafond de 4 096 — ni lenteur, ni "
             "troncature. Le défaut est que le modèle rend un JSON valide et conforme mais "
             "AMPUTÉ de personas : 4 lots sur 12 à 15 personas n'ont rendu que 5 à 8 "
             "décisions sur 15, soit 18 % de la population perdue. Aucune défense ne "
             "pouvait le voir — ni erreur HTTP, ni troncature, ni schéma invalide : le lot "
             "passait pour un succès et l'éval était mise en cache sur une sous-population. "
             "Trois défenses posées : comparaison des personas envoyés aux décisions rendues "
             "à chaque requête ; re-tir du lot incomplet par moitiés (redemander à "
             "l'identique en décodage déterministe redonne la même réponse — il faut réduire "
             "la demande) ; refus de mettre en cache une éval sous le plancher de couverture, "
             "la base ne gardant pas le nombre de personas vus. L'échec silencieux proprement "
             "dit est refermé : la boucle de retry rendait une liste vide en s'épuisant, elle "
             "lève désormais avec une [ALARME]. Réduire le lot atténue sans régler — à 8 "
             "personas, 40 lots sur 372 sont encore revenus incomplets, jusqu'à 1 persona "
             "rendu sur 8, tous rattrapés. La lignée est mesurée : 6 nœuds sur 6 sous "
             "gemini-3.1-flash-lite-preview · masse de probabilité, 432 appels (+16 % de "
             "re-tirs), sur la seconde clé Google — le quota journalier de la première étant "
             "épuisé, et la page regroupant les régimes par modèle · politique, pas par clé. "
             "La campagne peut reprendre sous cette politique, ce qu'aucune n'avait fait."},
]

SCORE_DIMS = [
    ("global", "toutes", "JSD inter-modes (×100)", "global",
     "Part modale de la population entière."),
    ("absent_penalty", "toutes", "5 × part cible du mode oublié", "absent_penalty",
     "Sanctionne un mode auquel plus personne n'accorde la moindre chance."),
    ("age", "ordinale", "EMD le long de l'axe des 15 tranches", "age",
     "Déplacer une préférence vers une tranche voisine coûte moins cher que vers une tranche lointaine."),
    ("occupation", "nominale", "JSD pondérée par effectif", "occupation",
     "7 modalités, de scolaire à retraité."),
    ("genre", "nominale", "JSD pondérée par effectif", "genre", "Homme / femme."),
    ("motif", "nominale", "JSD pondérée par effectif", "motif",
     "Travail, études, achats. Accompagnement n'est jamais produit par la simulation."),
    ("distance", "ordinale", "EMD le long des 7 tranches", "distance",
     "De moins d'1 km à plus de 50 km."),
    ("length_penalty", "prompt", "neutralisée ici", "length_penalty",
     "Sans objet hors du volet calibration : poids ramené à 0."),
]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y à %H:%M")


def build_score_def(manifest, weights: dict) -> dict:
    dims = [{"dim": key, "kind": kind, "metric": metric, "weight": weights.get(wkey, 0.0),
             "note": note} for key, kind, metric, wkey, note in SCORE_DIMS]
    return {
        "dimensions": dims,
        "primary": manifest.get("score.metric", "emd_jsd"),
        "secondary": manifest.get("score.secondary", "l1_composite"),
        "engine": "prompt_calibration/calibration/metrics.py",
        "cerema_note": (
            "La référence couvre huit axes : global, âge, occupation, genre, motif, "
            "distance, lieu de résidence et type de logement. Les six premiers entrent "
            "dans le composite ; les deux derniers sont affichés hors score. Le type de "
            "logement est produit depuis l'action A2, mais il est IMPUTÉ — aucune "
            "source de la chaîne de génération ne le porte, il est tiré dans la loi que "
            "l'enquête observe dans la zone fine du domicile — et le run épinglé, "
            "antérieur, ne le porte pas encore. Les modes « autres » et « deux-roues "
            "motorisé » sont exclus et les quatre modes restants renormalisés à 100 %."),
    }


def build_common_set(manifest, cerema: dict) -> tuple[dict, list[dict]]:
    run = frames.resolve_run(manifest)
    if not run.get("exists") or not run.get("moves", {}).get("exists"):
        return {"available": False,
                "reason": "Le run configuré est introuvable, ou il ne contient pas de "
                          "moves.csv exploitable.",
                "expected": [str(manifest.get("common_set.run")) + "/moves.csv"]}, []

    moves_path = REPO_ROOT / run["moves"]["path"]
    rows, stats = frames.read_moves(
        moves_path, manifest.get("common_set.exclude_selection_methods", []))
    warnings = []
    if stats.get("occupation_inconnue"):
        warnings.append(f"{stats['occupation_inconnue']} trajets portent une occupation "
                        "hors du référentiel EMC² : exclus de la dimension occupation.")
    # Le journal renseigne la colonne depuis l'action A2, mais le run épinglé peut lui
    # être antérieur : l'avertissement doit dire lequel des deux cas on lit, sans quoi
    # il reprocherait au journal un vide qui vient de la date du run.
    vides = stats.get("type_logement_vide", 0)
    if vides and vides == len(rows):
        warnings.append("Le type de logement est vide sur la totalité des trajets. Le "
                        "journal de déplacements renseigne désormais cette colonne "
                        "(action A2) et la population porte le trait, mais le run "
                        "épinglé a été écrit avant : l'axe se remplira au prochain run "
                        "épinglé, pas sur celui-ci.")
    elif vides:
        warnings.append(f"{vides} trajets sans type de logement : le domicile tombe "
                        "hors de la couche de zones fines, où le trait n'est pas imputé "
                        "(« non renseigné » n'est pas une modalité).")
    if stats.get("type_logement_hors_referentiel"):
        warnings.append(f"{stats['type_logement_hors_referentiel']} trajets portent un "
                        "type de logement « Autres » : l'enquête connaît cette modalité, "
                        "la ventilation EMC² publiée ne la reprend pas — ces trajets "
                        "sortent de la dimension type de logement.")
    if stats.get("sans_distribution"):
        warnings.append(f"{stats['sans_distribution']} trajets sans distribution de "
                        "probabilité (erreur LLM, itinéraire unique ou entrée de cache "
                        "héritée) : le mode retenu leur sert de masse.")
    if not run.get("population", {}).get("exists"):
        warnings.append("Le fichier de population du run est introuvable : le volet "
                        "modèle ne pourra pas reconstruire ses variables.")

    n_persons = len({r["agent_id"] for r in rows})
    total = max(1, len(rows))
    # Un chemin configuré qui se résout ailleurs est un symlink : la page ne décrit
    # alors pas un run stable, et le dire vaut mieux que le taire (action A1).
    configured = str(run.get("configured", ""))
    resolved = run.get("path", "")
    common = {
        "available": True,
        "run_id": run.get("run_id", "?"),
        "run_path": resolved,
        "run_pinned": bool(resolved) and configured.rstrip("/") == resolved.rstrip("/"),
        "run_date": (run.get("moves", {}).get("mtime") or "")[:10],
        "n_trips": len(rows),
        "n_persons": n_persons,
        "pct_distribution": 100.0 * stats.get("avec_distribution", 0) / total,
        "stats": stats,
        "warnings": warnings,
        "coverage": {},
    }
    return common, rows


def build_simulation(rows: list[dict], cerema: dict, scorer) -> dict:
    if not rows:
        return {"status": "missing",
                "reason": "Aucun trajet exploitable dans le run.",
                "expected": [],
                "action": "Vérifier common_set.run dans sources.yaml"}
    variants = frames.simulation_frames(rows)
    out: dict[str, Any] = {"status": "ok", "variants": {}}
    details: dict[str, list[dict]] = {}
    for name, frame in variants.items():
        gview = frames.global_view(frame, cerema)
        scores = scorer.score(frame, cerema) if scorer else {}
        out["variants"][name] = {"global": gview, "scores": scores,
                                 "n_rows": len(frame)}
    expected = variants["attendu"]
    for dim in DIMENSIONS:
        detail = frames.dimension_detail(expected, cerema, dim)
        if any(d["n"] for d in detail):
            details[dim["key"]] = detail
    out["details"] = details
    out["worst_strata"] = frames.worst_strata(
        {k: v for k, v in details.items()
         if any(d["key"] == k and d["scored"] for d in DIMENSIONS)})
    gv = out["variants"]["attendu"]["global"]
    total_mass = gv["mass"] + gv["excluded_mass"]
    out["excluded_pct"] = 100.0 * gv["excluded_mass"] / total_mass if total_mass else 0.0
    return out


def build_lineage(history: dict, by_regime: dict, pinned: dict) -> Optional[dict]:
    """Trajectoire d'une lignée entière mesurée sous un régime unique (action A5).

    Une courbe chronologique mélange des branches et des nœuds sans parenté : elle
    dit « le store contient des scores », pas « la calibration a progressé ». Une
    **lignée** — la chaîne seed → feuille des mutations acceptées — le dit, à la
    condition que tous ses nœuds soient mesurés sous le même régime.

    La feuille est **épinglée dans le manifeste**, pour la même raison que le run
    du jeu commun : une reconstruction automatique (« la plus longue chaîne
    disponible ») changerait de sujet à chaque campagne, sans que la page le
    signale. Un nœud manquant n'est pas masqué : il apparaît sans score, et la
    lignée est déclarée incomplète.
    """
    leaf = (pinned or {}).get("leaf")
    if not leaf:
        return None
    parents = {n["hash"]: n.get("parent") for n in history["nodes"]}
    chain = frames.lineage_chain(leaf, parents, history.get("edges", {}))
    if len(chain) < 2:
        return None

    def measured(bucket: dict) -> dict:
        """Mesure de la lignée sous un régime : un score par nœud de la chaîne."""
        by_hash = {n["hash"]: n for n in bucket["nodes"]}
        steps = [{"short": h[:8], "score": (by_hash.get(h) or {}).get("recomputed"),
                  "branch": (by_hash.get(h) or {}).get("branch", "—")} for h in chain]
        scored = [s for s in steps if s["score"] is not None]
        return {
            "label": bucket["label"], "steps": steps,
            # Provenance : les clés de cache réellement traversées. Plusieurs clés
            # pour un même régime = plusieurs providers (donc plusieurs clés d'API)
            # sur le même modèle — la mesure est la même, la trace le dit.
            "params_keys": sorted(bucket.get("keys") or ()),
            "n_scored": len(scored), "complete": len(scored) == len(chain),
            "seed_score": scored[0]["score"] if scored else None,
            "leaf_score": scored[-1]["score"] if scored else None,
            "gain": (scored[0]["score"] - scored[-1]["score"]) if len(scored) >= 2 else None,
        }

    # Un régime ne dit quelque chose de la lignée qu'à partir de deux nœuds mesurés.
    regimes = [m for m in (measured(b) for b in by_regime.values()) if m["n_scored"] >= 2]
    if not regimes:
        return None

    # Régime principal : celui demandé par le manifeste s'il couvre la lignée,
    # sinon le mieux couvrant. Les autres restent affichés en regard — la même
    # lignée mesurée par deux instruments dit si le gain tient à l'instrument.
    wanted = (pinned or {}).get("regime")
    primary = next((m for m in regimes if m["label"] == wanted), None)
    if primary is None:
        primary = max(regimes, key=lambda m: m["n_scored"])
    others = [m for m in regimes if m is not primary]
    others.sort(key=lambda m: -m["n_scored"])
    return {
        **primary,
        "leaf": leaf[:8],
        "n_nodes": len(chain),
        "pinned_regime": wanted,
        "is_pinned": bool(wanted) and primary["label"] == wanted,
        "regimes": [primary] + others,
    }


def sample_predicate(sample: dict):
    """Reconstruit le filtre d'échantillonnage décrit par le fichier de mesure.

    Le descriptif (namespace, modulo, seuil) est écrit DANS le fichier produit :
    la page rejoue donc la règle telle qu'elle a servi, et non une constante
    recopiée qui pourrait diverger. Repli sur les constantes du producteur quand
    le descriptif est incomplet (fichier d'une version antérieure).
    """
    from .common_set_eval import (SAMPLE_BUCKET_MAX, SAMPLE_MODULUS,
                                  SAMPLE_NAMESPACE)
    # Repli sur `is None` et non sur la véracité : un seuil de 0 est une valeur
    # LÉGITIME (échantillon vide), et `0 or défaut` la remplacerait silencieusement
    # par le seuil courant — la page décrirait alors un autre échantillon que celui
    # qui a été mesuré.
    sample = sample or {}
    namespace = sample.get("namespace")
    namespace = SAMPLE_NAMESPACE if namespace is None else str(namespace)
    modulus = sample.get("modulus")
    modulus = SAMPLE_MODULUS if modulus is None else int(modulus)
    bucket_max = sample.get("bucket_max")
    bucket_max = SAMPLE_BUCKET_MAX if bucket_max is None else int(bucket_max)
    if modulus <= 0:
        raise ValueError(f"Modulo d'échantillonnage invalide : {modulus}")

    def keep(agent_id: str) -> bool:
        digest = hashlib.sha256(f"{namespace}:{agent_id}".encode()).hexdigest()
        return int(digest, 16) % modulus < bucket_max

    return keep


def build_simulation_on_sample(rows: list[dict], cerema: dict, scorer,
                               sample: dict) -> Optional[dict]:
    """Le volet 1 restreint à l'échantillon du volet 2 — le témoin de taille.

    Sans lui, la matrice oppose une colonne calculée sur 5 945 décisions à des
    colonnes calculées sur ~500, et attribue au prompt un écart qui vient en
    bonne partie du nombre de personnes observées : les divergences par strate
    (JSD, EMD) sont biaisées vers le haut quand les effectifs sont petits, et
    l'effet est loin d'être négligeable — MESURÉ sur ce run, +5,02 points de
    composite pour la seule réduction de 881 personnes à 81, à décisions
    inchangées.

    Cette ligne est donc le point de comparaison honnête du volet 2 : même run,
    mêmes personnes, même loss. Elle ne remplace pas la ligne « Simulation »,
    qui reste la mesure de référence sur le run entier ; elle dit de combien il
    faut corriger la lecture avant d'attribuer un écart au prompt.
    """
    if not rows or scorer is None or not sample:
        return None
    keep = sample_predicate(sample)
    subset = [r for r in rows if keep(r["agent_id"])]
    if not subset:
        return None
    frame = frames.simulation_frames(subset)["attendu"]
    scores = scorer.score(frame, cerema)
    dims = scores.get(scorer.primary.name, {}) if scores else {}
    return {
        "dims": dims,
        "composite": dims.get("composite"),
        "n_trips": len(subset),
        "n_persons": len({r["agent_id"] for r in subset}),
    }


def build_common_set_eval(source, cerema: dict, scorer,
                          nodes_table: list[dict]) -> dict:
    """Prompts ré-évalués sur le jeu commun (action A3), scorés comme le reste.

    C'est ce qui rend le volet 2 commensurable au volet 1 : les mêmes personas, le
    même run, la même loss et les mêmes poids que partout ailleurs sur la page
    (``length_penalty`` à 0). Rien n'est recalculé de travers ici — le score sort
    du même ``Scorer`` que la simulation.

    Chaque prompt porte AUSSI son score sur les personas gelés, sous le même régime
    de mesure quand il existe. Ce sont deux chiffres différents, et la page doit
    dire lequel elle affiche : le premier répond « où en est la calibration sur le
    run », le second « où en était-elle sur son propre jeu d'entraînement ».

    Source absente → ``{"available": False}`` : la page affiche sa carte « Données
    manquantes » et se génère normalement (cas d'un clone sans les données).
    """
    if not source.exists or scorer is None:
        return {"available": False}
    entries = frames.load_common_set_eval(source.path)
    if not entries:
        return {"available": False}

    # Score du même nœud sur les personas gelés, sous le même régime : c'est le
    # point de comparaison qui dit si le gain de la calibration se transporte.
    frozen = {(r["short"], r["regime"]): r for r in nodes_table
              if r.get("recomputed") is not None}

    out = []
    for entry in entries:
        scores = scorer.score(entry["rows"], cerema)
        dims = scores.get(scorer.primary.name, {}) if scores else {}
        regime = (entry.get("regime") or {}).get("label")
        ref = frozen.get((entry.get("short"), regime))
        out.append({
            "role": entry.get("role"), "label": entry.get("label"),
            "short": entry.get("short"), "node": entry.get("node"),
            "branch": entry.get("branch"),
            "regime": regime,
            "regime_detail": entry.get("regime") or {},
            "sample": entry.get("sample") or {},
            "coverage": entry.get("coverage"),
            "n_decisions": entry.get("n_decisions"),
            "created_at": entry.get("created_at"),
            "dims": dims,
            "composite": dims.get("composite"),
            "secondary": scores.get(scorer.secondary.name, {}).get("composite")
            if (scorer.secondary and scores) else None,
            "frozen_composite": (ref or {}).get("recomputed"),
            "frozen_regime": regime if ref else None,
        })

    seed = next((e for e in out if e["role"] == "seed"), None)
    leaf = next((e for e in out if e["role"] == "leaf"), None)
    gain = None
    if seed and leaf and seed["composite"] is not None and leaf["composite"] is not None:
        gain = seed["composite"] - leaf["composite"]
    frozen_gain = None
    if seed and leaf and seed["frozen_composite"] is not None \
            and leaf["frozen_composite"] is not None:
        frozen_gain = seed["frozen_composite"] - leaf["frozen_composite"]
    sample = (out[0].get("sample") or {}) if out else {}
    # Une mesure faite sous deux régimes différents ne se lit pas d'un bloc : on le
    # signale plutôt que de laisser croire à une trajectoire.
    regimes = {e["regime"] for e in out if e["regime"]}
    return {
        "available": True,
        "entries": out,
        "seed": seed, "leaf": leaf,
        "gain": gain, "frozen_gain": frozen_gain,
        "sample": sample,
        "regime": sorted(regimes)[0] if len(regimes) == 1 else None,
        "mixed_regimes": len(regimes) > 1,
        "path": source.rel,
    }


def resample_composite(rows: list[dict], cerema: dict, scorer, n_agents: int,
                       n_draws: int = 200, seed: int = 20260731) -> Optional[dict]:
    """Distribution du composite d'une trame ramenée à ``n_agents`` personnes.

    C'est le témoin d'effectif du volet 2, et il ne coûte aucun appel LLM : on
    rejoue le score des décisions **déjà stockées**, sur des sous-ensembles de
    personnes tirés au hasard. Le tirage est PAR PERSONNE — toutes les décisions
    d'une personne retenue sont conservées — parce que c'est le nombre de
    personnes par strate qui biaise JSD et EMD, pas le nombre de lignes.

    Pourquoi il est indispensable ici : le jeu ``train`` porte 298 personnes, le
    jeu ``test`` 66. A3 a mesuré, sur la simulation et à décisions inchangées,
    +5,02 points de composite pour la seule réduction de 881 personnes à 81. Un
    écart train → test lu brut confondrait donc le surapprentissage avec l'effet
    d'effectif, et publierait précisément le chiffre trompeur que l'action A4
    prétend produire.

    La graine est fixée : la page se régénère à l'identique. ``None`` si la trame
    n'a pas assez de personnes pour que le tirage ait un sens.
    """
    if not rows or scorer is None or n_agents <= 0:
        return None
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_agent[str(row.get("agent_id"))].append(row)
    agents = sorted(by_agent)
    if len(agents) <= n_agents:
        return None
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(n_draws):
        picked = rng.sample(agents, n_agents)
        subset = [r for a in picked for r in by_agent[a]]
        scores = scorer.score(subset, cerema)
        composite = scores.get(scorer.primary.name, {}).get("composite")
        if composite is not None:
            values.append(composite)
    if not values:
        return None
    values.sort()

    def quantile(q: float) -> float:
        return values[min(len(values) - 1, max(0, int(round(q * (len(values) - 1)))))]

    return {
        "n_agents": n_agents, "n_draws": len(values),
        "n_agents_source": len(agents),
        "mean": sum(values) / len(values),
        "p05": quantile(0.05), "median": quantile(0.50), "p95": quantile(0.95),
        "seed": seed,
    }


def resample_gain(frame_a: list[dict], frame_b: list[dict], cerema: dict, scorer,
                  n_agents: int, n_draws: int = 200,
                  seed: int = 20260731) -> Optional[dict]:
    """Distribution du **gain** graine → feuille à l'effectif du jeu de retenue.

    Le témoin par nœud (``resample_composite``) est bruyant : rééchantillonner 66
    personnes parmi 298 fait bouger le composite de ±7 points, si bien qu'aucun
    écart de niveau ne ressort de la bande. Le *gain*, lui, est **apparié** — les
    deux prompts sont scorés sur les **mêmes** personnes tirées — et son bruit se
    compense en grande partie. C'est donc la quantité sur laquelle une conclusion
    de généralisation peut effectivement s'appuyer.

    Les deux trames doivent porter les mêmes personnes (deux évals du même jeu
    gelé) : sinon les tirages ne seraient plus appariés et la comparaison
    perdrait ce qui fait son intérêt. On l'exige plutôt que de l'espérer.
    """
    if not frame_a or not frame_b or scorer is None or n_agents <= 0:
        return None
    a_by_agent: dict[str, list[dict]] = defaultdict(list)
    b_by_agent: dict[str, list[dict]] = defaultdict(list)
    for row in frame_a:
        a_by_agent[str(row.get("agent_id"))].append(row)
    for row in frame_b:
        b_by_agent[str(row.get("agent_id"))].append(row)
    agents = sorted(set(a_by_agent) & set(b_by_agent))
    if len(agents) <= n_agents:
        return None
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(n_draws):
        picked = rng.sample(agents, n_agents)
        sa = scorer.score([r for p in picked for r in a_by_agent[p]], cerema)
        sb = scorer.score([r for p in picked for r in b_by_agent[p]], cerema)
        ca = sa.get(scorer.primary.name, {}).get("composite")
        cb = sb.get(scorer.primary.name, {}).get("composite")
        if ca is not None and cb is not None:
            values.append(ca - cb)
    if not values:
        return None
    values.sort()

    def quantile(q: float) -> float:
        return values[min(len(values) - 1, max(0, int(round(q * (len(values) - 1)))))]

    return {
        "n_agents": n_agents, "n_draws": len(values),
        "n_agents_paired": len(agents),
        "mean": sum(values) / len(values),
        "p05": quantile(0.05), "median": quantile(0.50), "p95": quantile(0.95),
        "seed": seed,
    }


def build_generalization(chain: list[str], by_key: dict, frames_by_key: dict,
                         cerema: dict, scorer, profile: dict,
                         regime: Optional[str], split_rule: Optional[str],
                         heldout_dataset: str = "test",
                         n_draws: int = 200) -> Optional[dict]:
    """Le score de la calibration sur un jeu que la boucle n'a jamais vu (action A4).

    Tout le reste du volet 2 est mesuré sur ``train`` — le jeu sur lequel la
    lignée a été *optimisée*. Un composite d'entraînement ne distingue pas un
    prompt qui a compris la population d'un prompt qui a mémorisé ses 298
    personas. Ce bloc apporte le chiffre manquant, et les deux garde-fous sans
    lesquels il serait trompeur :

    1. **Le témoin d'effectif** (``resample_composite``). Les deux jeux n'ont pas
       la même taille : comparer leurs niveaux bruts attribuerait au prompt un
       écart qui vient en bonne partie du nombre de personnes observées.
    2. **La nature du découpage** (``profile``, établi sur pièces par
       ``heldout_eval.dataset_profile``). Un découpage par personne et un
       découpage par déplacement ne soutiennent pas la même affirmation : le
       premier dit « des individus jamais vus », le second seulement « d'autres
       trajets des mêmes individus ». La page doit dire lequel c'est.

    Renvoie ``None`` tant qu'aucun nœud n'est mesuré des deux côtés : la page
    affiche alors sa carte « Données manquantes » plutôt qu'une demi-mesure.
    """
    if not chain or not regime:
        return None
    held = profile.get(heldout_dataset) or {}
    n_agents_held = held.get("n_agents") or 0

    steps = []
    for rank, node_hash in enumerate(chain):
        short = node_hash[:8]
        train_row = by_key.get((short, regime, "train"))
        held_row = by_key.get((short, regime, heldout_dataset))
        if train_row is None and held_row is None:
            continue
        control = None
        train_frame = frames_by_key.get((short, regime, "train"))
        if train_frame and n_agents_held:
            control = resample_composite(train_frame, cerema, scorer,
                                         n_agents_held, n_draws=n_draws)
        if rank == 0:
            role, label = "seed", "Graine"
        elif rank == len(chain) - 1:
            role, label = "leaf", "Meilleur prompt"
        else:
            role, label = "step", f"Étape {rank}"
        train_score = (train_row or {}).get("recomputed")
        held_score = (held_row or {}).get("recomputed")
        steps.append({
            "short": short, "role": role, "label": label, "rank": rank,
            "branch": (train_row or held_row or {}).get("branch", "—"),
            "train": train_score,
            "held": held_score,
            "held_dims": (held_row or {}).get("dims") or {},
            "train_dims": (train_row or {}).get("dims") or {},
            # Écart BRUT : affiché, mais jamais seul — il mêle l'effet d'effectif
            # et ce qui pourrait être du surapprentissage.
            "gap_raw": (held_score - train_score)
            if (held_score is not None and train_score is not None) else None,
            "control": control,
            # Écart CORRIGÉ : le test comparé au train ramené à l'effectif du test.
            # C'est le seul des deux qui parle du prompt.
            "gap_controlled": (held_score - control["mean"])
            if (held_score is not None and control) else None,
            "within_control": (control["p05"] <= held_score <= control["p95"])
            if (held_score is not None and control) else None,
        })
    measured = [s for s in steps if s["held"] is not None]
    if not measured:
        return None

    seed_step = next((s for s in steps if s["role"] == "seed"), None)
    leaf_step = next((s for s in steps if s["role"] == "leaf"), None)

    def gain(field: str) -> Optional[float]:
        if not (seed_step and leaf_step):
            return None
        a, b = seed_step.get(field), leaf_step.get(field)
        return (a - b) if (a is not None and b is not None) else None

    # Témoin du GAIN, apparié : c'est lui qui porte la conclusion, le témoin par
    # nœud étant trop bruyant pour trancher (cf. resample_gain).
    gain_control = None
    if seed_step and leaf_step and n_agents_held:
        gain_control = resample_gain(
            frames_by_key.get((seed_step["short"], regime, "train")) or [],
            frames_by_key.get((leaf_step["short"], regime, "train")) or [],
            cerema, scorer, n_agents_held, n_draws=n_draws)

    # Le découpage est-il par personne ? Établi sur les fichiers eux-mêmes, pas
    # sur la foi de la règle déclarée dans le manifeste des jeux gelés.
    shared = held.get("agents_shared_with_train")
    by_person = shared == 0
    return {
        "gain_control": gain_control,
        "available": True,
        "dataset": heldout_dataset,
        "regime": regime,
        "split_rule": split_rule,
        "profile": profile,
        "n_records": held.get("n_records"),
        "n_agents": n_agents_held,
        "train_records": (profile.get("train") or {}).get("n_records"),
        "train_agents": (profile.get("train") or {}).get("n_agents"),
        "agents_shared_with_train": shared,
        "by_person": by_person,
        # Différence de FORME d'entrée entre les deux jeux, et non de population :
        # `calibration.datasets` retire la section « Historique » de val et test
        # (mémoire STM/LTM du run source, non reproductible) et la garde dans le
        # train. Le prompt de test n'est donc pas seulement adressé à d'autres
        # personnes, il est plus court d'une section.
        "memory_train": (profile.get("train") or {}).get("memory_share"),
        "memory_held": held.get("memory_share"),
        "steps": steps,
        "seed": seed_step, "leaf": leaf_step,
        "n_measured": len(measured), "n_nodes": len(chain),
        "complete": len(measured) == len(chain),
        "gain_train": gain("train"),
        "gain_held": gain("held"),
    }


def build_calibration(manifest, cerema: dict, scorer) -> dict:
    repo = manifest.get("arms.calibration.repo", "prompt_calibration")
    dataset_dir = manifest.path_of("arms.calibration.datasets")
    manifest.track("calibration.datasets", dataset_dir or "prompt_calibration/calibration_datasets/v1",
                   "Jeux de personas gelés (train/val/test/screen)")
    metadata = frames.load_dataset_metadata(dataset_dir) if dataset_dir and dataset_dir.exists() else {}
    if not metadata:
        return {"status": "missing",
                "reason": "Les jeux de personas gelés sont introuvables : impossible de "
                          "rattacher les décisions stockées à leurs attributs.",
                "expected": [f"{repo}/calibration_datasets/v1/*.jsonl"],
                "action": "Reconstruire les jeux (calibrate datasets)"}

    keep = manifest.get("arms.calibration.keep_verdicts", ["accepted", "imported"])
    stores_out = []
    nodes_table: list[dict] = []
    eval_models: set[str] = set()
    # Nœuds mesurés sur un jeu **de retenue** (val/test), indexés par
    # (nœud, régime, jeu). Ils ne rejoignent pas `nodes_table` — la trajectoire et
    # la lignée du volet 2 se lisent sur le train, et y mêler un autre jeu
    # superposerait deux populations dans la même courbe. Ils servent au bloc de
    # généralisation, qui les oppose explicitement.
    by_key: dict[tuple, dict] = {}
    # Trames de décision correspondantes : gardées HORS du payload (elles pèsent
    # des milliers de lignes) et consommées seulement par le témoin d'effectif.
    frames_by_key: dict[tuple, list] = {}
    lineage_chain_full: list[str] = []

    for entry in manifest.get("arms.calibration.stores", []) or []:
        src = manifest.track(f"calibration.store.{entry['id']}", entry["path"],
                             f"Store de calibration — {entry.get('label', entry['id'])}")
        if not src.exists:
            stores_out.append({"id": entry["id"], "label": entry.get("label", entry["id"]),
                               "totals": {"nodes": 0, "mutations": 0, "evals": 0},
                               "kept": 0, "eval_models": [], "series": []})
            continue
        history = frames.read_store_history(src.path, keep)
        by_regime: dict[str, dict] = {}
        scored_nodes: list[dict] = []
        seen: set[tuple] = set()
        for node in history["nodes"]:
            # Un même nœud peut porter plusieurs évals (rejeux, params_key
            # distincts) : on ne garde qu'une ligne par couple nœud × jeu × régime.
            key = (node["short"], node["dataset"], node["eval_model"],
                   node["params_key"])
            if key in seen:
                continue
            seen.add(key)
            frame = frames.decisions_frame(node["decisions"], metadata, scorer.categorize) \
                if scorer else []
            scores = scorer.score(frame, cerema) if (frame and scorer) else {}
            recomputed = scores.get(scorer.primary.name, {}).get("composite") \
                if scorer and scores else None
            regime = frames.eval_regime(node["params_key"], node["eval_model"])
            row = {**{k: node[k] for k in
                      ("hash", "short", "branch", "created_at", "verdict", "eval_model")},
                   "store": entry.get("label", entry["id"]),
                   "dataset": node["dataset"],
                   "regime": regime["label"], "regime_key": regime["key"],
                   "recomputed": recomputed,
                   "stored": node["stored_scores"].get("composite"),
                   "dims": scores.get(scorer.primary.name, {}) if scorer else {}}
            # Indexé pour le bloc de généralisation, tous jeux confondus. La
            # première mesure gagne : les stores sont parcourus du plus ancien au
            # plus fourni, et un doublon rapatrié du cloud porte les mêmes
            # décisions.
            by_key.setdefault((node["short"], regime["label"], node["dataset"]), row)
            frames_by_key.setdefault(
                (node["short"], regime["label"], node["dataset"]), frame)
            if node["dataset"] != "train":
                continue
            eval_models.add(regime["label"])
            nodes_table.append(row)
            if recomputed is not None:
                scored_nodes.append(row)
                # Regroupement par LIBELLÉ (modèle · politique) et non par
                # `params_key` brute : celle-ci porte aussi le nom du provider, donc
                # la clé d'API utilisée. Deux clés sur le même modèle interrogent le
                # même modèle — c'est un seul régime de mesure, et un rejeu terminé
                # sur la seconde clé (quota de la première épuisé) doit rester une
                # seule courbe.
                bucket = by_regime.setdefault(
                    regime["label"], {"label": regime["label"], "points": [],
                                      "nodes": [], "keys": set()})
                bucket["keys"].add(regime["key"])
                bucket["points"].append(
                    {"score": recomputed,
                     "label": f'{node["short"]} · {node["branch"]}'})
                bucket["nodes"].append(row)
        series = [{"label": b["label"], "points": b["points"]}
                  for b in by_regime.values() if b["points"]]

        # Graine et meilleur nœud sont pris DANS UN SEUL régime — le plus fourni.
        # Les comparer d'un régime à l'autre reviendrait à opposer deux instruments
        # de mesure : c'est précisément ce que l'action A5 corrige.
        ref = max(by_regime.values(), key=lambda b: len(b["nodes"])) if by_regime else None
        ref_nodes = ref["nodes"] if ref else []
        seeds = [n for n in ref_nodes if n["verdict"] == "seed"]
        best = min(ref_nodes, key=lambda n: n["recomputed"]) if ref_nodes else None
        pinned_lineage = manifest.get("arms.calibration.lineage") or {}
        lineage = build_lineage(history, by_regime, pinned_lineage)
        if pinned_lineage.get("leaf") and not lineage_chain_full:
            candidate = frames.lineage_chain(
                pinned_lineage["leaf"],
                {n["hash"]: n.get("parent") for n in history["nodes"]},
                history.get("edges", {}))
            if len(candidate) > 1:
                lineage_chain_full = candidate
        stores_out.append({
            "id": entry["id"], "label": entry.get("label", entry["id"]),
            "totals": history["totals"],
            "kept": len(scored_nodes),
            "hashes": sorted({n["short"] for n in scored_nodes}),
            "eval_models": sorted({b["label"] for b in by_regime.values()}),
            "reference_regime": ref["label"] if ref else None,
            "series": series,
            "lineage": lineage,
            "seed": min(seeds, key=lambda n: n["created_at"] or "") if seeds else None,
            "best": best,
            "span": ([round(min(n["recomputed"] for n in ref_nodes), 2),
                      round(max(n["recomputed"] for n in ref_nodes), 2)]
                     if ref_nodes else None),
        })

    prompts_path = manifest.path_of("arms.calibration.prompts_yaml")
    src = manifest.track("calibration.prompts", prompts_path or "llm_module/prompts/prompts.yaml",
                         "Variantes de prompt livrées à la simulation")
    variants = frames.read_prompt_variants(src.path) if src.exists else {}

    common_eval = manifest.track(
        "calibration.common_set_eval",
        manifest.get("arms.calibration.common_set_eval"),
        "Décisions des prompts ré-évalués sur le jeu commun")
    common_set = build_common_set_eval(common_eval, cerema, scorer, nodes_table)

    # ── Généralisation : le jeu que la boucle n'a jamais vu (action A4) ──────
    # Le régime est celui épinglé par le manifeste. Ne pas retomber sur « le
    # régime le mieux couvrant » : un score de test lu sous un instrument et un
    # score d'entraînement lu sous un autre ne se soustraient pas.
    pinned = manifest.get("arms.calibration.lineage") or {}
    heldout_dataset = manifest.get("arms.calibration.heldout_dataset", "test")
    profile = heldout_eval.dataset_profile(dataset_dir) if dataset_dir else {}
    generalization = build_generalization(
        lineage_chain_full, by_key, frames_by_key, cerema, scorer, profile,
        pinned.get("regime"), heldout_eval.split_rule(dataset_dir) if dataset_dir else None,
        heldout_dataset)
    if generalization is None:
        generalization = {
            "available": False,
            "dataset": heldout_dataset,
            "regime": pinned.get("regime"),
            "profile": profile,
            "reason": f"Aucun nœud de la lignée épinglée n'est évalué sur le jeu "
                      f"« {heldout_dataset} » sous le régime "
                      f"{pinned.get('regime') or 'épinglé'} : la calibration n'a de "
                      f"score que sur le jeu qui a servi à l'optimiser.",
            "action": f"make heldout-eval PROVIDER=google2 "
                      f"(chiffrer d'abord : make heldout-eval DRY_RUN=1)",
        }

    # Le store cloud est régulièrement rapatrié dans le store local : tracer les
    # deux trajectoires donnerait deux fois la même courbe. On ne trace que les
    # stores qui apportent des nœuds propres.
    # Le store canonique est le plus fourni : à ensembles de nœuds scorés égaux,
    # c'est celui qui porte le plus d'historique complet.
    def richness(store: dict) -> tuple:
        return (len(store.get("hashes") or ()), store["totals"]["nodes"], store["id"])

    for store in stores_out:
        own = set(store.get("hashes") or ())
        if not own:
            store["subset_of"] = None
            continue
        store["subset_of"] = next(
            (o["label"] for o in stores_out
             if o is not store and own <= set(o.get("hashes") or ())
             and richness(o) > richness(store)),
            None)
    duplicated = {s["label"] for s in stores_out if s.get("subset_of")}
    table = [r for r in nodes_table if r["store"] not in duplicated]

    return {
        "status": "ok",
        "stores": stores_out,
        "nodes_table": sorted(table, key=lambda r: r["created_at"] or ""),
        "prompt_variants": variants,
        "mixed_models": len(eval_models) > 1,
        "common_set": common_set,
        "common_set_expected": [common_eval.rel],
        "generalization": generalization,
    }


def build_model_predictions(source, cerema: dict, scorer) -> dict:
    """Prédictions du modèle sur le jeu commun (action A8), scorées comme le reste.

    Même exigence que pour le volet 2 : le score sort du même ``Scorer`` — donc de la
    ``calibration.metrics`` du moteur, avec ``length_penalty`` à 0 — et porte sur le
    périmètre du volet 1. Rien n'est recalculé de travers ici.

    Trois lectures sont produites. ``attendu`` (masse de probabilité, renormalisée sur
    l'offre OTP) et ``elu`` (mode le plus probable) sont les deux faces du volet 1 ;
    ``brut`` est la même masse **avant** renormalisation, et n'a qu'un usage : mesurer
    ce que la correction OTP change réellement, plutôt que de l'affirmer.

    Source absente ou illisible → ``{"available": False}`` : la page affiche sa carte
    « Données manquantes » et se génère normalement.
    """
    if not source.exists or scorer is None:
        return {"available": False}
    loaded = frames.load_model_predictions(source.path)
    if not loaded:
        return {"available": False}

    variants: dict[str, Any] = {}
    for name, frame in loaded["variants"].items():
        if not frame:
            continue
        gview = frames.global_view(frame, cerema)
        scores = scorer.score(frame, cerema)
        dims = scores.get(scorer.primary.name, {})
        variants[name] = {
            "global": gview, "scores": scores, "dims": dims,
            "composite": dims.get("composite"),
            "secondary": scores.get(scorer.secondary.name, {}).get("composite")
            if scorer.secondary else None,
            "n_rows": len(frame),
        }

    details: dict[str, list[dict]] = {}
    expected = loaded["variants"]["attendu"]
    for dim in DIMENSIONS:
        detail = frames.dimension_detail(expected, cerema, dim)
        if any(d["n"] for d in detail):
            details[dim["key"]] = detail

    meta = loaded.get("meta") or {}
    summary = meta.get("summary") or {}
    gv = variants.get("attendu", {}).get("global", {})
    total_mass = gv.get("mass", 0.0) + gv.get("excluded_mass", 0.0)
    return {
        "available": True,
        "variants": variants,
        "details": details,
        "meta": meta,
        "summary": summary,
        # Deux masses écartées, et elles ne disent pas la même chose : les décisions
        # sorties du périmètre du modèle (zone inconnue, offre sans mode prédictible)
        # et, dans les décisions retenues, la part de probabilité tombant sur des modes
        # hors des quatre scorés. La seconde est nulle par construction ici — la
        # renormalisation ne laisse que des modes scorés.
        "excluded_decisions_pct": summary.get("excluded_pct"),
        "excluded_pct": (100.0 * gv.get("excluded_mass", 0.0) / total_mass
                         if total_mass else 0.0),
        "path": source.rel,
    }


def build_model(manifest, cerema: dict, scorer) -> dict:
    spec_src = manifest.track("model.feature_spec",
                              manifest.get("arms.model.feature_spec"),
                              "Spécification versionnée des variables du modèle")
    manifest.track("model.dataset", manifest.get("arms.model.dataset"),
                   "Déplacements PROGEDO préparés pour l'entraînement")
    policy = manifest.track("model.policy", manifest.get("arms.model.policy"),
                            "Modèle entraîné et sérialisé")
    preds = manifest.track("model.predictions", manifest.get("arms.model.predictions"),
                           "Probabilités prédites sur le jeu commun")
    zones = manifest.track("model.zones", manifest.get("arms.model.zones"),
                           "Couche de zones fines (résolveur point → zone)")

    predictions = build_model_predictions(preds, cerema, scorer)
    # Ce que la prédiction a réellement trouvé, plutôt que ce qu'on en attendait :
    # une variable « disponible » peut être massivement manquante à l'arrivée (une
    # modalité que la population synthétique porte et que le spec ne connaît pas
    # devient manquante à l'encodage, sans qu'aucune erreur ne le dise).
    measured_missing = ((predictions.get("meta") or {}).get("feature_missing") or {})
    n_scored = ((predictions.get("summary") or {}).get("n_scored") or 0)

    features = []
    if spec_src.exists:
        try:
            spec = json.loads(spec_src.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            spec = {}
        # Où chaque variable se trouve dans le jeu commun : c'est ce qui décide de
        # la faisabilité du volet, bien avant l'entraînement.
        persona = {"age", "gender", "household_size", "has_driving_license",
                   "has_pt_subscription", "number_of_cars", "car_availability",
                   "has_bike", "socioprofessional_class", "main_occupation",
                   "employed", "studies"}
        context = {"purpose", "purpose_origin", "departure_hour"}
        for name in spec.get("features", []) or []:
            fname = name if isinstance(name, str) else name.get("name", str(name))
            if fname in persona:
                source, status = "population_*.json → traits_json", "disponible"
            elif fname in context:
                source, status = "moves.csv + chaîne d'activités", "disponible"
            else:
                # Variables géo : dérivables depuis les coordonnées dès que la couche
                # de zones est là, le résolveur rejouant la formule d'entraînement.
                source = "population_*.json (coordonnées) + couche de zones fines"
                status = ("dérivable — résolveur de zone fine" if zones.exists
                          else "couche absente — `make zones`")
            gap = measured_missing.get(fname)
            if predictions.get("available"):
                status = ("renseignée" if not gap else
                          f"manquante sur {gap} décisions "
                          f"({100.0 * gap / max(1, n_scored):.1f} %)")
            features.append({"name": fname, "source": source, "status": status})

    # Le modèle entraîné porte ses propres métriques (il est autoportant par
    # conception, cf. fit_mode_choice_policy.py) : la page les relit chez lui plutôt
    # que d'ouvrir une source de plus. Agrégats seulement — aucune micro-donnée
    # d'enquête ne transite ici.
    trained = None
    if policy.exists:
        try:
            art = json.loads(policy.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            art = {}
        test = (art.get("metrics") or {})
        shares = test.get("mode_shares") or {}
        if test:
            trained = {
                "spec_version": art.get("spec_version"),
                "best_iteration": (art.get("training") or {}).get("best_iteration"),
                "n_test": test.get("n_rows"),
                "log_loss": test.get("log_loss_weighted"),
                "accuracy": test.get("accuracy_weighted"),
                "l1_mass": shares.get("l1_probability_mass"),
                "l1_argmax": shares.get("l1_argmax"),
                "classes": test.get("classes") or [],
                "observed": shares.get("observed") or [],
                "predicted": shares.get("predicted_probability_mass") or [],
                "top_features": [
                    {"name": f["name"], "gain": f["gain_share"]}
                    for f in (test.get("feature_importances") or [])[:6]
                ],
            }

    return {
        # « missing » tant que le volet ne peut pas produire de score sur le jeu
        # commun : un modèle entraîné mais jamais appliqué n'en produit aucun.
        "status": "ok" if predictions.get("available") else "missing",
        "trained": trained,
        "feature_spec": {"features": features},
        "predictions": predictions,
        "expected": [preds.rel] if policy.exists else [policy.rel, preds.rel],
    }


def build_synthesis(payload: dict) -> dict:
    dims = [{"key": d["key"], "label": d["label"]}
            for d in DIMENSIONS if d["scored"]]
    dims.insert(0, {"key": "global", "label": "Global"})
    dims.append({"key": "composite", "label": "Composite comparable"})

    sim = payload["arms"]["simulation"]
    primary = payload["score_def"]["primary"]
    arms_out = []

    def cells_from(scores: dict) -> list[dict]:
        values = scores.get(primary, {}) if scores else {}
        out = []
        for dim in dims:
            key = "global" if dim["key"] == "global" else dim["key"]
            out.append({"value": values.get(key)})
        return out

    def cells_from_dims(values: dict) -> list[dict]:
        return [{"value": values.get(d["key"])} for d in dims]

    if sim.get("status") == "ok":
        arms_out.append({"label": "Simulation",
                         "cells": cells_from(sim["variants"]["attendu"]["scores"])})
        arms_out.append({"label": "Sim. (tirée)",
                         "cells": cells_from(sim["variants"]["tire"]["scores"])})
        # Témoin de taille, inséré JUSTE AVANT les colonnes de calibration : c'est
        # à lui qu'elles doivent être comparées, pas à la colonne du run entier.
        on_sample = sim.get("on_calibration_sample")
        if on_sample:
            arms_out.append({
                "label": "Sim. (éch. V2)",
                "basis": f'jeu commun — {on_sample["n_persons"]} personnes de '
                         f'l\'échantillon du volet 2',
                "note": "témoin de taille, mêmes personnes que la calibration",
                "cells": cells_from_dims(on_sample.get("dims") or {})})
    else:
        arms_out.append({"label": "Simulation", "cells": [{"value": None}] * len(dims)})

    # Volet 2 : graine et meilleur prompt. DEUX substrats possibles, et la
    # différence n'est pas cosmétique.
    #
    # - le jeu commun (action A3) : les personas du run épinglé, ceux-là mêmes que
    #   le volet 1 — les colonnes sont alors commensurables ;
    # - à défaut, les personas gelés du moteur de calibration, c'est-à-dire un
    #   sous-ensemble d'un run ANTÉRIEUR. Comparer ce chiffre à celui du volet 1
    #   revient à comparer deux mesures faites sur deux populations.
    #
    # On préfère donc toujours le jeu commun quand il existe, et chaque colonne
    # déclare son substrat (``basis``) pour que la page ne puisse pas le taire.
    cal = payload["arms"]["calibration"]
    common = cal.get("common_set") or {}
    store = None
    if cal.get("status") == "ok":
        candidates = [s for s in cal["stores"] if s.get("best")]
        store = max(candidates, key=lambda s: s["kept"]) if candidates else None

    if common.get("available") and common.get("seed") and common.get("leaf"):
        for entry in (common["seed"], common["leaf"]):
            arms_out.append({
                "label": "Calib. graine" if entry["role"] == "seed" else "Calib. meilleur",
                "basis": "jeu commun",
                "note": f'{entry["short"]} · {entry.get("regime") or "régime inconnu"}',
                "cells": cells_from_dims(entry.get("dims") or {})})
    elif store:
        arms_out.append({"label": "Calib. graine", "basis": "personas gelés",
                         "note": f'{(store.get("seed") or {}).get("short", "?")} · '
                                 f'{(store.get("seed") or {}).get("regime", "?")}',
                         "cells": cells_from_dims((store.get("seed") or {}).get("dims", {}))})
        arms_out.append({"label": "Calib. meilleur", "basis": "personas gelés",
                         "note": f'{store["best"]["short"]} · {store["best"]["regime"]}',
                         "cells": cells_from_dims(store["best"]["dims"])})
    else:
        arms_out.append({"label": "Calibration", "basis": None,
                         "cells": [{"value": None}] * len(dims)})
    # Volet 3 : deux lectures, comme le volet 1. L'écart entre elles est structurel et
    # mesuré à l'entraînement (L1 des parts modales 0,021 en masse contre 0,087 en mode
    # élu, rappel vélo 0,128) : n'afficher que la première flatterait le modèle,
    # n'afficher que la seconde le condamnerait. Le substrat déclaré dit sur combien de
    # décisions du jeu commun la mesure porte réellement.
    model = payload["arms"].get("model") or {}
    preds = model.get("predictions") or {}
    if preds.get("available"):
        summary = preds.get("summary") or {}
        scored = summary.get("n_scored")
        total = summary.get("n_moves")
        basis = "jeu commun"
        if scored is not None and total and scored < total:
            basis = f"jeu commun — {scored}/{total} décisions prédictibles"
        note = "renormalisé sur l'offre OTP"
        for name, label in (("attendu", "Modèle"), ("elu", "Modèle (élu)")):
            variant = (preds.get("variants") or {}).get(name)
            if variant is None:
                continue
            arms_out.append({"label": label, "basis": basis, "note": note,
                             "cells": cells_from_dims(variant.get("dims") or {})})
    else:
        arms_out.append({"label": "Modèle", "basis": None,
                         "cells": [{"value": None}] * len(dims)})
    for arm in arms_out:
        arm.setdefault("basis", "jeu commun")
        arm.setdefault("note", "")
    # Le jeu de retenue (action A4) est un TROISIÈME substrat : ni le run, ni les
    # personas d'entraînement, mais des personas gelés jamais vus par la boucle. Il
    # n'entre volontairement pas dans la matrice — l'y coller ferait voisiner une
    # colonne de 66 personnes avec des colonnes de 881, c'est-à-dire rejouerait la
    # confusion que l'action A3 a corrigée. La matrice se contente de signaler que
    # le chiffre existe et où le lire.
    generalization = (cal.get("generalization") or {}) if isinstance(cal, dict) else {}
    return {"dims": dims, "arms": arms_out,
            "calibration_basis": ("jeu commun" if common.get("available")
                                  else "personas gelés"),
            "model_available": bool(preds.get("available")),
            "generalization_available": bool(generalization.get("available")),
            "generalization_dataset": generalization.get("dataset"),
            "commensurable": bool(common.get("available"))}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="manifeste de sources (défaut : sources.yaml)")
    parser.add_argument("--run", help="run servant de jeu commun (écrase le manifeste)")
    parser.add_argument("--out", help="chemin du HTML de sortie")
    parser.add_argument("--json", dest="json_out", help="chemin du JSON de sortie")
    args = parser.parse_args(argv)

    manifest = load_manifest(args.config)
    if args.run:
        manifest.raw.setdefault("common_set", {})["run"] = args.run

    cerema_src = manifest.track("cerema", manifest.get("cerema"),
                                "Référence EMC² 2023 — parts modales cibles")
    if not cerema_src.exists:
        print(f"[erreur] Référence EMC² introuvable : {cerema_src.rel}", file=sys.stderr)
        return 2
    cerema = frames.load_cerema(cerema_src.path)

    weights = manifest.get("score.weights", {})
    calibration, engine_error = import_calibration(
        manifest.get("arms.calibration.repo", "prompt_calibration"))
    scorer = None
    if calibration is not None:
        scorer = frames.Scorer(calibration, weights,
                               manifest.get("score.metric", "emd_jsd"),
                               manifest.get("score.secondary", "l1_composite"))
        engine_note = "Loss importée du moteur de calibration"
    else:
        engine_note = f"Score indisponible — {engine_error}"
        print(f"[avertissement] {engine_error}", file=sys.stderr)

    common, rows = build_common_set(manifest, cerema)
    if common.get("available"):
        expected = frames.simulation_frames(rows)["attendu"]
        common["coverage"] = frames.coverage_matrix(expected, cerema)

    payload: dict[str, Any] = {
        "generated_at": _now(),
        "engine_note": engine_note,
        "score_def": build_score_def(manifest, weights),
        "common_set": common,
        "arms": {
            "simulation": build_simulation(rows, cerema, scorer) if common.get("available")
            else {"status": "missing", "reason": common.get("reason", ""),
                  "expected": common.get("expected", []),
                  "action": "Vérifier common_set.run dans sources.yaml"},
            "calibration": build_calibration(manifest, cerema, scorer),
            "model": build_model(manifest, cerema, scorer),
        },
        "actions": ACTIONS,
    }
    # Témoin de taille : le volet 1 restreint aux personnes du volet 2. Calculé ici
    # parce qu'il croise les deux volets — il a besoin des trajets du run ET du
    # descriptif d'échantillon écrit par la mesure du volet 2.
    cal_arm = payload["arms"]["calibration"]
    common_eval = (cal_arm.get("common_set") or {}) if isinstance(cal_arm, dict) else {}
    if common_eval.get("available"):
        on_sample = build_simulation_on_sample(
            rows, cerema, scorer, common_eval.get("sample") or {})
        if on_sample:
            payload["arms"]["simulation"]["on_calibration_sample"] = on_sample
            # Le volet 2 doit pouvoir citer son témoin sans aller le chercher dans
            # un autre volet : c'est de lui que dépend la lecture de ses chiffres.
            full = ((payload["arms"]["simulation"].get("variants") or {})
                    .get("attendu", {}).get("scores", {})
                    .get(payload["score_def"]["primary"], {}) or {})
            common_eval["size_control"] = {
                **on_sample,
                "full_composite": full.get("composite"),
                "penalty": (on_sample["composite"] - full["composite"])
                if (on_sample.get("composite") is not None
                    and full.get("composite") is not None) else None,
            }

    payload["synthesis"] = build_synthesis(payload)
    payload["sources"] = [s.to_dict() for s in manifest.sources.values()]

    html_out = Path(args.out or manifest.get("output.html", "docs/synthesis/index.html"))
    if not html_out.is_absolute():
        html_out = REPO_ROOT / html_out
    html_out.parent.mkdir(parents=True, exist_ok=True)
    html_out.write_text(render.render(payload), encoding="utf-8")

    json_out = Path(args.json_out or manifest.get("output.json", "docs/synthesis/data.json"))
    if not json_out.is_absolute():
        json_out = REPO_ROOT / json_out
    json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8")

    # --out peut viser hors du dépôt (archive, comparaison) : afficher le chemin
    # absolu plutôt que d'échouer sur un relative_to() impossible.
    def display(path: Path) -> str:
        try:
            return str(path.relative_to(REPO_ROOT))
        except ValueError:
            return str(path)

    missing = [s for s in payload["sources"] if not s["exists"]]
    print(f"Page écrite : {display(html_out)}")
    print(f"Données     : {display(json_out)}")
    print(f"Sources     : {len(payload['sources']) - len(missing)} présentes, "
          f"{len(missing)} manquantes")
    for src in missing:
        print(f"  manquant : {src['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
