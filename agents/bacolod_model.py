import mesa
from mesa.time import RandomActivation
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
import numpy as np
import random
import os
import csv 
from stable_baselines3 import PPO

import barangay_config as config
from agents.household_agent import HouseholdAgent
from agents.barangay_agent import BarangayAgent
from agents.enforcement_agent import EnforcementAgent

def compute_global_compliance(model):
    agents = [a for a in model.schedule.agents if isinstance(a, HouseholdAgent)]
    if not agents: return 0.0
    return sum(1 for a in agents if a.is_compliant) / len(agents)

class BacolodModel(mesa.Model):
    def __init__(self, seed=None, train_mode=False, policy_mode="ppo", behavior_override=None): 
        if seed is not None:
            super().__init__(seed=seed)
            self._seed = seed
            np.random.seed(seed)
            random.seed(seed)
        else:
            super().__init__()

        self.train_mode = train_mode
        self.policy_mode = policy_mode 
        self.rl_agent = None
        self.tick = 0       
        self.quarter = 1    
        self.behavior_override = behavior_override

        if self.behavior_override:
            print(f"\n[INIT] Calibration Mode Active. Overriding config.")
        else:
            print(f"\n[INIT] BacolodModel created with Policy Mode: {self.policy_mode.upper()}")
        
        # CSV Logging Setup
        results_dir = "results"
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)

        self.log_filename = os.path.join(results_dir, f"bacolod_report_{self.policy_mode}.csv")
        
        if not self.behavior_override:
            with open(self.log_filename, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([
                    "Quarter", "Tick", "Barangay_ID", "Barangay_Name", 
                    "Total_Budget_PHP", "LGU_Allocation_PHP", "LGU_Share_Percent", "Local_Base_PHP",
                    "IEC_Alloc_PHP", "IEC_Percent", 
                    "Enf_Alloc_PHP", "Enf_Percent", 
                    "Inc_Alloc_PHP", "Inc_Percent",
                    "IEC_Intensity_Score", "Enf_Intensity_Score", "Incentive_Value_Per_Capita",
                    "Avg_Attitude", "Avg_SocialNorm", "Avg_PBC", "Avg_Utility",
                    "Compliance_Rate", "Active_Enforcers", "Political_Capital"
                ])

        if not self.train_mode and self.policy_mode == "ppo" and not self.behavior_override:
            model_path = "models/PPO/bacolod_ppo_final.zip"
            if os.path.exists(model_path):
                print(f"Loading Trained Agent from {model_path}...")
                self.rl_agent = PPO.load(model_path)
            else:
                print("Warning: No trained model found. Will default to Status Quo.")

        self.annual_budget = config.ANNUAL_BUDGET
        self.current_budget = self.annual_budget
        self.quarterly_budget = self.annual_budget / 4 
        
        self.total_fines_collected = 0
        self.total_incentives_distributed = 0
        self.total_enforcement_cost = 0
        self.total_iec_cost = 0
        self.recent_fines_collected = 0

        self.grid_width = 50   
        self.grid_height = 50 
        self.grid = MultiGrid(self.grid_width, self.grid_height, torus=False)
        self.schedule = RandomActivation(self)
        self.running = True
        
        self.political_capital = 1.0     
        self.alpha_sensitivity = 0.05    
        self.beta_recovery = 0.02        

        self.barangays = []
        self.agent_id_counter = 0 
        
        # --- INITIALIZE BARANGAYS ---
        for i, b_conf in enumerate(config.BARANGAY_LIST):
            b_agent = BarangayAgent(f"BGY_{i}", self, local_budget=b_conf["local_budget"])
            b_agent.name = b_conf["name"]
            b_agent.n_households = b_conf["N_HOUSEHOLDS"]
            
            if "allocation_profile" in b_conf:
                profile_key = b_conf["allocation_profile"]
                if hasattr(config, 'ALLOCATION_PROFILES'):
                     b_agent.local_allocation_ratios = config.ALLOCATION_PROFILES.get(profile_key, config.ALLOCATION_PROFILES["Ezperanza"])

            self.schedule.add(b_agent)
            self.barangays.append(b_agent)
            
            # --- HOUSEHOLD GENERATION ---
            profile_key = b_conf.get("behavior_profile", "Poblacion") 
            if self.behavior_override:
                behavior_data = self.behavior_override.get(profile_key, config.BEHAVIOR_PROFILES["Poblacion"])
            else:
                behavior_data = config.BEHAVIOR_PROFILES.get(profile_key, config.BEHAVIOR_PROFILES["Poblacion"])

            n_households = b_conf["N_HOUSEHOLDS"]
            profile_key_income = b_conf["income_profile"]
            income_probs = list(config.INCOME_PROFILES[profile_key_income])
            
            for _ in range(n_households):
                x = self.random.randrange(self.grid_width)
                y = self.random.randrange(self.grid_height)
                income = np.random.choice([1, 2, 3], p=income_probs)
                is_compliant = (random.random() < b_conf["initial_compliance"])
                
                a = HouseholdAgent(
                    self.agent_id_counter, 
                    self, 
                    income_level=income, 
                    initial_compliance=is_compliant,
                    behavior_params=behavior_data 
                )
                self.agent_id_counter += 1
                a.barangay = b_agent
                a.barangay_id = b_agent.unique_id
                
                self.schedule.add(a)
                self.grid.place_agent(a, (x, y))

        # --- INITIAL DECISION ---
        self.run_decision_logic() 

        reporters = {
            "Global Compliance": compute_global_compliance,
            "Total Fines": lambda m: m.total_fines_collected,
            "Political Capital": lambda m: m.political_capital
        }
        
        for bgy in self.barangays:
             reporters[bgy.name] = lambda m, b=bgy: b.get_local_compliance()

        self.datacollector = DataCollector(model_reporters=reporters)
        self.datacollector.collect(self)

    def update_political_capital(self):
        avg_enforcement = 0
        if self.barangays:
            avg_enforcement = sum(b.enforcement_intensity for b in self.barangays) / len(self.barangays)
        decay = self.alpha_sensitivity * avg_enforcement
        recovery = self.beta_recovery * (1.0 - avg_enforcement)
        self.political_capital = max(0.0, min(1.0, self.political_capital - decay + recovery))

    def calculate_costs(self):
        total_iec_alloc = sum(b.iec_fund for b in self.barangays)
        total_enf_alloc = sum(b.enf_fund for b in self.barangays)
        daily_fixed_cost = (total_iec_alloc + total_enf_alloc) / 90.0
        self.total_enforcement_cost += (total_enf_alloc / 90.0)
        self.total_iec_cost += (total_iec_alloc / 90.0)
        self.current_budget = self.current_budget - daily_fixed_cost + self.recent_fines_collected
        self.recent_fines_collected = 0

    def adjust_enforcement_agents(self, barangay):
        potential_enforcers = barangay.enf_fund / barangay.enforcer_salary_cost
        num_guaranteed = int(potential_enforcers) 
        remainder_prob = potential_enforcers - num_guaranteed 
        extra_agent = 1 if self.random.random() < remainder_prob else 0
        target_count = num_guaranteed + extra_agent

        current_enforcers = [a for a in self.schedule.agents 
                             if isinstance(a, EnforcementAgent) 
                             and a.barangay_id == barangay.unique_id]
        current_count = len(current_enforcers)

        if current_count < target_count:
            diff = target_count - current_count
            for _ in range(diff):
                safe_id = self.next_id() + 1000000
                a = EnforcementAgent(safe_id, self, barangay.unique_id)
                self.schedule.add(a)
                x = self.random.randrange(self.grid_width)
                y = self.random.randrange(self.grid_height)
                self.grid.place_agent(a, (x, y))
        elif current_count > target_count:
            diff = current_count - target_count
            for i in range(diff):
                agent_to_remove = current_enforcers[i]
                self.grid.remove_agent(agent_to_remove)
                self.schedule.remove(agent_to_remove)
        
        barangay.active_enforcers_count = target_count

    def log_quarterly_report(self, quarter):
        if self.behavior_override: return
        
        with open(self.log_filename, mode='a', newline='') as file:
            writer = csv.writer(file)
            for b in self.barangays:
                total_funds = b.iec_fund + b.enf_fund + b.inc_fund
                local_base = b.local_quarterly_budget
                lgu_allocation = max(0, total_funds - local_base)
                
                lgu_share_pct = 0.0
                if self.quarterly_budget > 0:
                    lgu_share_pct = (lgu_allocation / self.quarterly_budget) * 100

                iec_pct = (b.iec_fund / total_funds * 100) if total_funds > 0 else 0
                enf_pct = (b.enf_fund / total_funds * 100) if total_funds > 0 else 0
                inc_pct = (b.inc_fund / total_funds * 100) if total_funds > 0 else 0

                households = [a for a in self.schedule.agents 
                              if isinstance(a, HouseholdAgent) and a.barangay_id == b.unique_id]
                
                if households:
                    avg_att = np.mean([a.attitude for a in households])
                    avg_sn = np.mean([a.sn for a in households])
                    avg_pbc = np.mean([a.pbc for a in households])
                    avg_util = np.mean([a.utility for a in households])
                else:
                    avg_att, avg_sn, avg_pbc, avg_util = 0, 0, 0, 0

                active_enforcers = len([a for a in self.schedule.agents 
                                        if isinstance(a, EnforcementAgent) 
                                        and a.barangay_id == b.unique_id])

                writer.writerow([
                    quarter, self.schedule.steps, 
                    b.unique_id, b.name,
                    f"{total_funds:.2f}", f"{lgu_allocation:.2f}", f"{lgu_share_pct:.2f}%", f"{local_base:.2f}",
                    f"{b.iec_fund:.2f}", f"{iec_pct:.1f}%",
                    f"{b.enf_fund:.2f}", f"{enf_pct:.1f}%",
                    f"{b.inc_fund:.2f}", f"{inc_pct:.1f}%",
                    f"{b.iec_intensity:.4f}", f"{b.enforcement_intensity:.4f}", f"{b.incentive_val:.2f}",
                    f"{avg_att:.3f}", f"{avg_sn:.3f}", f"{avg_pbc:.3f}", f"{avg_util:.3f}",
                    f"{b.get_local_compliance():.2%}", active_enforcers, f"{self.political_capital:.4f}"
                ])
        print(f" > Detailed Report for Quarter {quarter} saved to {self.log_filename}")

    def run_decision_logic(self):
        if self.train_mode: return 

        current_quarter = (self.schedule.steps // 90) + 1
        if not self.behavior_override: 
            print(f"\n--- Quarter {current_quarter} Decision Point ({self.policy_mode.upper()}) ---")

        # 1. AI MODE (PPO)
        if self.policy_mode == "ppo" and self.rl_agent is not None:
            current_state = self.get_state()
            raw_action, _ = self.rl_agent.predict(current_state, deterministic=True)
            exps = np.exp(raw_action - np.max(raw_action))
            action = exps / np.sum(exps)
            self.apply_action(action)
            
        # 2. MANUAL STRATEGIES (Status Quo, Pure Enf, Pure Inc)
        else:
            action = []
            
            # === CHANGED: REMOVED POPULATION CALCULATION ===
            # We no longer calculate total_hh. 
            
            for b in self.barangays:
                # === NEW LOGIC: EQUAL DISTRIBUTION ===
                # By giving everyone a weight of 1.0, the total weight becomes 7.
                # The apply_action function calculates: (1.0 / 7.0) * Budget = Equal Share.
                share = 1.0 
                
                if self.policy_mode == "pure_enforcement":
                    # [IEC, ENF, INC] -> All to Enforcement (Index 1)
                    action.extend([0.0, share, 0.0])
                    
                elif self.policy_mode == "pure_incentives":
                    # [IEC, ENF, INC] -> All to Incentives (Index 2)
                    action.extend([0.0, 0.0, share])
                    
                else: 
                    # Default: "status_quo" -> All to IEC (Index 0)
                    action.extend([share, 0.0, 0.0])
            
            self.apply_action(action)

        self.log_quarterly_report(current_quarter)

    def step(self):
        self.tick += 1
        if self.tick % 90 == 0:
            self.quarter += 1
            if not self.behavior_override:
                print(f" >> New Quarter: {self.quarter}")
            for a in self.schedule.agents:
                if isinstance(a, HouseholdAgent):
                    a.redeemed_this_quarter = False

        if self.schedule.steps % 90 == 0:
            self.run_decision_logic()

        for b in self.barangays: b.step()
        self.schedule.step()
        self.update_political_capital() 
        self.calculate_costs()
        self.datacollector.collect(self)
        
        if self.schedule.steps >= 1080: self.running = False

    def get_state(self):
        compliance_rates = [b.get_local_compliance() for b in self.barangays]
        attitude_rates = []
        for b in self.barangays:
            households = [a for a in self.schedule.agents 
                          if isinstance(a, HouseholdAgent) and a.barangay_id == b.unique_id]
            avg_att = np.mean([a.attitude for a in households]) if households else 0.0
            attitude_rates.append(avg_att)

        norm_budget = max(0.0, min(1.0, self.current_budget / self.annual_budget))
        norm_time = max(0.0, min(1.0, self.quarter / 40.0))
        p_cap = max(0.0, min(1.0, self.political_capital)) 
        
        state = compliance_rates + attitude_rates + [norm_budget, norm_time, p_cap]
        return np.array(state, dtype=np.float32)
    
    def apply_action(self, action_vector):
        """
        Applies distribution.
        FIX: Only applies 'King of the Hill' logic if mode is PPO.
        """
        
        # === 1. GOLDEN TICKET (Only for Training) ===
        if self.train_mode and random.random() < 0.25:
            synthetic_vector = np.zeros(21)
            synthetic_vector[7] = 100.0 
            for i in range(21):
                if i != 7: synthetic_vector[i] = 0.1
            action_vector = synthetic_vector

        if len(action_vector) == 21:
            
            # === CRITICAL FIX: Only use Smart Logic for AI ===
            if self.policy_mode == "ppo":
                
                # --- IDENTIFY THE KING OF THE HILL ---
                worst_compliance = 1.0
                worst_bgy_index = -1
                
                for i, bgy in enumerate(self.barangays):
                    comp = bgy.get_local_compliance()
                    if comp < worst_compliance:
                        worst_compliance = comp
                        worst_bgy_index = i
                
                # --- APPLY SMART LOGIC (Amplification) ---
                for i, bgy in enumerate(self.barangays):
                    idx_start = i * 3
                    compliance = bgy.get_local_compliance()
                    
                    if compliance > 0.70:
                        # Maintenance Mode
                        action_vector[idx_start] = 0.1   
                        action_vector[idx_start+1] = 0.2 
                        action_vector[idx_start+2] = 0.1 
                    
                    elif i == worst_bgy_index:
                        # War Mode (King of the Hill)
                        action_vector[idx_start] *= 100.0
                        action_vector[idx_start+1] *= 100.0
                        action_vector[idx_start+2] *= 100.0
                    
                    else:
                        # Waiting Room
                        action_vector[idx_start] *= 0.1
                        action_vector[idx_start+1] *= 0.1
                        action_vector[idx_start+2] *= 0.1

            # === END OF FIX ===
            # If policy_mode is NOT "ppo" (e.g. Status Quo), 
            # it skips the block above and uses the vector exactly as given.

            # B. CALCULATE SHARES
            total_desire = np.sum(action_vector)
            
            if total_desire <= 0.001: 
                scale_factor = 0
            else:
                scale_factor = self.quarterly_budget / total_desire

            # C. APPLY
            for i, bgy in enumerate(self.barangays):
                idx = i * 3
                raw_iec = action_vector[idx] * scale_factor
                raw_enf = action_vector[idx+1] * scale_factor
                raw_inc = action_vector[idx+2] * scale_factor
                
                bgy.update_policy(raw_iec, raw_enf, raw_inc)
                self.adjust_enforcement_agents(bgy)

        # ... (Keep fallback logic) ...
        elif len(action_vector) >= 3:
            total_desire = sum(action_vector)
            scale_factor = (self.quarterly_budget / total_desire) if total_desire > 0 else 0
            
            if len(action_vector) == len(self.barangays):
                 for i, bgy in enumerate(self.barangays):
                     share = action_vector[i]
                     bgy.update_policy(share * scale_factor, 0, 0)
                     self.adjust_enforcement_agents(bgy)