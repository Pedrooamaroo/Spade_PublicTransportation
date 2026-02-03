from models.city_map import CityGraph

def run_tests():
    print("--- 🗺️ STARTING ADVANCED MAP TESTS 🗺️ ---\n")
    city = CityGraph()
    city.create_sample_map()
    print("✅ Map loaded successfully.\n")

    # TEST 1: Vehicle Restrictions (Bus vs Tram)
    
    print("🔍 TEST 1: Vehicle Type Restrictions")
    
    # Scenario A: Bus tries to use tram track
    path_bus = city.get_shortest_path("East", "Stadium", "bus")
    if path_bus:
        print(f"❌ ERROR: Bus used tram track! Route: {path_bus}")
    else:
        print("✅ SUCCESS: Bus forbidden from East->Stadium (Tram Exclusive).")

    # Scenario B: Tram tries to use highway
    path_tram = city.get_shortest_path("South", "Airport", "tram")
    if path_tram:
        print(f"❌ ERROR: Tram reached Airport! Route: {path_tram}")
    else:
        print("✅ SUCCESS: Tram forbidden from Airport (Bus Exclusive).")
    print("")

    # TEST 2: Traffic Logic vs. Fuel (CRITICAL)

    print("🔍 TEST 2: Traffic affects Time but NOT Distance")
    
    u, v = "Central", "North"
    path = [u, v]
    
    time_normal = city.get_total_time(path)
    dist_normal = city.get_total_distance(path)
    print(f"   Normal State: Time={time_normal}m | Distance={dist_normal}km")

    # Simulating traffic jam (weight increases, base_weight stays same)
    city.graph[u][v]["weight"] = 50 
    
    time_traffic = city.get_total_time(path)
    dist_traffic = city.get_total_distance(path)
    print(f"   With Traffic:  Time={time_traffic}m | Distance={dist_traffic}km")

    if time_traffic > time_normal and dist_traffic == dist_normal:
        print("✅ SUCCESS: Traffic increased delay, but distance remained the same!")
        print("            (Bus won't burn 5x fuel just by standing still)")
    else:
        print("❌ ERROR: Traffic/distance logic is incorrect.")
    
    # Resetting
    city.graph[u][v]["weight"] = 10
    print("")

    # TEST 3: One-Way Streets and Loops

    print("🔍 TEST 3: One-Way Streets (Loops)")
    
    path_reverse = city.get_shortest_path("North", "Stadium", "tram")
    expected_route = ['North', 'East', 'Stadium']
    
    if path_reverse == expected_route:
        print(f"✅ SUCCESS: Tram respected one-way (North -> East -> Stadium).")
    else:
        print(f"⚠️ WARNING: Weird route detected: {path_reverse}")
    print("")

    # TEST 4: Access to Gas Station
    
    print("🔍 TEST 4: Gas Station Access")
    
    path_to_pump = city.get_shortest_path("University", "GasStation", "bus")
    print(f"   To Pump (Univ -> Pump): {path_to_pump}")
    
    path_from_pump = city.get_shortest_path("GasStation", "North", "bus")
    print(f"   Return (Pump -> North): {path_from_pump}")

    if path_to_pump and path_from_pump:
        print("✅ SUCCESS: Gas Station access fully operational.")
    else:
        print("❌ ERROR: Path to/from pump is blocked.")
    print("")

    print("--- 🏁 END OF TESTS ---")

if __name__ == "__main__":
    run_tests()