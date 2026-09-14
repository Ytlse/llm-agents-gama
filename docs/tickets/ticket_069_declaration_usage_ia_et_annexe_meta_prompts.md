# Ticket 069 — Déclaration d'usage de l'IA et annexe des méta-prompts (conformité AAMAS 2027)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> **Le ticket ne s'exécute pas tout seul dans l'article.** Tout ce qui s'écrit sous
> `docs/paper/article/` passe par le verrou : skill `article-verrou`, diff présenté, accord humain
> explicite. Ce ticket cadre le texte à produire ; il ne l'autorise pas.

**Politique de référence :** [`SOUMISSION_AAMAS_2027.md` § 4](../paper/article/SOUMISSION_AAMAS_2027.md)
(déjà transcrite dans le dépôt). Elle demande, dès que l'IA a servi à formuler des hypothèses,
une méthodologie ou un plan expérimental : **le prompt exact, l'outil et sa version**, dans le
texte ou en annexe. Elle dispense de documentation la génération de code et le polissage
linguistique. Elle promet le *desk reject* en cas d'usage inapproprié — citations hallucinées en
tête de liste.

---

## 1. La distinction qui structure tout le ticket

Deux usages de LLM cohabitent dans ce travail, et les confondre rendrait la déclaration
illisible autant qu'inexacte.

| | **LLM objet d'étude** | **LLM assistant d'auteur** |
|---|---|---|
| Rôle | Les agents de mobilité *sont* des LLM. C'est le résultat de recherche. | Claude Code, Antigravity et consorts ont aidé à concevoir, coder, rédiger. |
| Où c'est déjà documenté | Ch. 5, Ch. 6, Annexes A / B / C / D, `config/llm_gateway/providers.yaml` | **Nulle part** — c'est le trou que ce ticket comble. |
| Ce que la politique AAMAS en dit | Rien : ce n'est pas de l'assistance, c'est le dispositif expérimental. | Tout le § 4. |

**Règle de rédaction :** la déclaration ne parle que de la colonne de droite, et dit en une
phrase que les modèles de la colonne de gauche relèvent du dispositif expérimental décrit au
Ch. 5 — sans quoi un relecteur croira que les 11 instances de la passerelle ont écrit l'article.

---

## 2. Où la déclaration se place — et pourquoi pas dans les Remerciements

L'évaluation AAMAS 2027 est à **double insu** (§ 1 de `SOUMISSION_AAMAS_2027.md`). Une section
Remerciements est retirée ou vidée de la version soumise : y loger la déclaration reviendrait à
ne pas la déclarer aux relecteurs, c'est-à-dire exactement à côté de l'objectif.

**Décision à acter :**

1. **Article principal — Méthodologie.** Un paragraphe court, non anonymisable, dans le chapitre
   qui porte la méthode (Ch. 3 *Architecture* ou Ch. 4 *Metrics and substrate* — trancher à la
   rédaction selon la place réelle : le budget est de 8 pages, références exclues).
   Ce paragraphe **renvoie explicitement à l'annexe**.
2. **Annexe H (nouvelle) — Méta-prompts.** Le détail exigé par la politique.
3. **Remerciements.** Rien sur l'IA en version soumise. Si la version *camera-ready* en gagne
   une, elle peut répéter la mention, jamais la remplacer.

---

## 3. Le paragraphe de l'article principal

L'exemple ci-dessous est une **base à reprendre entièrement**, pas un texte à recopier : il
nomme une architecture mémoire et des « simulations de revues critiques » qui doivent
correspondre à ce qui s'est réellement passé, ou disparaître.

> *Base de travail, à reprendre :* « Les modèles de langage (Claude [version exacte], Gemini
> [version exacte]) ont été utilisés lors de la phase d'idéation pour concevoir l'architecture de
> gestion de la mémoire des agents et pour éprouver les hypothèses de recherche via des
> simulations de revues critiques. La génération des scripts de simulation et le polissage du
> texte ont été assistés par l'IA en continu. Les prompts méthodologiques de référence sont
> documentés dans le matériel supplémentaire. Les auteurs assument l'entière responsabilité de la
> validité scientifique et de l'exactitude des résultats présentés. »

**Ce que la reprise doit garantir :**

- **Aucune version inventée.** Chaque nom d'outil et chaque numéro de version se justifie par une
  trace du dépôt (§ 5). Un « Claude 3.5 Sonnet » écrit par habitude dans un article dont le
  travail a tourné sur un autre modèle est une inexactitude de la même famille que celles que la
  politique sanctionne.
