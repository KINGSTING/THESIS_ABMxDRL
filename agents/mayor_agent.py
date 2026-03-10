import mesa
import numpy as np
import random
from agents.enforcement_agent import EnforcementAgent
from agents.household_agent import HouseholdAgent

class MayorAgent(mesa.Agent):
    """
    The Mayor Agent is the DRL-driven Executive.
    It manages the Municipal SWM Fund to perform 'Direct Intervention' 
    on top of the Barangay's base implementation.
    """
    def __init__(self, unique_id, model, quarterly_budget):
        super().__init__(unique_id, model)
        self.municipal_budget = quarterly_budget
        self.iec_active = False
        
        # --- FIX: Add this line so the Barangay can log LGU rewards here ---
        self.total_lgu_incentives_distributed = 0 

    def step(self):
        # The Mayor makes a strategic decision at the start of every Quarter (90 days)
        if self.model.tick % 90 == 0:
            self.run_decision_logic()

    def run_decision_logic(self):
        # 1. AI MODE (HuDRL)
        if self.model.policy_mode == "HuDRL" and self.model.rl_agent is not None:
            state = self.model.get_state()
            raw_action, _ = self.model.rl_agent.predict(state, deterministic=True)
            
            # --- MATCHES THE GYM ENVIRONMENT MATH ---
            amplified = np.exp(raw_action * 2.0)
            
            # --- MATCHES THE GYM HARD RULE ---
            compliance_rates = state[0:7]
            for i in range(7):
                if compliance_rates[i] >= 0.70:
                    amplified[i*3 : i*3+3] *= 0.01
                    
            total_desire = np.sum(amplified)
            
            if total_desire > 0:
                action_vector = amplified / total_desire
            else:
                action_vector = np.ones(21) / 21.0
            
        # 2. MANUAL STRATEGIES (Status Quo, Pure Enf, Pure Inc)
        else:
            action_vector = []
            share = 1.0 # Will distribute equal weights to all 7 barangays
            
            for b in self.model.barangays:
                if self.model.policy_mode == "pure_enforcement":
                    action_vector.extend([0.0, share, 0.0])
                elif self.model.policy_mode == "pure_incentives":
                    action_vector.extend([0.0, 0.0, share])
                else: 
                    # Default: "status_quo" -> All to IEC
                    action_vector.extend([share, 0.0, 0.0])
            
            # Normalize vector
            action_vector = np.array(action_vector)
            total_desire = np.sum(action_vector)
            if total_desire > 0:
                action_vector = action_vector / total_desire

        # 3. Transform the action_vector into Direct Interventions
        self.execute_intervention(action_vector)
        
        # Log the decisions to CSV
        self.model.log_quarterly_report(self.model.quarter)

    def execute_intervention(self, action_vector):
        """
        Directly implements LGU-funded levers across the 7 barangays.
        """
        scale_factor = self.municipal_budget # Total LGU money to spend this quarter
        
        # --- NEW: Initialize tracker for Political Recovery ---
        total_incentives_spent = 0.0 
        
        for i, bgy in enumerate(self.model.barangays):
            idx = i * 3
            # Extract LGU-specific budget for this specific Barangay
            lgu_iec = action_vector[idx] * scale_factor
            lgu_enf = action_vector[idx+1] * scale_factor
            lgu_inc = action_vector[idx+2] * scale_factor
            
            # Save these for the CSV Logger to read
            bgy.lgu_iec_fund = lgu_iec
            bgy.lgu_enf_fund = lgu_enf
            bgy.lgu_inc_fund = lgu_inc

            # --- LEVER 1: PURE ENFORCEMENT (Municipal Inspectors) ---
            self.deploy_municipal_inspectors(bgy, lgu_enf)

            # --- LEVER 2: UNIVERSAL INCENTIVES (LGU Reward Pool) ---
            # Households can redeem this on top of their local barangay goods
            bgy.lgu_incentive_fund = lgu_inc
            total_incentives_spent += lgu_inc  # <--- TRACK IT HERE!

            # --- LEVER 3: UNIFIED IEC (Municipal Awareness) ---
            # Direct boost to household attitude via LGU-led programs
            if lgu_iec > 0:
                self.run_municipal_iec(bgy, lgu_iec)

        # ==========================================================
        # POLITICAL CAPITAL RECOVERY (THE APPROVAL RATING)
        # ==========================================================
        
        # 1. Every 10,000 PHP spent on Incentives buys back 0.01 Political Capital
        ayuda_boost = (total_incentives_spent / 10000.0) * 0.01
        
        # 2. Calculate the "Clean City" Bonus
        households = [a for a in self.model.schedule.agents if hasattr(a, 'is_compliant')]
        compliant_count = sum(1 for h in households if h.is_compliant)
        global_compliance = compliant_count / max(1, len(households))
        
        # If the Mayor gets the city over 70% compliance, the public is happy!
        clean_city_boost = 0.05 if global_compliance >= 0.70 else 0.0
        
        # 3. Apply the healing (Capped at 1.0 or 100% approval)
        self.model.political_capital = min(1.0, self.model.political_capital + ayuda_boost + clean_city_boost)

    def deploy_municipal_inspectors(self, bgy, fund):
        import random # Ensure this is at the top of your file if not already there

        # 400 PHP * 30 Days = 12,000 PHP per enforcer task force contract
        target_inspectors = int(fund // (400 * 30)) 
        
        current_municipal = [a for a in self.model.schedule.agents 
                             if isinstance(a, EnforcementAgent) 
                             and getattr(a, 'is_municipal', False) 
                             and a.barangay_id == bgy.unique_id]

        current_count = len(current_municipal)

        # Add new inspectors if funding allows
        if current_count < target_inspectors:
            inspectors_to_add = target_inspectors - current_count
            for _ in range(inspectors_to_add):
                # IMPROVED UNIQUE ID: Include a random salt to prevent collisions
                new_id = f"LGU_ENF_{bgy.unique_id}_{self.model.tick}_{random.randint(10000, 99999)}"
                
                # --- SAFETY CHECK ---
                if new_id in self.model.schedule._agents:
                    continue # Skip if ID miraculously exists
                
                # Instantiate the enforcer
                inspector = EnforcementAgent(new_id, self.model, bgy.unique_id)
                
                # Configure their specific Task Force attributes
                inspector.is_municipal = True
                inspector.fine_amount = 1000 
                inspector.contract_days = 30  # <--- THE 30-DAY EXPIRATION TIMER
                
                # Position them on the grid
                pos = (self.random.randrange(self.model.grid.width), self.random.randrange(self.model.grid.height))
                
                self.model.schedule.add(inspector)
                self.model.grid.place_agent(inspector, pos)
                
        # Remove excess inspectors if budget was slashed 
        # (Though most will naturally expire after 30 days anyway due to the timer)
        elif current_count > target_inspectors:
            inspectors_to_remove = current_count - target_inspectors
            for inspector in current_municipal[:inspectors_to_remove]:
                self.model.grid.remove_agent(inspector)
                self.model.schedule.remove(inspector)

    def run_municipal_iec(self, bgy, fund):
        # --- LGU MACRO-IEC EQUATION ---
        # Based on MENRO Interview: Uses Radio Broadcasts (101.3 FM) and Large Assemblies
        C_RADIO = 500.0
        C_EVENT = 5000.0
        TARGET_RADIO = 90 # Goal: Daily radio spots
        TARGET_EVENTS = 3 # Goal: Monthly large assemblies

        # 1. Buy Radio Airtime first
        n_radio = min(TARGET_RADIO, int(fund // C_RADIO))
        rem = max(0.0, fund - (n_radio * C_RADIO))
        
        # 2. Fund Large Events with remainder
        n_events = min(TARGET_EVENTS, int(rem // C_EVENT))

        # Calculate LGU-driven intensity (How strong the campaign is this quarter)
        lgu_iec_intensity = min(1.0, (n_radio / TARGET_RADIO) * 0.4 + (n_events / TARGET_EVENTS) * 0.6)

        # Apply direct impact: LGU campaigns boost 'Attitude' and 'Social Norms' 
        households = [a for a in self.model.schedule.agents 
                      if type(a).__name__ == "HouseholdAgent" and getattr(a, 'barangay_id', None) == bgy.unique_id]
        
        if households and lgu_iec_intensity > 0:
            # The maximum boost a full LGU campaign can give in one quarter is +0.05
            impact = lgu_iec_intensity * 0.05 
            for h in households:
                h.attitude = min(0.95, h.attitude + impact)
                h.sn = min(0.95, h.sn + (impact * 0.5))