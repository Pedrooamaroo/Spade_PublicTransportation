import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def analyze_results():
    print("📊 Analyzing metrics from 'metrics.csv'...")
    
    data_list = []
    
    try:
        with open("metrics.csv", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 6:
                    metric_type = parts[1]
                    if metric_type in ["PASSENGER_SUCCESS", "PASSENGER_FAIL", "FLEET_USAGE", "NEGOTIATION_OK", "NEGOTIATION_FAIL"]:
                        data_list.append(parts)
        
        columns = ["Timestamp", "Type", "Source", "Target", "Value", "Extra"]
        df = pd.DataFrame(data_list, columns=columns)
        
        if df.empty:
            print("⚠️ Warning: No valid metrics found in file.")
            return

        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        df["Value"] = pd.to_numeric(df["Value"], errors='coerce')
        
    except FileNotFoundError:
        print("❌ Error: File 'metrics.csv' not found.")
        return

    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Performance Report: Decentralized Transport', fontsize=18, fontweight='bold')

    # CHART 1: Passenger Wait Time (Histogram)

    ax1 = axes[0, 0]
    success_data = df[df["Type"] == "PASSENGER_SUCCESS"].copy()
    
    if not success_data.empty:
        avg_wait = success_data["Value"].mean()
        sns.histplot(data=success_data, x="Value", bins=15, kde=True, ax=ax1, color="skyblue", edgecolor="black")
        ax1.axvline(avg_wait, color='red', linestyle='--', linewidth=2, label=f'Avg: {avg_wait:.1f}s')
        
        ax1.set_title("Wait Time Distribution", fontsize=14)
        ax1.set_xlabel("Seconds to Board")
        ax1.set_ylabel("No. of Passengers")
        ax1.legend()
    else:
        ax1.text(0.5, 0.5, "No Success Data", ha='center', va='center')
  
    # CHART 2: Fleet Usage (Time Series)
  
    ax2 = axes[0, 1]
    fleet_data = df[df["Type"] == "FLEET_USAGE"].copy()
    
    if not fleet_data.empty:
        ax2.plot(fleet_data["Timestamp"], fleet_data["Value"], color="green", linewidth=2)
        ax2.fill_between(fleet_data["Timestamp"], fleet_data["Value"], color="lightgreen", alpha=0.3)
        
        ax2.set_title("Real-Time Fleet Utilization", fontsize=14)
        ax2.set_xlabel("Simulation Time")
        ax2.set_ylabel("% Active Vehicles")
        ax2.set_ylim(0, 105)
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    else:
        ax2.text(0.5, 0.5, "No Fleet Data", ha='center', va='center')

    # CHART 3: Success vs Failure (Timeout) (Pie Chart)

    ax3 = axes[1, 0]
    failures = len(df[df["Type"] == "PASSENGER_FAIL"])
    successes = len(success_data)
    
    if (failures + successes) > 0:
        labels = [f'Success\n({successes})', f'Dropouts\n({failures})']
        sizes = [successes, failures]
        colors = ['#4CAF50', '#FF5252']
        
        ax3.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=140, 
                explode=(0.05, 0), shadow=True, textprops={'fontsize': 12})
        ax3.set_title("Passenger Satisfaction", fontsize=14)
    else:
        ax3.text(0.5, 0.5, "No Passenger Data", ha='center', va='center')

    # CHART 4: Top 5 Busiest Stations (Bar Chart)
   
    ax4 = axes[1, 1]
    demand_data = df[df["Type"].isin(["PASSENGER_SUCCESS", "PASSENGER_FAIL"])].copy()
    
    if not demand_data.empty:
        top_dests = demand_data["Target"].value_counts().nlargest(5)
        
        sns.barplot(x=top_dests.values, y=top_dests.index, ax=ax4, palette="viridis")
        ax4.set_title("Most Popular Destinations (Top 5)", fontsize=14)
        ax4.set_xlabel("No. of Trips (or Attempts)")
    else:
        ax4.text(0.5, 0.5, "No Demand Data", ha='center', va='center')

    plt.tight_layout()
    filename = "final_report.png"
    plt.savefig(filename)
    print(f"✅ Chart saved successfully: '{filename}'")
    plt.show()

if __name__ == "__main__":
    analyze_results()