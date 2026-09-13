# Ticket 046 — L'agent voit sa journée, le modèle tabulaire non : que dit le contrat ?

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-11 à la demande de l'auteur, **rien n'est lancé**.
>
> **Ce ticket n'implémente rien. Il examine des solutions et les chiffre.** Décision de
> l'auteur à l'ouverture : *en attendant, on reste en l'état* — l'agent garde son anticipation,
> le protocole ne bouge pas, et le [ticket 045](ticket_045_substrat_unique_v5_et_reconstruction_des_experiences.md)
> continue sur le substrat v5 sans attendre cette réponse.
>
> Prérequis : aucun. **Bloque** la publication de la section 1.3 et de tout chiffre qui s'en
> réclame, parce qu'aucune mesure ne se publie sous un contrat faux.

## Le fait, en une phrase

La règle 1 du contrat d'évaluation dit que l'agent et les modèles tabulaires « reçoivent les
mêmes 21 variables d'entrée ». **C'est faux** : l'agent en reçoit davantage.

## Ce qu'il reçoit en plus, exactement

Trois choses, et il faut les distinguer parce qu'elles n'ont pas le même statut.

| Surplus | Où | Nature |
|---|---|---|
| `agenda` — les trajets restants avant le retour au domicile | `mobility_llm/persona.py:39` | **anticipation de la chaîne**, ajoutée par le ticket 014 sous cet intitulé explicite |
| `day_outlook` — la météo des tranches horaires restantes | `mobility_llm/persona.py:38` | **anticipation du contexte** |
| la mémoire à court et long terme | `settings.agent.long_term_memory_enabled` | **hors périmètre de ce ticket** : elle est désactivée dans toutes les expériences de la plateforme (`memoire: false`) |

Le modèle tabulaire, lui, reçoit 21 variables qui ne portent **rien** sur la suite de la
journée : personne, ménage, motif, heure de départ, géométrie du trajet courant. Il décide
chaque déplacement isolément.

Le surplus est donc réel, et il porte sur **l'avenir de la journée** — exactement ce que la
chaîne des véhicules rend coûteux. Un agent peut décider le matin en sachant ce que ce choix
lui imposera le soir. Un modèle trajet-par-trajet ne le peut pas.

## Pourquoi ce n'est pas qu'une question de rédaction

Trois conséquences, dans l'ordre de gravité.

**a) Le contrat publié est faux.** Il l'est dans le résumé et dans l'introduction :

| Fichier | Ce qui est écrit |
|---|---|
| `docs/paper/article/fr/00_abstract.md` | « les mêmes 21 variables pour l'agent LLM, un logit multinomial et un oracle LightGBM » |
| `docs/paper/article/en/00_abstract.md` · `overleaf/00_abstract.tex` | « the same 21 variables for the LLM agent, a multinomial logit and a LightGBM oracle » |
| `docs/paper/article/fr/01_introduction.md` (§ 1.3, règle 1) | « reçoivent les mêmes 21 variables d'entrée » |
| `docs/paper/article/en/01_introduction.md` | idem |

**b) Le modèle tabulaire est jugé, en chaîne, sur une tâche qu'il n'a pas apprise.** Pire : il
subit les conséquences de ses propres choix du matin sans avoir pu les anticiper. Et l'effet
moyen du chaînage est **déjà dans ses probabilités**, puisqu'il a été ajusté sur des journées
réelles, elles aussi chaînées ; le simuler en chaîne applique la contrainte une seconde fois.
Sa lecture en chaîne est donc pessimiste.

**c) L'écart entre les deux est peut-être le meilleur résultat du dispositif.** Ce que coûte de
ne pas anticiper la journée est un chiffre publiable, et c'est l'argument le plus direct en
faveur des agents génératifs que ce dispositif puisse produire — bien plus qu'une part modale
mieux calée. Traiter l'asymétrie comme une faille à corriger reviendrait à jeter le résultat.

## L'argument tel qu'il est écrit au chapitre 4 est-il recevable ? — examen du 11 septembre

La formulation en service est : *« Décider en sachant ce que ce choix imposera le soir est
précisément la capacité qu'un classifieur trajet par trajet n'a pas. La parité porte donc sur la
description du déplacement courant, et le surplus est déclaré. »*

**Verdict : recevable comme déclaration, pas comme défense.** Trois raisons.

1. **Le mot « parité » fait le travail que la mesure ne fait pas.** Un relecteur lit « parité
   informationnelle » comme une garantie ; la phrase suivante la retire sur un axe. Annoncer une
   parité puis la restreindre dans la même phrase se lit comme une réparation, pas comme un choix
   de conception.
