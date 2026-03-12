import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from agents.bacolod_model import BacolodModel

def run_simulation(policy_mode, label, duration_quarters=12):
    """Runs simulation and halts immediately upon political collapse."""
    print(f"\n[SIMULATION START] Running {label}...")
    model = BacolodModel(train_mode=False, policy_mode=policy_mode)
    history = []
    collapse_quarter = None 
    
    for q in range(1, duration_quarters + 1):
        for day in range(90):
            if not model.running: 
                break # Actually stop the days if it crashed!
            model.step()
            
        df = model.datacollector.get_model_vars_dataframe()
        global_comp = df["Global Compliance"].iloc[-1]
        history.append(global_comp)
        
        # IF COLLAPSE HAPPENS: Mark it, print it, and completely break the loop!
        if model.political_capital < 0.10 or not model.running:
            print(f" > Quarter {q}: ⚠️ FATAL POLITICAL COLLAPSE! (Simulation Terminated)")
            collapse_quarter = q
            break 
            
        print(f" > Quarter {q}: Compliance = {global_comp:.2%}")
        
    return {'history': history, 'collapse_q': collapse_quarter}

def plot_comparison(results_dict):
    """Handles plotting with severed lines for collapsed policies."""
    plt.figure(figsize=(12, 7))
    
    colors = {
        'Status Quo (IEC)': '#7f8c8d',      
        'Pure Incentives': '#f39c12',       
        'Pure Enforcement': '#e74c3c',      
        'Mayor Agent': '#0052cc'            
    }
    
    for label, data in results_dict.items():
        history = data['history']
        collapse_q = data['collapse_q']
        
        # Only draw the line for the quarters it actually survived
        quarters = list(range(1, len(history) + 1))
        
        line_color = colors.get(label, '#000000')
        linewidth = 4 if "Mayor Agent" in label else 2
        zorder = 10 if "Mayor Agent" in label else 1
        
        line, = plt.plot(quarters, history, label=label, marker='o', 
                         linewidth=linewidth, color=line_color, zorder=zorder)
        
        # Pin the giant 'X' at the exact moment the line gets severed
        if collapse_q is not None:
            plt.scatter(quarters[-1], history[-1], color='darkred', s=200, marker='X', zorder=15)
            plt.annotate("Political Collapse", (quarters[-1], history[-1]), 
                         textcoords="offset points", xytext=(0,15), 
                         ha='center', color='darkred', fontweight='bold',
                         bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="darkred", alpha=0.8))

    plt.axhline(y=0.70, color='#27ae60', linestyle='--', alpha=0.8, linewidth=2, label='Lock-in Threshold (70%)')
    
    plt.xlabel("Quarter (90-day periods)", fontweight='bold')
    plt.ylabel("Global Compliance Rate", fontweight='bold')
    plt.title("LGU Policy Performance: AI vs Traditional Models", fontsize=16, fontweight='bold')
    
    # =================================================================
    # FIX: MOVED LEGEND OUTSIDE THE GRAPH (CENTER RIGHT)
    # =================================================================
    plt.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), title="Policies & Thresholds", 
               fontsize=11, framealpha=0.9)
    
    plt.grid(True, linestyle=':', alpha=0.7)
    plt.gca().yaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(1.0))
    
    plt.tight_layout()
    
    # FIX: ADDED bbox_inches='tight' SO THE EXTERNAL LEGEND IS SAVED PROPERLY
    plt.savefig('lgu_policy_comparison.png', dpi=300, bbox_inches='tight')
    print("\n[SUCCESS] Graph saved as 'lgu_policy_comparison.png'")

if __name__ == "__main__":
    QUARTERS = 12
    all_results = {}

    all_results['Status Quo (IEC)'] = run_simulation("status_quo", "Status Quo (IEC)", QUARTERS)
    all_results['Pure Incentives'] = run_simulation("pure_incentives", "Pure Incentives", QUARTERS)
    all_results['Pure Enforcement'] = run_simulation("pure_enforcement", "Pure Enforcement", QUARTERS)
    all_results['Mayor Agent'] = run_simulation("HuDRL", "Mayor Agent", QUARTERS)

    plot_comparison(all_results)