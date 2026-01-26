# barangay_config.py

# =============================================================================
#  MUNICIPAL LEVEL CONSTANTS 
# =============================================================================
ANNUAL_BUDGET = 1000000   
QUARTERLY_BUDGET = 375000 
MIN_WAGE = 400            

# =============================================================================
#  INCOME PROFILES
# =============================================================================
INCOME_PROFILES = {
    "Babalaya":      [0.80, 0.10, 0.10], 
    "Binuni":        [0.50, 0.30, 0.20], 
    "Demologan":     [0.80, 0.15, 0.05], 
    "Ezperanza":     [0.20, 0.50, 0.30], 
    "Liangan_East":  [0.40, 0.40, 0.20], 
    "Mati":          [0.90, 0.05, 0.05],
    "Poblacion":     [0.70, 0.25, 0.05],
}

# =============================================================================
#  BEHAVIORAL PROFILES (FINAL STABILIZATION)
#  Goal: Global Avg 10-15%.
#  Constraint: Binuni, Ezperanza, Babalaya are leaders (max 45%).
#  Mechanism: Increased c_effort significantly to prevent 100% spikes.
# =============================================================================
BEHAVIOR_PROFILES = {
    # --- THE TOP 3 PERFORMERS (Target: 30% - 45%) ---
    # We give them slightly lower effort costs than the rest, 
    # but still high enough to stop them from hitting 90%.

    # 1. Binuni (Rich & Capable):
    # Effort: 0.55 -> 0.60 (Increased friction to cap at ~40%)
    # Decay: 0.005 (Sticky habits help them maintain the lead)
    "Binuni":       { "w_a": 0.75, "w_sn": 0.80, "w_pbc": 0.65, "c_effort": 0.60, "decay": 0.005 },

    # 2. Ezperanza (Consistent):
    # Effort: 0.50 -> 0.58 (Harder now)
    # Decay: 0.015
    "Ezperanza":    { "w_a": 0.40, "w_sn": 0.70, "w_pbc": 0.50, "c_effort": 0.58, "decay": 0.015 },

    # 3. Babalaya (Motivated but Poor):
    # Effort: 0.60 -> 0.62 (Needs to be difficult due to poverty, but motivation is high)
    # Decay: 0.03
    "Babalaya":     { "w_a": 0.80, "w_sn": 0.90, "w_pbc": 0.70, "c_effort": 0.62, "decay": 0.03 },


    # --- THE LAGGARDS (Target: 5% - 15%) ---
    # We CRUSH these down with high c_effort to balance the global average.

    # 4. Liangan East (The False Spike):
    # CRITICAL FIX: Effort raised 0.45 -> 0.68.
    # This will stop the explosion to 78%. They will now struggle to pass 20%.
    "Liangan_East": { "w_a": 0.65, "w_sn": 0.60, "w_pbc": 0.50, "c_effort": 0.68, "decay": 0.05 },

    # 5. Poblacion (The Anchor):
    # Effort: 0.65 -> 0.75 (Maximum difficulty).
    # This ensures Poblacion stays near 0-2%, dragging the global average down.
    "Poblacion":    { "w_a": 0.55, "w_sn": 0.20, "w_pbc": 0.40, "c_effort": 0.75, "decay": 0.10 },

    # 6. Demologan:
    # Effort: 0.60 -> 0.68
    "Demologan":    { "w_a": 0.70, "w_sn": 0.60, "w_pbc": 0.50, "c_effort": 0.68, "decay": 0.08 },

    # 7. Mati:
    # Effort: 0.55 -> 0.65
    "Mati":         { "w_a": 0.60, "w_sn": 0.50, "w_pbc": 0.40, "c_effort": 0.65, "decay": 0.10 },
}

# =============================================================================
#  ALLOCATION PROFILES
# =============================================================================
ALLOCATION_PROFILES = {
    "Liangan_East": {"enf": 0.25, "inc": 0.65, "iec": 0.10},
    "Poblacion":    {"enf": 0.60, "inc": 0.20, "iec": 0.20},
    "Babalaya":     {"enf": 0.90, "inc": 0.05, "iec": 0.05},
    "Demologan":    {"enf": 0.85, "inc": 0.10, "iec": 0.05},
    "Binuni":       {"enf": 0.40, "inc": 0.40, "iec": 0.20},
    "Mati":         {"enf": 0.30, "inc": 0.50, "iec": 0.20},
    "Ezperanza":    {"enf": 0.50, "inc": 0.30, "iec": 0.20},
}

# =============================================================================
#  BARANGAY CONFIGURATION LIST
# =============================================================================
BARANGAY_LIST = [
    {
        "id": 1, "name": "Brgy Liangan East", "N_HOUSEHOLDS": 608, "local_budget": 30000, 
        "initial_compliance": 0.14, 
        "income_profile": "Liangan_East", "behavior_profile": "Liangan_East",
        "allocation_profile": "Liangan_East" 
    },
    {
        "id": 2, "name": "Brgy Ezperanza", "N_HOUSEHOLDS": 574, "local_budget": 90000, 
        "initial_compliance": 0.14, 
        "income_profile": "Ezperanza", "behavior_profile": "Ezperanza",
        "allocation_profile": "Ezperanza" 
    },
    {
        "id": 3, "name": "Brgy Poblacion", "N_HOUSEHOLDS": 1534, "local_budget": 200000, 
        "initial_compliance": 0.02, 
        "income_profile": "Poblacion", "behavior_profile": "Poblacion",
        "allocation_profile": "Poblacion" 
    },
    {
        "id": 4, "name": "Brgy Binuni", "N_HOUSEHOLDS": 507, "local_budget": 126370, 
        "initial_compliance": 0.15, 
        "income_profile": "Binuni", "behavior_profile": "Binuni",
        "allocation_profile": "Binuni" 
    },
    {
        "id": 5, "name": "Brgy Demologan", "N_HOUSEHOLDS": 463, "local_budget": 21000, 
        "initial_compliance": 0.11, 
        "income_profile": "Demologan", "behavior_profile": "Demologan",
        "allocation_profile": "Demologan" 
    },
    {
        "id": 6, "name": "Brgy Mati", "N_HOUSEHOLDS": 165, "local_budget": 80000, 
        "initial_compliance": 0.11, 
        "income_profile": "Mati", "behavior_profile": "Mati",
        "allocation_profile": "Mati" 
    },
    {
        "id": 7, "name": "Brgy Babalaya", "N_HOUSEHOLDS": 171, "local_budget": 15000, 
        "initial_compliance": 0.14, 
        "income_profile": "Babalaya", "behavior_profile": "Babalaya",
        "allocation_profile": "Babalaya" 
    }
]