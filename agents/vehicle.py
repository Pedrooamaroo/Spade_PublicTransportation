"""Vehicle agent logic."""

import asyncio
import json
import random
import time
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from models.city_map import CityGraph
from utils.ontology import TransportationOntology, Performative


class VehicleAgent(Agent):
    """
    Agent representing a vehicle (Bus or Tram).

    Navigates the city graph, accepts passengers via Contract Net (CNP),
    manages fuel/capacity, and handles breakdowns and refueling.
    """

    def __init__(
        self,
        jid,
        password,
        vehicle_type,
        start_location,
        maintenance_jid,
        gas_station_jid,
        dashboard_jid,
        capacity=4,
        patrol_route=None,
    ):
        """
        Creates a new vehicle agent.

        Args:
            jid (str): Agent XMPP identifier.
            password (str): Agent password.
            vehicle_type (str): "bus" or "tram".
            start_location (str): Name of the starting node in the graph.
            maintenance_jid (str): JID of the mechanic/workshop.
            gas_station_jid (str): JID of the gas station.
            dashboard_jid (str): JID of the dashboard agent.
            capacity (int): Max passenger capacity.
            patrol_route (list): List of stations to patrol when idle.
        """
        super().__init__(jid, password)
        self.vehicle_type = vehicle_type
        self.current_location = start_location

        self.maintenance_jid = maintenance_jid
        self.gas_station_jid = gas_station_jid
        self.dashboard_jid = dashboard_jid
        self.capacity = capacity

        self.patrol_route = patrol_route if patrol_route else []
        self.patrol_index = 0
        if self.current_location in self.patrol_route:
            self.patrol_index = self.patrol_route.index(self.current_location)

        self.manifest = []
        self.waypoints = []
        self.pending_bids = {}

        self.fuel_level = 100.0
        self.fuel_consumption = 0.2

        self.is_broken = False
        self.is_refueling = False

        self.city_map = CityGraph()
        self.city_map.create_sample_map()

    async def setup(self):
        """Initializes the vehicle and starts main behavior."""
        print(f"🚍 {self.vehicle_type.upper()} {self.name} starting...")
        b = self.TransportBehaviour()
        self.add_behaviour(b)

    class TransportBehaviour(CyclicBehaviour):
        """
        Main vehicle behaviour.

        In each cycle, it reads messages, updates status,
        and advances one movement step if possible.
        """

        async def on_start(self):
            """Reports initial status to the dashboard."""
            print(f"[{self.agent.name}] ✅ Connected! Reporting to Dashboard.")
            await self.send_status_update("idle")

        async def send_status_update(self, status):
            """Sends current status (loc, state, load, fuel) to dashboard."""
            if not self.agent.dashboard_jid:
                return
            load = len(self.agent.manifest)
            msg_data = TransportationOntology.format_status(
                vehicle_id=str(self.agent.jid),
                location=self.agent.current_location,
                status=status,
                current_load=load,
            )
            msg_data["fuel"] = self.agent.fuel_level
            msg = TransportationOntology.create_message(
                to_jid=self.agent.dashboard_jid,
                performative=Performative.INFORM,
                content_data=msg_data,
            )
            await self.send(msg)

        async def run(self):
            """Processes incoming messages and moves the vehicle on the graph."""
            msg = await self.receive(timeout=0.1)
            if msg:
                performative = msg.get_metadata("performative")
                content = json.loads(msg.body)

                if performative == Performative.INFORM and content.get("type") == "traffic_update":
                    u, v = content["edge"]
                    w = content["new_weight"]
                    if self.agent.city_map.graph.has_edge(u, v):
                        self.agent.city_map.graph[u][v]["weight"] = w
                        print(
                            f"[{self.agent.name}] ⚠️ Route updated: "
                            f"{u}->{v} now takes {w}m."
                        )

                elif performative == Performative.CFP:
                    await self.handle_cfp(msg, content)
                
                elif performative == Performative.ACCEPT_PROPOSAL:
                    await self.handle_acceptance(msg, content)

                elif content.get("status") in ["repaired", "refueled"]:
                    await self.process_service_message(msg)

                elif performative == Performative.INFORM and content.get("type") == "demand_surge":
                    target_station = content.get("station")
                    count = content.get("count")
                    
                    if (
                        len(self.agent.manifest) < self.agent.capacity
                        and target_station != self.agent.current_location
                        and target_station not in self.agent.waypoints
                        and not self.agent.is_broken
                        and not self.agent.is_refueling
                    ):
                        print(f"[{self.agent.name}] 🚨 ALERT: {count} people at {target_station}! Diverting route to assist.")
                        self.agent.waypoints.insert(0, target_station)


            if (
                not self.agent.is_broken
                and not self.agent.is_refueling
                and not self.agent.waypoints
                and self.agent.patrol_route
            ):
                next_idx = (self.agent.patrol_index + 1) % len(self.agent.patrol_route)
                next_stop = self.agent.patrol_route[next_idx]
                
                if self.agent.current_location == next_stop:
                    self.agent.patrol_index = next_idx
                else:
                    self.agent.waypoints.append(next_stop)
                    self.agent.patrol_index = next_idx
            
            if (
                not self.agent.is_broken
                and not self.agent.is_refueling
                and self.agent.waypoints
            ):
                await self.move_to_next_node()

        async def process_service_message(self, msg):
            """Handles confirmations from Workshop or Gas Station."""
            content = json.loads(msg.body)
            status = content.get("status")
            if status == "repaired":
                print(f"[{self.agent.name}] ✨ Repaired!")
                self.agent.is_broken = False
                if content.get("refueled"):
                    self.agent.fuel_level = 100.0
                    print(f"[{self.agent.name}] (Note: Refueled by workshop)")
                await self.send_status_update("idle")
            elif status == "refueled":
                print(f"[{self.agent.name}] ⛽ Tank full! Resuming service...")
                self.agent.fuel_level = 100.0
                self.agent.is_refueling = False
                self.agent.current_location = "GasStation" 
                await self.send_status_update("idle")

        async def move_to_next_node(self):
            """
            Advances one step in the route towards the next waypoint.

            Calculates shortest path based on current graph, applies fuel/time
            costs, and may trigger random breakdowns.
            """
            if not self.agent.waypoints:
                return
            target_stop = self.agent.waypoints[0]

            if self.agent.current_location == target_stop:
                self.agent.waypoints.pop(0)
                await self.process_stop(target_stop)
                return

            path = self.agent.city_map.get_shortest_path(
                self.agent.current_location,
                target_stop,
                self.agent.vehicle_type,
            )
            if not path or len(path) < 2:
                self.agent.waypoints.pop(0)
                return

            next_node = path[1]
            edge_data = self.agent.city_map.graph[self.agent.current_location][
                next_node
            ]

            travel_time = edge_data.get("weight", 10)
            distance = edge_data.get("base_weight", 10)
            fuel_cost = distance * self.agent.fuel_consumption

            if (
                self.agent.vehicle_type != "tram"
                and self.agent.fuel_level < fuel_cost
            ):
                print(f"[{self.agent.name}] Out of fuel to move.")
                await self.trigger_breakdown("no_fuel") 
                return

            await self.send_status_update("moving")

            TIME_SCALE = 0.1
            sleep_time = travel_time * TIME_SCALE
            await asyncio.sleep(sleep_time)

            self.agent.current_location = next_node
            if self.agent.vehicle_type != "tram":
                self.agent.fuel_level -= fuel_cost

            if random.random() < 0.01:
                await self.trigger_breakdown("engine_fail")
            else:
                await self.send_status_update("moving")

        async def process_stop(self, location):
            """
            Executes logic when arriving at a stop.

            Can request refuel, disembark passengers, and decide
            on a preventive trip to the gas station.
            """
            print(f"[{self.agent.name}] 🛑 Stop: {location}.")

            if location == "GasStation":
                print(f"[{self.agent.name}] ⛽ Requesting refuel...")
                msg_data = {
                    "type": "refuel_request",
                    "amount_needed": 100 - self.agent.fuel_level,
                }
                msg = TransportationOntology.create_message(
                    to_jid=self.agent.gas_station_jid,
                    performative=Performative.REQUEST,
                    content_data=msg_data,
                )
                await self.send(msg)
                self.agent.is_refueling = True
                return

            new_manifest = []
            exiting = 0
            for p in self.agent.manifest:
                if p["dest"] == location:
                    exiting += 1
                else:
                    new_manifest.append(p)

            if exiting > 0:
                self.agent.manifest = new_manifest
                print(
                    f"[{self.agent.name}] 👋 Dropped off {exiting} passengers. "
                    f"Load: {len(self.agent.manifest)}/{self.agent.capacity}"
                )

            if not self.agent.manifest and self.agent.vehicle_type != "tram":
                path_pump = self.agent.city_map.get_shortest_path(
                    location, "GasStation", "bus"
                )
                cost_to_pump = 0
                if path_pump:
                    cost_to_pump = (
                        self.agent.city_map.get_total_distance(path_pump)
                        * self.agent.fuel_consumption
                    )

                if self.agent.fuel_level < (cost_to_pump + 10):
                    if "GasStation" not in self.agent.waypoints:
                        print(
                            f"[{self.agent.name}] ⚠️ Fuel tight for return "
                            f"({self.agent.fuel_level:.1f}% "
                            f"vs {cost_to_pump:.1f}%). Heading to pump."
                        )
                        await self.go_to_gas_station()

            await self.send_status_update("idle")
            await asyncio.sleep(1.5)

        async def handle_cfp(self, msg, content):
            """
            Handles a CNP Call For Proposal.

            Checks fuel, capacity, and route feasibility,
            then decides whether to send PROPOSE or REFUSE.
            """
            thread_id = msg.thread

            if (
                self.agent.vehicle_type != "tram"
                and self.agent.fuel_level < 30
            ):
                await self.send_refuse(msg, "low_fuel")
                if (
                    not self.agent.manifest
                    and "GasStation" not in self.agent.waypoints
                ):
                    await self.go_to_gas_station()
                return

            if len(self.agent.manifest) >= self.agent.capacity:
                await self.send_refuse(msg, "full_capacity")
                return

            origin = content["origin"]
            destination = content["destination"]

            path_pickup = self.agent.city_map.get_shortest_path(
                self.agent.current_location,
                origin,
                self.agent.vehicle_type,
            )
            path_trip = self.agent.city_map.get_shortest_path(
                origin,
                destination,
                self.agent.vehicle_type,
            )
            if not path_pickup or not path_trip:
                await self.send_refuse(msg, "route_impossible")
                return

            pickup_time = self.agent.city_map.get_total_time(path_pickup)
            trip_time = self.agent.city_map.get_total_time(path_trip)
            pickup_cost = self.agent.city_map.get_total_distance(path_pickup)
            trip_cost = self.agent.city_map.get_total_distance(path_trip)
            fuel_needed = (pickup_cost + trip_cost) * self.agent.fuel_consumption

            if self.agent.vehicle_type != "tram":
                path_pump = self.agent.city_map.get_shortest_path(
                    destination, "GasStation", "bus"
                )
                safety = (
                    self.agent.city_map.get_total_time(path_pump)
                    * self.agent.fuel_consumption
                    if path_pump
                else 0
                )
                total_required = fuel_needed + safety + 15

                if self.agent.fuel_level < total_required:
                    await self.send_refuse(msg, "insufficient_fuel_safety")
                    return

            if thread_id:
                self.agent.pending_bids[thread_id] = {
                    "origin": origin,
                    "dest": destination,
                    "fuel_cost": fuel_needed,
                }

            reply = msg.make_reply()
            reply.set_metadata("performative", Performative.PROPOSE)
            proposal_data = TransportationOntology.format_proposal(
                str(self.agent.jid),
                pickup_cost,
                self.agent.capacity - len(self.agent.manifest),
                path_trip,
            )
            reply.body = json.dumps(proposal_data)
            await self.send(reply)

        async def handle_acceptance(self, msg, content):
            """
            Handles the acceptance of a proposal.

            Ensures no double-booking occurred and updates
            the manifest and waypoint list.
            """
            if len(self.agent.manifest) >= self.agent.capacity:
                print(
                    f"[{self.agent.name}] ❌ REJECTED (Double Booking): "
                    "Became full meanwhile!"
                )
                reply = msg.make_reply()
                reply.set_metadata("performative", Performative.REFUSE)
                reply.body = json.dumps(
                    {
                        "reason": "capacity_full_error",
                    }
                )
                await self.send(reply)
                return

            thread_id = msg.thread
            bid_data = self.agent.pending_bids.get(thread_id)

            if bid_data:
                origin = bid_data["origin"]
                dest = bid_data["dest"]
                p_id = content.get("passenger_id", "unknown")

                self.agent.manifest.append({"id": p_id, "dest": dest})

                if self.agent.current_location != origin:
                    if (
                        not self.agent.waypoints
                        or self.agent.waypoints[-1] != origin
                    ):
                        self.agent.waypoints.insert(0, origin)

                if dest not in self.agent.waypoints:
                    self.agent.waypoints.append(dest)

                print(
                    f"[{self.agent.name}] ➕ Accepted (Pax: {p_id}). "
                    f"Queue: {self.agent.waypoints}. "
                    f"Load: {len(self.agent.manifest)}/{self.agent.capacity}"
                )
                del self.agent.pending_bids[thread_id]
            else:
                print(f"[{self.agent.name}] ❌ ERROR: Bid expired.")

        async def go_to_gas_station(self):
            """Schedules a pit stop when necessary."""
            if self.agent.is_refueling or "GasStation" in self.agent.waypoints:
                return
            print(f"[{self.agent.name}] ⚠️ Scheduling pit stop...")
            self.agent.waypoints.append("GasStation")

        async def trigger_breakdown(self, issue_type="engine_fail"):
            """Simulates a breakdown and sends a repair request to workshop."""
            self.agent.is_broken = True
            await self.send_status_update("broken")
            
            msg_data = TransportationOntology.format_breakdown(
                str(self.agent.jid),
                self.agent.current_location,
                issue_type,
            )
            msg = TransportationOntology.create_message(
                to_jid=self.agent.maintenance_jid,
                performative=Performative.REQUEST,
                content_data=msg_data,
            )
            await self.send(msg)

        async def send_refuse(self, msg, reason):
            """Sends a REFUSE reply to a CFP with the given reason."""
            reply = msg.make_reply()
            reply.set_metadata("performative", Performative.REFUSE)
            reply.body = json.dumps({"reason": reason})
            await self.send(reply)