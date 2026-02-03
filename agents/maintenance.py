"""Maintenance agent.

Receives breakdown alerts from vehicles, simulates repairs
managing a limited number of available mechanics.
"""

import asyncio
import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from utils.ontology import TransportationOntology, Performative


class MaintenanceAgent(Agent):
    """
    Agent responsible for the workshop.
    Manages a waiting queue based on the number of mechanics.
    """

    def __init__(self, jid, password, num_mechanics=2):
        super().__init__(jid, password)
        self.num_mechanics = num_mechanics
        self.sem = None 

    async def setup(self):
        """Initializes the workshop and resources."""
        self.sem = asyncio.Semaphore(self.num_mechanics)
        
        print(f"🔧 WORKSHOP {self.name} opened with {self.num_mechanics} mechanics ready.")
        
        dispatcher = self.DispatcherBehaviour()
        self.add_behaviour(dispatcher)

    class DispatcherBehaviour(CyclicBehaviour):
        """Receives messages and creates a repair job for each."""

        async def run(self):
            msg = await self.receive(timeout=1)
            if msg:
                performative = msg.get_metadata("performative")
                content = json.loads(msg.body)

                if performative == Performative.REQUEST and content.get("type") == "breakdown_alert":
                    repair_job = self.agent.RepairJob(msg)
                    self.agent.add_behaviour(repair_job)

    class RepairJob(OneShotBehaviour):
        """
        Represents the job of repairing ONE specific vehicle.
        """
        def __init__(self, request_msg):
            super().__init__()
            self.request_msg = request_msg

        async def run(self):
            content = json.loads(self.request_msg.body)
            vehicle_id = content.get("vehicle_id")
            issue = content.get("issue")

            print(f"🔧 [WORKSHOP] Request received from {vehicle_id.split('@')[0]} ({issue}). Waiting for mechanic...")

            async with self.agent.sem:
                print(f"🔧 [MECHANIC] Repairing {vehicle_id.split('@')[0]}... (Resources free: {self.agent.sem._value})")
                
                await asyncio.sleep(5)
                is_refueled = (issue == "no_fuel")
                
                status_msg = "REPAIRED"
                if is_refueled:
                    status_msg += " (and emergency refueled)"

                print(f"🔧 [WORKSHOP] {vehicle_id.split('@')[0]} {status_msg}!")

                reply = self.request_msg.make_reply()
                reply.set_metadata("performative", Performative.INFORM)
                reply.body = json.dumps(
                    {
                        "status": "repaired",
                        "message": "Ready to go.",
                        "refueled": is_refueled }
                )
                await self.send(reply)