2. **L'argument explique l'asymétrie, il ne la traite pas.** Que l'anticipation soit hors de portée
   d'un classifieur trajet par trajet est vrai et intéressant — c'est même la thèse de l'article —
   mais cela ne dit pas pourquoi un écart mesuré serait attribuable.
3. **L'écart mesuré mêle deux causes** — la règle de décision et l'horizon d'information — et le
   texte ne dit pas laquelle il isole.

**Ce qui le rendrait recevable**, sans changer le protocole :

- **Ne plus revendiquer la parité sur cet axe.** La parité tient sur la description du déplacement
  courant ; sur l'horizon, il n'y en a pas, par construction. Le dire ainsi est plus fort, parce que
  c'est vérifiable.
- **Attribuer par la double lecture.** Jouer les familles tabulaires en chaîne et hors chaîne
  (ticket 045, lot 4e) isole l'effet de l'horizon **du côté tabulaire** et le chiffre. Sans elle,
  l'affirmation reste une assertion ; avec elle, elle devient une mesure.
- **Déclarer ce que la double lecture n'isole pas.** Le surplus de l'agent est **triple** : agenda,
  météo des tranches à venir, mémoire. Le 2×2 ne sépare que l'effet de chaîne. Le seul dispositif
  qui isolerait l'anticipation elle-même serait de la couper côté agent — écarté par l'auteur le
  11 septembre, et pour une raison recevable : c'est la capacité que l'article démontre.

**Conséquence sur la revendication de l'article**, et c'est le point central : il faut écrire *« les
agents font quelque chose qu'un modèle tabulaire ne peut pas faire »* et **non** *« à information
égale, les agents font mieux »*. La seconde n'est pas soutenable, la première l'est — et elle
n'exige aucune expérience de plus.

## Les solutions à examiner

Quatre, non exclusives. Chacune est chiffrée en coût et en ce qu'elle fait perdre.

### A — Aligner l'agent sur les variables communes

Couper `agenda_anticipation_enabled` : l'agent décide trajet par trajet, comme le modèle
tabulaire. Le drapeau existe (`settings.py:510`), **aucun code à écrire**.

- **Ce qu'on gagne** : une parité informationnelle vraie, et la règle 1 redevient exacte telle
  qu'elle est écrite.
- **Ce qu'on perd** : précisément ce qu'on veut démontrer. L'anticipation est la capacité pour
  laquelle des agents sont employés — faire ce qu'un modèle trajet-par-trajet ne peut pas.
  L'auteur a **déjà tranché contre** cette option le 11 septembre, dans le cadre du ticket 045.
- **Statut** : conservée ici comme **bras de contrôle** possible, pas comme protocole nominal.
  Jouée seule, elle répondrait à une question qui n'est pas celle de l'article.

### B — Double mesure de l'agent : avec et sans anticipation

Le même bras LLM joué deux fois, `agenda_anticipation_enabled` à vrai puis à faux, tout le
reste identique. L'écart chiffre **ce que l'anticipation apporte à l'agent**, sur le même
substrat et le même jeu.

- **Ce qu'on gagne** : l'asymétrie cesse d'être un défaut du contrat pour devenir une **variable
  mesurée**. Et le bras « sans anticipation » est comparable au modèle tabulaire à parité
  stricte — la règle 1 redevient vraie **pour ce bras-là**, nommément.
- **Ce que ça coûte** : un doublement des bras LLM, donc **payant**. À chiffrer avant de
  décider : sur la v5, 3 299 déplacements par bras.
- **Prérequis** : `agenda_anticipation_enabled` doit entrer dans la définition de l'expérience,
  dans `reglages_herites` et dans le nom — exactement comme `vehicule_chaine` et `verrou_retour`
  l'ont fait au ticket 045 (R13). Aujourd'hui il est dans `reglages_herites` mais **pas** dans
  la définition : deux exécutions ne différant que par lui porteraient le même nom.
- **Question ouverte** : une seule graine suffit-elle pour attribuer l'écart à l'anticipation
  plutôt qu'au bruit inter-graines ? La variabilité inter-graines n'est pas mesurée (différée
  par le ticket 045).

### C — Déclarer l'asymétrie, et en faire l'objet de l'étude

Ne rien changer au protocole, et corriger le **texte** pour qu'il dise ce qui est vrai :

> *les mêmes 21 variables décrivant la personne et le déplacement courant ; l'agent reçoit en
> outre l'agenda de sa journée, la météo des tranches restantes et sa mémoire, et ce surplus
> est précisément ce que la comparaison met à l'épreuve.*

