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
        
        # --- FIX 1: SLOW DOWN SOCIAL PRESSURE ---
        # Old: 0.95 / 0.05 (Fast adaptation)
        # New: 0.99 / 0.01 (Slow, sticky habits)
        # This prevents the entire neighborhood from flipping overnight.
        self.sn = (self.sn * 0.99) + (local_compliance_rate * 0.01)

    def update_attitude(self):
        # 1. Natural Decay
        self.attitude -= (self.attitude_decay_rate * 0.1) # Slow decay
        
        # 2. CALIBRATED GROWTH FIX (SNAIL MODE)
        if self.barangay and hasattr(self.barangay, 'iec_intensity'):
            intensity = self.barangay.iec_intensity
            if intensity > 1.0: intensity /= 100.0
            
            # --- THE CRITICAL CHANGE ---
            # Old: 0.025 (Massive)
            # Previous Attempt: 0.002 (Still too fast)
            # NEW: 0.0003 (Tiny nudge). 
            # This means it takes ~1000 ticks of full IEC to gain 0.30 attitude.
            boost = intensity * 0.0003 
            self.attitude += boost

        # 3. Enforcement Fatigue
        if self.barangay and self.barangay.enforcement_intensity > 0.8:
             self.attitude -= 0.002 # Reduced fatigue to match slower growth
             
        self.attitude = max(0.0, min(1.0, self.attitude))
        
    def make_decision(self):
        # 1. Net Cost
        gamma = 1.5 if self.income_level == 1 else (1.0 if self.income_level == 2 else 0.8)
        fine = self.barangay.fine_amount if self.barangay else 0
        prob_detection = self.barangay.enforcement_intensity if self.barangay else 0
        incentive = self.barangay.incentive_val if (self.barangay and not self.redeemed_this_quarter) else 0.0
        
        monetary_impact = incentive - (fine * prob_detection)
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
        self.utility -= 0.5 
        self.attitude -= 0.10
        if hasattr(self.model, 'total_fines_collected'):
            self.model.total_fines_collected += 500 
            self.model.recent_fines_collected += 500

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