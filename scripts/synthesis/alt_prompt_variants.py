"""Les dix variantes de prompt testées contre le report marche → transports collectifs.

**D'où viennent-elles.** Pas d'une intuition : des 494 justifications que le modèle a
lui-même écrites (colonne « Raisonnement » de ``moves.csv``) sur les décisions du
sous-jeu — celles où il a retenu les transports collectifs alors que la marche lui était
proposée. Le dépouillement de ces 494 phrases donne cinq arguments récurrents, et chaque
variante en vise un :

===================================  =======  ================================
Argument invoqué par le modèle       occur.   Variantes qui l'attaquent
===================================  =======  ================================
« le bus / le métro est plus rapide »   135    V1, V2, V6, V10
« la marche est trop longue »           232    V3, V4, V6
« il / elle est abonné·e au réseau »     88    V5
« la marche fatigue, vu l'âge »          39    V7, V8
« il fait froid »                        10    V9
correspondances et attente comptées      27    V2, V10 (à contrario)
===================================  =======  ================================

**Ce qu'elles sont toutes.** Un bloc de texte AJOUTÉ au prompt système de production,
sans en retirer une ligne : le prompt de la variante contient le prompt du run mot pour
mot, plus une section numérotée « 4) ». Deux conséquences — l'écart mesuré est
attribuable au seul ajout, et le prompt de production reste lisible dans chaque page.

**Ce qu'elles ne sont pas.** Aucune ne dit « choisis la marche ». Une consigne de ce
genre déplacerait la masse sans rien apprendre : elle produirait une part de marche
réglable à volonté, ce qui n'est pas une correction mais un thermostat. Chaque variante
fournit un **élément de calcul** que le modèle ignorait (l'attente, l'aléa, la marche de
rabattement déjà incluse, le coût porte-à-porte) et le laisse conclure.

⚠ **Neuf des dix sont des leviers de NIVEAU, pas de PENTE.** Le TODO de
``prompt_calibration`` chiffre le vrai défaut du modèle : une élasticité à la distance
quasi nulle (part voiture plate à 42-49 % quand la réelle va de 18 à 77 %). Un levier de
niveau peut améliorer l'agrégat en dégradant les tranches longues — c'est exactement le
« gaming de la distribution » que la campagne ``ref1`` a mesuré. Seule V4 est
explicitement conditionnée à la distance. Les pages publient donc le détail par tranche
de distance à côté de l'agrégat : c'est là que se voit la différence.
"""
from __future__ import annotations

# Point d'insertion dans le prompt système de production. Le bloc ajouté se range
# avec les critères d'évaluation (étapes 1 à 3), AVANT les instructions de sortie et
# le schéma JSON — mis après, il se lirait comme une consigne de format et plusieurs
# modèles le traitent alors comme secondaire.
INSERT_BEFORE = "\n\n[Instructions de sortie]"


