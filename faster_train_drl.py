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

    # --- MICRO-TEST MODE ---
    TIMESTEPS = 1000 
    
    model = PPO(
        "MlpPolicy",
        vec_env,
        verbose=1,
        learning_rate=0.001,  
        n_steps=60,          
        batch_size=60,       
        n_epochs=10,
        gamma=0.99,
        ent_coef=0.02,        # Forces aggressive exploration
        tensorboard_log="./logs/",
        device="cpu"
    )

    print(f"Bacolod DRL: MICRO-TEST Training Started on {num_cpu} Cores...")
    model.learn(total_timesteps=TIMESTEPS, progress_bar=True)
    
    model.save("models/ppo/bacolod_ppo_final")
    print("\n[SUCCESS] Micro-Test Complete!")

if __name__ == "__main__":
    train()