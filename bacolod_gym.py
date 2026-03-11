import gymnasium as gym
from gymnasium import spaces
import numpy as np
from agents.bacolod_model import BacolodModel
from agents.enforcement_agent import EnforcementAgent

class BacolodGymEnv(gym.Env):
    metadata = {'render.modes': ['human']}

    def __init__(self):
        super(BacolodGymEnv, self).__init__()
        # LEGAL: Maintaining the full 21 Municipal Levers
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(21,), dtype=np.float32)
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(17,), dtype=np.float32)
        self.model = None
        self.prev_compliance = np.zeros(7, dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.model = BacolodModel(train_mode=True, policy_mode="HuDRL")
        obs = self.model.get_state()
        
        # MUST BE HERE to prevent step 1 from crashing!
        self.prev_compliance = obs[0:7].copy() 
        
        return obs, {}
    
    def _get_observation(self):
        if self.model is None: return np.zeros(17, dtype=np.float32)
        return self.model.get_state()

    def step(self, action):
        # --- THE AGGRESSIVE 21-ACTION TRANSLATOR ---
        positive_desires = (action + 1.0) / 2.0
        
        # CALIBRATION: Power of 4. 
        # This mathematically forces "Sequential Saturation" while keeping all 21 choices legal.
        amplified = np.power(positive_desires, 4) 
        
        total_desire = np.sum(amplified)
        if total_desire > 0:
            action_vector = amplified / total_desire
        else:
            action_vector = np.ones(21) / 21.0
        
        # --- EXECUTE AND ADVANCE SIMULATION ---
        self.model.mayor.execute_intervention(action_vector)
        
        for _ in range(90):
            self.model.step() 
            if not self.model.running: 
                break

        # --- GATHER OBSERVATIONS ---
        obs = self.model.get_state()
        curr_compliance = obs[0:7]
        
        # --- CALCULATE REWARD ---
        reward = self.calculate_reward(obs, action_vector, self.prev_compliance)
        
        # --- UPDATE PREVIOUS COMPLIANCE FOR NEXT STEP ---
        self.prev_compliance = curr_compliance.copy()
        
        # --- ADD ATTITUDE BONUS ---
        avg_attitude = np.mean(obs[7:14])
        reward += (avg_attitude * 0.5)
        
        # --- CHECK STOP CONDITIONS ---
        terminated = not self.model.running
        truncated = False
        if terminated and self.model.political_capital < 0.10: 
            reward -= 10.0 
        
        info = {
            "quarter": self.model.quarter, 
            "compliance": np.mean(obs[0:7]), 
            "political_capital": obs[16]
        }
        
        return obs, float(reward), terminated, truncated, info

    def calculate_reward(self, obs, allocation_vector, prev_compliance):
        curr_compliance = obs[0:7] 
        political_capital = obs[16]
        budget_left = obs[14]
        
        # 1. Base reward for general compliance
        global_compliance = np.mean(curr_compliance)
        reward = global_compliance * 50.0  
        
        # 2. THE 90% SOCIAL NORM JACKPOT
        # The AI gets a massive injection of points only if it crosses 90%
        if global_compliance >= 0.90: 
            reward += 200.0                   
            
        compliance_gains = curr_compliance - prev_compliance
        
        for i in range(7):
            start_idx = i * 3
            bgy_allocation = np.sum(allocation_vector[start_idx:start_idx+3])
            enf_idx = start_idx + 1
            
            # 3. THE "SHOCK AND SUSTAIN" BREADCRUMBS
            if curr_compliance[i] < 0.90:
                # Hint: Use enforcement to break the initial resistance
                reward += (allocation_vector[enf_idx] * 10.0) 
                
                # Jackpot: Reward the AI heavily when its actions actually increase compliance
                if compliance_gains[i] > 0:
                    jackpot = (bgy_allocation * compliance_gains[i]) * 100.0  
                    reward += jackpot
            else:
                # Hint: Once past 90%, switch to IEC and Incentives to lock it in
                sustain_budget = allocation_vector[start_idx] + allocation_vector[start_idx + 2]
                reward += (sustain_budget * 20.0) 
                
                # Efficiency: Prevent the AI from wasting too much money on a "solved" barangay
                if bgy_allocation > 0.10: 
                    reward -= (bgy_allocation * 10.0) 
        
        # 4. FOCUS ALLOCATION BONUS
        # Give a small extra reward if the AI specifically targets the absolute worst barangay
        struggling_indices = np.where(curr_compliance < 0.90)[0]
        if len(struggling_indices) > 0:
            lowest_bgy_idx = struggling_indices[np.argmin(curr_compliance[struggling_indices])]
            focus_allocation = np.sum(allocation_vector[lowest_bgy_idx*3:(lowest_bgy_idx*3)+3])
            reward += (focus_allocation * 5.0)        
            
        # 5. RESOURCE & POLITICAL MANAGEMENT
        if budget_left <= 0.01: 
            reward -= 0.5                             
        
        # Political Capital is a gentle modifier, giving points for keeping approval high
        reward += (political_capital * 20.0)           

        return float(reward)