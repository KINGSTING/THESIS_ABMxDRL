import gymnasium as gym
from gymnasium import spaces
import numpy as np
from agents.bacolod_model import BacolodModel
from agents.enforcement_agent import EnforcementAgent

class BacolodGymEnv(gym.Env):
    metadata = {'render.modes': ['human']}

    def __init__(self):
        super(BacolodGymEnv, self).__init__()
        # PPO is mathematically optimized for ranges between -1 and 1
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(21,), dtype=np.float32)
        
        # 17 observations: 7 Compliance, 7 Attitude, 1 Budget, 1 Time, 1 Political Capital
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(17,), dtype=np.float32)
        self.model = None

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.model = BacolodModel(seed=seed, train_mode=True, policy_mode="HuDRL")
         
        return self._get_observation(), {}

    def step(self, action):
        # 1. SOFTMAX TEMPERATURE HACK
        # We multiply the action by 3.0 to "exaggerate" the AI's small initial guesses.
        # This allows it to hit 40-50% allocations much earlier in training.
        temperature_scale = 3.0
        scaled_action = action * temperature_scale
        
        exps = np.exp(scaled_action - np.max(scaled_action))
        allocation_percentages = exps / np.sum(exps)
        
        # 2. APPLY ACTION: Tell the Mayor how to spend the LGU budget
        self.model.mayor.execute_intervention(allocation_percentages)
        
        # 3. QUARTERLY FAST-FORWARD (The Speed Engine)
        # We run 90 days of "Math-only" simulation before giving control back to the AI
        for _ in range(90):
            self.model.step() # Calls the optimized step we wrote in bacolod_model
            if not self.model.running: 
                break

        # 4. OBSERVATION
        obs = self.model.get_state() # Use the model's get_state for consistency
        
        # 5. REWARD SHAPING (Thesis Alignment)
        reward = self.calculate_reward(obs, allocation_percentages)
        
        # Social Shield Bonus: Encourages "Soft Power" (IEC)
        avg_attitude = np.mean(obs[7:14])
        reward += (avg_attitude * 50.0)
        
        # 6. TERMINATION LOGIC
        # End if 10 years (40 quarters) pass OR if the Mayor is kicked out of office
        terminated = (self.model.quarter >= 40) or (not self.model.running)
        truncated = False
        
        # FATAL PENALTY: This is critical. Without this, the AI doesn't care if it loses.
        if not self.model.running and self.model.quarter < 40:
            reward -= 100000.0 
        
        info = {
            "quarter": self.model.quarter, 
            "compliance": np.mean(obs[0:7]),
            "political_capital": obs[16] # Assuming index 16 is Pol Cap in get_state
        }
        
        return obs, float(reward), terminated, truncated, info
    
    def _get_observation(self):
        if self.model is None: return np.zeros(17, dtype=np.float32)
        return self.model.get_state()

    def calculate_reward(self, obs, allocation_vector):
        curr_compliance = obs[0:7] 
        political_capital = obs[16]
        budget_left = obs[14]
        
        # Primary Objective: Compliance
        reward = np.sum(curr_compliance) * 100.0
        
        # --- THE GRADIENT HEURISTIC FIX ---
        # For every 1% allocated to Poblacion, the AI gets points immediately.
        poblacion_share = np.sum(allocation_vector[6:9])
        reward += (poblacion_share * 50000.0) 
            
        # Physics Check: Inspectors in Poblacion
        poblacion_bgy = self.model.barangays[2] 
        poblacion_lgu_inspectors = len([
            a for a in self.model.schedule.agents 
            if isinstance(a, EnforcementAgent) 
            and a.barangay_id == poblacion_bgy.unique_id 
            and getattr(a, 'is_municipal', False)
        ])
        
        # Reward per inspector, not a cliff of 10
        reward += (poblacion_lgu_inspectors * 5000.0)
            
        # --- PENALTIES ---
        
        # 1. Bankruptcy
        if budget_left <= 0.01: 
            reward -= 5000.0
        
        # --- TWO-TIERED POLITICAL BACKLASH ---
        
        # 2a. The Light Tax: Any lost capital hurts a little bit.
        # Example: Dropping from 1.0 to 0.8 loses 0.2. (0.2 * 5000 = -1000 points)
        capital_lost = 1.0 - political_capital
        reward -= (capital_lost * 5000.0)
        
        # 2b. The Danger Zone: Massive penalty if it drops below the 60% safety net.
        # Example: Dropping to 0.4 means a critical loss of 0.2. (0.2 * 50000 = -10000 points)
        if political_capital < 0.60:
            critical_loss = 0.60 - political_capital
            reward -= (critical_loss * 50000.0)

        return float(reward)