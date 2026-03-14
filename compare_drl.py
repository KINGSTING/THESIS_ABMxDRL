import numpy as np
import matplotlib.pyplot as plt
from stable_baselines3 import PPO
from bacolod_gym import BacolodGymEnv
import os

def evaluate_agent(env, agent, episodes=5):
    """Runs the environment for a set number of episodes and averages the results."""
    metrics = {
        "rewards": [],
        "compliances": [],
        "political_capitals": []
    }

    for ep in range(episodes):
        obs, _ = env.reset()
        done = False
        truncated = False
        total_reward = 0.0
        
        while not (done or truncated):
            # Deterministic=True means the AI uses its best learned policy without random exploration
            action, _ = agent.predict(obs, deterministic=True)
            obs, reward, done, truncated, info = env.step(action)
            total_reward += reward

        metrics["rewards"].append(total_reward)
        metrics["compliances"].append(info["compliance"] * 100) # Convert to percentage
        metrics["political_capitals"].append(info["political_capital"] * 100) # Scale for chart

    return {
        "avg_reward": np.mean(metrics["rewards"]),
        "avg_compliance": np.mean(metrics["compliances"]),
        "avg_pol_cap": np.mean(metrics["political_capitals"])
    }

def main():
    model_path = "models/ppo/bacolod_ppo_final.zip"
    
    if not os.path.exists(model_path):
        print(f"Error: Trained model not found at {model_path}")
        print("Please run train_drl.py first!")
        return

    print("Loading Trained Agent...")
    agent = PPO.load(model_path)

    # 1. Evaluate HuDRL (Heuristics ON)
    print("\nEvaluating HuDRL (With Target Lock & Guardrails)...")
    env_hudrl = BacolodGymEnv(policy_mode="HuDRL")
    hudrl_results = evaluate_agent(env_hudrl, agent, episodes=5)

    # 2. Evaluate Vanilla PPO (Heuristics OFF)
    print("Evaluating Vanilla PPO (No Heuristics)...")
    env_vanilla = BacolodGymEnv(policy_mode="Vanilla_DRL") 
    vanilla_results = evaluate_agent(env_vanilla, agent, episodes=5)

    # --- Print Console Report ---
    print("\n" + "="*50)
    print("      HEURISTIC VS VANILLA PPO COMPARISON")
    print("="*50)
    print(f"{'Metric':<25} | {'HuDRL':<10} | {'Vanilla PPO':<10}")
    print("-" * 50)
    print(f"{'Avg Episode Reward':<25} | {hudrl_results['avg_reward']:<10.1f} | {vanilla_results['avg_reward']:<10.1f}")
    print(f"{'Final Global Compliance':<25} | {hudrl_results['avg_compliance']:<9.1f}% | {vanilla_results['avg_compliance']:<9.1f}%")
    print(f"{'Final Political Capital':<25} | {hudrl_results['avg_pol_cap']:<9.1f}% | {vanilla_results['avg_pol_cap']:<9.1f}%")
    print("="*50)

    # --- Generate Comparison Chart ---
    labels = ['Avg Total Reward', 'Final Compliance (%)', 'Political Capital (%)']
    
    # Scale reward down slightly just so it fits nicely on the same Y-axis as percentages
    # (Adjust the / 10 if your rewards are massively higher or lower)
    hudrl_bars = [hudrl_results['avg_reward'] / 10, hudrl_results['avg_compliance'], hudrl_results['avg_pol_cap']]
    vanilla_bars = [vanilla_results['avg_reward'] / 10, vanilla_results['avg_compliance'], vanilla_results['avg_pol_cap']]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, hudrl_bars, width, label='HuDRL (Heuristics ON)', color='#2ca02c')
    rects2 = ax.bar(x + width/2, vanilla_bars, width, label='Vanilla PPO (Heuristics OFF)', color='#1f77b4')

    ax.set_ylabel('Score / Percentage')
    ax.set_title('Ablation Study: Impact of Heuristic Guardrails on DRL Agent')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    # Add text labels on top of bars
    ax.bar_label(rects1, padding=3, fmt='%.1f')
    ax.bar_label(rects2, padding=3, fmt='%.1f')

    plt.tight_layout()
    
    # Save and show
    os.makedirs("results", exist_ok=True)
    chart_path = "results/hudrl_vs_vanilla.png"
    plt.savefig(chart_path, dpi=300)
    print(f"\n> Comparison chart saved successfully to: {chart_path}")
    
    plt.show()

if __name__ == "__main__":
    main()