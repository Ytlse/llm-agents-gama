# Dépôt des références de mémoire — ticket 071, § 3.3

> Écrit le 2026-09-14. **Rien n'est déposé par ce document** : il dit, référence par référence,
> d'où elle vient légitimement et ce qui manque pour cocher les quatre conditions de
> [`CITATIONS.md`](../article/CITATIONS.md).
>
> **État vérifié le 2026-09-14** sur le contenu de `etat_de_lart/` (52 PDF) : **2 des 24
> références de mémoire y sont**, Park et al. (2023) et Vu et al. (2025). Les 22 autres
> manquent, et la section 3.4 de l'article ne cite donc personne alors qu'elle décrit
> l'architecture de Park et al. adaptée par Vu et al.

## Les quatre conditions de `CITATIONS.md`

1. le PDF est dans `etat_de_lart/`, **ou l'ouvrage est consulté** pour les livres sans PDF ;
2. l'attribution est exacte ;
3. le passage est identifié ;
4. la clé BibTeX existe dans `sources/sample.bib`.

Cocher une case, c'est avoir vérifié les quatre **à la main**.

---

## A. Déposables librement — préprints arXiv

Le PDF de l'auteur est diffusé par arXiv sous une licence qui en autorise la copie. Aucune
barrière, aucun contournement.

| Référence | Source | Sert à |
|---|---|---|
| Sumers, Yao, Narasimhan & Griffiths (2024), *Cognitive Architectures for Language Agents* | arXiv:2309.02427 (paru dans TMLR, février 2024) | § 3.4, épisodique / sémantique porté aux agents de langue |
| Zhong, Guo, Gao, Ye & Wang (2024), *MemoryBank* | arXiv:2305.10250 (AAAI-24) | § 3.4, courbe d'oubli et renforcement au rappel |
| Chhikara, Khant, Aryan, Singh & Yadav (2025), *Mem0* | arXiv:2504.19413 | ch. 8, opérations choisies par le modèle |
| Xu, Liang, Mei, Gao, Tan & Zhang (2025), *A-MEM* | arXiv:2502.12110 (NeurIPS 2025) | ch. 8, évolution des notes ; **voie par seuil écartée** |
| Packer, Wooders, Lin, Fang, Patil, Stoica & Gonzalez (2023), *MemGPT* | arXiv:2310.08560 | ch. 8, le *working context* — origine de la mémoire noyau |
| Liu et al. (2025), *GATSim* | arXiv:2506.23306 | § 3.4, réflexion périodique et habitudes en transport |
| Gutiérrez, Shu, Gu, Yasunaga & Su (2024), *HippoRAG* | arXiv:2405.14831 (NeurIPS 2024) | ch. 8 **seulement**, comme piste — aucun mécanisme n'en dérive |
| Ciancone et al. (2024), *MTEB-French* | arXiv:2405.20468 | ⚠ **devenue inutile** : le passage au plongement francophone est abandonné (bascule anglaise, ticket 074). À retirer du § 3.3 plutôt qu'à déposer. |

## B. Déposables — accès ouvert par l'éditeur

| Référence | Source | Sert à |
|---|---|---|
| Papineni, Roukos, Ward & Zhu (2002), *BLEU* | ACL Anthology, actes ACL 2002, p. 311-318 | § 3.4, uniquement pour **ne pas** appeler BLEU ce qui n'en est pas un |
| Reimers & Gurevych (2019), *Sentence-BERT* | ACL Anthology, EMNLP-IJCNLP 2019 ; arXiv:1908.10084 | § 3.4, le cadre dont `all-MiniLM-L6-v2` est un modèle |

## C. Sous licence éditeur — PDF non déposable sans droit d'accès

Ces articles sont derrière une barrière d'accès. **Ne pas contourner.** Deux voies : un accès
institutionnel légitime, qui permet le dépôt si la licence l'autorise, ou la mention « ouvrage
consulté » avec page pointée, que `CITATIONS.md` admet.

| Référence | Notice | Sert à |
|---|---|---|
| Anderson & Schooler (1991) | *Reflections of the environment in memory*, Psychological Science 2(6), 396-408 | ch. 8, ce que l'activation de base encode — **pas** l'équation d'ACT-R |
| Anderson, Bothell, Byrne, Douglass, Lebiere & Qin (2004) | *An integrated theory of the mind*, Psychological Review 111(4), 1036-1060 | l'équation d'activation, notice de référence |
| Wixted & Ebbesen (1991) | *On the form of forgetting*, Psychological Science 2(6), 409-415 | ch. 8, l'oubli humain suit une **loi de puissance** — à citer là où l'exponentielle est assumée |
| McGaugh (2004) | *The amygdala modulates the consolidation of memories of emotionally arousing experiences*, Annual Review of Neuroscience 27, 1-28 | § 3.4, la gravité allonge la rétention |
| Diekelmann & Born (2010) | *The memory function of sleep*, Nature Reviews Neuroscience 11(2), 114-126 | § 3.4, consolidation en fin de journée |
| McClelland, McNaughton & O'Reilly (1995) | *Why there are complementary learning systems…*, Psychological Review 102(3), 419-457 | § 3.4 et ch. 8, deux systèmes |
| Verplanken & Aarts (1999) | *Habit, attitude, and planned behaviour*, European Review of Social Psychology 10(1), 101-134 | ch. 8, l'habitude comme automatisme |
| Goodwin (1977) | *Habit and hysteresis in mode choice*, Urban Studies 14(1), 95-98 | ch. 7 et 8, l'hystérésis du choix modal |

