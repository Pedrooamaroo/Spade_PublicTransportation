"""Gas station agent.

Receives refueling requests from vehicles and responds
when the filling process is complete.
"""

import asyncio
import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from utils.ontology import TransportationOntology, Performative


class GasStationAgent(Agent):
    """
    Agent responsible for refueling vehicles.

    Receives requests from vehicles, simulates filling time,
    and responds with the updated fuel level.
    """

    async def setup(self):
        """Initializes the agent and starts the service behaviour."""
        print(f"⛽ GAS STATION {self.name} open and ready.")
        b = self.RefuelServiceBehaviour()
        self.add_behaviour(b)

    class RefuelServiceBehaviour(CyclicBehaviour):
        """
        Cyclic behaviour for gas station service.

        Processes fuel requests and responds after simulating
        the refueling time.
        """

        async def run(self):
            """Processes refueling requests and sends confirmation."""
            msg = await self.receive(timeout=1)
            if msg:
                performative = msg.get_metadata("performative")
                content = json.loads(msg.body)

                if performative == Performative.REQUEST and content.get("type") == "refuel_request":
                    vehicle_id = str(msg.sender).split("/")[0]
                    amount_needed = content.get("amount_needed", 0)

                    print(f"⛽ [PUMP] Refueling {vehicle_id} ({amount_needed:.1f}L)...")
                    await asyncio.sleep(3)
                    print(f"⛽ [PUMP] {vehicle_id} full! You may leave.")

                    reply = msg.make_reply()
                    reply.set_metadata("performative", Performative.INFORM)
                    reply.body = json.dumps(
                        {
                            "status": "refueled",
                            "fuel_level": 100.0,
                        }
                    )
                    await self.send(reply)
