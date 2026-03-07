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
            print(f" > Quarter {q}: SIMULATION HALTED (Political Collapse).")
            return history # Returns shorter list so plot_comparison can detect it
            
        print(f" > Quarter {q}: Compliance = {global_comp:.2%}")
    return history

def plot_comparison(results_dict):
    """Handles the specialized plotting including the 'Collapse' markers."""
    plt.figure(figsize=(12, 7))
    
    for label, history in results_dict.items():
        quarters = list(range(1, len(history) + 1))
        
        # Determine color/style based on label
        color = '#007acc' if "HuDRL" in label else None
        linewidth = 3 if "HuDRL" in label else 2
        
        line, = plt.plot(quarters, history, label=label, marker='o', linewidth=linewidth, color=color)
        
        # If simulation collapsed (lasted less than 12 quarters)
        if len(history) < 12:
            plt.scatter(quarters[-1], history[-1], color='red', s=150, marker='X', zorder=5)
            plt.annotate("Political Collapse", (quarters[-1], history[-1]), 
                         textcoords="offset points", xytext=(0,10), 
                         ha='center', color='red', fontweight='bold')

    # Reference lines for TPB Logic
    plt.axhline(y=0.70, color='green', linestyle=':', alpha=0.6, label='Lock-in Threshold (70%)')
    
    plt.xlabel("Quarter (90-day periods)")
    plt.ylabel("Global Compliance Rate")
    plt.title("LGU Policy Performance: The Cost of Strictness", fontsize=14, fontweight='bold')
    plt.legend(loc='lower right')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.gca().yaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(1.0))
    
    plt.savefig('lgu_policy_comparison.png', dpi=300)
    print("\n[SUCCESS] Graph saved as 'lgu_policy_comparison.png'")

if __name__ == "__main__":
    QUARTERS = 12
    all_results = {}

    # Run the different scenarios
    all_results['Status Quo (IEC)'] = run_simulation("status_quo", "Status Quo", QUARTERS)
    all_results['Pure Incentives'] = run_simulation("pure_incentives", "Incentives", QUARTERS)
    all_results['Pure Enforcement'] = run_simulation("pure_enforcement", "Enforcement", QUARTERS)
    all_results['HuDRL (Smart)'] = run_simulation("HuDRL", "HuDRL", QUARTERS)

    # Execute the plotting function
    plot_comparison(all_results)