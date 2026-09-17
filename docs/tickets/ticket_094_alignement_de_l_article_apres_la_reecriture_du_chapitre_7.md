# Ticket 094 — Ce que la réécriture du chapitre 7 laisse faux ailleurs dans l'article

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-17, à la clôture de la réécriture du chapitre 7 en `brouillon v1.0`.
>
> **Objet.** Six corrections dans quatre fichiers verrouillés. Deux d'entre elles portent sur des
> phrases du résumé qui étaient **déjà** fausses avant cette réécriture : le résumé annonce trente
> articles et 120 prédictions quand le chapitre 1 en annonce cinq et vingt depuis sa `v0.23`, et il
> promet une ablation causale du registre de mémoire que l'ambition déclarée ne porte pas.
>
> **Ce ticket n'écrit rien de lui-même.** Chaque fichier visé est sous le verrou de
> `docs/paper/article/` : la procédure de la skill `article-verrou` s'applique, diff présenté puis
> accord explicite.

---

## 1. D'où vient ce ticket

Le chapitre 7 était le dernier brouillon hérité du manuscrit `v1.6`. Sa réécriture du 2026-09-17
retire la formule $w_m(t)$, qui n'est implémentée nulle part, les parts modales du manuscrit, que
personne n'a mesurées, le vocabulaire « Tier », et ramène l'épreuve de presse aux cinq événements
que le chapitre 1 annonce. Le signalement de fin de tâche a croisé ces changements avec le reste du
texte. Il a trouvé trois écarts majeurs et trois mineurs.

Deux des trois majeurs ne sont pas nés de la réécriture. Le résumé et le chapitre 1 se
contredisaient déjà ; le chapitre 7 disait comme le résumé, ce qui rendait l'écart invisible. Il
dit maintenant comme le chapitre 1, et le résumé reste seul.

---

## 2. Majeur — le résumé annonce un périmètre que l'article n'évalue pas

**Où :** `fr/00_abstract.md` § 3 et `en/00_abstract.md` § 4.

**Ce que le texte dit aujourd'hui :**

> Trente articles portent 120 prédictions gelées avant tout appel au modèle, dont [xx] % vérifiées.

> Thirty articles carry 120 predictions frozen before any call to the model, [xx] % of them met.

**Pourquoi c'est faux.** Le § 1.3 du chapitre 1 gèle **cinq** événements et **vingt** prédictions
signées depuis sa `v0.23` du 2026-09-17. Les trente scénarios de
`docs/paper/sources/actualites/RAPPORT_SCENARIOS_QUALITATIFS_TOULOUSE.md` sont une matrice de
candidats, dont le rapport retient cinq ; le chapitre 7 renvoie la matrice en annexe et n'évalue
que les cinq. Écrit à trente, le résumé annonce une campagne de 494 850 décisions — cinq
conditions sur les 3 299 déplacements de la cohorte, trente fois — quand la campagne annoncée en
pèse 82 475.

**Correction proposée :**

> Cinq articles portent vingt prédictions signées, gelées avant tout appel au modèle, dont [xx]
> vérifiées.

La barre du test binomial passe alors de 50 % sur 120 items à **quinze signes sur vingt**
($p = 0{,}021$ ; quatorze ne suffit pas, $p = 0{,}058$). Elle est écrite au § 7.1.3 ; le résumé n'a
pas à la porter, mais il ne doit pas suggérer un effectif qu'elle n'a pas.

---

## 3. Majeur — le résumé promet une ablation causale que l'article ne conduit pas

**Où :** `fr/00_abstract.md` § 3 et `en/00_abstract.md` § 4.

**Ce que le texte dit aujourd'hui :**

> Cinq jours après une panne de métro, l'ablation du registre de mémoire dit si l'inertie vient de
> lui.

> Five days after a metro failure, ablating the memory register says whether the inertia comes
> from it.

**Pourquoi c'est faux.** La position de l'auteur du 2026-09-14 est que la mémoire est un élément du
dispositif et non l'objet d'une preuve causale isolée. Le chapitre 1 le dit dans le titre même de sa
contribution C3, « évalués pour leur **robustesse** ». Le chapitre 7 rapporte l'ordre des trois
conditions au troisième jour et la monotonie du retour ; les variantes de vitesse d'oubli partent en
annexe au titre de la robustesse, conformément au § 6.3 du plan longitudinal.

**Correction proposée :**

> Cinq jours après une panne de métro, trois conditions disent si l'inertie survit au
> rétablissement du réseau.

---

## 4. Majeur — la fiche d'avancement du chapitre 7 décrit le brouillon précédent

**Où :** `fr/README.md`, fiche 7 (lignes 207 à 215), ligne 43 du tableau de synthèse, et ligne 62.

**Ce que le texte dit aujourd'hui :**

| Emplacement | Contenu périmé |
|---|---|
| Fiche 7, statut | `🟠 brouillon hérité · brouillon v0 · 1 220 mots` |
| Fiche 7, présent | `5.1 · 5.2 · 5.3 — même contenu, numérotation du manuscrit` |
| Fiche 7, sections prévues | `7.1 hystérésis · 7.2 presse · 7.3 prédictions` |
| Fiche 7, reste à faire | « les chiffres cités viennent du manuscrit », « vocabulaire Tier 1/2/3 à reprendre » |
| Tableau, ligne 43 | `🟠 brouillon hérité · brouillon v0 · campagnes non jouées, numérotation périmée` |
| Ligne 62 | « Les cinq derniers partagent la même dette : vocabulaire Tier 1/2/3 à remplacer » |

