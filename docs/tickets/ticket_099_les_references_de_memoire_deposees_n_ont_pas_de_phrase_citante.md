# Ticket 099 — Les références de mémoire déposées n'ont pas de phrase citante

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-21, en reliquat du [ticket 071](ticket_071_evolution_memoire_du_code_actuel_a_l_etat_vise.md)
> clos le même jour. Le 071 a déposé les PDF et créé les clés ; il reste à écrire les phrases
> qui les citent, et à trancher un cas que ni le code ni moi ne pouvons trancher.

---

## 1. La question, en une phrase

Onze références de mémoire sont déposées, référencées et prêtes à servir — et la section qui
décrit leurs mécanismes n'en cite toujours aucune.

---

## 2. Où en est le dépôt

La règle de tenue de `CITATIONS.md` pose quatre conditions. Au 2026-09-21 :

| Condition | État |
|---|---|
| 1 · le PDF est dans `etat_de_lart/` | ✅ pour 11 références |
| 2 · l'attribution est exacte | ✅ les 11 PDF ouverts, titre confronté à la notice |
| 4 · la clé BibTeX existe dans `sample.bib` | ✅ 11 clés, `sumers2024coala` à `laplace1814essai` |
| 3 · le passage citant est identifié | ❌ **pour 9 des 11** |

Les entrées `A40` à `A50` de `CITATIONS.md` existent et portent chacune la section visée et le
passage à pointer. Leur case reste ouverte parce que la phrase, elle, n'est pas écrite.

Deux exceptions déjà servies : `A49` Reflexion, que le chapitre 5 citait depuis toujours sans
dépôt, et `A50` Laplace, appelée par le chapitre 7.

---

## 3. Ce qu'il reste, en trois lots

### Lot A — Les neuf phrases citantes

Le § 3.4 décrit l'architecture de Park et al. adaptée par Vu et al. sans nommer l'une ni
l'autre, et le chapitre 8 discute des mécanismes venus de Mem0, A-MEM et MemGPT sans les citer.
Chaque entrée `A40`–`A48` porte déjà la section où elle sert et le passage à pointer.

Deux points à ne pas perdre en écrivant :

- **A44, HippoRAG** se cite **comme piste seulement**. Aucun mécanisme du dépôt n'en dérive, et
  le laisser croire serait faux.
- **A43, A-MEM** se cite **avec sa divergence** : la voie par seuil de similarité y est décrite,
  et ce dépôt l'a explicitement écartée au profit d'opérations désignées par le modèle.

À dire aussi quand Vu et al. seront cités : leurs poids publiés sont 0,3 / 0,3 / 0,4, la récence
portant le poids fort, là où le dispositif sert 0,30 / 0,10 / 0,20 / 0,20 / 0,20. L'écart est
propre à ce dépôt.

### Lot B — Tulving (1972), à trancher

Le § 3.4 FR et EN attribue la distinction épisodique / sémantique à Tulving. Ni PDF ni clé, et
c'est un chapitre d'ouvrage sans version libre. **Ni le code ni une session ne peuvent lever
ce point** : il faut soit consulter l'ouvrage et poser la mention « ouvrage consulté », soit
renoncer à l'attribution et décrire la distinction sans la nommer.

C'est la citation la plus porteuse de la section — elle nomme le partage dont tout le reste du
mécanisme découle.

### Lot C — Les douze références restées hors dépôt

Huit articles sous licence éditeur (Anderson & Schooler 1991, Anderson et al. 2004, Wixted &
Ebbesen 1991, McGaugh 2004, Diekelmann & Born 2010, McClelland et al. 1995, Verplanken & Aarts
1999, Goodwin 1977) et trois ouvrages sans PDF (Anderson & Lebiere 1998, Tulving 1972,
Ebbinghaus 1885). Chacune demande un accès institutionnel ou la mention « ouvrage consulté ».
Aucun paywall ne se contourne.

**Une référence non déposée n'est pas une référence à citer** : tant que le lot C n'est pas
traité, l'ancrage ACT-R demandé par la relecture extérieure ne peut pas entrer dans le texte.

Classement complet et notices recoupées :
[`docs/paper/sources/DEPOT_MEMOIRE_TICKET_071.md`](../paper/sources/DEPOT_MEMOIRE_TICKET_071.md).

---

## 4. Relevé au passage, sans lien avec les citations

Le chapitre 9 dépasse le seuil de densité de gras du détecteur de style, dans les deux langues
et **avant** les corrections du 21 septembre : 12,9/1k en français et 11,6/1k en anglais sur
`HEAD`, pour un seuil de 10,0. Le dé-graisser demande de réécrire des paragraphes, ce qui
relève d'une passe de style et non d'une correction de citation.

---

## Critères de clôture

- [ ] Les neuf phrases citantes sont écrites, sous accord explicite (verrou de l'article), et
      les cases de `A40` à `A48` sont cochées.
- [ ] Le cas Tulving est tranché — ouvrage consulté et clé créée, ou attribution retirée du
      § 3.4 FR et EN.
- [ ] Le lot C est traité référence par référence : déposée, ou déclarée « ouvrage consulté »,
      ou la citation est renoncée par écrit.
- [ ] Aucune citation du texte ne manque une des quatre conditions de `CITATIONS.md`.
