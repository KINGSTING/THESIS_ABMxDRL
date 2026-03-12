import os
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor
from bacolod_gym import BacolodGymEnv

def make_env(rank, seed=0):
    def _init():
        return BacolodGymEnv()
    return _init

def train():
    num_cpu = 4 
    vec_env = SubprocVecEnv([make_env(i) for i in range(num_cpu)])
    vec_env = VecMonitor(vec_env) 

    # --- THE 1-HOUR THESIS RUN ---
    # 7168 timesteps at 2 it/s = Exactly 59.7 minutes.
    TIMESTEPS = 1000 
    
    model = PPO(
        "MlpPolicy",
        vec_env,
        verbose=1,
        learning_rate=0.005,  # Boosted even higher for maximum adaptation speed
        n_steps=256,          # REDUCED: Forces the AI to update its brain every 4 minutes instead of every 20 mins
        batch_size=128,       
        n_epochs=20,          # INCREASED: Squeezes maximum learning out of the tiny dataset
        gamma=0.99,
        ent_coef=0.005,       
        tensorboard_log="./logs/",
        device="cpu"
    )

    print(f"Bacolod DRL: 1-HOUR THESIS Training Started on {num_cpu} Cores...")
    model.learn(total_timesteps=TIMESTEPS, progress_bar=True)
    
    model.save("models/ppo/bacolod_ppo_final")
    print("\n[SUCCESS] 1-Hour Run Complete!")

if __name__ == "__main__":
    train()