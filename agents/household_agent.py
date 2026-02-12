import mesa
import random

class HouseholdAgent(mesa.Agent):
    """
    Household Agent based on Theory of Planned Behavior (TPB).
    """
    def __init__(self, unique_id, model, income_level, initial_compliance, behavior_params=None):
        super().__init__(unique_id, model)
        self.income_level = income_level
        self.is_compliant = initial_compliance
        self.barangay = None    
        self.barangay_id = None 

        if behavior_params is None:
            behavior_params = {"w_a": 0.4, "w_sn": 0.3, "w_pbc": 0.3, "c_effort": 0.2, "decay": 0.005}

        self.w_a = behavior_params["w_a"]
        self.w_sn = behavior_params["w_sn"]
        self.w_pbc = behavior_params["w_pbc"]
        self.c_effort_base = behavior_params["c_effort"]
        self.attitude_decay_rate = behavior_params["decay"]

        # --- SEEDING: Controlled Start ---
        if self.is_compliant:
            self.attitude = random.uniform(0.75, 0.90) # Cap at 0.90 so there's room to fall
            self.sn = random.uniform(0.6, 0.9)
            self.pbc = random.uniform(0.6, 0.9)
        else:
            self.attitude = random.uniform(0.1, 0.4)
            self.sn = random.uniform(0.1, 0.4)
            self.pbc = random.uniform(0.1, 0.4)

        self.utility = 0.0
        self.redeemed_this_quarter = False

    def update_social_norms(self):
        neighbors = self.model.grid.get_neighbors(self.pos, moore=True, radius=2)
        household_neighbors = [
            n for n in neighbors 
            if isinstance(n, HouseholdAgent) and n.barangay_id == self.barangay_id
        ]
        
        if not household_neighbors: return 
            
        compliant_count = sum(1 for n in household_neighbors if n.is_compliant)
        local_compliance_rate = compliant_count / len(household_neighbors)
        
        # --- NEW LOGIC: AUTHORITY SIGNAL ---
        # "If the government is strict, I assume the Social Norm is to comply."
        authority_signal = 0.0
        if self.barangay:
            # If enforcement is high (e.g., 0.8), add a 0.10 boost to norms
            authority_signal = self.barangay.enforcement_intensity * 0.10

        # Combine Neighbor observation + Authority Signal
        target_sn = local_compliance_rate + authority_signal
        
        # Cap at 1.0
        target_sn = min(1.0, target_sn)

        # Apply sticky update
        self.sn = (self.sn * 0.99) + (target_sn * 0.01)

    def update_attitude(self):
        # --- 1. THE SOCIAL NORM SHIELD (New Logic) ---
        # "If everyone around me is doing it, I don't lose interest."
        # This prevents the "Rot" that destroys compliant barangays during Maintenance Mode.
        
        decay_damper = 1.0
        
        # If Social Norm is strong (> 70%), decay is blocked by 90%.
        if self.sn > 0.70:
            decay_damper = 0.1 
        # If Social Norm is moderate (> 50%), decay is slowed by 50%.
        elif self.sn > 0.50:
            decay_damper = 0.5
            
        # Apply the damped decay
        self.attitude -= (self.attitude_decay_rate * 0.1 * decay_damper)
        
        # 2. REALISTIC SYNERGY (Keep your existing logic below)
        if self.barangay and hasattr(self.barangay, 'iec_intensity'):
            # ... (Rest of your existing synergy code) ...
            iec_intensity = self.barangay.iec_intensity
            if iec_intensity > 1.0: iec_intensity /= 100.0
            
            base_factor = 0.025 
            enf_intensity = self.barangay.enforcement_intensity
            synergy_multiplier = 1.0 + (enf_intensity * 3.0) 

            boost = iec_intensity * base_factor * synergy_multiplier
            self.attitude += boost

        # 3. Enforcement Fatigue
        if self.barangay and self.barangay.enforcement_intensity > 0.8:
             self.attitude -= 0.002 
             
        self.attitude = max(0.0, min(1.0, self.attitude))
        
    def make_decision(self):
        # 1. Net Cost
        gamma = 1.5 if self.income_level == 1 else (1.0 if self.income_level == 2 else 0.8)
        fine = self.barangay.fine_amount if self.barangay else 0
        prob_detection = self.barangay.enforcement_intensity if self.barangay else 0
        # FIX: Remove "and not self.redeemed_this_quarter"
        # The incentive value must persist in their mind for the whole quarter to sustain behavior.
        incentive = self.barangay.incentive_val if self.barangay else 0.0
        
        # FIX: Add the fine avoidance to the impact
        monetary_impact = incentive + (fine * prob_detection)
        c_net = self.c_effort_base - (gamma * monetary_impact / 2000.0) 

        # 2. TPB Calculation
        epsilon = self.random.gauss(0, 0.05)
        self.utility = (self.w_a * self.attitude) + \
                       (self.w_sn * self.sn) + \
                       (self.w_pbc * self.pbc) - \
                       c_net + epsilon

        # 3. Threshold > 0.0
        self.is_compliant = (self.utility > 0.0)

    def get_fined(self):
        # 1. Apply Pain (The Deterrent)
        self.utility -= 0.5 
        
        # 2. Impact Attitude 
        # Getting caught creates resentment towards the system
        self.attitude -= 0.10
        
        # 3. STATISTICAL LOGGING ONLY
        # We track the amount for your Thesis Graphs, but we DO NOT 
        # add it to the playable budget (due to legislative restrictions).
        fine_amount = 500
        
        if hasattr(self.model, 'total_fines_collected'):
            self.model.total_fines_collected += fine_amount 
            self.model.recent_fines_collected += fine_amount

        # Note: We deliberately REMOVED the lines that transfer money 
        # to self.barangay.current_cash_on_hand or self.model.current_budget.
        # The budget is fixed. Fines are just a penalty mechanism.

    def attempt_redemption(self):
        if self.is_compliant and not self.redeemed_this_quarter and self.barangay:
            if self.random.random() < 0.10: 
                reward_amount = self.barangay.incentive_val
                success = self.barangay.give_reward(reward_amount)
                if success:
                    self.redeemed_this_quarter = True
                    self.attitude += 0.02

    def step(self):
        self.update_attitude()
        self.update_social_norms()
        self.make_decision()
        self.attempt_redemption()