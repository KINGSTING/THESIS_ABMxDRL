import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from agents.bacolod_model import BacolodModel

def run_simulation(policy_mode, label, duration_quarters=12):
    """Runs simulation and returns history. Stops early if political collapse occurs."""
    print(f"\n[SIMULATION START] Running {label}...")
    model = BacolodModel(train_mode=False, policy_mode=policy_mode)
    history = []
    
    for q in range(1, duration_quarters + 1):
        for day in range(90):
            if not model.running: break 
            model.step()
            
        df = model.datacollector.get_model_vars_dataframe()
        global_comp = df["Global Compliance"].iloc[-1]
        history.append(global_comp)
        
        if not model.running:
            # ONLY print collapse if capital actually dropped below 10%
            if model.political_capital < 0.10:
                print(f" > Quarter {q}: SIMULATION HALTED (Political Collapse).")
                return history 
            else:
                pass # It successfully survived the 3 years!
            
        print(f" > Quarter {q}: Compliance = {global_comp:.2%}")
    return history

def plot_comparison(results_dict):
    """Handles the specialized plotting including the 'Collapse' markers."""
    plt.figure(figsize=(12, 7))
    
    # --- EXPLICIT COLOR DICTIONARY ---
    colors = {
        'Status Quo (IEC)': '#7f8c8d',      # Dull Gray
        'Pure Incentives': '#f39c12',       # Orange
        'Pure Enforcement': '#e74c3c',      # Red
        'Mayor Agent': '#0052cc'            # Vibrant Royal Blue
    }
    
    for label, history in results_dict.items():
        quarters = list(range(1, len(history) + 1))
        
        line_color = colors.get(label, '#000000')
        linewidth = 4 if "Mayor Agent" in label else 2
        zorder = 10 if "Mayor Agent" in label else 1
        
        line, = plt.plot(quarters, history, label=label, marker='o', 
                         linewidth=linewidth, color=line_color, zorder=zorder)
        
        # If simulation collapsed (lasted less than 12 quarters)
        if len(history) < 12:
            plt.scatter(quarters[-1], history[-1], color='darkred', s=200, marker='X', zorder=15)
            plt.annotate("Political Collapse", (quarters[-1], history[-1]), 
                         textcoords="offset points", xytext=(0,15), 
                         ha='center', color='darkred', fontweight='bold',
                         bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="darkred", alpha=0.8))

    # Reference lines for TPB Logic
    plt.axhline(y=0.70, color='#27ae60', linestyle='--', alpha=0.8, linewidth=2, label='Lock-in Threshold (70%)')
    
    plt.xlabel("Quarter (90-day periods)", fontweight='bold')
    plt.ylabel("Global Compliance Rate", fontweight='bold')
    plt.title("LGU Policy Performance: The Cost of Strictness", fontsize=16, fontweight='bold')
    plt.legend(loc='upper left')
    plt.grid(True, linestyle=':', alpha=0.7)
    plt.gca().yaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(1.0))
    
    plt.tight_layout()
    plt.savefig('lgu_policy_comparison.png', dpi=300)
    print("\n[SUCCESS] Graph saved as 'lgu_policy_comparison.png'")

if __name__ == "__main__":
    QUARTERS = 12
    all_results = {}

    # Run the different scenarios
    all_results['Status Quo (IEC)'] = run_simulation("status_quo", "Status Quo (IEC)", QUARTERS)
    all_results['Pure Incentives'] = run_simulation("pure_incentives", "Pure Incentives", QUARTERS)
    all_results['Pure Enforcement'] = run_simulation("pure_enforcement", "Pure Enforcement", QUARTERS)
    all_results['Mayor Agent'] = run_simulation("HuDRL", "Mayor Agent", QUARTERS)

    # Execute the plotting function
    plot_comparison(all_results)