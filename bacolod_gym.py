import gymnasium as gym
from gymnasium import spaces
import numpy as np
from agents.bacolod_model import BacolodModel
from agents.household_agent import HouseholdAgent

class BacolodGymEnv(gym.Env):
    metadata = {'render.modes': ['human']}

    def __init__(self):
        super(BacolodGymEnv, self).__init__()
        self.action_space = spaces.Box(low=-5.0, high=5.0, shape=(21,), dtype=np.float32)
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(17,), dtype=np.float32)
        self.model = None
        self.prev_compliance = np.zeros(7, dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.model = BacolodModel(seed=seed, train_mode=True, policy_mode="ai")
        obs = self._get_observation()
        self.prev_compliance = obs[0:7]
        return obs, {}

    def step(self, action):
        # 1. Softmax
        exps = np.exp(action - np.max(action))
        allocation_percentages = exps / np.sum(exps)
        
        # 2. Apply Action
        self.model.apply_action(allocation_percentages)
        
        # 3. Fast Forward 90 Days (The "Loop Fix" is critical)
        for _ in range(90):
            self.model.step()
            if not self.model.running: break

        # 4. Observe
        obs = self._get_observation()
        
        # 5. Reward
        reward = self.calculate_reward(obs, allocation_percentages)
        
        terminated = self.model.quarter >= 40
        truncated = False
        
        info = {
            "quarter": self.model.quarter, 
            "compliance": np.mean(obs[0:7]),
        }
        return obs, reward, terminated, truncated, info

    def _get_observation(self):
        if self.model is None: return np.zeros(17, dtype=np.float32)
        return self.model.get_state()

    def calculate_reward(self, obs, allocation_vector):
        curr_compliance = obs[0:7] 
        
        # 1. Base Compliance
        reward = np.sum(curr_compliance) * 100.0
        
        # 2. THE MEGA BRIBE (Poblacion Share)
        # We pay massively for allocating > 40% to Poblacion (Indices 6,7,8)
        poblacion_share = np.sum(allocation_vector[6:9])
        
        if poblacion_share > 0.20:
            reward += (poblacion_share * 5000.0) # Scaled up
            
        if poblacion_share > 0.40:
            reward += 20000.0 # JACKPOT! Impossible to ignore.
            
        # 3. THE PHYSICS CHECK (Intensity)
        poblacion_bgy = self.model.barangays[2]
        if poblacion_bgy.enforcement_intensity > 0.8:
            reward += 50000.0 # The Ultimate Goal
            
        # 4. Bankruptcy Penalty
        if obs[14] <= 0.01: reward -= 5000.0

        return float(reward)