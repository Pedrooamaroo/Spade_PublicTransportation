"""Passenger agent for the transport system.

Each passenger requests a ride from a station, waits for a response,
has a maximum wait time, and logs the result in metrics.
"""

import asyncio
import json
import time
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour, CyclicBehaviour
from utils.ontology import TransportationOntology, Performative


class PassengerAgent(Agent):
    """
    Agent representing a passenger.

    Sends a ride request to a station, waits for a response
    within a time limit, and logs success or failure.
    """

    def __init__(self, jid, password, origin_station_jid, destination_name):
        """
        Creates a new passenger.

        Args:
            jid (str): Agent XMPP identifier.
            password (str): Agent password.
            origin_station_jid (str): JID of the origin station.
            destination_name (str): Name of the destination station.
        """
        super().__init__(jid, password)
        self.origin_station_jid = origin_station_jid
        self.destination = destination_name
        self.start_time = 0
        self.MAX_PATIENCE = 60

    async def setup(self):
        """Initializes the passenger and starts request/wait behaviours."""
        print(
            f"👤 Passenger {self.name} entered "
            f"{self.origin_station_jid.split('_st_')[1].split('@')[0].title()}. "
            f"Destination: {self.destination}"
        )
        self.start_time = time.time()

        wait = self.WaitForRideBehaviour()
        self.add_behaviour(wait)

        req = self.RequestRideBehaviour()
        self.add_behaviour(req)

    class RequestRideBehaviour(OneShotBehaviour):
        """Behavior that sends an initial ride request to the station."""

        async def run(self):
            """Sends the ride request to the origin station."""
            print(f"👤 {self.agent.name} requesting ticket to {self.agent.destination}...")
            msg_data = {
                "type": "travel_request",
                "destination": self.agent.destination,
            }
            msg = TransportationOntology.create_message(
                self.agent.origin_station_jid,
                Performative.REQUEST,
                msg_data,
            )
            await self.send(msg)

    class WaitForRideBehaviour(CyclicBehaviour):
        """
        Behavior that waits for station response.

        Manages patience timeout, handles success responses,
        and retries if the request is refused.
        """

        async def run(self):
            """Checks wait time and processes station responses."""
            if (time.time() - self.agent.start_time) > self.agent.MAX_PATIENCE:
                print(f"👤 {self.agent.name}: 😡 Gave up (Timeout).")

                cancel_msg = TransportationOntology.create_message(
                    to_jid=self.agent.origin_station_jid,
                    performative=Performative.CANCEL, 
                    content_data={"type": "cancel_request"}
                )

                wait_time = time.time() - self.agent.start_time
                TransportationOntology.log_metric(
                    "PASSENGER_FAIL",
                    self.agent.name,
                    self.agent.destination,
                    f"{wait_time:.2f}",
                    "TIMEOUT",
                )

                await self.agent.stop()
                return

            
            msg = await self.receive(timeout=1)
            if msg:
                performative = msg.get_metadata("performative")

                
                if performative == Performative.INFORM:
                    content = json.loads(msg.body)
                    eta = content.get("eta")
                    print(
                        f"👤 {self.agent.name}: Yay! Vehicle coming "
                        f"(ETA: {eta}m)."
                    )

                    wait_time = time.time() - self.agent.start_time
                    TransportationOntology.log_metric(
                        "PASSENGER_SUCCESS",
                        self.agent.name,
                        self.agent.destination,
                        f"{wait_time:.2f}",
                        f"ETA:{eta}",
                    )

                    await self.agent.stop()

                
                elif performative == Performative.REFUSE:
                    print(
                        f"👤 {self.agent.name}: Station refused. "
                        "Retrying in 5s..."
                    )
                    await asyncio.sleep(5)

                    b = self.agent.RequestRideBehaviour()
                    self.agent.add_behaviour(b)