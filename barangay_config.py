# barangay_config.py

# =============================================================================
#  MUNICIPAL LEVEL CONSTANTS 
#  Source: Appendix B.1 (MENRO Interview) & Appropriation Ord. No. 2024-01
# =============================================================================
ANNUAL_BUDGET = 1500000   # Updated from 1.1M to 1.5M based on MENRO Interview
QUARTERLY_BUDGET = 375000 # 1.5M / 4
MIN_WAGE = 400            # Daily minimum wage reference (Region X)

# =============================================================================
#  INCOME PROFILES (Calibrated from Appendix B Interviews)
#  Format: [Low Income %, Middle Income %, High Income %]
#  Note: "The income_profile should be unique per barangay"
# =============================================================================
INCOME_PROFILES = {
    # Source: Appendix B.2
    "Babalaya":      [0.80, 0.10, 0.10], 
    
    # Source: Appendix B.3
    "Binuni":        [0.50, 0.30, 0.20], 
    
    # Source: Appendix B.4
    "Demologan":     [0.80, 0.15, 0.05], 
    
    # Source: Appendix B.5
    "Ezperanza":     [0.20, 0.50, 0.30], 
    
    # Source: Appendix B.6 (Described as "Middle Class", est. 40/40/20)
    "Liangan_East":  [0.40, 0.40, 0.20], 
    
    # Source: Appendix B.7 (90% Farmers/Low Income)
    "Mati":          [0.90, 0.05, 0.05],
    
    # Source: Appendix B.8
    "Poblacion":     [0.70, 0.25, 0.05],
}

# =============================================================================
#  BEHAVIORAL PROFILES (Derived from Qualitative Interviews in Appendix B)
#  w_a: Attitude, w_sn: Social Norms, w_pbc: Perceived Control
#  c_effort: Cost of Effort (Lower = Easier to comply)
#  decay: Rate at which compliance habits fade (Higher = Faster decay)
# =============================================================================
BEHAVIOR_PROFILES = {
    # Appendix B.2: "100% compliant", "Not much effort", "High social norms"
    "Babalaya": {
        "w_a": 0.80, "w_sn": 0.90, "w_pbc": 0.70, "c_effort": 0.10, "decay": 0.005
    },

    # Appendix B.3: "95% compliance", "Well-practiced", "Low Decay"
    "Binuni": {
        "w_a": 0.75, "w_sn": 0.80, "w_pbc": 0.65, "c_effort": 0.10, "decay": 0.001
    },

    # Appendix B.4: "60% compliance", "Segregation has become a hobby" (High Attitude)
    "Demologan": {
        "w_a": 0.70, "w_sn": 0.60, "w_pbc": 0.50, "c_effort": 0.20, "decay": 0.010
    },

    # Appendix B.5: "20% compliance", "Mental attitude lacking" (Low Attitude)
    "Ezperanza": {
        "w_a": 0.40, "w_sn": 0.70, "w_pbc": 0.50, "c_effort": 0.30, "decay": 0.020
    },

    # Appendix B.6: "60-70% compliance", "Need constant reminders" (Moderate Decay)
    "Liangan_East": {
        "w_a": 0.65, "w_sn": 0.60, "w_pbc": 0.50, "c_effort": 0.20, "decay": 0.030
    },

    # Appendix B.7: "70% compliance", "High Decay", "Slide back to old habits"
    "Mati": {
        "w_a": 0.60, "w_sn": 0.50, "w_pbc": 0.40, "c_effort": 0.25, "decay": 0.100
    },

    # Appendix B.8: "2% compliance", "Social norms are low", "Discipline is challenge"
    "Poblacion": {
        "w_a": 0.30, "w_sn": 0.20, "w_pbc": 0.40, "c_effort": 0.50, "decay": 0.050
    },
}

# =============================================================================
#  BARANGAY CONFIGURATION LIST
#  Loads demographics, budget, and profiles into the simulation
#  COMPATIBILITY NOTE: Kept name 'BARANGAY_LIST' to match existing repo code.
# =============================================================================
BARANGAY_LIST = [
    {
        "id": 1, 
        "name": "Brgy Liangan East", 
        "N_HOUSEHOLDS": 608,       #
        "local_budget": 30000,     #
        "initial_compliance": 0.65, # Averaged from 60-70%
        "income_profile": "Liangan_East",
        "behavior_profile": "Liangan_East"
    },
    {
        "id": 2, 
        "name": "Brgy Ezperanza", 
        "N_HOUSEHOLDS": 574,       #
        "local_budget": 90000,     #
        "initial_compliance": 0.20, #
        "income_profile": "Ezperanza",
        "behavior_profile": "Ezperanza"
    },
    {
        "id": 3, 
        "name": "Brgy Poblacion", 
        "N_HOUSEHOLDS": 1534,      #
        "local_budget": 200000,    #
        "initial_compliance": 0.02, #
        "income_profile": "Poblacion",
        "behavior_profile": "Poblacion"
    },
    {
        "id": 4, 
        "name": "Brgy Binuni", 
        "N_HOUSEHOLDS": 507,       #
        "local_budget": 126370,    #
        "initial_compliance": 0.95, #
        "income_profile": "Binuni",
        "behavior_profile": "Binuni"
    },
    {
        "id": 5, 
        "name": "Brgy Demologan", 
        "N_HOUSEHOLDS": 463,       #
        "local_budget": 21000,     #
        "initial_compliance": 0.60, #
        "income_profile": "Demologan",
        "behavior_profile": "Demologan"
    },
    {
        "id": 6, 
        "name": "Brgy Mati", 
        "N_HOUSEHOLDS": 165,       #
        "local_budget": 80000,     #
        "initial_compliance": 0.70, #
        "income_profile": "Mati",
        "behavior_profile": "Mati"
    },
    {
        "id": 7, 
        "name": "Brgy Babalaya", 
        "N_HOUSEHOLDS": 171,       #
        "local_budget": 15000,     #
        "initial_compliance": 1.00, #
        "income_profile": "Babalaya",
        "behavior_profile": "Babalaya"
    }
]