**Ce qui est vrai depuis le 2026-09-17.** Le chapitre est en `brouillon v1.0`, 1 523 mots de prose,
trois sections écrites (7.1 presse, 7.2 hystérésis, 7.3 ce que le chapitre transmet), sans une
occurrence de « Tier » ni un chiffre du manuscrit. Ce qui reste vrai : les deux campagnes ne sont
pas jouées, et c'est désormais dit dans le chapitre lui-même plutôt que dans sa fiche.

**Correction proposée.** Refaire la fiche sur les trois sections écrites, retirer le chapitre 7 de
la liste des cinq chapitres qui partagent la dette « Tier » en ligne 62, et porter la ligne 43 à
`🟡 rédigé, campagnes à jouer`.

---

## 5. Mineurs — trois endroits qui annoncent l'ordre inverse

Le chapitre passe la presse avant l'hystérésis, l'inverse de ce qui est annoncé. Le motif est
qu'après le chapitre 6, la presse n'ajoute qu'un texte au contexte, à mémoire éteinte, quand
l'hystérésis ajoute la mémoire : le dispositif reçoit ses ingrédients un à la fois.

| Fichier | Ce qui reste à permuter |
|---|---|
| `fr/01_introduction.md` § 1.4 | « les deux régimes non tabulés, hystérésis et événements de presse » |
| `en/01_introduction.md` § 1.4 | la même phrase en anglais |
| `plan/PLAN.md` lignes 77-80 | les trois sous-sections listées, qui suivent l'ancien découpage |
| `README.md` ligne 58 | la ligne d'avancement du chapitre 7, restée à « brouillon » |

**Autre issue, à trancher par l'auteur.** Remettre le chapitre dans l'ordre annoncé coûte deux
permutations de sous-sections et rend ces quatre corrections sans objet. L'ordre du chapitre n'est
pas un résultat ; il se défait sans perte.

---

## 6. Ce que ce ticket ne couvre pas

**Le chapitre 9 et les annexes.** `fr/09_conclusion.md` porte encore « Tier 2 », « Tier 3 », la
thèse attribuée à Baronchelli et l'architecture hybride en cascade comme contribution, que le
chapitre 1 a retirée en `v0.2` ; `fr/99_annexes.md` porte la même dette. Le détecteur de style les
signale tous deux au-dessus des seuils (`09` à 12,8 gras pour 1 000 mots, `99` à 6,9 cadratins et
13,2 gras). C'est le chantier de deux chapitres à réécrire, pas un alignement : il relève du
ticket 067 ou d'un ticket à ouvrir, pas de celui-ci.

**Les huit points à traiter avant la première campagne du chapitre 7.** Ils vivent dans la note de
travail en fin de `fr/07_untabulated_regimes.md` et appartiennent à leurs tickets : grille des vingt
signes incomplète sur trois cellules et textes des articles absents (059, 064) ; `experiments.yaml`
encore sur les trois événements antérieurs (064) ; conditions non jouables dans le même mode,
conversion des déclarations d'oubli, profil de choc à un ou deux jours (041, 048, 079) ; intégrité
de ce que la mémoire apprend (077).

**Les deux citations d'ordre de grandeur.** Le § 7.2.2 porte sans appel de citation les pertes
permanentes de part relevées après une grève de transport, de 0,3 à 2,5 %. Les sources existent
dans le plan longitudinal (van Exel & Rietveld, 2001 ; Larcom, Rauch & Willems, 2017) mais n'ont ni
PDF au dépôt ni entrée au bib. À instruire dans `CITATIONS.md` avant de les nommer, selon la règle
du 2026-09-17.

---

## 7. Ordre de marche

1. Trancher l'ordre des deux régimes : garder celui du chapitre, ou le remettre dans l'ordre
   annoncé. La réponse décide si le § 5 existe.
2. Présenter un seul diff couvrant `fr/00_abstract.md`, `en/00_abstract.md`, `fr/README.md`,
   et selon le point 1, `fr/01_introduction.md`, `en/01_introduction.md`, `plan/PLAN.md`,
   `README.md`.
3. Écrire après accord, puis `make paper-style` sur chaque chapitre touché.
4. Vérifier que le résumé et le § 1.3 disent le même effectif, à la main : un grep sur « cinq »
   ne distingue pas les cinq événements des cinq conditions.

---

## 8. Critères d'acceptation

- Le résumé, dans les deux langues, annonce cinq articles et vingt prédictions.
- Le résumé, dans les deux langues, n'annonce plus que l'ablation dit d'où vient l'inertie.
- La fiche 7 de `fr/README.md` décrit les sections réellement écrites, et le chapitre 7 ne figure
  plus dans la dette « Tier ».
- L'ordre des deux régimes est le même dans le chapitre, le chapitre 1 et le plan.
- `make paper-style` ne signale aucun écart nouveau sur les fichiers touchés.
