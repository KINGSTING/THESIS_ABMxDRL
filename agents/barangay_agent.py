import mesa
import random
import math

class BarangayAgent(mesa.Agent):
    def __init__(self, unique_id, model, local_budget=0):
        super().__init__(unique_id, model)
        
        # --- 1. Identity & Demographics ---
        self.name = ""
        self.n_households = 1  
        
        # --- 2. State Metrics ---
        self.compliance_rate = 0.0
        self.total_households = 0
        self.compliant_count = 0
        
        # --- 3. Policy Variables (TOTALS) ---
        self.iec_fund = 0.0
        self.enf_fund = 0.0
        self.inc_fund = 0.0
        self.fine_amount = 500
        
        # --- 4. Intensities ---
        self.enforcement_intensity = 0.5
        self.iec_intensity = 0.0
        self.incentive_val = 500.0  # FIXED: Now represents the prize amount per winner

        # --- 5. Financials ---
        self.local_annual_budget = local_budget
        self.local_quarterly_budget = local_budget / 4.0 
        self.local_allocation_ratios = {"enf": 0.50, "inc": 0.30, "iec": 0.20}
        self.current_cash_on_hand = 0.0

    def update_policy(self, lgu_iec_fund, lgu_enf_fund, lgu_inc_fund):
        """Combines Local Base Budget with LGU Top-ups and implements Thesis Eq 3.1 & 3.3"""
        
        # --- A. Calculate Local Base Allocations ---
        local_enf = self.local_quarterly_budget * self.local_allocation_ratios["enf"]
        local_inc = self.local_quarterly_budget * self.local_allocation_ratios["inc"]
        local_iec = self.local_quarterly_budget * self.local_allocation_ratios["iec"]

        # --- B. Stack LGU Funds (Total Budget per category) ---
        self.iec_fund = local_iec + lgu_iec_fund
        self.enf_fund = local_enf + lgu_enf_fund
        self.inc_fund = local_inc + lgu_inc_fund

        # --- C. FULL IMPLEMENTATION: Cost of Enforcement (Eq. 3.1) ---
        # The budget determines the number of enforcers the Bgy can afford for the quarter
        # Cost_Per_Enforcer = W_Daily * 66
        cost_per_enforcer_quarterly =  400 * 66
        
        # N_Enforcers = Budget / (W_Daily * 66)
        self.n_enforcers = int(self.enf_fund // cost_per_enforcer_quarterly)
        
        # C_Enf = N_Enforcers * W_Daily * 66 (The actual realized expenditure)
        self.actual_enforcement_cost = self.n_enforcers * cost_per_enforcer_quarterly

        # --- D. FULL IMPLEMENTATION: Cost of IEC (Eq. 3.3) ---
        R_RADIO = 500.0
        C_MOBILIZATION = 5000.0
        TARGET_SPOTS = 90
        TARGET_EVENTS = 3
        
        # n_spots = amount allocated for radio / R_Radio
        self.n_spots = min(TARGET_SPOTS, int(self.iec_fund // R_RADIO))
        rem = max(0.0, self.iec_fund - (self.n_spots * R_RADIO))
        
        # n_events = remaining amount / C_Mobilization
        self.n_events = min(TARGET_EVENTS, int(rem // C_MOBILIZATION))
        
        # C_IEC = (N_Spots * R_Radio) + (N_Events * C_Mobilization)
        self.actual_iec_cost = (self.n_spots * R_RADIO) + (self.n_events * C_MOBILIZATION)
        
        # Calculate Intensity for the ABM mechanics
        self.iec_intensity = min(1.0, (self.n_spots/TARGET_SPOTS)*0.5 + (self.n_events/TARGET_EVENTS)*0.5)

        # --- E. Operational Cash for Incentives (Eq. 3.2) ---
        self.current_cash_on_hand = self.inc_fund
        
        self.iec_intensity = min(1.0, (self.n_spots/TARGET_SPOTS)*0.5 + (self.n_events/TARGET_EVENTS)*0.5)

    def distribute_local_incentives(self):
        """Logic for the 'Selected Few' Draw at end of Quarter."""
        # 1. Calculate capacity: Budget / 500
        max_winners = int(self.current_cash_on_hand // 500)
        
        # 2. Find eligible households (Compliant in THIS barangay)
        eligible_households = [
            a for a in self.model.schedule.agents 
            if getattr(a, 'barangay_id', None) == self.unique_id 
            and hasattr(a, 'is_compliant') and a.is_compliant
        ]
        
        if not eligible_households:
            return

        # 3. Random Selection
        num_to_pay = min(len(eligible_households), max_winners)
        winners = random.sample(eligible_households, num_to_pay)
        
        # 4. Reward Winners
        for household in winners:
            household.receive_incentive(500)
            self.current_cash_on_hand -= 500
            
        # 5. Penalize Losers (Disappointment Effect)
        losers = [h for h in eligible_households if h not in winners]
        for household in losers:
            household.attitude -= 0.15 
            household.perceived_unfairness = True

    def get_local_compliance(self):
        self.total_households = 0
        self.compliant_count = 0
        for a in self.model.schedule.agents:
            if getattr(a, 'barangay_id', None) == self.unique_id and hasattr(a, 'is_compliant'):
                self.total_households += 1
                if a.is_compliant: self.compliant_count += 1
        
        self.compliance_rate = self.compliant_count / self.total_households if self.total_households > 0 else 0
        return self.compliance_rate

    def step(self):
        self.get_local_compliance()
        # Trigger the draw only on the last day of the quarter
        if self.model.tick > 0 and self.model.tick % 90 == 0:
            self.distribute_local_incentives()

    def give_reward(self, amount):
        """
        Bridge function to satisfy the HouseholdAgent's request for a reward.
        """
        # Check if the Barangay has money left in its current cash pool
        if self.current_cash_on_hand >= amount:
            self.current_cash_on_hand -= amount
            return True
        return False