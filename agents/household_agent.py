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

        # --- SEEDING ---
        if self.is_compliant:
            self.attitude = random.uniform(0.75, 0.90) 
            self.sn = random.uniform(0.6, 0.9)
            self.pbc = random.uniform(0.6, 0.9)
        else:
            self.attitude = random.uniform(0.1, 0.4)
            self.sn = random.uniform(0.1, 0.4)
            self.pbc = random.uniform(0.1, 0.4)

        self.utility = 0.0
        self.redeemed_this_quarter = False

    def update_social_norms(self):
        """
        Updates Social Norms (SN).
        FIX: ENFORCEMENT increases SN. 
        High Enforcement -> Higher Perception of Norms.
        """
        # 1. PEER INFLUENCE (The Drift)
        neighbors = self.model.grid.get_neighbors(self.pos, moore=True, radius=2)
        household_neighbors = [n for n in neighbors if isinstance(n, HouseholdAgent) and n.barangay_id == self.barangay_id]
        
        if household_neighbors:
            compliant_count = sum(1 for n in household_neighbors if n.is_compliant)
            local_compliance = compliant_count / len(household_neighbors)
        else:
            local_compliance = 0.0

        # 2. AUTHORITY INFLUENCE (The Boost)
        # LOGIC: "Budget for Enforcement increases Social Norms"
        # If Enforcement is maxed (1.0), we add a strong pressure (+0.50).
        # This ensures that even if local compliance is 0%, high enforcement 
        # pushes SN to 0.50, giving a fighting chance to flip the agent.
        authority_boost = 0.0
        if self.barangay:
            authority_boost = self.barangay.enforcement_intensity * 0.50

        # Combine: Neighbors + Authority
        # We cap at 1.0.
        self.sn = min(1.0, local_compliance + authority_boost)

    def update_attitude(self):
        """
        Updates Attitude with Decay and Synergy.
        FIX: The 'Social Norm Shield' now activates based on COMPLIANCE TIPPING POINT.
        """
        # --- 1. THE SOCIAL NORM SHIELD ---
        # "If compliance reaches the tipping point, the shield activates."
        
        decay_damper = 1.0
        current_compliance = 0.0
        
        # Get the OFFICIAL compliance rate from the Barangay Agent
        if self.barangay:
            current_compliance = self.barangay.compliance_rate

        # THE LOGIC CHECK:
        if current_compliance > 0.70:
            # TIPPING POINT REACHED: The crowd sustains itself.
            decay_damper = 0.1 # 90% reduction in decay
        elif current_compliance > 0.50:
            # Momentum Building
            decay_damper = 0.5 
            
        # Apply the damped decay
        self.attitude -= (self.attitude_decay_rate * decay_damper)
        
        # --- 2. IEC SYNERGY (Standard) ---
        if self.barangay and hasattr(self.barangay, 'iec_intensity'):
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
        
        incentive = self.barangay.incentive_val if self.barangay else 0.0
        
        # Cost includes fine avoidance value
        monetary_impact = incentive + (fine * prob_detection)
        c_net = self.c_effort_base - (gamma * monetary_impact / 2000.0) 

        # 2. TPB Calculation
        epsilon = self.random.gauss(0, 0.05)
        self.utility = (self.w_a * self.attitude) + \
                       (self.w_sn * self.sn) + \
                       (self.w_pbc * self.pbc) - \
                       c_net + epsilon

        # 3. Decision
        self.is_compliant = (self.utility > 0.0)

    def get_fined(self):
        self.utility -= 0.5 
        self.attitude -= 0.10
        
        fine_amount = 500
        if hasattr(self.model, 'total_fines_collected'):
            self.model.total_fines_collected += fine_amount 
            self.model.recent_fines_collected += fine_amount

    def attempt_redemption(self):
        if self.is_compliant and not self.redeemed_this_quarter and self.barangay:
            if self.random.random() < 0.10: 
                reward_amount = self.barangay.incentive_val
                success = self.barangay.give_reward(reward_amount)
                if success:
                    self.redeemed_this_quarter = True
                    self.attitude += 0.02

    def step(self):
        self.update_attitude()      # Check Shield (Compliance > 0.70?)
        self.update_social_norms()  # Check Enforcement (Boost SN)
        self.make_decision()        # Calculate Utility
        self.attempt_redemption()