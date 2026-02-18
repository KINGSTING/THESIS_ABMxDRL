import matplotlib
matplotlib.use('Agg') # Force headless mode to prevent window errors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from agents.bacolod_model import BacolodModel

def run_simulation(policy_mode, label, duration_quarters=12):
    """
    Runs a single simulation instance with the specified policy mode.
    Returns the Global Compliance history per quarter.
    """
    print(f"\n[SIMULATION START] Running {label} (Mode: {policy_mode})...")
    
    # Initialize Model
    # Note: We set train_mode=False so it runs normally.
    model = BacolodModel(train_mode=False, policy_mode=policy_mode)
    
    history = []
    
    # Run for the specified duration (e.g., 12 Quarters = 3 Years)
    for q in range(1, duration_quarters + 1):
        # Run 90 ticks (1 Quarter)
        for day in range(90):
            model.step()
            
            # Optional: Print progress every 30 days to show it's alive
            if day % 30 == 0:
                print(f"   . Day {day}...", end="\r")

        # Capture Data at the end of the Quarter
        # We use the DataCollector to get the precise global compliance
        df = model.datacollector.get_model_vars_dataframe()
        global_comp = df["Global Compliance"].iloc[-1]
        
        print(f" > Quarter {q}: Compliance = {global_comp:.2%}")
        history.append(global_comp)
        
    print(f"[SIMULATION END] {label} Final Score: {history[-1]:.2%}")
    return history

if __name__ == "__main__":
    print("=============================================================")
    print("   PERFORMANCE TEST: STATUS QUO vs. HEURISTIC (NEW)")
    print("=============================================================")

    # 1. RUN OLD LOGIC (Status Quo)
    # Passing "status_quo" causes the model to SKIP the Heuristic block 
    # in apply_action and use the standard equal/weighted distribution.
    results_old = run_simulation("status_quo", "Old Logic (Status Quo)")

    # 2. RUN NEW LOGIC (Heuristic)
    # Passing "ppo" triggers the 'if self.policy_mode == "ppo"' block 
    # in apply_action, activating your Worst-First + Sustain + TBTF logic.
    results_new = run_simulation("ppo", "New Logic (Heuristic)")

    # 3. GENERATE COMPARISON PLOT
    print("\n[INFO] Generating Comparison Graph...")
    quarters = range(1, 13)
    
    plt.figure(figsize=(12, 7))
    
    # Plot Old Logic (Gray, Dashed)
    plt.plot(quarters, results_old, marker='o', linestyle='--', color='gray', alpha=0.7, linewidth=2, label='Non-Heuristic Approach')
    
    # Plot New Logic (Blue, Solid, Bold)
    plt.plot(quarters, results_new, marker='o', linestyle='-', color='#007acc', linewidth=3, label='Heuristic Approach')
    
    # Add Reference Lines
    plt.axhline(y=0.70, color='red', linestyle=':', alpha=0.5, label='Stability Threshold (70%)')
    plt.axhline(y=0.40, color='orange', linestyle=':', alpha=0.5, label='Collapse Zone (40%)')

    # Formatting
    plt.title('Comparison of Non-Hueristic & Hueristic Approach', fontsize=14)
    plt.xlabel('Quarter', fontsize=12)
    plt.ylabel('Global Compliance Rate', fontsize=12)
    plt.xticks(quarters)
    plt.ylim(0, 1.05)
    plt.legend(loc='lower right', fontsize=11)
    plt.grid(True, alpha=0.3)
    
    # Save File
    filename = 'heuristic_vs_status_quo.png'
    plt.savefig(filename, dpi=300)
    print(f"[SUCCESS] Graph saved as '{filename}'")