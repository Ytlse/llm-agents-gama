# Ticket 050 — Formalisation mathématique du dispositif agentique (Chapitre 3)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-13 suite à l'arbitrage de la liste des actions pour la publication AAMAS 2027.
>
> **Touche l'article** : modification directe de [`docs/paper/article/fr/03_architecture.md`](../paper/article/fr/03_architecture.md).

## Contexte & Enjeux (Standard AAMAS)

Le chapitre 3 actuel ([`fr/03_architecture.md`](../paper/article/fr/03_architecture.md)) est rédigé sous un style narratif issu des premières versions de travail (« GAMA porte le monde, le contrôleur le cycle de vie, le module LLM le choix »). 

Face aux exigences méthodologiques d'AAMAS (*Autonomous Agents and Multiagent Systems*), l'absence de formalisation d'état et d'espace d'action expose le papier à l'objection critique d'un modèle d'agent purement discursif. Il est indispensable d'introduire dès la présentation du système un bloc formel mathématique rigoureux et compact.

## Ce que le ticket livre

Remplacer la description narrative du § 3.1 et du § 3.3 par une formalisation propre en un bloc compact :

1. **Définition formelle de l'agent par un quadruplet d'état :**
   $$\text{Agent}_i = \langle P_i, M_{i,t}, C_i, \pi_\theta \rangle$$
   où :
   - $P_i \in \mathcal{P}$ est le vecteur de persona socio-démographique scellé, strictement restreint au contrat des 21 variables alignées sur l'enquête Cerema EMC² 2023 (12 individu/ménage, 3 contexte de déplacement, 6 géographie fine).
   - $M_{i,t} = \langle \mathcal{M}^{\text{STM}}_{i,t}, \mathcal{M}^{\text{LTM}}_{i,t} \rangle$ est le registre d'état bi-composante de mémoire à l'instant $t$ associant le tampon circulaire d'observations récentes de la journée et l'index vectoriel épisodique long-terme avec décroissance temporelle.
   - $C_i \in \mathcal{C}$ est l'état physique de la chaîne de véhicules du ménage de l'individu (localisation géographique instantanée de la voiture et du vélo, statut de motorisation, détention du permis).
   - $\pi_\theta$ est la politique décisionnelle verbalisée paramétrée par le grand modèle de langue $\theta$.

2. **Espace d'action contextuel restreint $\mathcal{A}(o_t, C_i)$ :**
   - L'espace d'action offert à l'agent à l'instant $t$ n'est pas un ensemble abstrait de modes, mais le sous-ensemble fini des itinéraires viables produits par OpenTripPlanner (grilles horaires réelles GTFS) et OSMnx (plus court chemin réseau routier/piéton) :
     $$\mathcal{A}(o_t, C_i) \subseteq \mathcal{O}(o_t)$$
     strictement conditionné par le filtre d'éligibilité et de localisation des véhicules $C_i$ (ex: un mode véhiculé personnel requiert que le véhicule soit présent au point de départ et que l'agent soit habilité).

3. **Règle de décision stochastique :**
   - Formaliser la décision non comme un maximum déterministe ($\operatorname{argmax}$), mais comme un tirage probabiliste :
     $$a_t \sim \pi_\theta(\cdot \mid o_t, M_{i,t})$$
     sur la distribution de probabilité verbalisée par le modèle, garantissant la conservation de l'hétérogénéité individuelle et la reproductibilité via une graine dépendante du contexte.

## Fichiers cibles
- [`docs/paper/article/fr/03_architecture.md`](../paper/article/fr/03_architecture.md) (§ 3.1 & § 3.3)
- Miroir anglais à reporter lors de la phase de parité [`docs/paper/article/en/03_architecture.md`](../paper/article/en/03_architecture.md)

## Critères d'acceptation
- [ ] Le quadruplet $\text{Agent}_i = \langle P_i, M_{i,t}, C_i, \pi_\theta \rangle$ est posé dès la première page du chapitre 3.
- [ ] L'espace d'action $\mathcal{A}(o_t, C_i)$ est formellement lié aux moteurs de calcul d'itinéraire OTP/OSMnx.
- [ ] Le processus d'échantillonnage probabiliste $a_t \sim \pi_\theta$ est rigoureusement distingué d'un classifieur argmax déterministe.
- [ ] Les fichiers de suivi [`docs/paper/article/actions.md`](../paper/article/actions.md) (§ 3) et [`docs/paper/article/ameliorations.md`](../paper/article/ameliorations.md) (§ 7) sont marqués comme pris en charge.
