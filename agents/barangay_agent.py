import mesa
import random
import math
from agents.household_agent import HouseholdAgent

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
        
        # --- 3. Policy Variables (LOCAL TOTALS) ---
        self.iec_fund = 0.0
        self.enf_fund = 0.0
        self.inc_fund = 0.0
        self.fine_amount = 500
        
        # LGU Intervention Buckets (Managed by MayorAgent)
        self.lgu_iec_fund = 0.0
        self.lgu_enf_fund = 0.0
        self.lgu_incentive_fund = 0.0
        
        # --- 4. Intensities & Outcomes ---
        self.enforcement_intensity = 0.5
        self.iec_intensity = 0.0
        self.incentive_val = 500.0  # Prize amount per winner
        self.n_enforcers = 0

        # --- 5. Financials ---
        self.local_annual_budget = local_budget
        self.local_quarterly_budget = local_budget / 4.0 
        self.local_allocation_ratios = {"enf": 0.50, "inc": 0.30, "iec": 0.20}
        self.current_cash_on_hand = 0.0

        # Initialize local policy immediately on Day 0
        self.setup_local_policy()

    def setup_local_policy(self):
        """Sets up the LOCAL implementation based purely on the Barangay's own IRA/Budget."""
        # --- A. Calculate Local Base Allocations ---
        self.enf_fund = self.local_quarterly_budget * self.local_allocation_ratios["enf"]
        self.inc_fund = self.local_quarterly_budget * self.local_allocation_ratios["inc"]
        self.iec_fund = self.local_quarterly_budget * self.local_allocation_ratios["iec"]

        # --- B. FULL IMPLEMENTATION: Cost of Enforcement (Eq. 3.1) ---
        cost_per_enforcer_quarterly = 400 * 66
        self.n_enforcers = int(self.enf_fund // cost_per_enforcer_quarterly)
        self.actual_enforcement_cost = self.n_enforcers * cost_per_enforcer_quarterly

        # Let the model know it needs to sync local Tanods
        self.model.adjust_enforcement_agents(self)

        # --- C. FULL IMPLEMENTATION: Cost of Barangay IEC (Micro-Level) ---
        # Based on interviews: Barangays rely on Recorida and Purok Meetings
        C_RECORIDA = 200.0  # Gas for barangay vehicle
        C_PUROK = 1000.0    # Snacks/materials for neighborhood meetings
        TARGET_RECORIDA = 30 # Goal: Every 3 days
        TARGET_PUROK = 3     # Goal: Once a month
        
        # 1. Fund Recoridas first (Cheapest, widest local reach)
        self.n_recorida = min(TARGET_RECORIDA, int(self.iec_fund // C_RECORIDA))
        rem = max(0.0, self.iec_fund - (self.n_recorida * C_RECORIDA))
        
        # 2. Fund Purok Meetings with whatever is left
        self.n_purok = min(TARGET_PUROK, int(rem // C_PUROK))
        self.actual_iec_cost = (self.n_recorida * C_RECORIDA) + (self.n_purok * C_PUROK)
        
        # Calculate local intensity (0.0 to 1.0)
        self.iec_intensity = min(1.0, (self.n_recorida / TARGET_RECORIDA) * 0.5 + (self.n_purok / TARGET_PUROK) * 0.5)

        # --- D. Operational Cash for Incentives (Eq. 3.2) ---
        self.current_cash_on_hand = self.inc_fund

    def local_iec_implementation(self):
        """Provides a small daily boost to local households representing localized IEC (Recorida/Purok)"""
        # FIX: We now use the calculated 'iec_intensity' instead of the raw fund.
        # We also use the high-speed dictionary so this doesn't slow down the DRL training.
        if self.iec_intensity > 0:
            impact = self.iec_intensity * 0.0005 # Small daily drip of awareness
            households = self.model.households_by_bgy.get(self.unique_id, [])
            for h in households:
                h.attitude = min(0.95, h.attitude + impact)

    def distribute_local_incentives(self):
        """Logic for the 'Selected Few' Draw at end of Quarter using LOCAL funds."""
        max_winners = int(self.current_cash_on_hand // 500)
        
        # High-Speed Fetch
        households = self.model.households_by_bgy.get(self.unique_id, [])
        eligible_households = [h for h in households if h.is_compliant]
        
        if not eligible_households or max_winners == 0:
            return

        num_to_pay = min(len(eligible_households), max_winners)
        winners = random.sample(eligible_households, num_to_pay)
        
        for household in winners:
            household.receive_incentive(500)
            self.current_cash_on_hand -= 500
            
        losers = [h for h in eligible_households if h not in winners]
        for household in losers:
            household.attitude -= 0.15 
            household.perceived_unfairness = True

    def get_local_compliance(self):
        """High-speed compliance calculation"""
        households = self.model.households_by_bgy.get(self.unique_id, [])
        self.total_households = len(households)
        
        if self.total_households > 0:
            self.compliant_count = sum(1 for h in households if h.is_compliant)
            self.compliance_rate = self.compliant_count / self.total_households
        else:
            self.compliance_rate = 0.0
            
        return self.compliance_rate

    def step(self):
        self.get_local_compliance()
        self.local_iec_implementation()
        
        # Calculate final enforcement pressure (Local Tanods + LGU Intervention)
        self.update_enforcement_intensity() 
        
        # End of Quarter Actions
        if self.model.tick > 0 and self.model.tick % 90 == 0:
            self.distribute_local_incentives()
            self.setup_local_policy() # Refresh funds for the next quarter

    def give_reward(self, amount):
        """
        Bridge function to satisfy the HouseholdAgent's request for a reward.
        Layers the LGU Universal Reward pool on top of the Local pool.
        """
        # 1. Try to pay from Local Barangay Grocery Fund
        if self.current_cash_on_hand >= amount:
            self.current_cash_on_hand -= amount
            return True
            
        # 2. If Barangay is broke, check if the Mayor allocated Universal Incentives here
        elif self.lgu_incentive_fund >= amount:
            self.lgu_incentive_fund -= amount
            self.model.mayor.total_lgu_incentives_distributed += amount 
            return True
            
        # 3. No funds available in either tier
        return False
        
    def update_enforcement_intensity(self):
        """
        Eq 3.1 & 3.4 logic: Combines Local Tanods and LGU Enforcers 
        to determine the final enforcement pressure.
        """
        # 1. Calculate base intensity from local tanods
        local_pressure = min(1.0, self.n_enforcers / 10.0)

        # 2. Add the LGU-funded enforcement (The DRL's "Extra Stick")
        lgu_pressure = 0.0
        if self.lgu_enf_fund > 0:
            # $26,400 is roughly the cost of 1 extra full-time patrol per quarter
            lgu_pressure = (self.lgu_enf_fund / 26400.0) * 0.2 
        
        # 3. Final Intensity used by HouseholdAgent.step()
        self.enforcement_intensity = min(1.0, local_pressure + lgu_pressure)