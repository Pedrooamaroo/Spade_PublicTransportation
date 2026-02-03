"""Main script for the multi-agent simulation.

Creates and starts agents and manages the simulation loop.
"""

import asyncio
import random
from agents.station import StationAgent
from agents.vehicle import VehicleAgent
from agents.passenger import PassengerAgent
from agents.maintenance import MaintenanceAgent
from agents.gas_station import GasStationAgent
from agents.dashboard import DashboardAgent
from agents.traffic_manager import TrafficManagerAgent


async def main():
    """
    Main simulation function.
    """
    print("--- 🏙️ OPTIMIZED SIMULATION (FULL DOCUMENTATION) 🏙️ ---")

    SERVER = "jabb.im"
    PASSWORD = "PublicTransportation"
    PREFIX = "pedro"

    dash_jid = f"{PREFIX}_dashboard@{SERVER}"
    dashboard = DashboardAgent(dash_jid, PASSWORD)
    await dashboard.start()

    print("🔧 Opening Workshop...")
    mech_jid = f"{PREFIX}_mechanic@{SERVER}"
    mechanic = MaintenanceAgent(mech_jid, PASSWORD, num_mechanics=2)
    await mechanic.start()

    fuel_jid = f"{PREFIX}_fuel@{SERVER}"
    fuel_station = GasStationAgent(fuel_jid, PASSWORD)
    await fuel_station.start()

    route_bus_1 = ["South", "Central", "North", "West", "University", "South"]
    route_bus_2 = ["University", "South", "Airport", "East", "North", "West", "University"]
    route_bus_3 = ["Airport", "South", "Central", "East", "Airport"]
    route_tram_1 = ["North", "East", "Stadium", "North"]
    route_tram_2 = ["East", "Central", "West", "Central", "North", "East"]

    vehicles_config = [
        (f"{PREFIX}_bus_1@{SERVER}", "bus", "South", 4, route_bus_1),
        (f"{PREFIX}_bus_2@{SERVER}", "bus", "University", 4, route_bus_2),
        (f"{PREFIX}_bus_3@{SERVER}", "bus", "Airport", 4, route_bus_3),
        (f"{PREFIX}_tram_1@{SERVER}", "tram", "North", 6, route_tram_1),
        (f"{PREFIX}_tram_2@{SERVER}", "tram", "East", 6, route_tram_2),
    ]
    vehicles_jids = [v[0] for v in vehicles_config]

    print(f"🚌 Launching {len(vehicles_config)} vehicles with custom routes...")
    fleet = []
    for jid, v_type, start_loc, cap, route in vehicles_config:
        v = VehicleAgent(
            jid,
            PASSWORD,
            v_type,
            start_loc,
            maintenance_jid=mech_jid,
            gas_station_jid=fuel_jid,
            dashboard_jid=dash_jid,
            capacity=cap,
            patrol_route=route,
        )
        await v.start()
        fleet.append(v)
        print(f"   -> {jid} online (Route: {len(route)} stops).")
        await asyncio.sleep(1)

    print("🚦 Starting Traffic Control...")
    traffic_jid = f"{PREFIX}_traffic@{SERVER}"
    traffic_manager = TrafficManagerAgent(
        traffic_jid,
        PASSWORD,
        known_vehicles=vehicles_jids,
    )
    await traffic_manager.start()

    print("🏭 Opening stations...")
    station_names = [
        "Central", "North", "South", "East", "West",
        "Airport", "University", "Stadium",
    ]
    station_agents = {}
    for loc in station_names:
        s_jid = f"{PREFIX}_st_{loc.lower()}@{SERVER}"
        s_agent = StationAgent(
            s_jid,
            PASSWORD,
            location=loc,
            known_vehicles=vehicles_jids,
        )
        await s_agent.start()
        station_agents[loc] = s_jid
        await asyncio.sleep(0.1)

    print("⏳ Waiting for stabilization (5s)...")
    await asyncio.sleep(5)

    print("\n>>> STARTING TRAFFIC <<<")
    passenger_pool = [f"{PREFIX}_p_{i}@{SERVER}" for i in range(1, 41)]
    
    active_passengers = []
    rush_hour = False
    cycle = 0

    try:
        while True:
            cycle += 1

            if cycle % 10 == 0:
                rush_hour = not rush_hour
                print(
                    f"\n*** STATE CHANGE: "
                    f"{'🔥 RUSH HOUR' if rush_hour else '☕ CALM PERIOD'} ***\n"
                )

            active_passengers = [p for p in active_passengers if p.is_alive()]
            
            target = 20 if rush_hour else 8

            if len(active_passengers) < target:
                used = [str(p.jid) for p in active_passengers]
                avail = [jid for jid in passenger_pool if jid not in used]

                if avail:
                    for _ in range(min(2, len(avail))):
                        if len(active_passengers) >= target:
                            break
                        
                        p_jid = avail.pop(0)
                        origin = random.choice(station_names)
                        dest = random.choice([s for s in station_names if s != origin])

                        print(f"🎫 NEW: {origin} -> {dest} ({p_jid.split('_')[2]})")
                        p = PassengerAgent(
                            p_jid,
                            PASSWORD,
                            station_agents[origin],
                            dest,
                        )
                        await p.start()
                        active_passengers.append(p)

            wait = 1 if rush_hour else 3
            print(
                f"   [Status: {'RUSH' if rush_hour else 'CALM'}] "
                f"Active Pax: {len(active_passengers)}"
            )
            
            await asyncio.sleep(wait)

    except KeyboardInterrupt:
        print("Shutting down...")
        for a in fleet:
            await a.stop()
        await dashboard.stop()
        await traffic_manager.stop()

if __name__ == "__main__":
    asyncio.run(main())