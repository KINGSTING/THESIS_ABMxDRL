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
        # 1. MARK VISITED (Keep existing logic)
        nearby_agents = self.model.grid.get_neighbors(self.pos, moore=True, radius=1, include_center=True)
        for agent in nearby_agents:
            if isinstance(agent, HouseholdAgent):
                self.visited_households.add(agent.unique_id)

        # 2. DETERMINE MOVEMENT (The "Separate Patrol" Fix)
        # Scan only local area (radius 10) instead of global map.
        # This ensures Agent A sees targets in the North, and Agent B sees targets in the South.
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
            # CHASE MODE: If I see a unvisited house nearby, go to it
            target_household = min(visible_targets, key=lambda h: self.get_distance(self.pos, h.pos))
            if possible_steps:
                next_position = min(possible_steps, key=lambda p: self.get_distance(p, target_household.pos))
        else:
            # PATROL MODE: If I see nothing, move RANDOMLY
            # This is crucial. It keeps agents spread out covering different streets.
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