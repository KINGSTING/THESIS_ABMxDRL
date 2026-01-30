import os
import signal
import sys
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.env_checker import check_env
from bacolod_gym import BacolodGymEnv

# Global model reference for the safety handler
model = None
models_dir = "models/PPO"

def signal_handler(sig, frame):
    """
    Catches Ctrl+C and saves the model before exiting.
    """
    global model
    print("\n\n!!! INTERRUPT RECEIVED !!!")
    if model is not None:
        save_path = f"{models_dir}/bacolod_ppo_interrupted"
        model.save(save_path)
        print(f"Safety Save: Model saved to {save_path}.zip")
        print("You can load this model later to continue training.")
    sys.exit(0)

def main():
    global model
    
    # 1. Setup Directories
    log_dir = "logs"
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    # 2. Instantiate Environment
    env = BacolodGymEnv()
    # Optional: check_env(env) # silenced for speed

    # 3. Define Model
    # Check if a saved model exists to continue training (Optional)
    # model = PPO.load("models/PPO/bacolod_ppo_final", env=env) 
    
    # OR Start Fresh:
    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        tensorboard_log=log_dir,
        learning_rate=0.0003,
        gamma=0.99,
        ent_coef=0.2, # Exploration
        policy_kwargs=dict(net_arch=dict(pi=[64, 64], vf=[64, 64]))
    )

    # 4. Setup Checkpoints (Auto-Save every 5,000 steps)
    checkpoint_callback = CheckpointCallback(
        save_freq=5000,
        save_path=models_dir,
        name_prefix="bacolod_checkpoint"
    )

    # 5. Register the Safety Handler (Ctrl+C protection)
    signal.signal(signal.SIGINT, signal_handler)

    # 6. Train
    TIMESTEPS = 50000 
    print(f"Starting training for {TIMESTEPS} steps...")
    print("... You can press Ctrl+C at any time to safely stop and save ...")
    
    model.learn(
        total_timesteps=TIMESTEPS, 
        progress_bar=True, 
        callback=checkpoint_callback
    )
    
    # 7. Final Save (If it finishes normally)
    save_path = f"{models_dir}/bacolod_ppo_final"
    model.save(save_path)
    print(f"DONE! Model saved to: {save_path}.zip")

if __name__ == "__main__":
    main()