# Ticket 102 — La suite `scripts/tests` ne distingue plus une régression d'un fond de décor

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-22, à la demande de l'auteur, après le constat fait en clôturant
> l'étape 2 du [ticket 095](ticket_095_duree_d_un_souvenir_et_enquete_du_soir.md).
>
> **Objet.** `scripts/tests` rend **62 échecs**. Aucun ne vient du travail du jour — vérifié en
> rejouant la suite sur un worktree détaché au commit `2baf55b`, puis en comparant les **noms**
> des tests en échec, pas les comptes. Mais tant que ce fond existe, une régression neuve y
> disparaît : c'est déjà arrivé le 2026-09-22, où « 1946 tests, 0 échec » a été annoncé pendant
> des jours sur un périmètre qui n'incluait pas `scripts/tests`.
>
> **Ce ticket ne bloque aucune campagne.** Le chemin qu'emprunte une campagne est vert :
> `services/llm-agents` 1950/0, les trois paquets 0 échec, les quatre fichiers de test qui
> touchent `run_sequential_cohort.py` 68/0. Les 62 sont dans le tableau de bord (54 sur 62), le
> détecteur de style, le tirage météo et l'outillage papier.

---

## 0. Les chiffres, et comment ils ont été établis

| Mesure | Valeur |
|---|---:|
| Échecs `scripts/tests` dans l'arbre de travail | **62** (1435 passés, 22 ignorés) |
| Échecs au commit `2baf55b`, worktree détaché | **73** |
| Tests en échec **chez nous et pas au commit** | **1** |
| Tests en échec **isolément**, fichier par fichier | **28** |
| Tests qui n'échouent que **dans la suite complète** | **34** |

Méthode, à reproduire telle quelle avant de conclure quoi que ce soit sur ce ticket :

```bash
git worktree add --detach /tmp/base_head HEAD
(cd /tmp/base_head && services/llm-agents/.venv/bin/python -m pytest scripts/tests -q) > base.txt
services/llm-agents/.venv/bin/python -m pytest scripts/tests -q > courant.txt
comm -13 <(grep ^FAILED base.txt | sed 's/^FAILED //;s/ - .*//' | sort) \
         <(grep ^FAILED courant.txt | sed 's/^FAILED //;s/ - .*//' | sort)
```

⚠ **Comparer les noms, jamais les comptes.** Le worktree détaché ignore 123 tests là où l'arbre
de travail n'en ignore que 22 (fichiers non suivis absents) : les totaux ne sont pas comparables,
les noms le sont.

---

## 1. Lot A — `st.button()` à l'intérieur d'un `st.form()` · **le cœur du ticket**

**14 tests** portent cette exception Streamlit :

```
`st.button()` can't be used in an `st.form()`. Use `st.form_submit_button()` instead.
```

Ce n'est **pas** un test instable : c'est une violation réelle de l'API, levée au rendu. Elle ne
se déclenche que sur un chemin que la suite complète débloque — les mêmes tests passent joués
seuls. Les trois `st.form(` du tableau de bord (`app.py` 682 et 756, `mes_travaux.py` 277) ne
contiennent aucun `st.button` en propre : l'appel fautif vient d'un helper rendu à l'intérieur,
et c'est ce helper qu'il faut trouver.

C'est le lot qui commande les autres : tant que 14 échecs dépendent de l'ordre d'exécution,
la suite n'est pas un signal.

- [ ] Localiser l'appel (reproduire avec `AppTest` sur l'onglet `tickets`, état accumulé)
- [ ] Le corriger dans l'application, pas dans le test
- [ ] Vérifier que les 14 passent aussi bien seuls qu'en suite

---

## 2. Lot B — Attentes périmées, sans arbitrage

Trois tests décrivent un état que le dépôt a quitté. Aucun ne demande de décision.

**B1 · L'onglet « 🔁 Campagne »** — `test_dashboard_onglet_url::test_les_slugs_couvrent_tous_les_onglets_dessines`.
Le test garde **sa propre copie** de la table `ONGLETS`, et son commentaire dit pourquoi :
« elle est recopiée ici, et c'est le point : l'oubli se voit ». L'alarme a donc fonctionné —
l'onglet a été ajouté à `app.py` sans être décoché ici. Une ligne à ajouter.

**B2 · La liste des services requis s'est élargie** — famille `test_dashboard_app::test_R1*`.
Le bloc attend « 2 service(s) à démarrer » et deux pastilles ⚪ ; il en rend davantage
(`otp1`, `otp2`, `otp3`, `osmnx1`). L'attendu suit la nouvelle liste.

**B3 · Le chapitre choisi par `test_083` n'est plus chargé** —
`test_le_hook_signale_un_chapitre_charge` prend `fr/99_annexes.md` en le supposant au-dessus
des seuils de style, pour voir le hook afficher « signal, pas une autorité ». La réécriture de
l'article l'a nettoyé, le hook répond `SUCCÈS`. ⚠ **Ne pas dégrader le seuil pour faire passer
le test** : il lui faut un chapitre FABRIQUÉ, écrit pour l'occasion. Un test qui dépend d'un
livrable vivant se périme à chaque relecture.

- [ ] B1, B2, B3

---

## 3. Lot C — Travail en cours d'autres chantiers · **vérifier avant de toucher**

**~14 tests** de `test_dashboard_app` (champ `jeu` absent du brouillon, famille « inspirer »)
et **8** de `test_qualification_60_tickets` (car scolaire : éligibilité par âge, hors Tisséo,
motif études, gratuité, plage horaire, rendu GAMA, compteurs).

