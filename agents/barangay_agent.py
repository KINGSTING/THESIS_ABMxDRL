import mesa
# REMOVED: from agents.household_agent import HouseholdAgent (Avoids circular import)

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
        # These now track Local + LGU combined funds
        self.iec_fund = 0.0
        self.enf_fund = 0.0
        self.inc_fund = 0.0
        self.fine_amount = 500
        
        # --- 4. Intensities ---
        self.enforcement_intensity = 0.5
        self.iec_intensity = 0.0
        self.incentive_val = 0.0  

        # --- 5. Financials (Base Layer) ---
        # Store the local budget authorized by Ordinance
        self.local_annual_budget = local_budget
        self.local_quarterly_budget = local_budget / 4.0 

        # === CRITICAL FIX: DEFINING THE COST ===
        # 400 PHP/day * 60 days/quarter = 24,000 PHP per enforcer
        self.enforcer_salary_cost = 7000.0 
        # =======================================

        # FIXED: ALLOCATION RATIOS (The "Status Quo" Priorities)
        # Without LGU help, how does the Barangay spend its own money?
        # 50% on Tanods (Security/Enforcement)
        # 30% on Clean-up/Rewards (Incentives)
        # 20% on Education (IEC)
        self.local_allocation_ratios = {"enf": 0.50, "inc": 0.30, "iec": 0.20}

        self.current_cash_on_hand = 0.0

    def update_policy(self, lgu_iec_fund, lgu_enf_fund, lgu_inc_fund):
        """
        Combines Local Implementation (Base) with LGU Augmentation (Top-up).
        Arguments passed here are strictly the LGU's contribution.
        """
        
        # --- A. CALCULATE LOCAL BASE SPENDING ---
        local_enf = self.local_quarterly_budget * self.local_allocation_ratios["enf"]
        local_inc = self.local_quarterly_budget * self.local_allocation_ratios["inc"]
        local_iec = self.local_quarterly_budget * self.local_allocation_ratios["iec"]

        # --- B. AUGMENT WITH LGU FUNDS (The "Stacking" Effect) ---
        # We update the class attributes so the Model sees the TOTAL available power.
        self.iec_fund = local_iec + lgu_iec_fund
        self.enf_fund = local_enf + lgu_enf_fund
        self.inc_fund = local_inc + lgu_inc_fund

        # --- C. UPDATE OPERATIONAL CASH ---
        # This is the pot available for immediate payouts (give_reward)
        self.current_cash_on_hand = self.inc_fund 

        # --- D. CALCULATE INTENSITIES (Using TOTAL Funds) ---
        
        # 1. IEC Intensity (Variable Cost Model)
        # Cost ~P650 per household for full saturation
        IEC_COST_PER_HEAD = 650.0 
        
        if self.n_households > 0:
            saturation_target = self.n_households * IEC_COST_PER_HEAD
        else:
            saturation_target = 375000.0 # Fallback

        self.iec_intensity = min(1.0, self.iec_fund / saturation_target)
        
        # 2. Enforcement Intensity (Fixed Area Cost Model)
        # Cost to patrol the geographic area effectively
        ENF_SATURATION = 375000.0
        self.enforcement_intensity = min(1.0, self.enf_fund / ENF_SATURATION)

        # 3. Incentive Value (The "Carrot")
        # Households see the reward based on the TOTAL available pot
        if self.n_households > 0:
            self.incentive_val = self.inc_fund / self.n_households
        else:
            self.incentive_val = 0

    def get_local_compliance(self):
        """
        Calculates compliance for the DataCollector.
        ROBUST FIX: Checks attributes instead of Class Type to avoid import errors.
        """
        self.total_households = 0
        self.compliant_count = 0
        
        for a in self.model.schedule.agents:
            # 1. Check if agent belongs to this Barangay
            if getattr(a, 'barangay_id', None) == self.unique_id:
                
                # 2. Check if agent is a Household (has 'is_compliant' attr)
                # This excludes Enforcers automatically.
                if hasattr(a, 'is_compliant'):
                    self.total_households += 1
                    if a.is_compliant:
                        self.compliant_count += 1
        
        # Avoid division by zero
        if self.total_households == 0:
            self.compliance_rate = 0.0
        else:
            self.compliance_rate = self.compliant_count / self.total_households
            
        return self.compliance_rate

    def step(self):
        self.get_local_compliance()

    def give_reward(self, amount):
        """
        Attempt to give a reward to a household.
        Returns TRUE if successful (budget exists), FALSE if bankrupt.
        """
        if self.current_cash_on_hand >= amount:
            self.current_cash_on_hand -= amount
            # Update the global tracker for reporting
            self.model.total_incentives_distributed += amount
            return True
        return False