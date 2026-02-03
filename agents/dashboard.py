"""Dashboard agent.

Receives updates from vehicles, maintains fleet state,
and periodically generates the SVG map and HTML dashboard.
"""

import json
import time
import math

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour

from models.city_map import CityGraph
from utils.ontology import Performative, TransportationOntology


class DashboardAgent(Agent):
    """
    Agent responsible for the web dashboard.

    Receives vehicle updates, tracks fleet status,
    and periodically generates the SVG map and HTML dashboard.
    """

    async def setup(self):
        """Initializes graph, vehicle memory, and cyclic behaviour."""
        print(f"🌐 WEB DASHBOARD {self.name} starting...")
        print("   -> Open 'dashboard.html' in your browser to view!")

        self.city = CityGraph()
        self.city.create_sample_map()

        self.vehicles_state = {}

        self.last_render_time = 0
        self.last_metric_time = 0

        behaviour = self.WebWriterBehaviour()
        self.add_behaviour(behaviour)

    class WebWriterBehaviour(CyclicBehaviour):
        """
        Main dashboard behaviour.

        1. Receives vehicle updates (INFORM with status_update).
        2. Updates the agent's vehicles_state dictionary.
        3. Periodically:
           - generates SVG map (city_map.svg),
           - generates HTML (dashboard.html),
           - logs global metrics.
        """

        async def run(self):
            msg = await self.receive(timeout=0.5)

            if msg:
                performative = msg.get_metadata("performative")
                if performative == Performative.INFORM:
                    try:
                        content = json.loads(msg.body)
                    except Exception:
                        content = {}
                    if content.get("type") == "status_update":
                        v_id = content.get("vehicle_id", "").split("@")[0]
                        if v_id:
                            self.agent.vehicles_state[v_id] = {
                                "location": content.get("location"),
                                "fuel": float(content.get("fuel", 0)),
                                "status": content.get("status", "unknown"),
                                "load": int(content.get("load", 0)),
                            }

            now = time.time()

            if now - self.agent.last_render_time > 2.0:
                self.generate_svg_map()
                self.generate_html_file()
                self.agent.last_render_time = now

            if now - self.agent.last_metric_time > 5.0:
                self.record_fleet_metrics()
                self.agent.last_metric_time = now


        def generate_svg_map(self):
            """
            Generates an SVG map of the city (city_map.svg).

            Shows:
            - Roads with different styles based on allowed modes.
            - Stations (nodes).
            - Vehicles distributed in a circle around the station.
            """
            pos = self.agent.city.pos
            G = self.agent.city.graph

            if not pos:
                return

            xs = [x for x, y in pos.values()]
            ys = [y for x, y in pos.values()]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)

            width, height = 900, 700
            margin = 80
            usable_w = width - 2 * margin
            usable_h = height - 2 * margin

            def to_svg_coords(x, y):
                """Converts graph coordinates to SVG canvas coordinates."""
                if max_x == min_x:
                    sx = width / 2
                else:
                    sx = margin + (x - min_x) / (max_x - min_x) * usable_w

                if max_y == min_y:
                    sy = height / 2
                else:
                    sy = height - (margin + (y - min_y) / (max_y - min_y) * usable_h)

                return sx, sy

            svg = []

            svg.append(
                f'<svg width="{width}" height="{height}" '
                f'xmlns="http://www.w3.org/2000/svg">'
            )

            for u, v, data in G.edges(data=True):
                x1, y1 = pos[u]
                x2, y2 = pos[v]
                sx1, sy1 = to_svg_coords(x1, y1)
                sx2, sy2 = to_svg_coords(x2, y2)

                allowed = data.get("allowed_types", [])
                is_bus = "bus" in allowed
                is_tram = "tram" in allowed

                if is_bus and is_tram:
                    stroke = "#d4d4d8"  
                    width_px = 3
                    dash = "none"
                elif is_bus and not is_tram:
                    stroke = "#3b82f6"   
                    width_px = 2.4
                    dash = "6,4"
                else:  
                    stroke = "#f97373"  
                    width_px = 2.4
                    dash = "none"

                dash_attr = f'stroke-dasharray="{dash}"' if dash != "none" else ""

                svg.append(
                    f'<line x1="{sx1:.1f}" y1="{sy1:.1f}" '
                    f'x2="{sx2:.1f}" y2="{sy2:.1f}" '
                    f'stroke="{stroke}" stroke-width="{width_px}" {dash_attr} />'
                )

            for name, (x, y) in pos.items():
                sx, sy = to_svg_coords(x, y)

                svg.append(
                    f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="25" '
                    f'fill="rgba(15,23,42,0.02)" />'
                )
                svg.append(
                    f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="21" '
                    f'fill="white" stroke="#374151" stroke-width="2"/>'
                )
                svg.append(
                    f'<text x="{sx:.1f}" y="{sy + 5:.1f}" '
                    f'font-size="11" text-anchor="middle" '
                    f'font-family="Segoe UI" fill="#111827">{name}</text>'
                )

            station_vehicles = {}
            for v_name, v_data in self.agent.vehicles_state.items():
                loc = v_data.get("location")
                if loc in pos:
                    station_vehicles.setdefault(loc, []).append((v_name, v_data))

            for station, vehicles in station_vehicles.items():
                base_x, base_y = pos[station]
                sx_base, sy_base = to_svg_coords(base_x, base_y)

                n = len(vehicles)
                if n == 1:
                    offsets = [(0.0, 0.0)]
                else:
                    radius = 26  
                    offsets = []
                    for i in range(n):
                        angle = 2 * math.pi * i / n
                        dx = radius * math.cos(angle)
                        dy = radius * math.sin(angle)
                        offsets.append((dx, dy))

                for (v_name, v_data), (dx, dy) in zip(vehicles, offsets):
                    sx = sx_base + dx
                    sy = sy_base + dy

                    status = v_data.get("status", "unknown")
                    fuel = v_data.get("fuel", 0.0)

                    color = "#22c55e"  
                    if status == "broken":
                        color = "#ef4444"
                    elif status == "refueling":
                        color = "#facc15"
                    elif "tram" not in v_name and fuel < 30:
                        color = "#f97316"

                    svg.append(
                        f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="11" '
                        f'fill="{color}" stroke="white" stroke-width="2"/>'
                    )

                    label = "T" if "tram" in v_name else "B"
                    svg.append(
                        f'<text x="{sx:.1f}" y="{sy + 4:.1f}" '
                        f'font-size="10" text-anchor="middle" '
                        f'font-family="Segoe UI" fill="white">{label}</text>'
                    )

            svg.append("</svg>")

            with open("city_map.svg", "w", encoding="utf-8") as f:
                f.write("\n".join(svg))


        def generate_html_file(self):
            """
            Generates the HTML page with:
            - metric cards,
            - SVG city map,
            - legend,
            - fleet status table.

            Trams do not show fuel info.
            """
            total = len(self.agent.vehicles_state)
            active = sum(
                1
                for v in self.agent.vehicles_state.values()
                if v["status"] in ["moving", "refueling"]
            )
            broken = sum(
                1
                for v in self.agent.vehicles_state.values()
                if v["status"] == "broken"
            )

            if total > 0:
                avg_fuel = (
                    sum(v["fuel"] for v in self.agent.vehicles_state.values()) / total
                )
            else:
                avg_fuel = 0.0


            table_rows = ""
            for v_name, data in self.agent.vehicles_state.items():
                status = data["status"].lower()

                badge_color = "#9ca3af"
                if status == "moving":
                    badge_color = "#22c55e"
                elif status == "broken":
                    badge_color = "#ef4444"
                elif status == "refueling":
                    badge_color = "#facc15"
                elif status == "idle":
                    badge_color = "#6b7280"

                vtype = "🚍 Bus" if "bus" in v_name else "🚋 Tram"

                if "tram" in v_name:
                    fuel_display = "—"
                    fuel_bar = ""
                else:
                    fuel_val = data["fuel"]
                    fuel_display = f"{fuel_val:.1f}%"
                    fuel_bar = f"""
                    <div style="width:100%; background:#e5e7eb; border-radius:4px; height:6px; margin-top:2px;">
                        <div style="width:{fuel_val}%; height:6px; border-radius:4px; background:#4b5563;"></div>
                    </div>
                    """

                table_rows += f"""
                <tr>
                    <td>{v_name}</td>
                    <td>{vtype}</td>
                    <td>{data['location']}</td>
                    <td>
                        <span style="
                            padding:3px 10px;
                            border-radius:999px;
                            font-size:11px;
                            color:white;
                            background:{badge_color};
                            text-transform:uppercase;">
                            {data['status']}
                        </span>
                    </td>
                    <td>{data['load']}</td>
                    <td style="min-width:90px;">
                        {fuel_display}
                        {fuel_bar}
                    </td>
                </tr>
                """

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Transport Dashboard</title>
                <meta http-equiv="refresh" content="2" />

                <style>
                    body {{
                        font-family: "Segoe UI", sans-serif;
                        margin: 0;
                        padding: 0;
                        background: #eef2f7;
                    }}

                    h1 {{
                        margin: 0;
                        padding: 20px 32px;
                        background: white;
                        border-bottom: 1px solid #e5e7eb;
                        font-size: 24px;
                        display: flex;
                        align-items: center;
                        gap: 10px;
                    }}

                    .title-icon {{
                        width: 24px;
                        height: 24px;
                        border-radius: 999px;
                        background: linear-gradient(135deg,#22c55e,#3b82f6);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: white;
                        font-size: 14px;
                    }}

                    .metrics {{
                        display: grid;
                        grid-template-columns: repeat(4, 1fr);
                        gap: 12px;
                        padding: 20px 32px;
                    }}

                    .card {{
                        background: white;
                        padding: 12px 16px;
                        border-radius: 14px;
                        box-shadow: 0 2px 4px rgba(15,23,42,0.06);
                        border: 1px solid #e5e7eb;
                    }}

                    .card-title {{
                        font-size: 12px;
                        color: #6b7280;
                        margin-bottom: 4px;
                    }}

                    .card-value {{
                        font-size: 20px;
                        font-weight: 600;
                        color: #111827;
                    }}

                    .container {{
                        display: grid;
                        grid-template-columns: 2fr 1.2fr;
                        gap: 20px;
                        padding: 0 32px 24px 32px;
                    }}

                    .map-box, .data-box {{
                        background: white;
                        padding: 18px 20px;
                        border-radius: 16px;
                        box-shadow: 0 2px 4px rgba(15,23,42,0.06);
                        border: 1px solid #e5e7eb;
                    }}

                    .map-box h2, .data-box h2 {{
                        margin-top: 0;
                        font-size: 16px;
                        color: #111827;
                    }}

                    table {{
                        width: 100%;
                        border-collapse: collapse;
                        font-size: 13px;
                    }}

                    th {{
                        text-align: left;
                        padding: 8px;
                        border-bottom: 1px solid #e5e7eb;
                        background: #f9fafb;
                        font-size: 12px;
                        color: #6b7280;
                    }}

                    td {{
                        padding: 6px 8px;
                        border-bottom: 1px solid #f3f4f6;
                        vertical-align: middle;
                    }}

                    tr:hover td {{
                        background: #f9fafb;
                    }}

                    img {{
                        width: 100%;
                        border-radius: 16px;
                        border: 1px solid #e5e7eb;
                    }}

                    .legend {{
                        margin-top: 10px;
                        font-size: 11px;
                        color: #6b7280;
                        display: flex;
                        flex-wrap: wrap;
                        gap: 14px;
                        align-items: center;
                    }}

                    .legend-item-line {{
                        display: inline-block;
                        width: 26px;
                        height: 0;
                        border-bottom-width: 3px;
                        border-bottom-style: solid;
                        margin-right: 6px;
                        vertical-align: middle;
                    }}
                </style>
            </head>

            <body>

                <h1>
                    <span class="title-icon">⭑</span>
                    <span>Transport System Dashboard</span>
                </h1>

                <div class="metrics">
                    <div class="card">
                        <div class="card-title">Vehicles</div>
                        <div class="card-value">{total}</div>
                    </div>

                    <div class="card">
                        <div class="card-title">Active</div>
                        <div class="card-value">{active}</div>
                    </div>

                    <div class="card">
                        <div class="card-title">Broken</div>
                        <div class="card-value">{broken}</div>
                    </div>

                    <div class="card">
                        <div class="card-title">Avg Fuel</div>
                        <div class="card-value">{avg_fuel:.1f}%</div>
                    </div>
                </div>

                <div class="container">
                    <div class="map-box">
                        <h2>City Map</h2>
                        <img src="city_map.svg?t={time.time()}" alt="City Map" />
                        <div class="legend">
                            <span>
                                <span class="legend-item-line" style="border-bottom-color:#d4d4d8;"></span>
                                Bus + Tram
                            </span>
                            <span>
                                <span class="legend-item-line" style="border-bottom-color:#3b82f6; border-bottom-style:dashed;"></span>
                                Bus
                            </span>
                            <span>
                                <span class="legend-item-line" style="border-bottom-color:#f97373;"></span>
                                Tram
                            </span>
                        </div>
                    </div>

                    <div class="data-box">
                        <h2>Fleet Status</h2>
                        <table>
                            <thead>
                                <tr>
                                    <th>Vehicle</th>
                                    <th>Type</th>
                                    <th>Location</th>
                                    <th>Status</th>
                                    <th>Pass.</th>
                                    <th>Fuel</th>
                                </tr>
                            </thead>
                            <tbody>
                                {table_rows}
                            </tbody>
                        </table>
                    </div>
                </div>

            </body>
            </html>
            """

            with open("dashboard.html", "w", encoding="utf-8") as f:
                f.write(html_content)


        def record_fleet_metrics(self):
            """
            Logs simple fleet usage metrics.

            Calculates the percentage of active vehicles (moving or
            refueling) and logs a FLEET_USAGE record to metrics.csv.
            """
            total = len(self.agent.vehicles_state)
            if total == 0:
                return

            active = sum(
                1
                for v in self.agent.vehicles_state.values()
                if v["status"] in ["moving", "refueling"]
            )
            utilization = (active / total) * 100

            TransportationOntology.log_metric(
                "FLEET_USAGE",
                "Dashboard",
                "City",
                f"{utilization:.1f}",
                f"{active}/{total}_active",
            )