## D. Ouvrages — pas de PDF, « ouvrage consulté »

`CITATIONS.md` prévoit explicitement ce cas. Il demande en échange un passage identifié.

| Référence | Notice | Passage à pointer |
|---|---|---|
| Anderson & Lebiere (1998) | *The Atomic Components of Thought*, Lawrence Erlbaum | l'équation `A_i = B_i + Σ W_j S_ji + ε`, l'apprentissage de base, l'appariement partiel, le seuil de rappel |
| Tulving (1972) | *Episodic and semantic memory*, in Tulving & Donaldson (dir.), *Organization of Memory*, Academic Press, 381-403 | la distinction épisodique / sémantique |
| Ebbinghaus (1885) | *Über das Gedächtnis*, Duncker & Humblot | la courbe d'oubli que MemoryBank reprend. Domaine public : une numérisation d'archive convient |
| Laplace (1814) | *Essai philosophique sur les probabilités*, Courcier | la règle de succession. Domaine public : une numérisation d'archive convient |

---

## État du dépôt au 21 septembre 2026

**Fait.** Les neuf PDF des groupes A et B sont déposés dans `etat_de_lart/`, indexés au § 9 de
son `README.md`, et leurs neuf clés BibTeX sont dans `sources/sample.bib`. Chaque PDF a été
ouvert et son titre vérifié contre la notice : les neuf correspondent. Conditions 1, 2 et 4
remplies pour ces neuf.

| Fichier déposé | Clé BibTeX |
|---|---|
| `Sumers_2024_CoALA.pdf` | `sumers2024coala` |
| `Zhong_2024_MemoryBank.pdf` | `zhong2024memorybank` |
| `Chhikara_2025_Mem0.pdf` | `chhikara2025mem0` |
| `Xu_2025_A-MEM.pdf` | `xu2025amem` |
| `Packer_2023_MemGPT.pdf` | `packer2023memgpt` |
| `Liu_2025_GATSim.pdf` | `liu2025gatsim` |
| `Gutierrez_2024_HippoRAG.pdf` | `gutierrez2024hipporag` |
| `Reimers_2019_Sentence-BERT.pdf` | `reimers2019sbert` |
| `Papineni_2002_BLEU.pdf` | `papineni2002bleu` |

⚠ **La condition 3 n'est remplie pour aucune des neuf** : le passage citant doit être identifié
dans `CITATIONS.md`, qui est sous verrou d'écriture. Neuf entrées y restent à créer, sous accord.

⚠ **`CITATIONS.md` pointe une bibliographie qui n'existe pas.** Sa condition 4 nomme
`../sources/references.bib` ; seul `sample.bib` existe, et c'est lui que le template LaTeX
appelle (`\bibliography{sample}`). Le pointeur est à corriger, sous verrou.

## Ce qu'il reste à faire, dans cet ordre

1. **Retirer Ciancone et al. (2024)** du § 3.3 du ticket : le passage au plongement francophone
   est abandonné, la référence n'a plus d'objet.
2. ~~Déposer les dix PDF des groupes A et B~~ — **fait le 21 septembre 2026**, neuf fichiers
   (Ciancone sortie de la liste).
3. **Trancher pour le groupe C** : accès institutionnel, ou mention « ouvrage consulté ».
   *Demande une main humaine : aucun paywall ne se contourne.*
4. **Consulter les quatre ouvrages du groupe D** et pointer le passage.
   *Demande une main humaine : un ouvrage ne se consulte pas à ma place.*
5. ~~Ajouter les clés BibTeX dans `sources/sample.bib`~~ — **fait le 21 septembre 2026** pour les
   neuf déposées. Les douze références des groupes C et D restent sans clé, ce qui est correct :
   une référence non déposée n'est pas une référence à citer.
6. **Créer les neuf entrées de `CITATIONS.md`** avec leur phrase citante et leur passage pointé,
   sous accord explicite (verrou de l'article).

⚠ **Une référence non déposée n'est pas une référence à citer.** La règle de tenue de
`CITATIONS.md` existe pour cela, et la section 3.4 de l'article ne doit pas s'appuyer sur ce
qui n'a pas passé les quatre conditions.
