"""Traffic manager agent."""

import asyncio
import json
import random
from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour
from utils.ontology import TransportationOntology, Performative


class TrafficManagerAgent(Agent):
    """
    Agent responsible for traffic simulation.

    Periodically changes the cost of certain city edges
    to simulate congestion and sends updates to vehicles.
    """

    def __init__(self, jid, password, known_vehicles):
        """
        Creates a new traffic manager.

        Args:
            jid (str): Agent XMPP identifier.
            password (str): Agent password.
            known_vehicles (list[str]): List of vehicle JIDs.
        """
        super().__init__(jid, password)
        self.known_vehicles = known_vehicles
        self.edges = [
            ("Central", "North"),
            ("North", "Central"),
            ("Central", "East"),
            ("East", "Central"),
            ("South", "Airport"),
            ("Airport", "South"),
        ]

    async def setup(self):
        """Initializes the agent and starts the periodic traffic behaviour."""
        print(f"🚦 TRAFFIC CONTROL {self.name} activated.")
        self.add_behaviour(self.TrafficJamBehaviour(period=15))

    class TrafficJamBehaviour(PeriodicBehaviour):
        """
        Periodic behaviour for traffic updates.

        In each execution, picks a street, decides if it's congested
        or clear, and broadcasts the update to all vehicles.
        """

        async def run(self):
            """Updates an edge weight and broadcasts the change."""
            u, v = random.choice(self.agent.edges)

            is_jam = random.random() > 0.3

            new_weight = random.randint(30, 60) if is_jam else 10
            status = "CONGESTED" if is_jam else "CLEAR"

            print(
                f"\n🚦 [TRAFFIC] Update on {u}->{v}: "
                f"{status} (New cost: {new_weight}m)"
            )

            msg_content = {
                "type": "traffic_update",
                "edge": [u, v],
                "new_weight": new_weight,
            }

            for v_jid in self.agent.known_vehicles:
                msg = TransportationOntology.create_message(
                    to_jid=v_jid,
                    performative=Performative.INFORM,
                    content_data=msg_content,
                )
                await self.send(msg)