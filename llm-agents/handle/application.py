"""
FastAPI application for LLM-GAMA integration.

This module provides the HTTP API and WebSocket communication layer between
the GAMA simulation and external LLM (Large Language Model) systems. It handles
world initialization, synchronization, and real-time observation/action exchange.
"""

import asyncio
import json
import os
import orjson
import uvicorn
from loguru import logger
from helper import create_json_logger
from gama_models import GamaPersonData, MessageResponse, MessageType, WorldInitResponse, WorldSyncRequest
from urban_mobility_agents.core.scenario import BaseScenario, Observation
from handle.websocket import WebSocketClient
from settings import settings
import traceback
from fastapi import FastAPI
import urban_mobility_agents.factory.factory



# Set working directory from environment if specified
workdir = os.environ.get("APP_WORKDIR", "")
if workdir:
    settings.update_workdir(workdir)

# Initialize JSON logging
create_json_logger()

# Create FastAPI application instance
app = FastAPI()

# Configure orjson for faster JSON serialization (handles numpy arrays)
def orjson_serializer(obj):
    return orjson.dumps(obj, option=orjson.OPT_SERIALIZE_NUMPY).decode()
app.router.json_dumps = orjson_serializer

# Debug print current history file path
print(settings.app.history_file_v2)


class LoopContainer:
    """
    Container for managing WebSocket communication and message loops.

    This class handles the bidirectional communication between the FastAPI server
    and the GAMA simulation via WebSocket. It manages observation publishing and
    action message handling.
    """
    action_topic = "action/data"
    system_greeting_topic = "system/greeting"
    observation_topic = "observation/data"

    def __init__(self):
        self.client = None
        self.scenario = None
        # Initialize WebSocket client for GAMA communication
        self.websocket_client = WebSocketClient(settings.server.gama_ws_url)
        self.websocket_client.on_message = self.handle_message

    def set_scenario(self, scenario: BaseScenario):
        """Set the active simulation scenario."""
        self.scenario = scenario

    async def greeting(self):
        """Send a greeting message to the WebSocket server"""
        await self.websocket_client.connect()

        greeting_message = {
            "topic": self.system_greeting_topic,
            "payload": {
                "type": "greeting",
                "message": "Hello from FastAPI + WebSocket client!"
            }
        }
        success = await self.websocket_client.send_json(greeting_message)
        if not success:
            logger.error("Failed to send greeting message")

    async def publish_loop(self):
        """
        Main publishing loop that sends action messages to GAMA via WebSocket.

        Continuously checks for new messages from the scenario and publishes them
        to the GAMA simulation. Handles connection failures and retries.
        """
        while True:
            try:
                # Check if scenario has messages to publish
                if self.scenario and await self.scenario.has_messages():
                    messages = await self.scenario.pop_all_messages()
                    len_messages = len(messages)
                    while messages:
                        message = messages[0]
                        payload = message.model_dump()
                        success = await self.websocket_client.send_json({
                            "topic": self.action_topic,
                            "payload": payload,
                        })
                        if not success:
                            logger.error(f"Failed to send message: {payload}")
                            await asyncio.sleep(1)  # Wait before retrying
                            continue
                        messages.pop(0)  # Remove the message from the list after sending

                    logger.info(f"Websocket loop Sent {len_messages} messages to {self.action_topic}")
            except Exception as e:
                logger.error(f"WebSocket publish loop error: {e}")
                await asyncio.sleep(self.reconnect_interval)

            await asyncio.sleep(1)  # Adjust sleep time as needed

    async def handle_message(self, text: str):
        """Handle received Websocket message"""
        try:
            logger.debug(f"Received: {self.observation_topic} -> {text}")
            await self.process_observation(self.observation_topic, text)

        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error handling message: {e}")

    async def process_observation(self, topic: str, payload: str):
        """
        Process observation data received from GAMA simulation.

        Parses the observation payload and forwards it to the scenario for processing.
        Observations contain agent state information for LLM decision making.
        """
        try:
            data = json.loads(payload)
            assert data["topic"] == self.observation_topic, "Invalid topic in observation data"
            observation = Observation(**data["payload"])
            await self.scenario.handle_observation(observation)
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error processing observation: {e}")

# Global loop container instance
loop_container = LoopContainer()
# Bootstrap the simulation scenario
scenario = urban_mobility_agents.factory.factory.bootstrap()
loop_container.set_scenario(scenario)

@app.on_event("startup")
async def startup_event():
    """
    FastAPI startup event handler.

    Initializes WebSocket connection and starts background tasks for
    real-time communication with GAMA simulation.
    """
    # Send greeting and start WebSocket communication loops
    await loop_container.greeting()
    asyncio.create_task(loop_container.websocket_client.run_with_reconnect())
    asyncio.create_task(loop_container.publish_loop())

@app.on_event("shutdown")
async def shutdown_event():
    """FastAPI shutdown event handler - closes WebSocket connections."""
    await loop_container.websocket_client.stop()

@app.get("/")
async def root():
    """Root endpoint - returns service status."""
    return {"status": "FastAPI + Websocket running"}

@app.post("/init")
async def init():
    """
    Initialize the simulation world.

    Returns the complete population data to initialize the GAMA simulation
    with all agents and their home locations.
    """
    logger.info("Publishing world data")

    people = scenario.population.get_people_list()

    person_response = [
        GamaPersonData(
            **person.model_dump(),
            location=scenario.population.get_person_home_location(person.person_id),
            name=person.identity.name,
        )
        for person in people
    ]
    return MessageResponse(
        message_type=MessageType.AG_WORLD_INIT,
        data=WorldInitResponse(
            people=person_response,
            num_people=len(people),
            # TODO: remove this
            timestamp=0,
        )
    )

@app.post("/reflect")
async def reflect(request: WorldSyncRequest):
    """
    Reflect the current world state at a specific timestamp.

    Forces all agents to update their state to match the simulation time.
    Used for synchronization and debugging.
    """
    logger.info(f"Reflecting world at timestamp: {request.timestamp}")

    if loop_container.scenario:
        await loop_container.scenario.reflect_all(request.timestamp)
        return MessageResponse(
            data="reflected",
            success=True,
        )
    else:
        return MessageResponse(
            success=False,
            error="Scenario not set"
        )

@app.post("/sync")
async def sync(request: WorldSyncRequest):
    """
    Synchronize the world state with idle population data.

    Updates the scenario with current idle agents and their locations.
    Called periodically by the GAMA simulation for state synchronization.
    """
    logger.info(f"Synchronizing world at timestamp: {request.timestamp}")

    if loop_container.scenario:
        await loop_container.scenario.sync(request.timestamp, idle_people=request.idle_people)
        return MessageResponse(
            data="synchronized",
            success=True,
        )
    else:
        return MessageResponse(
            success=False,
            error="Scenario not set"
        )


if __name__ == "__main__":
    """
    Main entry point for running the FastAPI application.

    Starts the server on host 0.0.0.0 and port 8000.
    This provides the HTTP API for LLM-GAMA integration.
    """
    uvicorn.run(app, host="0.0.0.0", port=8000)
