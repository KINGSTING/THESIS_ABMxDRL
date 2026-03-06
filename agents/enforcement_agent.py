import mesa
import math
from agents.household_agent import HouseholdAgent

class EnforcementAgent(mesa.Agent):
    """
    Represents a Barangay Official or Tanod who patrols for non-compliance.
    Modified to patrol randomly until a target is spotted nearby.
    """
    def __init__(self, unique_id, model, barangay_id, patrol_range=5):
        super().__init__(unique_id, model)
        self.barangay_id = barangay_id 
        self.patrol_range = patrol_range
        self.fine_amount = 500
        self.visited_households = set()

    def get_distance(self, pos_1, pos_2):
        x1, y1 = pos_1
        x2, y2 = pos_2
        return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

    def step(self):
        households_checked_today = 0
        MAX_DAILY_CAPACITY = 30
        
        # 1. MARK VISITED & PROCESS ENFORCEMENT
        # We combine the scan and enforce loops so we don't exceed the 30-household limit.
        catch_zone = self.model.grid.get_neighbors(self.pos, moore=True, radius=1, include_center=True)
        local_households = [a for a in catch_zone if isinstance(a, HouseholdAgent)]
        
        for agent in local_households:
            if households_checked_today >= MAX_DAILY_CAPACITY:
                break # Enforcer has reached physical limit for the day
                
            # Process household if not visited yet
            if agent.unique_id not in self.visited_households:
                self.visited_households.add(agent.unique_id)
                households_checked_today += 1
                
                # Check compliance and issue fine
                if not agent.is_compliant:
                    if hasattr(agent, 'get_fined'):
                        agent.get_fined()
                    else:
                        agent.utility -= 0.5
        
        # 2. DETERMINE MOVEMENT 
        # Scan local area (radius 10) for unvisited targets
        local_scan = self.model.grid.get_neighbors(self.pos, moore=True, radius=10, include_center=False)
        
        visible_targets = [
            a for a in local_scan 
            if isinstance(a, HouseholdAgent) 
            and a.unique_id not in self.visited_households
            and a.barangay_id == self.barangay_id
        ]

        next_position = self.pos
        possible_steps = self.model.grid.get_neighborhood(self.pos, moore=True, include_center=False)

        if visible_targets:
            # CHASE MODE: Move towards closest unvisited target
            target_household = min(visible_targets, key=lambda h: self.get_distance(self.pos, h.pos))
            if possible_steps:
                next_position = min(possible_steps, key=lambda p: self.get_distance(p, target_household.pos))
        else:
            # PATROL MODE: Move randomly if no targets are visible
            if possible_steps:
                next_position = self.random.choice(possible_steps)

        self.model.grid.move_agent(self, next_position)

        # 3. ENFORCEMENT (Keep existing logic)
        catch_zone = self.model.grid.get_neighbors(self.pos, moore=True, radius=1, include_center=True)
        for agent in catch_zone:
            if isinstance(agent, HouseholdAgent):
                if not agent.is_compliant:
                    if hasattr(agent, 'get_fined'):
                        agent.get_fined()
                    else:
                        agent.utility -= 0.5