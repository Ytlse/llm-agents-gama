from settings import settings

settings.force_reload()
# Le contrôleur est le processus propriétaire du run : c'est lui, et lui seul, qui fait
# pointer `experiments/current` et `GAMA/CityTransport/results` vers son répertoire. Un
# import de `settings` ne déplace plus ces liens (cf. `FactorySettings.claim_run`).
settings.claim_run()

from handle.application import app

__all__ = ["app"]