⚠ Ces échecs viennent de chantiers qu'une autre session écrit peut-être en ce moment. Avant
d'en corriger un seul : vérifier `git worktree list` et l'état des branches. Corriger par-dessus
un travail en cours produit un conflit, pas une amélioration. Si le chantier est vivant, ces
tests reviennent à **son** porteur et sortent de ce ticket.

- [ ] Établir à qui appartient chaque famille
- [ ] Corriger celles qui n'ont pas de porteur, renvoyer les autres

---

## 4. Lot D — Deux arbitrages qui reviennent à l'auteur

**D1 · Le quota journalier insuffisant : refus ou détail ?**
`test_dashboard_filtres_hygiene::test_les_modeles_a_quota_derisoire_sont_ecartes` attend que
`gemini-3.8-flash` (20 requêtes/jour déclarées contre ~2 285 pour la charge de référence) soit
écarté du formulaire. `aptitude.py` a été changé : le manque de quota est passé de **refus** à
**détail**, avec ce motif — « les limites de `providers.yaml` sont déclaratives et connues comme
parfois fausses : ce n'est pas un refus ». Les deux positions se défendent ; il faut trancher,
puis aligner celui des deux qui a tort. Le message d'erreur du test est en plus trompeur (« un
dict vide signale un import muet ») : le module se charge parfaitement, c'est le verdict qui a
changé. À corriger dans tous les cas.

**D2 · Le ticket 095 n'a pas de bloc `triage`** —
`test_dashboard_tickets_status::test_R34_tous_les_tickets_ouverts_sont_tries`. Les deux échelles
et l'axe AAMAS se posent avec leur raison écrite ; ce n'est pas à une session de les inventer.

- [ ] D1 tranché, puis appliqué au code ou au test
- [ ] D1 : message d'erreur du test corrigé quoi qu'il arrive
- [ ] D2 tranché

---

## 5. Lot E — Le reste, à instruire

| Test | Symptôme |
|---|---|
| `test_weather_draw` (2) | lit le `config.yaml` **vivant** et exige qu'il active le tirage — un test couplé à un fichier que chaque run modifie |
| `test_mode_choice_forest` (2) | `rf_mode_choice_policy` apparaît dans une source qui ne devrait pas le nommer |
| `test_gama_includes` (1) | `0 != 2` sur la fenêtre et le masque binaire |
| `test_synthese_generation_population` (1) | `docs/paper/population/synthese_representativite…` absent — livrable non généré |

- [ ] Instruire les quatre

---

## 5 bis. Lot F — Les tests qui lisent un fichier que chaque run réécrit

Motif trouvé le 2026-09-22 **pendant** la campagne c3, et il est plus grave que les autres : un
test peut être vert parce qu'un fichier de configuration se trouve dans le bon état, et non parce
que le code est juste.

**Le cas établi.** Cinq tests de `test_079_chocs.py` posaient `settings.chocs.*`, la clé du
ticket 079. Depuis le ticket 100, `_declaration_demandee()` regarde `settings.evenements`
D'ABORD et ne descend sur `chocs` que si le premier bloc est éteint. Tant que le `config.yaml`
du dépôt portait l'ancienne clé, `settings.evenements.enabled` était faux et les cinq passaient —
**pour la mauvaise raison**. La campagne a écrit la clé neuve dans ce fichier et ils sont tombés
d'un coup, en cherchant une déclaration à un chemin de conteneur. Corrigé : la fixture éteint les
DEUX blocs à l'entrée et les rend à leur valeur d'origine à la sortie ; le fichier ne lit plus
`config.yaml`.

**Ce qui reste à faire.**

- [ ] `test_100_lot1_migration.py` et `test_100_lot2_canal_lu.py` posent aussi `settings.chocs` :
      vérifier s'ils portent la même dépendance latente, et appliquer la même isolation.
- [ ] `test_weather_draw` (lot E) exige que le `config.yaml` vivant active le tirage — même
      famille, même remède.
- [ ] Chercher les autres : `grep -rn "settings\.\(chocs\|evenements\|cache\)" services/llm-agents/tests/`.
      Tout test qui MUTE le singleton `settings` sans le restaurer appartient à ce lot.

⚠ **Un run en cours réécrit `services/llm-agents/config/config.yaml`.** Une suite lancée pendant
une campagne ne mesure donc pas la même chose qu'une suite lancée à froid. C'est vrai aujourd'hui
et il faut que ça cesse — sinon le critère central ci-dessous (même verdict en entier et fichier
par fichier) restera hors d'atteinte.

---

## 6. Critères d'acceptation

- [ ] `scripts/tests` rend **le même verdict joué en entier et fichier par fichier**. C'est le
      critère central : un écart entre les deux signifie qu'il reste de l'état partagé.
- [ ] Zéro échec, ou une liste **nommée** d'échecs connus avec leur raison — un test qu'on
      choisit de laisser rouge se déclare, il ne se subit pas.
- [ ] Une cible `make` unique lance TOUT le périmètre (`services/llm-agents`, `scripts`, les
      trois paquets). Le défaut d'origine est là : trois périmètres, trois commandes, et un
      chiffre annoncé qui n'en couvrait qu'un.

---

## 7. Ce que ce ticket ne fait pas

Il ne touche pas aux tests de `services/llm-agents` ni des paquets : ils sont au vert et le
restent. Il ne réécrit aucun test pour le faire passer — un attendu se change quand la décision
qui le fondait a changé, et le ticket dit alors laquelle.
