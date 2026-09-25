from typing import Optional
from pydantic import BaseModel
from text_helper.templates.repository import tpl_describe_the_ob_trip_feedback
from text_helper.type import EnvOb

# Une demi-journée. Les reports de CALENDRIER déplacent un départ d'un jour entier (bouclage
# J+1, `departure_time += 86400`) ou jusqu'au lundi suivant (deux à trois jours) ; le glissement
# ORDINAIRE d'un départ — une activité qui déborde — se compte en minutes et n'approche jamais
# ce seuil. C'est ce qui permet de distinguer les deux sans drapeau porté depuis GAMA.
SEUIL_REPORT_CALENDAIRE_S = 43_200


def retard_d_arrivee(
    arrive_at: int,
    expected_arrive_at: int,
    schedule_at: Optional[int] = None,
    started_at: Optional[int] = None,
) -> int:
    """Le retard réellement SUBI, le report de calendrier retiré.

    `expected_arrive_at` est calculé par GAMA depuis le `schedule_at` d'ORIGINE, et il n'est
    pas recalculé quand le départ est reporté — ni par le bouclage J+1, ni par la règle
    `agent.no_weekend_departures`. Un trajet du vendredi soir joué le lundi comptait donc
    soixante-douze heures de retard, alors qu'il s'était parfaitement déroulé : parti 19:15,
    arrivé 19:27, douze minutes contre quinze planifiées (run du 2026-09-23, jour 5).

    Ce que ça coûtait : une gravité de 0,70 et un souvenir « grave » dans la ligne de base,
    indiscernable d'un choc déclaré à 0,75 — et, dans le prompt de l'agent, un
    « Late by: 23 hours » qu'il n'a pas vécu.

    Le report se DÉDUIT : `started_at - schedule_at` au-delà d'une demi-journée ne peut être
    qu'un report de calendrier. Le retard se mesure alors contre l'arrivée attendue REBASÉE sur
    le départ effectif, c'est-à-dire `expected_arrive_at + report`.

    ⚠ Ce qui reste compté : un départ qui glisse de vingt minutes parce que l'activité
    précédente a débordé. C'est un retard VÉCU et il doit le rester — seul le report décidé par
    le calendrier est retiré. `departure_delay_s` de `gama_arrivals.csv` porte le glissement
    ordinaire pour qui veut le lire à part.
    """
    report = 0
    if schedule_at is not None and started_at is not None:
        glissement = int(started_at) - int(schedule_at)
        if glissement >= SEUIL_REPORT_CALENDAIRE_S:
            report = glissement
    # Une arrivée en avance vaut zéro et non un retard négatif, qui viendrait compenser un
    # incident réel dans la même entrée.
    return max(0, int(arrive_at) - int(expected_arrive_at) - report)


class EnvObArrival(EnvOb):
    expected_arrive_at: int
    prepare_before_seconds: Optional[int] = 0
    arrive_at: int
    purpose: str
    duration: Optional[float]
    plan_duration: Optional[float]
    moving_id: Optional[str] = None
    # Portés par l'observation GAMA depuis le ticket 071 ; déclarés ici depuis le 2026-09-23
    # pour que `late` puisse retirer un report de calendrier. Absents, le retard se calcule
    # comme avant — aucun appelant existant ne change de comportement.
    schedule_at: Optional[int] = None
    started_at: Optional[int] = None

    @property
    def late(self) -> int:
        return retard_d_arrivee(
            self.arrive_at, self.expected_arrive_at, self.schedule_at, self.started_at
        )

    @property
    def is_late(self) -> bool:
        return self.late > 0

    def describe(self, weather=None) -> str:
        return tpl_describe_the_ob_trip_feedback.render(ob=self, weather=weather)


if __name__ == "__main__":
    # Example usage
    event = EnvObArrival(
        type="arrival",
        timestamp=1234567890,
        moving_id="123",
        expected_arrive_at=1234567890,
        arrive_at=1234567890,
        purpose="work",
        duration=3600.0,
        plan_duration=2600.0,
    )
    print(event.describe())

