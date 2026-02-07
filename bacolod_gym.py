import gymnasium as gym
from gymnasium import spaces
import numpy as np
from agents.bacolod_model import BacolodModel
from agents.household_agent import HouseholdAgent

class BacolodGymEnv(gym.Env):
    """
    Custom Environment that follows gymnasium interface.
    Connects the BacolodModel (ABM) to the RL Agent.
    """
    metadata = {'render.modes': ['human']}

    def __init__(self):
        super(BacolodGymEnv, self).__init__()

        # --- 1. DEFINE ACTION SPACE ---
        # shape=(21,) -> Unlocks "Granular Control"
        # Structure: [Bgy0_IEC, Bgy0_Enf, Bgy0_Inc, Bgy1_IEC, ... Bgy6_Inc]
        self.action_space = spaces.Box(low=-5.0, high=5.0, shape=(21,), dtype=np.float32)

        # --- 2. DEFINE OBSERVATION SPACE ---
        # 10 Continuous values: [CB_1..7, Budget, Time, PolCap]
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(17,), dtype=np.float32)

        self.model = None

        # Initialize memory for the previous compliance rates (7 barangays)
        self.prev_compliance = np.zeros(7, dtype=np.float32)

    def reset(self, seed=None, options=None):
        """
        Resets the environment to the initial state.
        """
        super().reset(seed=seed)
        
        self.model = BacolodModel(seed=seed, train_mode=True, policy_mode="ai")
        
        obs = self._get_observation()
        
        # === ADD THIS LINE ===
        # Capture the starting compliance (usually zeros or initial config)
        self.prev_compliance = obs[0:7]
        
        return obs, {}

    def step(self, action):
        """
        Execute one step in the environment.
        """
        # --- FIX: SOFTMAX NORMALIZATION ---
        # 1. Shift values to prevent overflow (Numerical Stability)
        # 2. Calculate Softmax
        exps = np.exp(action - np.max(action))
        allocation_percentages = exps / np.sum(exps)
        
        # 3. Apply these % to the ABM
        self.model.apply_action(allocation_percentages)
        self.model.step()

        # 4. Get New State
        obs = self._get_observation()
        
        # 5. Calculate Reward
        reward = self.calculate_reward(obs)
        
        # 6. Check Termination (10 Years = 40 Quarters)
        terminated = self.model.quarter >= 40
        truncated = False
        
        # 7. Info for Logs
        info = {
            "quarter": self.model.quarter, 
            "compliance": np.mean(obs[0:7]),
            "raw_ai_output": action,
            "actual_allocation": allocation_percentages
        }

        return obs, reward, terminated, truncated, info

    def _get_observation(self):
        if self.model is None:
            return np.zeros(17, dtype=np.float32)

        # 1. Compliance Rates
        compliance_rates = [b.compliance_rate for b in self.model.barangays]
        
        # 2. NEW: Attitude Levels (X-Ray Vision)
        # We calculate the average attitude for each barangay
        attitude_rates = []
        for b in self.model.barangays:
            # Filter agents belonging to this barangay
            households = [a for a in self.model.schedule.agents 
                          if isinstance(a, HouseholdAgent) and a.barangay_id == b.unique_id]
            
            if households:
                avg_att = np.mean([a.attitude for a in households])
            else:
                avg_att = 0.0
            attitude_rates.append(avg_att)

        # 3. Global Variables
        budget_norm = np.clip(self.model.quarterly_budget / 400000.0, 0, 1)
        time_norm = self.model.quarter / 40.0
        pol_cap = getattr(self.model, 'political_capital', 1.0)

        # Combine everything (7 + 7 + 3 = 17 values)
        obs_list = compliance_rates + attitude_rates + [budget_norm, time_norm, pol_cap]
        
        # Safety padding if needed
        if len(obs_list) < 17:
             obs_list += [0.0] * (17 - len(obs_list))
             
        return np.array(obs_list, dtype=np.float32)

    def calculate_reward(self, obs):
        curr_compliance = obs[0:7] 
        min_idx = np.argmin(curr_compliance)
        min_compliance = curr_compliance[min_idx]
        weakest_bgy = self.model.barangays[min_idx]
        
        # --- REWARD ---
        # 1. The Main Goal: Compliance
        # High multiplier (500) to make success very valuable.
        reward = min_compliance * 500.0 
        
        # 2. The "Nudge" (Not a Bribe)
        # We give a small reward for allocation ONLY if compliance is zero.
        # Once compliance starts moving (> 1%), this turns off.
        # This forces the AI to transition from "Spending" to "Results".
        if min_compliance < 0.01:
             total_funds = sum(b.iec_fund + b.enf_fund + b.inc_fund for b in self.model.barangays)
             if total_funds > 0:
                 share = (weakest_bgy.iec_fund + weakest_bgy.enf_fund + weakest_bgy.inc_fund) / total_funds
                 reward += (share * 10.0) # Small nudge (was 200.0)
            
        # Bankruptcy Penalty
        if obs[14] <= 0.01: reward -= 5.0

        return float(reward)
    
    def render(self, mode='human'):
        if self.model:
            obs = self._get_observation()
            print(f"--- Quarter {self.model.quarter} Report ---")
            print(f"Avg Compliance: {np.mean(obs[0:7]):.2f}")
            print(f"Budget Left:    {obs[7]*100:.1f}%")