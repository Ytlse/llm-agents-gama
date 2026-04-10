from urban_mobility_agents.agents.llm_agent import LlmAgent
from world.population import WorldPopulation
from urban_mobility_agents.core.schemas import Action, Observation

class BaseScenario:
    agent: "LlmAgent"

    async def sync(self, timestamp: int, idle_people: list[Observation] = None):
        """Synchronize the scenario with a given timestamp"""
        raise NotImplementedError("This method should be overridden by subclasses")

    async def handle_observation(self, observation: Observation):
        """Handle observation data"""
        raise NotImplementedError("This method should be overridden by subclasses")

    async def has_messages(self) -> bool:
        """Check if there are messages to process"""
        raise NotImplementedError("This method should be overridden by subclasses")

    async def pop_all_messages(self) -> list[Action]:
        """Pop all messages from the queue"""
        raise NotImplementedError("This method should be overridden by subclasses")

    @property
    def population(self) -> "WorldPopulation":
        """Get the current population of the scenario"""
        raise NotImplementedError("This method should be overridden by subclasses")