- **Le périmètre, délimité dans les deux sens.** Ce que l'IA a fait *et* ce qu'elle n'a pas fait :
  ni le choix du terrain, ni la convention de données, ni les résultats chiffrés, ni les décisions
  de réfutation d'hypothèses.
- **Les usages dispensés, cités quand même, brièvement.** Code et polissage linguistique n'ont pas
  à être documentés ; les mentionner d'une phrase coûte une ligne et évite le soupçon d'omission.
- **La responsabilité, sans conditionnel.** Une phrase, à la charge des auteurs, sur l'exactitude,
  les sources et l'absence de plagiat.
- **L'anonymat.** Pas de nom de compte, d'adresse, de chemin local, de nom d'établissement ni de
  numéro de convention nominative dans le paragraphe.

---

## 4. Annexe H — Méta-prompts

**Critère d'inclusion, strict :** seuls entrent les **méta-prompts ayant orienté la conception** —
ceux qui ont produit une hypothèse, une méthode, un plan expérimental, une objection retenue.
**Sont exclus** l'historique conversationnel, les requêtes de débogage, les demandes de
reformulation, les prompts système des agents de mobilité (ils appartiennent au Ch. 5 et à
`prompts.yaml`, pas ici).

Structure attendue :

### H.1 — Spécification des outils
Par outil : éditeur, nom commercial, **version exacte du modèle**, période d'utilisation, nature
de l'usage (idéation / méthode / code / style). Un tableau suffit.

### H.2 — Prompts d'idéation et de méthodologie
Par phase, le **texte intégral du prompt**, cité tel qu'il a été envoyé, suivi d'une ligne sur ce
que la réponse a changé dans le travail (et, le cas échéant, sur ce qui a été écarté). Les trois
phases à couvrir, sur le modèle suivant :

- **Exploration.** *« Recherche et synthétise la littérature existante sur la gestion de la
  mémoire dans les systèmes multi-agents. Identifie les limites techniques des approches
  actuelles. »*
- **Conception.** *« Génère une proposition de mécanisme pour la gestion de la mémoire des agents
  basée sur les concepts X et Y. Applique ensuite une critique stricte de cette proposition pour
  identifier les goulots d'étranglement ou les failles logiques. »*
- **Validation conceptuelle (persona).** *« Agis en tant que chercheur spécialiste des systèmes
  multi-agents de l'Université de Stanford. Évalue de manière critique l'approche suivante
  concernant la mémoire de l'agent. Réfute les arguments faibles, identifie les biais cognitifs ou
  architecturaux, et propose des modèles théoriques alternatifs plus robustes : [concept]. »*

**Ces trois-là sont des exemples de forme.** Le livrable les remplace par les prompts réellement
utilisés — ou les conserve si ce sont bien ceux-là, ce qui se vérifie et ne se suppose pas.

### H.3 — Ce que l'annexe ne contient pas
Une phrase explicite sur l'exclusion du débogage et de l'historique conversationnel : elle évite
qu'un relecteur lise l'annexe comme un extrait partiel d'un journal qu'on lui cacherait.

**Placement :** Annexe H du Ch. 99, à la suite de l'annexe G. Si l'article principal ne peut pas
la porter dans ses 8 pages, elle part dans le *Supplementary Material* — et le paragraphe de la
Méthodologie dit lequel des deux.

---

## 5. Inventaire préalable — établir les faits avant d'écrire

Rien ne s'écrit avant cet inventaire. Sources à recouper dans le dépôt :

| Ce qu'il faut établir | Où chercher |
|---|---|
| Outils agentiques d'auteur et modèles associés | `.claude/` (agents, skills, commandes), `.agents/skills/`, `specs/decideur-antigravity.md` |
| Plateforme Antigravity et modèles Gemini | `docs/paper/article/fr/99_annexes.md` § Annexe A, `.agents/skills/piloter-experience-antigravity/SKILL.md` |
| Modèles du **dispositif expérimental** (à ne PAS mélanger) | `config/llm_gateway/providers.yaml`, Annexes A et C |
| Périodes d'usage | journal git (`git log --format='%ad %s'`), `docs/changelog.md` |
| Traces de sessions conservées | `docs/traces/` (hors git depuis le 2026-09-02 — vérifier ce qui subsiste sur disque) |

