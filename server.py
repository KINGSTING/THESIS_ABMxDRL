import mesa
from mesa.visualization.modules import CanvasGrid, ChartModule, TextElement
from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.UserParam import Choice

# Import your custom agents and model
from agents.bacolod_model import BacolodModel
from agents.household_agent import HouseholdAgent
from agents.enforcement_agent import EnforcementAgent
from agents.barangay_agent import BarangayAgent

# --- 1. Portrayal Factory ---
def make_barangay_portrayal(barangay_target_id):
    def local_portrayal(agent):
        if agent is None: return None
        
        # Filter: Only show agents belonging to this specific Barangay Grid
        if hasattr(agent, 'barangay_id') and agent.barangay_id != barangay_target_id: return None
        if isinstance(agent, BarangayAgent) and agent.unique_id != barangay_target_id: return None

        portrayal = {}
        agent_class = type(agent).__name__
        
        if agent_class == "HouseholdAgent":
            portrayal["Shape"] = "circle"
            portrayal["Filled"] = "true"
            portrayal["r"] = 0.5   
            portrayal["Layer"] = 0
            is_compliant = getattr(agent, "is_compliant", False)
            portrayal["Color"] = "green" if is_compliant else "red"
            
        elif agent_class == "EnforcementAgent":
            portrayal["Shape"] = "rect"
            portrayal["Filled"] = "true"
            portrayal["Layer"] = 1
            
            # --- VISUAL MULTI-LAYERED GOVERNANCE ---
            # Distinguish between LGU Inspectors and Local Tanods
            if getattr(agent, "is_municipal", False):
                portrayal["w"] = 0.9  # LGU Inspectors are larger
                portrayal["h"] = 0.9
                portrayal["Color"] = "purple" # LGU Color
                portrayal["text"] = "M"       # 'M' for Municipal
                portrayal["text_color"] = "white"
            else:
                portrayal["w"] = 0.7  # Tanods are standard size
                portrayal["h"] = 0.7
                portrayal["Color"] = "blue"   # Local Color
                portrayal["text"] = "T"       # 'T' for Tanod
                portrayal["text_color"] = "white"
            
        elif agent_class == "BarangayAgent":
            portrayal["Shape"] = "circle"
            portrayal["Filled"] = "true"
            portrayal["r"] = 1.0  
            portrayal["Layer"] = 2
            portrayal["Color"] = "black"
            
        return portrayal
    return local_portrayal

# --- 2. UI Layout Classes ---

class Spacer(mesa.visualization.TextElement):
    def render(self, model):
        # Keeps charts pushed down below the map
        return '<div style="height: 850px; width: 100%; display: block; z-index: -1;"></div>'

