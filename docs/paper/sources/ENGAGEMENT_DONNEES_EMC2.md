# Engagement d'utilisation des microdonnées EMC² 2023 (Quetelet-Progedo-Diffusion, lil-1750)

<!-- Dernière mise à jour : 2026-09-11 -->

**Document :** `v1.0` (11 septembre 2026). Recopie l'engagement signé auprès de
Quetelet-Progedo-Diffusion pour l'accès aux microdonnées de l'enquête, puis dit ce qu'il impose
au texte de l'article, à son matériel supplémentaire et au dépôt.
**Portée :** toute publication, communication, planche ou archive issue de ce dépôt.
**Ce qui fait foi :** la convention signée elle-même. Ce fichier est un rappel de travail, pas une
source juridique — en cas d'écart entre les deux, c'est la convention qui tranche.

---

## 1. L'enquête concernée

Le fichier diffusé est l'**Enquête Ménages Déplacements de Toulouse / Grande agglomération
toulousaine**, enquête mobilité certifiée Cerema (**EMC² 2023**), sous la convention
**lil-1750** de Quetelet-Progedo-Diffusion (ADISP).

> **Correction de libellé.** La notification de diffusion recopiée portait « … - 2013 ».
> L'enquête utilisée dans ce travail, et la seule à citer, est celle de **2023** — correction de
> l'auteur, 11 septembre 2026. Le reste du dépôt écrit déjà « EMC² 2023 » ; aucun chiffre n'en
> dépend, seul le millésime cité change.

---

## 2. Les engagements pris

La communication du fichier engage le signataire à :

1. utiliser les données **exclusivement dans une finalité de recherche** ;
2. **ne pas céder ces données**, sous quelque forme que ce soit, à une tierce personne, que ce
   soit à titre gratuit ou onéreux ;
3. traiter ces données **conformément aux règles de l'art et du secret statistique** ;
4. faire inscrire la recherche dans le **registre de déclaration de traitement des données** de
   son établissement ;
5. respecter la **réglementation en matière de protection des données personnelles** ;
6. **mentionner la source** des données dans ses communications et publications, conformément au
   **modèle de citation** annexé à la convention ;
7. **informer le diffuseur** de ses communications et publications, et lui en faire parvenir les
   références ;
8. informer le diffuseur des **constats relatifs à la qualité des données** ou à leur difficulté
   d'utilisation ;
9. informer le diffuseur de toute **réutilisation des données pour une autre recherche** que
   celle spécifiée à la demande ;
10. **stocker les données sur un serveur sécurisé ou dans un espace chiffré** pendant le travail
    de recherche ;
11. **détruire les fichiers à l'issue** du travail de recherche.

Toute infraction expose à des poursuites pénales — articles 226-13 et 226-14 du code pénal
(atteinte au secret professionnel), articles 226-16 à 226-24 (atteintes aux droits de la personne
résultant des fichiers ou des traitements informatiques) — et à des poursuites en responsabilité
civile, avec les conséquences pécuniaires qui s'y attachent.

---

## 3. Ce que cela impose, engagement par engagement

| Engagement | Conséquence concrète | Où c'est porté / état |
|---|---|---|
| Finalité de recherche (1) | L'usage est un article AAMAS 2027 et sa méthode ; aucun usage opérationnel ni commercial. | Respecté par construction. |
| Non-cession (2) | **Aucune microdonnée, ni fichier qui en reproduirait le contenu ou le découpage, dans le ZIP de soumission, sur Zenodo ou sur GitHub.** Le jeu de test scellé de 13 045 trajets n'accompagne pas l'article. | § 4.7 du chapitre 4, Annexe G, note ajoutée au § 3 de `SOUMISSION_AAMAS_2027.md`. Statut des **ressources dérivées** de `mobility_core/data/` (lois agrégées, listes de zones fines) : **à trancher**, [ticket 038](../../tickets/ticket_038_licence_des_ressources_emc2_de_mobility_core.md). |
| Secret statistique (3) | Aucun individu, aucun ménage, aucune sortie sur effectif trop faible dans le texte ni dans les figures. Les scores publiés sont des agrégats. | À vérifier au moment de figer les tableaux du chapitre 6. |
| Registre de traitement (4) | La recherche doit être inscrite au registre de l'établissement. | **Hors dépôt, à vérifier.** Ne peut pas figurer dans la version en double insu (nomme l'établissement). |
| Protection des données (5) | Pas de donnée personnelle dans les logs, les caches ni les traces publiées. | Règle déjà générale au dépôt. |
| Mention de la source (6) | Citation de la source **selon le modèle de la convention**, dans l'article et dans toute planche qui montre un chiffre d'enquête. | § 4.7, Annexe G, entrées bib `tisseo2023emc2` et `progedo2023emc2microdata`. **Le libellé exact du modèle reste à recopier** (§ 5). |
| Information du diffuseur (7) | À chaque soumission ou communication : prévenir le diffuseur et envoyer les références. | Journal au § 4 de ce fichier — **vide à ce jour**. |
| Constats de qualité (8) | Les difficultés d'utilisation rencontrées se remontent au diffuseur, et non seulement aux tickets du dépôt. | À faire ; la question de la granularité publiable (zones fines à faible effectif) est déjà posée au ticket 038. |
| Autre réutilisation (9) | Tout usage hors du périmètre déclaré (autre article, autre terrain) demande une information préalable. | À surveiller si le module de calibration de prompt sort du cadre de l'article. |
| Stockage chiffré (10) | Les fichiers sources vivent dans `data/PROGEDO 2023/`, **hors git** (`.gitignore`), sur poste à disque chiffré. | Exclusion git vérifiée. **Chiffrement du support à confirmer.** |
| Destruction (11) | À l'issue de la recherche, les fichiers sources sont détruits ; seuls survivent les résultats agrégés, les coefficients ajustés et le code. | À planifier avec la date de fin de travaux. |

---

## 4. Journal des informations envoyées au diffuseur

| Date | Communication concernée | Références envoyées | Réponse |
|---|---|---|---|
| — | *aucune à ce jour* | — | — |

Une ligne par envoi, y compris les refus et les soumissions non retenues : l'engagement porte sur
les communications, pas sur les publications acceptées.

---

## 5. Ce qui reste à compléter

1. **Le modèle de citation exact.** La convention l'annexe (« cf. ci-après ») ; il n'a pas été
   recopié ici. En attendant, l'article porte un emplacement à remplir et une formulation
   provisoire, clairement marquée comme telle.
2. **La version en double insu.** La mention du registre de traitement de l'établissement et
   l'identité du signataire ne peuvent pas figurer dans la version soumise ; elles reviennent
   dans la version finale.
3. **Le statut des ressources dérivées** ([ticket 038](../../tickets/ticket_038_licence_des_ressources_emc2_de_mobility_core.md)) :
   l'engagement 2 dit « sous quelque forme que ce soit », ce qui pèse en faveur de l'exclusion
   des ressources reproduisant un découpage de l'enquête. La décision reste à l'auteur.
4. **La date de destruction** des fichiers sources, à arrêter avec la fin des travaux.
