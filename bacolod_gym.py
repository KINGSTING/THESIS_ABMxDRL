import gymnasium as gym
from gymnasium import spaces
import numpy as np
from agents.bacolod_model import BacolodModel

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
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(10,), dtype=np.float32)

        self.model = None

    def reset(self, seed=None, options=None):
        """
        Resets the environment to the initial state.
        """
        super().reset(seed=seed)
        
        # Initialize the ABM Model
        # train_mode=True speeds it up, policy_mode="ai" connects the brain
        self.model = BacolodModel(seed=seed, train_mode=True, policy_mode="ai")
        
        # Return the first observation
        return self._get_observation(), {}

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
        """
        Extracts the state from the ABM and normalizes it for the AI.
        """
        if self.model is None:
            return np.zeros(10, dtype=np.float32)

        # 1. Compliance Rates (0.0 to 1.0) for 7 Barangays
        compliance_rates = [b.compliance_rate for b in self.model.barangays]
        
        # 2. Budget Remaining (Normalized)
        # Assuming Max Budget is roughly 400k for normalization
        budget_norm = self.model.quarterly_budget / 400000.0
        budget_norm = np.clip(budget_norm, 0, 1)

        # 3. Time Remaining (Normalized 0 to 1)
        time_norm = self.model.quarter / 40.0
        
        # 4. Political Capital (Normalized)
        pol_cap = getattr(self.model, 'political_capital', 1.0)

        # Combine into a single array
        obs_list = compliance_rates + [budget_norm, time_norm, pol_cap]
        
        # Safety padding if compliance_rates is missing data
        if len(obs_list) < 10:
            obs_list += [0.0] * (10 - len(obs_list))
            
        obs = np.array(obs_list, dtype=np.float32)
        return obs

    def calculate_reward(self, obs):
        """
        Thesis Section 3.4.4: Revised Multi-Objective Reward Function
        """
        # A. COMPLIANCE (Maximize)
        compliances = obs[0:7]
        avg_compliance = np.mean(compliances)
        
        # Power function: 0.9 is WAY better than 0.5
        r_compliance = (avg_compliance ** 2) * 10.0 

        # B. FAIL PENALTY (Disabled for training stability)
        r_fail = 0.0

        # C. BANKRUPTCY PENALTY
        # Punish only if budget is effectively zero
        budget_remaining = obs[7]
        r_bankruptcy = 0.0
        if budget_remaining <= 0.01:
            r_bankruptcy = -5.0

        # D. POLITICAL CAPITAL
        pol_cap = obs[9]
        r_pol_cap = 0.0
        if pol_cap < 0.3:
            r_pol_cap = -5.0

        # TOTAL
        total_reward = r_compliance + r_fail + r_bankruptcy + r_pol_cap
        return float(total_reward)

    def render(self, mode='human'):
        if self.model:
            obs = self._get_observation()
            print(f"--- Quarter {self.model.quarter} Report ---")
            print(f"Avg Compliance: {np.mean(obs[0:7]):.2f}")
            print(f"Budget Left:    {obs[7]*100:.1f}%")