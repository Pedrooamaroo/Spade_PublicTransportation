"""Station agent for the transport system.

Receives requests, launches CNP to find best vehicle, logs metrics.
"""

import asyncio
import json
import datetime
import uuid
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour, PeriodicBehaviour
from utils.ontology import TransportationOntology, Performative


class StationAgent(Agent):
    """
    Agent representing a bus/tram stop.

    Detects passenger requests, initiates the Contract Net Protocol (CNP)
    with known vehicles, and logs negotiation metrics.
    """

    def __init__(self, jid, password, location, known_vehicles):
        """
        Creates a new station agent.

        Args:
            jid (str): Agent XMPP identifier.
            password (str): Agent password.
            location (str): Station name (node in the city graph).
            known_vehicles (list[str]): List of known vehicle JIDs.
        """
        super().__init__(jid, password)
        self.location = location
        self.known_vehicles = known_vehicles
        self.passenger_queue = []

    async def setup(self):
        """Initializes the station and starts listening behavior."""
        print(f"[{self.location}] Station Online.")
        listen = self.ListenForPassengers()
        self.add_behaviour(listen)

        broadcast = self.BroadcastStateBehaviour(period=30)
        self.add_behaviour(broadcast)

    class ListenForPassengers(CyclicBehaviour):
        """Listens for passenger requests."""

        async def run(self):
            """Receives messages and dispatches based on performative."""
            msg = await self.receive(timeout=1)
            if msg:
                performative = msg.get_metadata("performative")
                try:
                    content = json.loads(msg.body)
                except Exception:
                    content = {}

                if performative == Performative.REQUEST:
                    if content.get("type") == "travel_request":
                        destination = content.get("destination")
                        passenger_jid = str(msg.sender)
                        
                        print(f"[{self.agent.location}] 🛎️ Passenger {passenger_jid.split('@')[0]} wants to go to {destination}.")
                        
                        self.agent.passenger_queue.append(passenger_jid)
                        cnp = self.agent.CNPManager(destination, passenger_jid)
                        self.agent.add_behaviour(cnp)

                elif performative == Performative.CANCEL:
                    p_jid = str(msg.sender)
                    if p_jid in self.agent.passenger_queue:
                        self.agent.passenger_queue.remove(p_jid)
                        print(f"[{self.agent.location}] 🗑️ Passenger {p_jid.split('@')[0]} left the queue.")

                elif performative == Performative.INFORM and content.get("type") == "demand_surge":
                    origin_st = content.get("station")
                    count = content.get("count")
                    print(f"[{self.agent.location}] ⚠️ Received alert: Station {origin_st} has {count} people!")

    class BroadcastStateBehaviour(PeriodicBehaviour):
        """Warns neighbors if station is crowded."""
        async def run(self):
            queue_size = len(self.agent.passenger_queue)
            
            if queue_size > 2:
                print(f"[{self.agent.location}] 📢 I have {queue_size} pax waiting! Requesting help...")
                
                msg_data = {
                    "type": "demand_surge",
                    "station": self.agent.location,
                    "count": queue_size
                }
                
                for v_jid in self.agent.known_vehicles:
                    msg = TransportationOntology.create_message(
                        to_jid=v_jid,
                        performative=Performative.INFORM, 
                        content_data=msg_data
                    )
                    await self.send(msg)

    class CNPManager(OneShotBehaviour):
        """
        Contract Net Protocol Manager.

        Sends CFP to vehicles, collects proposals within a timeout,
        selects the best one (lowest ETA), accepts the winner,
        rejects the others, and informs the passenger.
        """

        def __init__(self, destination, passenger_jid):
            """
            Initializes a CNP manager for a specific passenger/request.

            Args:
                destination (str): Desired destination station.
                passenger_jid (str): JID of the passenger requesting the ride.
            """
            super().__init__()
            self.destination = destination
            self.passenger_jid = passenger_jid
            self.conversation_id = str(uuid.uuid4())

        async def run(self):
            """Executes a full CNP cycle for a single request."""
            msg_data = TransportationOntology.format_cfp(
                origin=self.agent.location,
                destination=self.destination,
                passenger_count=1,
            )

            for v_jid in self.agent.known_vehicles:
                msg = TransportationOntology.create_message(
                    v_jid,
                    Performative.CFP,
                    msg_data,
                    thread_id=self.conversation_id,
                )
                await self.send(msg)

            proposals = []
            cutoff = datetime.datetime.now() + datetime.timedelta(seconds=10)

            while datetime.datetime.now() < cutoff:
                response = await self.receive(timeout=0.5)
                if response and response.thread == self.conversation_id:
                    if response.get_metadata("performative") == Performative.PROPOSE:
                        content = json.loads(response.body)
                        eta = content["eta"]
                        proposals.append((response, eta))

            if proposals:
                proposals.sort(key=lambda x: x[1])

                best_proposal = proposals[0][0]
                best_eta = proposals[0][1]
                best_vehicle = json.loads(best_proposal.body)["vehicle_id"]

                print(
                    f"[{self.agent.location}] ✅ Vehicle "
                    f"{best_vehicle.split('@')[0]} hired (ETA: {best_eta}m)."
                )

                reply_accept = best_proposal.make_reply()
                reply_accept.set_metadata("performative", Performative.ACCEPT_PROPOSAL)
                reply_accept.body = json.dumps({"passenger_id": self.passenger_jid})
                await self.send(reply_accept)

                for prop, _ in proposals[1:]:
                    reply_reject = prop.make_reply()
                    reply_reject.set_metadata("performative", Performative.REJECT_PROPOSAL)
                    reply_reject.body = json.dumps({"reason": "better_proposal_found"})
                    await self.send(reply_reject)

                msg_p = TransportationOntology.create_message(
                    to_jid=self.passenger_jid,
                    performative=Performative.INFORM,
                    content_data={"status": "vehicle_found", "eta": best_eta},
                )
                await self.send(msg_p)

                if self.passenger_jid in self.agent.passenger_queue:
                    self.agent.passenger_queue.remove(self.passenger_jid)

                TransportationOntology.log_metric(
                    "NEGOTIATION_OK",
                    self.agent.location,
                    self.destination,
                    best_eta,
                    f"Vehicle:{best_vehicle}|Proposals:{len(proposals)}",
                )

            else:
                TransportationOntology.log_metric(
                    "NEGOTIATION_FAIL",
                    self.agent.location,
                    self.destination,
                    "0",
                    "No_Proposals",
                )

                if self.passenger_jid in self.agent.passenger_queue:
                    self.agent.passenger_queue.remove(self.passenger_jid)

                    msg_p = TransportationOntology.create_message(
                        to_jid=self.passenger_jid,
                        performative=Performative.REFUSE,
                        content_data={"reason": "no_vehicles_available"},
                    )
                    await self.send(msg_p)
                else:
                    print(f"[{self.agent.location}] 🤷 Passenger {self.passenger_jid.split('@')[0]} had already left. Not sending REFUSE.")