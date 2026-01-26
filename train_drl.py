import os
import gymnasium as gym
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from bacolod_gym import BacolodGymEnv

def main():
    # 1. Setup Directories
    models_dir = "models/PPO"
    log_dir = "logs"
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    # 2. Instantiate Environment
    env = BacolodGymEnv()
    check_env(env)

    # 3. Define Model with EXPLORATION
    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        tensorboard_log=log_dir,
        learning_rate=0.0003,
        gamma=0.99,
        
        # CRITICAL FIX: Force the AI to try different things!
        ent_coef=0.2, 
        
        policy_kwargs=dict(net_arch=dict(pi=[64, 64], vf=[64, 64]))
    )

    # 4. Train
    # 1,000 is okay for a syntax check, but for results use 50,000+
    TIMESTEPS = 50000 
    print(f"Starting training for {TIMESTEPS} steps...")
    model.learn(total_timesteps=TIMESTEPS, progress_bar=True)
    
    # 5. Save
    save_path = f"{models_dir}/bacolod_ppo_final"
    model.save(save_path)
    print(f"Model saved to: {save_path}.zip")

    # --- TESTING THE MODEL ---
    print("\n--- TEST RUN (AI CONTROLLED) ---")
    
    # RELOAD to ensure we are testing what we saved
    del model
    model = PPO.load(save_path)
    
    obs, _ = env.reset()
    done = False
    
    while not done:
        # deterministic=False allows a bit of "noise" so you don't just see 
        # the exact same action if the confidence is low.
        action, _states = model.predict(obs, deterministic=False)
        
        # Apply action
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        
        # DEBUG: Print the raw action to see if it's changing
        # If this prints [1.0, 0.0, 0.0] constantly, check bacolod_gym.py reset()!
        print(f"Action Output: {action}") 
        print(f"Step: {info.get('step')} | Budget: {info.get('budget'):.0f} | Compliance: {info.get('compliance'):.2%}")

if __name__ == "__main__":
    main()