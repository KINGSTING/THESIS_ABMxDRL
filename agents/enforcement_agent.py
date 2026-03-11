import mesa
import math
import random
from agents.household_agent import HouseholdAgent

class EnforcementAgent(mesa.Agent):
    def __init__(self, unique_id, model, barangay_id, patrol_range=10):
        super().__init__(unique_id, model)
        self.barangay_id = barangay_id 
        self.patrol_range = patrol_range
        self.fine_amount = 500
        self.is_municipal = False 
        
        # --- THE MISSING LINE ---
        self.visited_households = set()

    def step(self):
        import random
        
        # --- NEW: 30-DAY CONTRACT CHECK ---
        if getattr(self, 'is_municipal', False):
            if hasattr(self, 'contract_days'):
                self.contract_days -= 1
                if self.contract_days <= 0:
                    self.model.grid.remove_agent(self)
                    self.model.schedule.remove(self)
                    return # Exit the step instantly, they went home!

        self.visited_households.clear() 
        is_municipal = getattr(self, 'is_municipal', False)
        
        # ==========================================================
        # STOCHASTIC PATROLLING (The Nerf)
        # ==========================================================
        if is_municipal:
            # The Mayor's Task Force is dedicated and patrols every day
            max_daily_capacity = 25 
            daily_travel_budget = 150
        else:
            # Tanods only catch 1 person max...
            max_daily_capacity = 1
            daily_travel_budget = 20
            
            # ...and they are busy with other duties 90% of the time!
            if random.random() > 0.10: 
                return # Skips the garbage patrol for today

        caught_count = 0

        # ==========================================================
        # 1. THE MATH: Catch up to quota from ANYWHERE in the barangay
        # ==========================================================
        bgy_households = self.model.households_by_bgy.get(self.barangay_id, [])
        targets = [h for h in bgy_households if not h.is_compliant]
        
        if targets:
            # Instantly grab random targets from the whole barangay
            caught_count = min(max_daily_capacity, len(targets))
            caught = random.sample(targets, caught_count)
            
            for target in caught:
                if hasattr(target, 'get_fined'):
                    target.get_fined(self.fine_amount)

        # ==========================================================
        # 2. THE VISUALS: Walk 1 step to look busy on the UI
        # ==========================================================
        if not getattr(self.model, 'train_mode', False):
            possible_steps = self.model.grid.get_neighborhood(self.pos, moore=True, include_center=False)
            if possible_steps:
                self.model.grid.move_agent(self, getattr(self.model, 'random', random).choice(possible_steps))