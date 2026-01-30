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
    def __init__(self, seed=None, train_mode=False, policy_mode="status_quo", behavior_override=None): 
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
                    "Total_Allocation_PHP", "IEC_Percent", "Enforcement_Percent", 
                    "Incentives_Percent", "Compliance_Rate", "Active_Enforcers"
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
        
        # --- INITIALIZE BARANGAYS WITH SPECIFIC PROFILES ---
        for i, b_conf in enumerate(config.BARANGAY_LIST):
            b_agent = BarangayAgent(f"BGY_{i}", self, local_budget=b_conf["local_budget"])
            b_agent.name = b_conf["name"]
            b_agent.n_households = b_conf["N_HOUSEHOLDS"]
            
            # === CRITICAL FIX: LOAD ALLOCATION PROFILE ===
            # This ensures Liangan East uses the "Trader" profile (High Incentive)
            # and Poblacion uses "Police State" (High Enforcement)
            if "allocation_profile" in b_conf:
                profile_key = b_conf["allocation_profile"]
                if hasattr(config, 'ALLOCATION_PROFILES'):
                     b_agent.local_allocation_ratios = config.ALLOCATION_PROFILES.get(profile_key, config.ALLOCATION_PROFILES["Ezperanza"])
                     # Note: using 'Ezperanza' as fallback since it's the "Middle Class/Standard" one
            # =============================================

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

        # --- FORCE STATUS QUO INJECTION AT START ---
        total_hh = sum(b.n_households for b in self.barangays)
        
        for bgy in self.barangays:
            share_pop = (bgy.n_households / total_hh)
            lgu_money = self.quarterly_budget * share_pop
            
            # IF STATUS QUO -> LGU gives 100% IEC funding
            # The BarangayAgent will MIX this with their local "Allocation Profile"
            if self.policy_mode == "status_quo":
                bgy.update_policy(lgu_money, 0.0, 0.0)
            else:
                # Default safety (33/33/33)
                bgy.update_policy(lgu_money/3, lgu_money/3, lgu_money/3)
            
            self.adjust_enforcement_agents(bgy)
        # -----------------------------------------------------------

        reporters = {
            "Global Compliance": compute_global_compliance,
            "Total Fines": lambda m: m.total_fines_collected,
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
        # Calculate how many enforcers the CURRENT budget (Local + LGU) can afford
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
                self.grid.place_agent(a, (0, 0))
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
                total = b.iec_fund + b.enf_fund + b.inc_fund
                iec_pct = (b.iec_fund / total * 100) if total > 0 else 0
                enf_pct = (b.enf_fund / total * 100) if total > 0 else 0
                inc_pct = (b.inc_fund / total * 100) if total > 0 else 0
                active_enforcers = len([a for a in self.schedule.agents if isinstance(a, EnforcementAgent) and a.barangay_id == b.unique_id])
                
                writer.writerow([
                    quarter, self.schedule.steps, b.unique_id, b.name,
                    f"{total:.2f}", f"{iec_pct:.2f}%", f"{enf_pct:.2f}%", f"{inc_pct:.2f}%",
                    f"{b.get_local_compliance():.2%}", active_enforcers
                ])
        print(f" > Report for Quarter {quarter} saved to {self.log_filename}")

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
            current_quarter = (self.schedule.steps // 90) + 1
            
            # --- PART A: DECISION MAKING (The Overwrite Protection) ---
            # We ONLY run this internal logic if the AI (Gym) is NOT in charge.
            if not self.train_mode:
                if not self.behavior_override: 
                    print(f"\n--- Quarter {current_quarter} Decision Point ({self.policy_mode.upper()}) ---")
                
                current_state = self.get_state()
                action = []

                if self.policy_mode == "ppo" and self.rl_agent is not None:
                    action, _ = self.rl_agent.predict(current_state, deterministic=True)
                else:
                    # Status Quo / Manual Logic
                    base_share = 0 
                    pop_share = 1 
                    total_hh = sum(b.n_households for b in self.barangays)

                    for b in self.barangays:
                        share_base = (1.0 / len(self.barangays)) * base_share
                        share_pop = (b.n_households / total_hh) * pop_share
                        total_weight = share_base + share_pop
                        # Default Status Quo Distribution
                        action.extend([total_weight, 0.0, 0.0]) 
                
                # Only apply action here if we are NOT in training mode
                self.apply_action(action)

            # --- PART B: REPORTING (Always Run This) ---
            # We un-indented this so it runs even during training!
            self.log_quarterly_report(current_quarter)

        for b in self.barangays: b.step()
        self.schedule.step()
        self.update_political_capital() 
        self.calculate_costs()
        self.datacollector.collect(self)
        
        if self.schedule.steps >= 1080: self.running = False

    def get_state(self):
        compliance_rates = [b.get_local_compliance() for b in self.barangays]
        norm_budget = max(0.0, min(1.0, self.current_budget / self.annual_budget))
        norm_time = max(0.0, min(1.0, self.quarter / 40.0))
        p_cap = max(0.0, min(1.0, self.political_capital)) 
        state = compliance_rates + [norm_budget, norm_time, p_cap]
        return np.array(state, dtype=np.float32)
    
    def apply_action(self, action_vector):
        if len(action_vector) == 3:
            global_iec_desire = action_vector[0]
            global_enf_desire = action_vector[1]
            global_inc_desire = action_vector[2]
            
            total_desire = sum(action_vector)
            scale_factor = (self.quarterly_budget / total_desire) if total_desire > 0 else 0

            total_iec_alloc = global_iec_desire * scale_factor
            total_enf_alloc = global_enf_desire * scale_factor
            total_inc_alloc = global_inc_desire * scale_factor
            
            needy_barangays = [b for b in self.barangays if b.get_local_compliance() < 0.80]
            if not needy_barangays: needy_barangays = self.barangays 

            total_needy_households = sum(b.n_households for b in needy_barangays)

            for bgy in self.barangays:
                if bgy in needy_barangays:
                    share = (bgy.n_households / total_needy_households) if total_needy_households > 0 else (1.0 / len(needy_barangays))
                    bgy.update_policy(total_iec_alloc * share, total_enf_alloc * share, total_inc_alloc * share)
                else:
                    bgy.update_policy(0,0,0)
                self.adjust_enforcement_agents(bgy)

        elif len(action_vector) == 21:
            total_desire = sum(action_vector)
            scale_factor = (self.quarterly_budget / total_desire) if total_desire > 0 else 0

            for i, bgy in enumerate(self.barangays):
                idx = i * 3
                bgy.update_policy(action_vector[idx]*scale_factor, action_vector[idx+1]*scale_factor, action_vector[idx+2]*scale_factor)
                self.adjust_enforcement_agents(bgy)
        else:
            print(f"ERROR: Action vector has length {len(action_vector)}, expected 3 or 21.")