VARIANTS: list[dict] = [
    {
        "id": 1,
        "slug": "fiabilite",
        "title": "Aléa du réseau : panne, retard, correspondance manquée",
        "targets": "« le bus est plus rapide » (135 raisons) — durée OTP lue comme certaine",
        "heading": "Fiabilité de l'horaire annoncé",
        "body": (
            "Les durées de transport collectif affichées dans les options sont des "
            "horaires THÉORIQUES. Le réseau réel connaît des incidents : rame de métro "
            "immobilisée, bus pris dans la circulation ou supprimé, correspondance "
            "manquée d'une minute qui coûte l'intervalle entier. Un trajet à pied, lui, "
            "n'a aucun aléa : sa durée annoncée est sa durée vécue. Quand l'avantage "
            "horaire du transport collectif sur la marche est faible ou modéré, cet "
            "avantage n'est pas acquis, et la fiabilité de la marche pèse dans l'autre "
            "sens. Ne traite un gain de temps en transport collectif comme décisif que "
            "s'il reste décisif en cas de retard ordinaire."
        ),
    },
    {
        "id": 2,
        "slug": "attente",
        "title": "Temps d'attente et fréquence, comptés avant de comparer",
        "targets": "attente et correspondances quasi jamais comptées (27 raisons sur 494)",
        "heading": "Attente et fréquence",
        "body": (
            "La durée affichée d'une option en transport collectif ne compte PAS "
            "l'attente à l'arrêt. Avant de la comparer à la marche, ajoute-lui une "
            "attente réaliste : environ 5 minutes en heure de pointe (7h-9h, 17h-19h), "
            "10 minutes en journée creuse, 15 minutes en soirée et le week-end — et "
            "autant à CHAQUE correspondance. Une option annoncée à 13 minutes avec une "
            "correspondance vaut donc 25 à 35 minutes porte-à-porte selon l'heure. "
            "Compare la marche à ce total-là, jamais au temps affiché."
        ),
    },
    {
        "id": 3,
        "slug": "rabattement",
        "title": "La marche de rabattement est déjà de la marche",
        "targets": "« la marche est trop longue » (232 raisons) alors que l'option TC en contient",
        "heading": "Part piétonne déjà contenue dans l'option",
        "body": (
            "Une option du type « foot, bus, foot » CONTIENT déjà de la marche : "
            "rejoindre l'arrêt, puis rejoindre la destination. Le détail des étapes te "
            "donne cette part piétonne. Calcule-la, puis compare-la à la marche "
            "intégrale : quand un trajet en transport collectif impose 11 minutes de "
            "marche pour en économiser 6, l'écart réel n'est pas celui qu'annoncent les "
            "durées totales. Écarter la marche comme « trop longue » en retenant une "
            "option qui en contient presque autant est une contradiction : vérifie-la "
            "avant de répartir la masse."
        ),
    },
    {
        "id": 4,
        "slug": "seuil",
        "title": "Seuil urbain : sous 2 km, la marche est le défaut",
        "targets": "« distance excessive » invoquée jusque sur des trajets de 1 à 2 km",
        "heading": "Ce qu'est une distance marchable en ville dense",
        "body": (
            "Dans une ville dense comme Toulouse, marcher 20 à 25 minutes — soit environ "
            "1,5 à 2 km — est un déplacement ORDINAIRE, pas un effort exceptionnel. En "
            "dessous de ce seuil, la marche est l'option par défaut et c'est au "
            "transport collectif de justifier qu'on lui préfère un trajet avec attente, "
            "rabattement et rupture de charge. Au-dessus, l'arbitrage s'inverse "
            "progressivement, et au-delà d'une heure de marche le transport collectif "
            "s'impose. Applique ce seuil à la distance RÉELLE de l'option piétonne, pas "
            "à une impression de longueur."
        ),
    },
    {
        "id": 5,
        "slug": "abonnement",
        "title": "L'abonnement rend le réseau possible, pas obligatoire",
        "targets": "l'abonnement TC invoqué comme motif dans 88 raisons",
        "heading": "Ce que dit — et ne dit pas — un abonnement",
        "body": (
            "Un abonnement de transport collectif rend le réseau disponible et gratuit à "
            "l'usage. Il ne rend PAS son usage obligatoire, et il ne prédit pas le mode "
            "d'un trajet donné : un abonné marche aussi, notamment sur les trajets "
            "courts où sortir l'abonnement ne fait rien gagner. Symétriquement, "
            "l'absence d'abonnement n'interdit pas le réseau (tickets à l'unité). "
            "N'utilise jamais l'équipement — abonnement, vélo, voiture — comme motif "
            "suffisant : il ouvre une option, il ne la choisit pas."
        ),
    },
    {
        "id": 6,
        "slug": "porte-a-porte",
        "title": "Comparaison porte-à-porte, chaîne complète contre chaîne complète",
        "targets": "temps véhicule comparé au temps total de marche (135 + 232 raisons)",
        "heading": "Porte-à-porte",
        "body": (
            "Compare des trajets porte-à-porte, jamais un temps de véhicule à un temps "
            "de marche. La chaîne d'un transport collectif est : rejoindre l'arrêt, "
            "attendre, rouler, éventuellement changer et attendre encore, puis rejoindre "
            "la destination — chaque rupture ajoutant un risque de rater la suite. La "
            "chaîne de la marche est : marcher. Elle part à l'heure voulue, arrive sans "
            "correspondance, ne dépend d'aucun horaire. C'est cette comparaison-là qui "
            "doit fonder la répartition de probabilité."
        ),
    },
    {
        "id": 7,
        "slug": "utilite-marche",
        "title": "La marche a une utilité propre, pas seulement un coût",
        "targets": "marche traitée comme pis-aller dans la quasi-totalité des 494 raisons",
        "heading": "Valeur propre de la marche",
        "body": (
            "La marche n'est pas seulement un coût en temps. Elle a une utilité propre : "
            "elle est gratuite, elle fournit l'activité physique quotidienne "
            "recommandée, elle n'impose ni horaire, ni attente, ni correspondance, ni "
            "stationnement, et elle rend le temps de trajet prévisible. Pour beaucoup de "
            "personnes elle est le mode PRÉFÉRÉ sur les trajets courts, et pas un "
            "recours faute de mieux. Porte cette utilité dans la matrice de coût au lieu "
            "de ne compter que les minutes."
        ),
    },
    {
        "id": 8,
        "slug": "fatigue",
        "title": "L'effort d'un trajet en transport collectif, pour une personne âgée",
        "targets": "âge et fatigue invoqués contre la marche dans 39 raisons",
        "heading": "L'effort réel des deux options, pour une personne fragile",
        "body": (
            "Pour une personne âgée ou en santé fragile, un trajet en transport collectif "
            "n'est pas un trajet sans effort : il faut marcher jusqu'à l'arrêt, attendre "
            "debout, parfois sans abri, monter et descendre des marches, tenir debout "
            "dans un véhicule bondé, puis marcher encore jusqu'à la destination. Cet "
            "effort-là se compare à celui d'une marche directe, souvent PLUS COURTE que "
            "la somme des rabattements, faite à son rythme et interruptible à volonté. "
            "L'âge n'écarte donc pas la marche par principe : il impose de comparer deux "
            "efforts réels."
        ),
    },
    {
        "id": 9,
        "slug": "meteo",
        "title": "Une météo tempérée n'écarte pas la marche",
        "targets": "froid ou pluie invoqués contre la marche dans 10 raisons",
        "heading": "Ce qui, dans la météo, gêne vraiment la marche",
        "body": (
            "À Toulouse, entre 3 et 25 °C sans précipitations, la météo n'est pas un "
            "motif d'écarter la marche : c'est le temps ordinaire d'un jour de semaine, "
            "et les habitants marchent par ce temps-là. Seuls constituent une gêne "
            "réelle la pluie soutenue, le gel, la canicule, ou la nuit dans un secteur "
            "non éclairé. Un ciel dégagé à 3 °C ne justifie pas de préférer le transport "
            "collectif, d'autant que l'attente à l'arrêt s'y fait immobile, donc au "
            "froid, ce que la marche évite."
        ),
    },
    {
        "id": 10,
        "slug": "cumul",
        "title": "Cumul : attente, rabattement et aléa réunis",
        "targets": "les trois leviers horaires (V1 + V2 + V3) posés ensemble",
        "heading": "Le coût complet d'une option en transport collectif",
        "body": (
            "Avant de comparer une option en transport collectif à la marche, "
            "reconstitue son coût complet, en trois corrections que les durées affichées "
            "omettent toutes les trois. (a) ATTENTE : ajoute environ 5 minutes en heure "
            "de pointe, 10 en journée creuse, 15 en soirée et le week-end, à la montée "
            "et à chaque correspondance. (b) RABATTEMENT : la part de marche déjà "
            "contenue dans l'option (rejoindre l'arrêt, puis la destination) est de la "
            "marche — déduis-la avant de juger la marche intégrale « trop longue ». "
            "(c) ALÉA : l'horaire est théorique ; incident, retard ou correspondance "
            "manquée sont ordinaires, alors qu'un trajet à pied tient toujours sa durée. "
            "Compare la marche à ce coût-là."
        ),
    },
]

VARIANTS_BY_ID = {v["id"]: v for v in VARIANTS}


def directive(variant: dict) -> str:
    """Le bloc de texte ajouté au prompt de production, tel qu'il y est inséré."""
    return f"4) {variant['heading']} : {variant['body']}"


def system_prompt(base: str, variant: dict) -> str:
    """Prompt système de la variante : celui du run, plus la section « 4) ».

    Refuse bruyamment si le point d'insertion est absent : concaténer en fin de
    prompt placerait la consigne APRÈS le schéma JSON, ce qui n'est pas la même
    mesure — et le silence ferait passer les deux placements pour un seul.
    """
    if INSERT_BEFORE not in base:
        raise ValueError(
            f"[ALARME] point d'insertion « {INSERT_BEFORE.strip()} » absent du prompt "
            f"système du run : la variante {variant['id']} serait ajoutée après le "
            f"schéma JSON au lieu des critères d'évaluation. Insertion refusée.")
    return base.replace(INSERT_BEFORE, "\n" + directive(variant) + INSERT_BEFORE, 1)
