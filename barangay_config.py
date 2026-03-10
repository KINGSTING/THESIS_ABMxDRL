# barangay_config.py

# =============================================================================
#  MUNICIPAL LEVEL CONSTANTS 
#  Source: Appendix B.1 (MENRO Interview) & Appropriation Ord. No. 2024-01
# =============================================================================
ANNUAL_BUDGET = 1500000   # Updated from 1.1M to 1.5M based on MENRO Interview
QUARTERLY_BUDGET = 375000 # 1.5M / 4
MIN_WAGE = 400            # Daily minimum wage reference (Region X)
WORKING_DAYS = 66

# =============================================================================
#  INCOME PROFILES (Calibrated from Appendix B Interviews)
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
#  BEHAVIOR PROFILES (CALIBRATED TO HIT ~12.5% BASELINE)
# =============================================================================
# =============================================================================
#  BEHAVIOR PROFILES (CALIBRATED TO INTERVIEW TRANSCRIPTS - ~12.5% BASELINE)
# =============================================================================
BEHAVIOR_PROFILES = {
    # Poblacion: Compliance is around 2%. Social norms are low with no reporting of non-compliance. 
    # Residents put mixed garbage in sacks, indicating high effort resistance. Even educated residents struggle with high decay.
    "Poblacion":     {"w_a": 0.25, "w_sn": 0.15, "w_pbc": 0.20, "c_effort": 0.75, "decay": 0.0030},
    
    # Liangan East: Compliance hits 60-70% but is only good at the start. 
    # High decay is present, and low-income households lack money to buy segregation bins, creating an economic effort barrier.
    "Liangan_East":  {"w_a": 0.25, "w_sn": 0.30, "w_pbc": 0.20, "c_effort": 0.65, "decay": 0.0035},
    
    # Ezperanza: Compliance is around 20%. Social norms are high. 
    # Effort is low, but the mental attitude and appreciation of the ordinance are lacking. Decay is low.
    "Ezperanza":     {"w_a": 0.20, "w_sn": 0.35, "w_pbc": 0.25, "c_effort": 0.65, "decay": 0.0015},
    
    # Mati: Compliance is around 70%. Reporting of illegal dumping is high due to social norms. 
    # However, there is high decay because people slide back into old habits.
    "Mati":          {"w_a": 0.30, "w_sn": 0.40, "w_pbc": 0.25, "c_effort": 0.60, "decay": 0.0030},
    
    # Demologan: Compliance is around 60%. Effort is low because an MRF and collector are available. 
    # Awareness is high. Decay is low.
    "Demologan":     {"w_a": 0.35, "w_sn": 0.35, "w_pbc": 0.30, "c_effort": 0.55, "decay": 0.0010},

    # Binuni: Compliance is very high at around 95%. Social norms are high. 
    # The effort is low because it is well-practiced. Decay is low.
    "Binuni":        {"w_a": 0.40, "w_sn": 0.45, "w_pbc": 0.35, "c_effort": 0.45, "decay": 0.0010},
    
    # Babalaya: Compliance is at 100%. There is high social pressure acting as an information campaign. 
    # Residents find the effort low. There is low decay.
    "Babalaya":      {"w_a": 0.35, "w_sn": 0.50, "w_pbc": 0.35, "c_effort": 0.40, "decay": 0.0010}
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