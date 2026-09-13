from collections import Counter
from text_helper.templates.repository import \
    get_transit_route_type, \
    tpl_describe_the_travel_plan, \
    tpl_describe_the_travel_plan_lite
from models import TravelPlan

class TravelPlanWrapper(TravelPlan):
    def describe(self) -> str:
        # Describe the trip feedback observation in a human-readable format
        return tpl_describe_the_travel_plan.render(
            plan=self,
        )

    # ⚠ `is_transfer` ET `not is_terminal` : depuis le ticket 013, les jambes
    # d'accès et de diffusion portent `is_transfer=True` (c'est ce qui garde
    # `get_code()` inchangé) mais ne sont PAS de la marche — chercher une place de
    # stationnement n'en est pas. Sans l'exclusion, un plan voiture déclarait ici
    # 10 min de « marche » et 200 m de distance de marche, ces 200 m venant du
    # repli `distance or 100.0` de `Transit.get_distance()` appliqué à deux jambes
    # sans distance réseau. Le gabarit v2 ne rend pas ces deux propriétés pour un
    # plan à jambes terminales (la branche `has_terminal_legs` passe avant), mais
    # rien ne doit dépendre de cet ordre.
    @property
    def walking_time(self) -> int:
        return sum(leg.get_duration() for leg in self.legs
                   if leg.is_transfer and not leg.is_terminal)

    @property
    def walking_distance(self) -> float:
        return sum(leg.get_distance() for leg in self.legs
                   if leg.is_transfer and not leg.is_terminal)

    # ── Temps terminal (ticket 013) ──────────────────────────────────────────
    # Le gabarit reste volontairement pauvre : il restitue ce que ces propriétés
    # lui donnent (décision T3). Toute la logique — quelles jambes, quels
    # libellés, quelles durées — vient de la construction du scénario et de
    # `config/terminal_time.yaml`, jamais du gabarit.

    @property
    def has_terminal_legs(self) -> bool:
        """Le plan porte-t-il un temps d'accès / de diffusion nommé ?

        Vrai pour les plans voiture et vélo, faux pour la marche (porte-à-porte)
        et les transports collectifs (jambes de marche déjà routées par OTP).
        """
        return any(leg.is_terminal for leg in self.legs)

    @property
    def terminal_time(self) -> int:
        """Somme des durées des jambes terminales, en secondes."""
        return sum(leg.get_duration() for leg in self.legs if leg.is_terminal)

    @property
    def direct_leg(self):
        """Jambe routée d'un plan direct (marche / vélo / voiture), ou ``None``.

        Reconnue au marqueur ``__DIRECT`` et non à la longueur de ``legs`` : depuis
        le ticket 013, un plan voiture ou vélo en compte trois (accès, trajet,
        diffusion) et un test sur ``legs | length == 1`` le manquerait.
        """
        for leg in self.legs:
            if leg.transit_route and '__DIRECT' in leg.transit_route:
                return leg
        return None

    @property
    def total_seconds(self) -> int:
        """Durée totale du plan en secondes, bornes normalisées (ms ou s)."""
        from helper import ensure_timestamp_in_seconds

        return (ensure_timestamp_in_seconds(self.end_time)
                - ensure_timestamp_in_seconds(self.start_time))

    @property
    def _terminal_profile(self):
        """Profil terminal du mode principal du plan, ou ``None``.

        Le mode est lu sur la jambe NON terminale : les jambes d'accès et de
        diffusion n'en portent pas, précisément pour ne pas polluer l'étiquette de
        mode de l'option.
        """
        from trip_helper.terminal_time import terminal_profile

        for leg in self.legs:
            if leg.is_terminal or leg.mode is None:
                continue
            profile = terminal_profile(str(leg.mode))
            if profile is not None:
                return profile
        return None

    @property
    def terminal_label(self) -> str:
        """Qualificatif du « dont … » de l'en-tête, propre au mode.

        « de marche » serait faux pour une voiture : chercher une place n'est pas
        de la marche. Le libellé vient donc du profil du mode
        (``d'accès et de stationnement`` / ``d'accès et d'attache``) et non d'une
        formule unique appliquée à tout.
        """
        profile = self._terminal_profile
        return profile.labels["terminal"] if profile is not None else "d'accès"

    @property
    def described_steps(self) -> list[tuple[str, int]]:
        """Sous-étapes ``(libellé, durée en secondes)`` d'un plan à jambes nommées.

        Le libellé de la jambe de diffusion porte un ``{destination}`` : ``purpose``
        n'est posé sur le plan qu'après le routage, donc l'interpolation ne peut se
        faire qu'ici. Sans destination connue, on retombe sur la formulation du
        profil qui n'en nomme aucune — pas sur un nom inventé.
        """
        profile = self._terminal_profile
        steps: list[tuple[str, int]] = []
        for leg in self.legs:
            label = leg.step_label
            if not label:
                continue
            if "{destination}" in label:
                label = (profile.egress_label(self.purpose) if profile is not None
                         else label.format(destination=self.purpose or ""))
            steps.append((label, leg.get_duration()))
        return steps

    def summary(self) -> str:
        n_transits = len([leg for leg in self.legs if not leg.is_transfer])
        n_transfers = len(self.legs) - n_transits
        transit_types = [get_transit_route_type(leg.transit_route) for leg in self.legs
                         if leg.transit_route and not leg.is_terminal]
        counter = Counter(transit_types)
        return f"{n_transits} transits, {n_transfers} transfers, including {', '.join([f'{v} {k}' for k, v in counter.items()])}"


class TravelPlanLiteWrapper(TravelPlanWrapper):
    def describe(self) -> str:
        # Describe the trip feedback observation in a human-readable format
        return tpl_describe_the_travel_plan_lite.render(
            plan=self
        )
