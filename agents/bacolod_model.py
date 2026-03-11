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
from agents.mayor_agent import MayorAgent 

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
        
        # =================================================================
        # THREE SEPARATE CSV REPORTS (NOW WITH PERCENTAGES)
        # =================================================================
        results_dir = "results"
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)

        self.csv_local = os.path.join(results_dir, f"{self.policy_mode}_1_LOCAL_BASE.csv")
        self.csv_mayor = os.path.join(results_dir, f"{self.policy_mode}_2_MAYOR_INTERVENTION.csv")
        self.csv_global = os.path.join(results_dir, f"{self.policy_mode}_3_GLOBAL_SUMMARY.csv")
        
        if not self.behavior_override:
            # 1. LOCAL BARANGAY CSV
            with open(self.csv_local, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([
                    "Quarter", "Barangay", "Local_Base_Budget_PHP", 
                    "Local_IEC_PHP", "Local_IEC_%", 
                    "Local_Enf_PHP", "Local_Enf_%", 
                    "Local_Inc_PHP", "Local_Inc_%", 
                    "Local_Tanods_Active", "Local_Compliance"
                ])
            # 2. MAYOR LGU CSV 
            with open(self.csv_mayor, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([
                    "Quarter", "Barangay", "Mayor_Total_Given_PHP", "Share_of_LGU_Budget_%",
                    "Mayor_IEC_PHP", "Mayor_IEC_%", 
                    "Mayor_Enf_PHP", "Mayor_Enf_%", 
                    "Mayor_Inc_PHP", "Mayor_Inc_%", 
                    "Municipal_Inspectors_Deployed"
                ])
            # 3. GLOBAL CSV 
            with open(self.csv_global, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([
                    "Quarter", "Global_Compliance", "Political_Capital", 
                    "Total_Fines_Collected", "Avg_City_Attitude"
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
        
        # --- FIXED POLITICAL CAPITAL MATH ---
        self.political_capital = 1.0     
        self.alpha_sensitivity = 0.0030 # High enough to cause collapse if strictly abused
        self.beta_recovery = 0.0002      # Slow recovery if they ease up

        self.barangays = []
        self.agent_id_counter = 0
        self.households_by_bgy = {}
        
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
                
                if b_agent.unique_id not in self.households_by_bgy:
                    self.households_by_bgy[b_agent.unique_id] = []
                self.households_by_bgy[b_agent.unique_id].append(a)
                
                self.schedule.add(a)
                self.grid.place_agent(a, (x, y))

        self.mayor = MayorAgent("MAYOR_0", self, self.quarterly_budget)
        self.schedule.add(self.mayor)
        self.mayor.run_decision_logic() 

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
        # 1. Calculate the raw enforcement pressure
        avg_enforcement = 0
        if self.barangays:
            avg_enforcement = sum(b.enforcement_intensity for b in self.barangays) / len(self.barangays)
            
        # 2. Calculate the Citizens' Average Attitude (The "Incentive Shield")
        all_households = [a for a in self.schedule.agents if isinstance(a, HouseholdAgent)]
        if all_households:
            avg_attitude = np.mean([a.attitude for a in all_households])
        else:
            avg_attitude = 0.5 
            
        # 3. The Holland (2017) Buffer: 
        # Attitude ranges from 0.0 to 1.0. 
        # If attitude is 0.8 (Very Happy), modifier becomes 0.4 (Decay is cut by 60%)
        # If attitude is 0.2 (Very Angry), modifier becomes 1.6 (Decay is 60% faster)
        attitude_modifier = 2.0 * (1.0 - avg_attitude)
        
        # 4. Apply the modifier to the decay
        effective_decay = (self.alpha_sensitivity * avg_enforcement) * attitude_modifier
        recovery = self.beta_recovery * (1.0 - avg_enforcement)
        
        self.political_capital = max(0.0, min(1.0, self.political_capital - effective_decay + recovery))

    def calculate_costs(self):
        total_iec_alloc = sum(b.iec_fund for b in self.barangays)
        total_enf_alloc = sum(b.enf_fund for b in self.barangays)
        daily_fixed_cost = (total_iec_alloc + total_enf_alloc) / 90.0
        self.total_enforcement_cost += (total_enf_alloc / 90.0)
        self.total_iec_cost += (total_iec_alloc / 90.0)
        self.current_budget = self.current_budget - daily_fixed_cost + self.recent_fines_collected
        self.recent_fines_collected = 0

    def adjust_enforcement_agents(self, barangay_agent):
        existing_agents = [a for a in self.schedule.agents 
                        if isinstance(a, EnforcementAgent) 
                        and a.barangay_id == barangay_agent.unique_id
                        and not getattr(a, 'is_municipal', False)]
        
        current_count = len(existing_agents)
        target_count = barangay_agent.n_enforcers 
        
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
        
        all_attitudes = []

        with open(self.csv_local, mode='a', newline='') as file_local, \
             open(self.csv_mayor, mode='a', newline='') as file_mayor:
            
            writer_local = csv.writer(file_local)
            writer_mayor = csv.writer(file_mayor)

            for b in self.barangays:
                # --- 1. LOCAL DATA (WITH PERCENTAGES) ---
                local_total = b.local_quarterly_budget
                l_iec_pct = (b.iec_fund / local_total * 100) if local_total > 0 else 0
                l_enf_pct = (b.enf_fund / local_total * 100) if local_total > 0 else 0
                l_inc_pct = (b.inc_fund / local_total * 100) if local_total > 0 else 0
                
                local_tanods = len([a for a in self.schedule.agents 
                                    if isinstance(a, EnforcementAgent) 
                                    and a.barangay_id == b.unique_id 
                                    and not a.is_municipal])
                
                writer_local.writerow([
                    quarter, b.name, f"{local_total:.2f}",
                    f"{b.iec_fund:.2f}", f"{l_iec_pct:.1f}%", 
                    f"{b.enf_fund:.2f}", f"{l_enf_pct:.1f}%", 
                    f"{b.inc_fund:.2f}", f"{l_inc_pct:.1f}%",
                    local_tanods, f"{b.get_local_compliance():.2%}"
                ])

                # --- 2. MAYOR DATA (WITH PERCENTAGES) ---
                lgu_iec = getattr(b, 'lgu_iec_fund', 0)
                lgu_enf = getattr(b, 'lgu_enf_fund', 0)
                lgu_inc = getattr(b, 'lgu_incentive_fund', 0)
                lgu_total = lgu_iec + lgu_enf + lgu_inc
                
                m_iec_pct = (lgu_iec / lgu_total * 100) if lgu_total > 0 else 0
                m_enf_pct = (lgu_enf / lgu_total * 100) if lgu_total > 0 else 0
                m_inc_pct = (lgu_inc / lgu_total * 100) if lgu_total > 0 else 0
                
                # How much of the TOTAL municipal budget did this barangay get?
                m_share_overall = (lgu_total / self.quarterly_budget * 100) if self.quarterly_budget > 0 else 0
                
                lgu_inspectors = len([a for a in self.schedule.agents 
                                      if isinstance(a, EnforcementAgent) 
                                      and a.barangay_id == b.unique_id 
                                      and a.is_municipal])

                writer_mayor.writerow([
                    quarter, b.name, f"{lgu_total:.2f}", f"{m_share_overall:.1f}%",
                    f"{lgu_iec:.2f}", f"{m_iec_pct:.1f}%", 
                    f"{lgu_enf:.2f}", f"{m_enf_pct:.1f}%", 
                    f"{lgu_inc:.2f}", f"{m_inc_pct:.1f}%",
                    lgu_inspectors
                ])

                households = self.households_by_bgy.get(b.unique_id, [])
                if households:
                    all_attitudes.extend([a.attitude for a in households])

        # --- 3. GLOBAL DATA ---
        with open(self.csv_global, mode='a', newline='') as file_global:
            writer_global = csv.writer(file_global)
            global_comp = compute_global_compliance(self)
            avg_att = np.mean(all_attitudes) if all_attitudes else 0.0
            
            writer_global.writerow([
                quarter, f"{global_comp:.2%}", f"{self.political_capital:.4f}", 
                self.total_fines_collected, f"{avg_att:.3f}"
            ])

        if not self.train_mode:
            print(f" > Split Reports (Local, Mayor, Global) saved for Quarter {quarter}")

    def step(self):
        self.tick += 1
        
        if self.tick % 90 == 0:
            self.quarter += 1
            for a in self.schedule.agents:
                if isinstance(a, HouseholdAgent):
                    a.redeemed_this_quarter = False
            
            if not self.train_mode and not self.behavior_override:
                print(f" >> New Quarter: {self.quarter}")

        for b in self.barangays: 
            b.step()
            
        for a in self.schedule.agents:
            if isinstance(a, (HouseholdAgent, EnforcementAgent, MayorAgent)):
                a.step()

        self.update_political_capital() 
        self.calculate_costs()

        if not self.train_mode:
            self.datacollector.collect(self)

        max_ticks = 3600 if self.train_mode else 1080
        
        if self.tick >= max_ticks: 
            self.running = False
            
       # REMOVE OR COMMENT OUT THIS HALT CONDITION
        # if self.political_capital < 0.10:
        #     print("SIMULATION HALTED (Political Collapse).")
        #     self.running = False

    def get_state(self):
        compliance_rates = [b.get_local_compliance() for b in self.barangays]
        attitude_rates = []
        
        for b in self.barangays:
            households = self.households_by_bgy.get(b.unique_id, [])
            avg_att = np.mean([a.attitude for a in households]) if households else 0.0
            attitude_rates.append(avg_att)

        norm_budget = max(0.0, min(1.0, self.current_budget / self.annual_budget))
        norm_time = max(0.0, min(1.0, self.quarter / 40.0))
        p_cap = max(0.0, min(1.0, self.political_capital)) 
        
        state = compliance_rates + attitude_rates + [norm_budget, norm_time, p_cap]
        return np.array(state, dtype=np.float32)