**Piste de départ, à confirmer et non à recopier :** le dépôt porte des traces d'un usage de
Claude via Claude Code et de Gemini via Antigravity (Annexe A cite *Gemini 3.6 Flash* et
*3.5 Flash Lite*, mais pour le **dispositif expérimental**, ce qui ne dit rien des modèles ayant
servi à la rédaction). Les versions de la déclaration se relèvent, elles ne se déduisent pas.

---

## 6. Pièges identifiés

- **Citations hallucinées.** La politique en fait un motif de rejet d'emblée. Croiser toute
  référence issue d'une phase d'exploration assistée avec
  [`CITATIONS.md`](../paper/article/CITATIONS.md) et `docs/paper/sources/references.bib` — DOI en
  main. Recouvrement direct avec le [Ticket 065](ticket_065_consolidation_etat_de_lart_et_harmonisation_bibtex.md).
- **Le biais introduit par l'outil.** La politique demande aux auteurs de s'en prémunir. Si une
  hypothèse ou une objection vient d'un persona simulé, le dire — un « chercheur de Stanford »
  synthétique n'est pas une revue par les pairs, et le présenter comme une validation serait plus
  dommageable que de l'omettre.
- **La confusion des deux colonnes du § 1.** Reformulée ici parce que c'est l'erreur la plus
  probable à la relecture.
- **Le budget de pages.** 8 pages, références exclues. Le paragraphe de Méthodologie tient en
  5 à 8 lignes ; tout le reste est en annexe.
- **L'anonymat du matériel supplémentaire.** L'annexe H part dans le ZIP double-aveugle : les
  prompts cités ne doivent contenir ni nom, ni chemin `/Users/...`, ni identifiant de compte.
- **Périmètre du verrou.** Ce ticket touche `fr/`, `en/` et `99_annexes.md`. Chaque écriture
  s'annonce et s'attend, un accord par tâche.

---

## 7. Livrables

1. **Inventaire factuel** des outils, modèles, versions et périodes (§ 5), tracé et sourcé.
2. **Paragraphe de déclaration** dans la Méthodologie, versions FR et EN, renvoyant à l'annexe.
3. **Annexe H** (`99_annexes.md`) : spécification des outils, méta-prompts par phase, exclusions.
4. **Mise à jour de `SOUMISSION_AAMAS_2027.md`** : cocher le § 4 comme traité et pointer vers les
   deux emplacements.
5. **Ligne de suivi** dans [`suivi_actions_publication.md`](../paper/suivi_actions_publication.md)
   (section IV, Matériel AAMAS).

---

## 8. Critères d'acceptation

- [ ] Chaque outil nommé dans l'article porte une version exacte, justifiée par une trace du dépôt.
- [ ] Aucune version n'a été déduite, arrondie ou recopiée d'un exemple.
- [ ] La déclaration distingue explicitement le LLM objet d'étude du LLM assistant d'auteur.
- [ ] La déclaration figure dans une section **conservée en version double-aveugle**, pas dans les
      Remerciements.
- [ ] L'annexe H ne contient que des méta-prompts de conception, cités intégralement, chacun suivi
      de son effet sur le travail.
- [ ] Aucun prompt de débogage, aucun historique conversationnel, aucun prompt système d'agent de
      mobilité dans l'annexe H.
- [ ] Aucune donnée identifiante dans les prompts cités.
- [ ] Toute référence issue d'une phase assistée est recoupée dans `references.bib` avec son DOI.
- [ ] La phrase de responsabilité des auteurs est présente, sans conditionnel.
- [ ] Parité FR / EN vérifiée (`make paper-parite`, cf. [Ticket 066](ticket_066_controle_outille_conformite_et_parite_globale.md)).

---

## 9. Tickets et documents liés

- [`SOUMISSION_AAMAS_2027.md`](../paper/article/SOUMISSION_AAMAS_2027.md) § 4 — la politique.
- [Ticket 062](ticket_062_revue_et_alignement_des_annexes_techniques.md) — annexes A à G ; l'annexe H s'y range.
- [Ticket 065](ticket_065_consolidation_etat_de_lart_et_harmonisation_bibtex.md) — contrôle des citations.
- [Ticket 066](ticket_066_controle_outille_conformite_et_parite_globale.md) — parité et conformité outillée.
- [Ticket 053](ticket_053_acces_donnees_recherche_et_reproductibilite.md) — matériel supplémentaire et reproductibilité.
