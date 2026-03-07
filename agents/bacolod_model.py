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
from agents.mayor_agent import MayorAgent # <--- NEW IMPORT

def compute_global_compliance(model):
    agents = [a for a in model.schedule.agents if isinstance(a, HouseholdAgent)]
    if not agents: return 0.0
    return sum(1 for a in agents if a.is_compliant) / len(agents)

class BacolodModel(mesa.Model):
    def __init__(self, seed=None, train_mode=False, policy_mode="HuDRL", behavior_override=None): 
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

        if not self.train_mode and self.policy_mode == "HuDRL" and not self.behavior_override:
            model_path = "models/ppo/bacolod_ppo_final.zip"
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

        # --- FAST MATH DECLARATIONS ---
        self.barangays = []
        self.agent_id_counter = 0 
        self.households_by_bgy = {} # <--- The Dictionary Fix 
        
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
                
                # --- FAST MATH DICTIONARY POPULATION ---
                if b_agent.unique_id not in self.households_by_bgy:
                    self.households_by_bgy[b_agent.unique_id] = []
                self.households_by_bgy[b_agent.unique_id].append(a)
                # ---------------------------------------

                self.agent_id_counter += 1
                a.barangay = b_agent
                a.barangay_id = b_agent.unique_id
                
                self.schedule.add(a)
                self.grid.place_agent(a, (x, y))

        # --- INITIALIZE MAYOR AGENT (DRL Executive) ---
        self.mayor = MayorAgent("MAYOR_0", self, self.quarterly_budget)
        self.schedule.add(self.mayor)

        # Trigger initial Day 0 Deployment
        self.mayor.run_decision_logic() 

        # --- SILENCE DATA COLLECTOR DURING TRAINING ---
        if not self.train_mode:
            reporters = {
                "Global Compliance": compute_global_compliance,
                "Total Fines": lambda m: m.total_fines_collected,
                "Political Capital": lambda m: m.political_capital
            }
            
            for bgy in self.barangays:
                 reporters[bgy.name] = lambda m, b=bgy: b.get_local_compliance()

            self.datacollector = DataCollector(model_reporters=reporters)
            self.datacollector.collect(self)
        else:
            self.datacollector = None

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

    def adjust_enforcement_agents(self, barangay_agent):
        """Syncs the LOCAL BARANGAY TANODS with the local barangay budget."""
        # Note: We filter out Municipal Inspectors so the Barangay only manages its own Tanods
        existing_agents = [a for a in self.schedule.agents 
                        if isinstance(a, EnforcementAgent) 
                        and a.barangay_id == barangay_agent.unique_id
                        and not getattr(a, 'is_municipal', False)]
        
        current_count = len(existing_agents)
        target_count = barangay_agent.n_enforcers # Derived from Barangay's local enf_fund
        
        if current_count < target_count:
            for i in range(target_count - current_count):
                new_id = f"Tanod_{barangay_agent.unique_id}_{self.tick}_{i}"
                pos = (self.random.randrange(self.grid.width), self.random.randrange(self.grid.height))
                agent = EnforcementAgent(new_id, self, barangay_agent.unique_id)
                self.schedule.add(agent)
                self.grid.place_agent(agent, pos)
                
        elif current_count > target_count:
            for i in range(current_count - target_count):
                agent_to_remove = existing_agents[i]
                self.grid.remove_agent(agent_to_remove)
                self.schedule.remove(agent_to_remove)

    def log_quarterly_report(self, quarter):
        if self.behavior_override: return
        
        with open(self.log_filename, mode='a', newline='') as file:
            writer = csv.writer(file)
            for b in self.barangays:
                
                # Fetch dynamically assigned LGU funds (assigned by MayorAgent)
                lgu_iec = getattr(b, 'lgu_iec_fund', 0)
                lgu_enf = getattr(b, 'lgu_enf_fund', 0)
                lgu_inc = getattr(b, 'lgu_incentive_fund', 0)
                lgu_allocation = lgu_iec + lgu_enf + lgu_inc
                
                # Total Combines Local Base + LGU Intervention
                total_iec = b.iec_fund + lgu_iec
                total_enf = b.enf_fund + lgu_enf
                total_inc = b.inc_fund + lgu_inc
                total_funds = total_iec + total_enf + total_inc
                local_base = b.local_quarterly_budget
                
                lgu_share_pct = 0.0
                if self.quarterly_budget > 0:
                    lgu_share_pct = (lgu_allocation / self.quarterly_budget) * 100

                iec_pct = (total_iec / total_funds * 100) if total_funds > 0 else 0
                enf_pct = (total_enf / total_funds * 100) if total_funds > 0 else 0
                inc_pct = (total_inc / total_funds * 100) if total_funds > 0 else 0

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
                    f"{total_iec:.2f}", f"{iec_pct:.1f}%",
                    f"{total_enf:.2f}", f"{enf_pct:.1f}%",
                    f"{total_inc:.2f}", f"{inc_pct:.1f}%",
                    f"{b.iec_intensity:.4f}", f"{b.enforcement_intensity:.4f}", f"{b.incentive_val:.2f}",
                    f"{avg_att:.3f}", f"{avg_sn:.3f}", f"{avg_pbc:.3f}", f"{avg_util:.3f}",
                    f"{b.get_local_compliance():.2%}", active_enforcers, f"{self.political_capital:.4f}"
                ])
        print(f" > Detailed Report for Quarter {quarter} saved to {self.log_filename}")

    def step(self):
        self.tick += 1
        
        # --- 1. QUARTERLY RESET (Every 90 Days) ---
        if self.tick % 90 == 0:
            self.quarter += 1
            # Reset 'redeemed' flags for all household agents
            for a in self.schedule.agents:
                if isinstance(a, HouseholdAgent):
                    a.redeemed_this_quarter = False
            
            # This block was likely empty or mis-indented before
            if not self.train_mode and not self.behavior_override:
                print(f" >> New Quarter: {self.quarter}")

        # --- 2. OPTIMIZED AGENT STEPPING ---
        for b in self.barangays: 
            b.step()
            
        for a in self.schedule.agents:
            if isinstance(a, (HouseholdAgent, EnforcementAgent, MayorAgent)):
                a.step()

        # --- 3. ECONOMICS & POLITICS ---
        self.update_political_capital() 
        self.calculate_costs()

        # --- 4. DATA COLLECTION ---
        # The indentation here is crucial. 
        # During training, we skip collection to increase speed.
        if not self.train_mode:
            self.datacollector.collect(self)
        else:
            pass # Explicitly do nothing if training

        # --- 5. STOP CONDITIONS ---
        if self.tick >= 1080: 
            self.running = False
            
        if self.political_capital < 0.10:
            self.running = False

    def get_state(self):
        compliance_rates = [b.get_local_compliance() for b in self.barangays]
        attitude_rates = []
        for b in self.barangays:
            # --- FASTER DICTIONARY LOOKUP ---
            households = self.households_by_bgy.get(b.unique_id, [])
            avg_att = np.mean([a.attitude for a in households]) if households else 0.0
            attitude_rates.append(avg_att)

        norm_budget = max(0.0, min(1.0, self.current_budget / self.annual_budget))
        norm_time = max(0.0, min(1.0, self.quarter / 40.0))
        p_cap = max(0.0, min(1.0, self.political_capital)) 
        
        state = compliance_rates + attitude_rates + [norm_budget, norm_time, p_cap]
        return np.array(state, dtype=np.float32)