class ViewSwitcher(mesa.visualization.TextElement):
    def render(self, model):
        # This HTML block includes the "Image Hack" (onerror) to force the JS to run
        return """
        <div class="switcher-container">
            <div class="switcher-box">
                <h4>Active Simulation View</h4>
                <div class="btn-group" id="bgy-btn-group">
                    <button id="btn_0" class="bgy-btn active" onclick="window.switchView(0)">Poblacion</button>
                    <button id="btn_1" class="bgy-btn" onclick="window.switchView(1)">Liangan East</button>
                    <button id="btn_2" class="bgy-btn" onclick="window.switchView(2)">Ezperanza</button>
                    <button id="btn_3" class="bgy-btn" onclick="window.switchView(3)">Binuni</button>
                    <button id="btn_4" class="bgy-btn" onclick="window.switchView(4)">Demologan</button> 
                    <button id="btn_5" class="bgy-btn" onclick="window.switchView(5)">Mati</button>
                    <button id="btn_6" class="bgy-btn" onclick="window.switchView(6)">Babalaya</button>
                </div>
            </div>
            
            <img src="x" style="display:none;" onerror="
                if (!window.switchView) {
                    window.switchView = function(targetIndex) {
                        // 1. Handle Maps
                        let maps = document.getElementsByClassName('world-grid-parent');
                        if (maps.length < 7) { 
                            setTimeout(() => window.switchView(targetIndex), 100); 
                            return; 
                        }
                        
                        targetIndex = parseInt(targetIndex);
                        for (let i = 0; i < 7; i++) {
                            let mapBox = maps[i];
                            if (i === targetIndex) {
                                mapBox.style.opacity = '1'; 
                                mapBox.style.zIndex = '100'; 
                                mapBox.style.pointerEvents = 'auto';
                                mapBox.style.border = '2px solid #007bff';
                            } else {
                                mapBox.style.opacity = '0'; 
                                mapBox.style.zIndex = '1'; 
                                mapBox.style.pointerEvents = 'none';
                                mapBox.style.border = 'none';
                            }
                        }

                        // 2. Handle Buttons
                        let container = document.getElementById('bgy-btn-group');
                        if (container) {
                            let btns = container.getElementsByClassName('bgy-btn');
                            for(let i = 0; i < btns.length; i++) {
                                btns[i].classList.remove('active');
                            }
                            let activeBtn = document.getElementById('btn_' + targetIndex);
                            if(activeBtn) {
                                activeBtn.classList.add('active');
                            }
                        }
                    };
                    
                    // Initialize view after short delay
                    setTimeout(() => window.switchView(0), 500);
                }
            ">

            <style>
                /* CENTERED MAP STYLE */
                .world-grid-parent {
                    position: absolute !important;
                    top: 360px; 
                    left: 60% !important;           /* Center horizontally */
                    transform: translateX(-50%) !important; /* Perfect center alignment */
                    margin: 0 !important;
                    width: 600px !important; 
                    height: 600px !important;
                    transition: opacity 0.3s ease;
                    background: white;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    border-radius: 4px;
                }

                .switcher-container {
                    width: 100%; text-align: center; padding: 15px; 
                    background: white; z-index: 9999 !important; position: relative;
                    display: flex; justify-content: center;
                }
                .switcher-box {
                    padding: 15px; background: #f8f9fa; border-radius: 8px;
                    border: 1px solid #dee2e6;
                }
                .bgy-btn { 
                    padding: 10px 20px; margin: 2px; border: 1px solid #aaa; 
                    cursor: pointer; border-radius: 4px; background: #f8f9fa; font-weight: bold;
                }
                .bgy-btn.active { 
                    background-color: #007bff !important; 
                    color: white !important; 
                    border-color: #0056b3 !important; 
                }
                .bgy-btn:hover { background: #e2e6ea; }
            </style>
        </div>
        """

# --- 3. Setup Elements ---
visual_elements = []
visual_elements.append(ViewSwitcher()) 
visual_elements.append(Spacer())

# A. Create the 7 Maps
for i in range(7):
    portrayal_fn = make_barangay_portrayal(f"BGY_{i}")
    grid = CanvasGrid(portrayal_fn, 50, 50, 600, 600)
    visual_elements.append(grid)

# B. Compliance Chart
barangay_chart_data = [
    {"Label": "Brgy Poblacion",    "Color": "red"},     
    {"Label": "Brgy Liangan East", "Color": "orange"},  
    {"Label": "Brgy Ezperanza",    "Color": "gold"},    
    {"Label": "Brgy Binuni",       "Color": "green"},   
    {"Label": "Brgy Babalaya",     "Color": "cyan"},    
    {"Label": "Brgy Mati",         "Color": "blue"},    
    {"Label": "Brgy Demologan",    "Color": "purple"}   
]

chart_compliance = ChartModule(
    [{"Label": "Global Compliance", "Color": "Black"}] + barangay_chart_data,
    data_collector_name='datacollector'
)
visual_elements.append(chart_compliance)

# --- 4. Launch with Policy Choice ---
model_params = {
    "seed": 42,
    "train_mode": False,
    "policy_mode": Choice(
        name="LGU Policy Strategy",  
        value="status_quo",      
        choices=["NO_LGU", "status_quo", "pure_incentives", "pure_enforcement", "HuDRL"]
    )
}

server = ModularServer(
    BacolodModel,
    visual_elements,
    "Bacolod Multi-Layered Governance Simulation",
    model_params
)

server.port = 8522 
server.launch()