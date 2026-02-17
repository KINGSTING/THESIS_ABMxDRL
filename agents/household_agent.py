import mesa
import random

class HouseholdAgent(mesa.Agent):
    """
    Household Agent based on Theory of Planned Behavior (TPB).
    Implements a 'Two-Stage Social Shield' based on 2020-2026 SWM Research.
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
        Updates Social Norms (SN) with 'Two-Stage Shielding'.
        - Stage 1 (>40%): The 'Bayanihan' Activation.
        - Stage 2 (>70%): The 'Norm Lock-In' (80.3% effect).
        """
        # 1. CALCULATE RAW TARGET SN
        neighbors = self.model.grid.get_neighbors(self.pos, moore=True, radius=2)
        household_neighbors = [n for n in neighbors if isinstance(n, HouseholdAgent) and n.barangay_id == self.barangay_id]
        
        if household_neighbors:
            compliant_count = sum(1 for n in household_neighbors if n.is_compliant)
            local_compliance = compliant_count / len(household_neighbors)
        else:
            local_compliance = 0.0

        # Authority Boost (Enforcement creates perceived norm)
        authority_boost = 0.0
        if self.barangay:
            authority_boost = self.barangay.enforcement_intensity * 0.50

        # The "Real" SN right now (Perception + Reality)
        target_sn = min(1.0, local_compliance + authority_boost)

        # 2. APPLY SHIELD (Inertia/Stickiness)
        current_compliance = 0.0
        if self.barangay:
            current_compliance = self.barangay.compliance_rate

        # LOGIC: "Damper the Decay"
        if target_sn < self.sn: 
            
            if current_compliance > 0.70:
                # STAGE 2: LOCK-IN (Keep this strong)
                self.sn = (0.95 * self.sn) + (0.05 * target_sn)
                
            elif current_compliance > 0.40:
                # STAGE 1: ACTIVATION 
                # CHANGE THIS: 0.50 is too weak. Raise it to 0.85.
                # This allows the agents to "slide" down to 40% rather than plummet.
                self.sn = (0.85 * self.sn) + (0.15 * target_sn)
                
            else:
                # NO SHIELD: Free Fall (Below 40%)
                self.sn = target_sn
        else:
            # GROWTH MODE: Update instantly
            self.sn = target_sn

    def update_attitude(self):
        """
        Updates Attitude with 'Two-Stage Shielding'.
        """
        # --- 1. THE SOCIAL NORM SHIELD ---
        decay_damper = 1.0
        current_compliance = 0.0
        
        if self.barangay:
            current_compliance = self.barangay.compliance_rate

        # THE LOGIC CHECK:
        if current_compliance > 0.70:
            # STAGE 2: TIPPING POINT (Hard Shield)
            # 95% reduction in decay.
            decay_damper = 0.05 
            
        elif current_compliance > 0.40:
            # STAGE 1: ACTIVATION (Soft Shield)
            # 50% reduction in decay.
            decay_damper = 0.50 
            
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

        # 3. Enforcement Fatigue (CRITICAL FIX)
        # OLD LOGIC: Drained attitude unless compliance was > 85%.
        # RESULT: Agents in the 40%-85% range were getting drained to 0.0.
        
        if self.barangay and self.barangay.enforcement_intensity > 0.8:
             # NEW LOGIC: If we are in the "Safe Zone" (>40%), 
             # residents view the enforcement as "Protective", not "Oppressive".
             if self.barangay.compliance_rate > 0.40:
                  self.attitude += 0.0005 # Small "Peace of Mind" Bonus
             else:
                  # Only get annoyed if the place is chaotic AND strict
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
        self.update_attitude()      # Check Shield (Attitude)
        self.update_social_norms()  # Check Shield (Norms)
        self.make_decision()        # Calculate Utility
        self.attempt_redemption()