- **Ce qu'on gagne** : la formulation devient exacte, l'asymétrie devient l'objet de l'étude, et
  **aucune mesure n'est à refaire**. Coût nul.
- **Ce qu'on perd** : la phrase « parité informationnelle stricte » disparaît du résumé, ce qui
  affaiblit une accroche. À remplacer par une formulation qui dit ce que le dispositif fait
  réellement, et qui est plus intéressante.
- **Statut** : **c'est le minimum obligatoire**, quelle que soit la suite. Les options A, B et D
  s'ajoutent à C ; aucune ne la remplace.

### D — Deux lectures déclarées pour les modèles tabulaires

Publier chaque famille de référence **en chaîne** et **hors chaîne** :

| Lecture | Ce qu'elle mesure | À quoi elle se compare |
|---|---|---|
| **en chaîne** | le modèle comme moteur de décision dans la simulation, mêmes jeux de choix que l'agent | au bras LLM, terme à terme |
| **hors chaîne** | chaque déplacement isolément, offre restreinte par ce qui ne dépend pas des décisions antérieures (équipement du ménage, permis, faisabilité physique) | à l'enquête — la tâche pour laquelle le modèle a été ajusté |

- **Ce qu'on gagne** : l'oracle **hors chaîne** devient le plafond **distributionnel** honnête,
  celui contre lequel H0 se teste ; l'oracle **en chaîne** en est la lecture **opérationnelle**,
  handicapée par une anticipation qu'il ne peut pas faire. L'écart entre les deux chiffre ce que
  coûte l'absence de prévoyance. C'est le point **c)** ci-dessus, rendu mesurable.
- **Ce que ça coûte** : **gratuit** — quatre familles, hors ligne, aucun appel LLM.
- **Ce qu'il ne faut PAS faire** : retirer la chaîne aux modèles tabulaires dans la lecture
  principale. Cela les créditerait d'une voiture restée au bureau, produirait des journées
  physiquement impossibles, et romprait la règle 3 (renormalisation sur l'offre) comme le
  principe du substrat unique.
- **Statut** : le plus rentable du lot. Gratuit, et il produit un résultat publiable.

### Recommandation de départ, à confirmer par l'auteur

**C obligatoire, D en premier parce qu'il est gratuit, B si le budget le permet, A jamais seule.**

## Ce qu'il faut mesurer avant de décider

Aucune de ces options ne se tranche sur un raisonnement. À chiffrer, **sur le substrat v5 et
sur des mesures existantes seulement** :

1. **Combien de décisions l'agenda change-t-il réellement ?** Sur les exécutions archivées, la
   proportion de décisions où la chaîne restante contraignait déjà le choix. Si elle est faible,
   toute cette discussion porte sur un effet marginal, et C suffit.
2. **Quelle part des 21 variables porte déjà, indirectement, de l'information de chaîne ?**
   `number_of_cars`, `has_driving_license`, le motif, l'heure de départ : un modèle tabulaire
   n'est pas totalement aveugle à la journée. L'asymétrie est peut-être plus étroite qu'annoncé.
3. **Le coût réel de l'option B** : nombre de sollicitations, jetons, fenêtre de quota.
4. **L'écart en chaîne / hors chaîne pour une famille**, mesuré avant de le généraliser aux
   quatre.

## Hors périmètre

- La mémoire à court et long terme : désactivée dans toutes les expériences de la plateforme.
  Elle est mentionnée dans la reformulation de C pour être exacte, mais elle ne joue pas.
- Le choix de l'oracle de référence (tickets 042, 043, 044).
- Le substrat, les prompts, le nommage : c'est le ticket 045.
- La variabilité inter-graines : différée par le ticket 045, et elle conditionne la lecture de
  l'option B.

## Questions ouvertes

1. **L'option B doit-elle jouer tous les bras LLM ou un seul ?** Un seul suffit à chiffrer
   l'apport de l'anticipation ; tous permettent de dire si cet apport dépend du modèle. Le coût
   n'est pas le même.
2. **Que devient la phrase « parité informationnelle stricte » dans le résumé ?** Elle est
   fausse et c'est une accroche. Il faut lui trouver un remplaçant qui dise le vrai sans
   affaiblir le propos.
3. **L'écart en chaîne / hors chaîne appartient-il au chapitre 4 (références) ou au chapitre 7
   (limites) ?** Il se défend des deux côtés : c'est une propriété des références, et c'est un
   argument sur ce que les agents apportent.
