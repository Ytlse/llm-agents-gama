# Questions vivantes — ticket 085 (une contrainte de run dans un fichier global)

> Écrites pendant l'implémentation, à poser en fin de lot. Chaque hypothèse retenue est tenue par
> au moins un test du contrat (`specs/ticket_085/tests.md`) : si elle est tranchée autrement, le
> test qui tombe dit où toucher.

## Q1 — Le refus déterministe doit-il arrêter le run ? *(question du § 9 du ticket)*

Quand le client reçoit le refus du lot A, faut-il **arrêter l'exécution** plutôt que laisser chaque
décision échouer jusqu'au détecteur d'immobilité ? Une faute de configuration ne se répare pas en
réessayant, et dix échecs rapides valent mieux que dix échecs lents — mais ils restent dix échecs.

**Hypothèse retenue :** on ne change **pas** le comportement du client. Le lot A rend le motif juste
et rapide ; la pause automatique pour immobilité (« 420 s sans avancée ») fait déjà le reste, et
elle le fait pour tous les blocages, pas seulement celui-là. Tenu par le test A7.

**Alternative :** ajouter `configuration` à la liste des types terminaux de `runner.py`, à côté de
`epuise`. Coût : une catégorie de plus dans une machine à états déjà dense, pour gagner ~400 s sur
un incident qui, une fois le lot A livré, se lit dans le journal dès la première décision.

## Q2 — Le nom du type d'erreur côté client

`configuration:` est un préfixe **nouveau** : il apparaîtra dans `attentes_par_type` du tableau de
bord et dans `erreurs.jsonl` comme un type jamais vu.

**Hypothèse retenue :** c'est voulu. Le réutiliser sous un nom existant (`passerelle_occupee`,
`epuise`) est exactement l'erreur que le lot A corrige — le seau où on le range envoie chercher la
panne au mauvais endroit. Un type nouveau est le prix d'un diagnostic juste.

## Q3 — `execution.yaml` en reprise

Une reprise rouvre une exécution existante. Si la restriction a changé entre le lancement et la
reprise, que doit dire la trace ?

**Hypothèse retenue :** la liste effectivement en vigueur est réécrite, et le changement est
journalisé. Une trace qui décrit la restriction du premier jour pour une mesure poursuivie sous une
autre est fausse au sens qui compte.

**Alternative :** ne jamais toucher une exécution existante, et refuser la reprise quand la
restriction diffère. Plus strict, mais il bloque une reprise légitime après un simple ajout de clé
aux fournisseurs — or B2 dérive justement la liste du modèle pour rester vraie dans ce cas-là.

## Q4 — `cache.enabled` et `cache_dir` *(§ 8 du ticket)*

Même forme de défaut : un état par run logé dans un fichier partagé, mutable et non versionné, que
`make run` réécrit en place pendant qu'une autre expérience le lit. Non traités ici.

**Hypothèse retenue :** hors périmètre, à ouvrir en ticket propre — avec `make run` et son injection
par run, qui est la vraie condition pour clore le sujet (§ 3 du ticket).
