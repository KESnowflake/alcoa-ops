import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import copy
import os
import re

st.set_page_config(
    page_title="Alcoa Australia | Operations Control",
    page_icon=":material/factory:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── BRAND COLOURS ─────────────────────────────────────────────────────────────
NAVY   = "#003087"
BLUE   = "#0057A8"
CYAN   = "#00B4D8"
GREEN  = "#10B981"
AMBER  = "#F59E0B"
RED    = "#EF4444"
BORDER = "#1E3A5F"
TXT    = "#E2E8F0"
MUTED  = "#94A3B8"
BG     = "#0A1628"
CARD   = "#0D2137"

st.markdown(f"""
<style>
  .stApp {{ background-color: {BG}; }}
  section[data-testid="stSidebar"] {{ background-color: {NAVY}; }}
  section[data-testid="stSidebar"] * {{ color: white !important; }}
  h1, h2, h3, h4 {{ color: {TXT} !important; }}
  p, li, span {{ color: #CBD5E1; }}
  label {{ color: {TXT} !important; }}
  [data-testid="stMetricValue"] {{ color: {TXT} !important; font-size: 1.5rem !important; }}
  [data-testid="stMetricLabel"] {{ color: {MUTED} !important; font-size: 0.72rem !important; text-transform: uppercase; letter-spacing: 0.5px; }}
  [data-testid="stMetricDelta"] {{ font-size: 0.75rem !important; }}
  div[data-testid="stExpander"] details {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}
  div[data-testid="stExpander"] summary {{ color: {TXT} !important; }}
  .stTabs [data-baseweb="tab-list"] {{ background: {CARD}; border-radius: 10px; gap: 4px; padding: 4px; }}
  .stTabs [data-baseweb="tab"] {{ color: {MUTED}; border-radius: 8px; }}
  .stTabs [aria-selected="true"] {{ background: {BLUE} !important; color: white !important; }}
  .stButton > button {{ background: {BLUE}; color: white; border: none; border-radius: 8px; font-weight: 600; padding: 0.5em 1.5em; }}
  .stButton > button:hover {{ background: #0066cc !important; border: none !important; }}
  .stButton > button[kind="primary"] {{ background: linear-gradient(135deg, {GREEN}, #059669) !important; font-size: 1em; }}
  .stSelectbox > div > div {{ background: {CARD}; color: {TXT}; border-color: {BORDER}; }}
  hr {{ border-color: {BORDER}; opacity: 0.4; }}
  .stAlert {{ background: {CARD} !important; border-radius: 10px; }}
  [data-testid="stRadio"] label {{ color: white !important; font-size: 0.9rem; }}
  [data-testid="stRadio"] div[role="radiogroup"] {{ gap: 4px; }}
  .pill-tag {{ display:inline-block; padding:2px 10px; border-radius:12px; font-size:0.7rem; font-weight:700; letter-spacing:0.5px; }}
  .impact-card {{ background: {CARD}; border-radius:10px; padding:16px; margin:6px 0; }}
  .rec-row {{ border-left:3px solid; border-radius:0 6px 6px 0; padding:10px 14px; margin:6px 0; background:rgba(0,0,0,0.25); }}
</style>
""", unsafe_allow_html=True)

# ── STAGE REGISTRY ────────────────────────────────────────────────────────────
STAGES = [
    {"id":"s1","num":1,"name":"Land Clearing",        "icon":":material/park:"},
    {"id":"s2","num":2,"name":"Drill & Blast",         "icon":":material/bolt:"},
    {"id":"s3","num":3,"name":"Excavation & Haulage",  "icon":":material/local_shipping:"},
    {"id":"s4","num":4,"name":"Crushing & Screening",  "icon":":material/settings:"},
    {"id":"s5","num":5,"name":"Digestion",              "icon":":material/science:"},
    {"id":"s6","num":6,"name":"Clarification",          "icon":":material/water_drop:"},
    {"id":"s7","num":7,"name":"Precipitation",          "icon":":material/ac_unit:"},
    {"id":"s8","num":8,"name":"Calcination",            "icon":":material/local_fire_department:"},
    {"id":"s9","num":9,"name":"Port & Shipping",        "icon":":material/directions_boat:"},
]

# ── BASE STATE (nominal operations) ───────────────────────────────────────────
BASE = {
    "s1": {"hectares_today":3.2,  "soil_moisture":18.5,  "wind_kmh":12.3,   "temp_c":24.1,      "dozer_util":78},
    "s2": {"frag_d50":185,        "penetration":2.3,     "ppv":8.2,         "holes":124,        "blast_eff":87},
    "s3": {"trucks":12,           "max_trucks":15,       "payload":185,     "cycle_min":28,     "haul_tph":2280,  "fuel_lph":142},
    "s4": {"throughput":2150,     "motor_pct":82,        "particle_d80":48, "bearing_vib":3.2,  "belt_pct":78,    "dust_pm10":42},
    "s5": {"temp_c":145,          "pressure_bar":3.8,    "caustic_gl":235,  "ph":13.4,          "feed_tph":620,   "steam_gjt":8.4,  "al2o3_pct":91.2},
    "s6": {"turbidity":12,        "flocculant_gt":45,    "bed_pct":62,      "density_kgm3":1420,"liquor_m3h":545, "rake_torq":35},
    "s7": {"temp_c":55,           "crystal_um":78,       "yield_gl":68,     "agitator_pct":72,  "liq_density":1280,"res_time_h":36},
    "s8": {"temp_z1":450,         "temp_z2":850,         "temp_z3":1050,    "feed_tph":46,      "energy_gjt":3.2, "nox":180,        "moisture_pct":0.08},
    "s9": {"silo_pct":78,         "prod_moisture":0.06,  "wagons":24,       "port_stock_t":85000,"ship_tph":2400, "vessel_eta":2.3},
}

# ── SYNTHETIC HISTORY ─────────────────────────────────────────────────────────
@st.cache_data
def gen_history():
    np.random.seed(42)
    now = datetime.now()
    t = [now - timedelta(hours=23-i) for i in range(24)]
    df = pd.DataFrame({"ts": t})
    wave = np.sin(np.arange(24) * 0.35) * 60
    df["haul_tph"]      = np.clip(BASE["s3"]["haul_tph"]    + np.random.randn(24)*100 + wave, 1600, 2800).round()
    df["crusher_tph"]   = (df["haul_tph"] * 0.944 + np.random.randn(24)*40).round()
    df["dig_feed_tph"]  = (df["crusher_tph"] * 0.92 + np.random.randn(24)*25).round()
    df["alumina_tph"]   = (df["dig_feed_tph"] * 0.455 + np.random.randn(24)*12).round()
    df["energy_mw"]     = np.clip(48 + np.random.randn(24)*2.8 + np.sin(np.arange(24)*0.3)*3.5, 38, 62).round(1)
    df["caustic_gl"]    = (235 + np.random.randn(24)*3.5).round(1)
    df["crystal_um"]    = (78  + np.random.randn(24)*2.2).round(1)
    df["kiln_temp"]     = (1050+ np.random.randn(24)*14).round()
    df["turbidity"]     = np.clip(12 + np.random.randn(24)*2, 4, 25).round(1)
    return df

HIST = gen_history()

# ── SIMULATION ENGINE ─────────────────────────────────────────────────────────
def compute_state(scenario, value):
    state = copy.deepcopy(BASE)
    affected = set()
    msgs = {}

    if scenario == "none":
        return state, affected, msgs

    if scenario == "reduced_trucks":
        trucks = int(value)
        state["s3"]["trucks"] = trucks
        ratio = trucks / BASE["s3"]["max_trucks"]
        state["s3"]["haul_tph"]  = int(BASE["s3"]["haul_tph"]  * ratio)
        state["s3"]["fuel_lph"]  = int(BASE["s3"]["fuel_lph"]  * ratio)
        f4  = min(1.0, ratio)
        state["s4"]["throughput"] = int(BASE["s4"]["throughput"] * f4)
        state["s4"]["belt_pct"]   = int(BASE["s4"]["belt_pct"]   * f4)
        state["s4"]["motor_pct"]  = int(BASE["s4"]["motor_pct"]  * (0.55 + 0.45*f4))
        f5 = f4 * 0.97
        state["s5"]["feed_tph"]   = int(BASE["s5"]["feed_tph"] * f5)
        state["s5"]["al2o3_pct"]  = round(BASE["s5"]["al2o3_pct"] * (0.96 + 0.04*f5), 1)
        state["s6"]["liquor_m3h"] = int(BASE["s6"]["liquor_m3h"] * f5 * 0.98)
        state["s7"]["yield_gl"]   = round(BASE["s7"]["yield_gl"] * (0.88 + 0.12*f5), 1)
        state["s8"]["feed_tph"]   = round(BASE["s8"]["feed_tph"] * f5 * 0.97, 1)
        state["s9"]["silo_pct"]   = max(10, BASE["s9"]["silo_pct"] - int((1-f4)*40))
        state["s9"]["ship_tph"]   = int(BASE["s9"]["ship_tph"] * max(0.5, f5))
        if trucks < 10:
            affected = {"s3","s4","s5","s6","s7","s8","s9"}
            msgs = {
                "s3": (RED,   f"Only {trucks}/15 trucks active — haulage at {state['s3']['haul_tph']:,} t/hr ({int((1-ratio)*100)}% below baseline)"),
                "s4": (RED,   f"Crusher feed starved. Throughput {state['s4']['throughput']:,} t/hr. Motor under-utilised at {state['s4']['motor_pct']}%"),
                "s5": (AMBER, f"Digestion feed reduced to {state['s5']['feed_tph']} t/hr. Al₂O₃ extraction at {state['s5']['al2o3_pct']}%"),
                "s6": (AMBER, f"Green liquor flow down to {state['s6']['liquor_m3h']} m³/hr. Thickener underloaded — chemistry drift risk"),
                "s7": (AMBER, f"Precipitation yield reduced to {state['s7']['yield_gl']} g/L. Crystal growth slowed"),
                "s8": (AMBER, f"Calciner feed at {state['s8']['feed_tph']} t/hr. Energy wasted maintaining kiln temp on reduced feed"),
                "s9": (AMBER, f"Silo inventory falling to {state['s9']['silo_pct']}%. Vessel schedule risk"),
            }
        elif trucks < 12:
            affected = {"s3","s4","s5"}
            msgs = {
                "s3": (AMBER, f"{trucks}/15 trucks. Haulage at {state['s3']['haul_tph']:,} t/hr"),
                "s4": (AMBER, f"Crusher throughput {state['s4']['throughput']:,} t/hr — slightly below target"),
                "s5": (AMBER, f"Minor feed reduction to {state['s5']['feed_tph']} t/hr"),
            }

    elif scenario == "oversized_rock":
        d50 = value
        state["s2"]["frag_d50"]   = d50
        over = d50 / BASE["s2"]["frag_d50"]
        state["s2"]["blast_eff"]  = max(50, int(BASE["s2"]["blast_eff"] / over))
        cp = min(1.0, 185 / d50)
        state["s4"]["throughput"]  = int(BASE["s4"]["throughput"] * cp)
        state["s4"]["motor_pct"]   = min(98, int(BASE["s4"]["motor_pct"] * over * 0.92))
        state["s4"]["bearing_vib"] = round(BASE["s4"]["bearing_vib"] * (1 + (over-1)*1.6), 1)
        state["s4"]["particle_d80"]= round(BASE["s4"]["particle_d80"] * (1 + (over-1)*0.55), 1)
        state["s5"]["feed_tph"]    = int(BASE["s5"]["feed_tph"] * cp)
        state["s5"]["al2o3_pct"]   = round(BASE["s5"]["al2o3_pct"] * (0.84 + 0.16*cp), 1)
        state["s5"]["steam_gjt"]   = round(BASE["s5"]["steam_gjt"] * (1 + (over-1)*0.28), 1)
        f56 = cp * 0.96
        state["s6"]["liquor_m3h"]  = int(BASE["s6"]["liquor_m3h"] * f56)
        state["s6"]["turbidity"]   = round(BASE["s6"]["turbidity"] * (1 + (1-cp)*1.4), 1)
        state["s7"]["yield_gl"]    = round(BASE["s7"]["yield_gl"] * f56, 1)
        state["s7"]["crystal_um"]  = round(BASE["s7"]["crystal_um"] * (0.9 + 0.1*cp), 1)
        state["s8"]["feed_tph"]    = round(BASE["s8"]["feed_tph"] * f56, 1)
        state["s9"]["silo_pct"]    = max(20, int(BASE["s9"]["silo_pct"] * f56))
        if d50 > 250:
            affected = {"s2","s4","s5","s6","s7","s8","s9"}
            msgs = {
                "s2": (RED,   f"Fragment D50 {d50:.0f}mm (target 185mm). Blast efficiency {state['s2']['blast_eff']}%. Secondary blasting required"),
                "s4": (RED,   f"Motor current {state['s4']['motor_pct']}% — overload risk. Throughput {state['s4']['throughput']:,} t/hr. Bearing vib {state['s4']['bearing_vib']} mm/s ⚠"),
                "s5": (AMBER, f"Coarser feed — Al₂O₃ extraction down to {state['s5']['al2o3_pct']}%. Steam up to {state['s5']['steam_gjt']} GJ/t"),
                "s6": (AMBER, f"Turbidity rising to {state['s6']['turbidity']} NTU. Flocculant adjustment needed"),
                "s7": (AMBER, f"Yield {state['s7']['yield_gl']} g/L. Crystal size reduced to {state['s7']['crystal_um']} µm"),
                "s8": (AMBER, f"Calciner feed {state['s8']['feed_tph']} t/hr. Adjust fuel-to-feed ratio"),
                "s9": (AMBER, f"Silo declining to {state['s9']['silo_pct']}%. Monitor shipping schedule"),
            }
        elif d50 > 200:
            affected = {"s2","s4","s5"}
            msgs = {
                "s2": (AMBER, f"Fragment D50 {d50:.0f}mm — slightly above target. Monitor crusher"),
                "s4": (AMBER, f"Motor {state['s4']['motor_pct']}%, vibration {state['s4']['bearing_vib']} mm/s"),
                "s5": (AMBER, f"Minor extraction penalty — Al₂O₃ at {state['s5']['al2o3_pct']}%"),
            }

    elif scenario == "high_dig_temp":
        temp = value
        delta = temp - 145
        state["s5"]["temp_c"]      = temp
        state["s5"]["pressure_bar"]= round(BASE["s5"]["pressure_bar"] + delta*0.08, 1)
        state["s5"]["caustic_gl"]  = round(BASE["s5"]["caustic_gl"]   - delta*1.2, 0)
        state["s5"]["steam_gjt"]   = round(BASE["s5"]["steam_gjt"]    + delta*0.12, 1)
        state["s5"]["al2o3_pct"]   = round(min(95, BASE["s5"]["al2o3_pct"] + delta*0.15), 1)
        state["s6"]["turbidity"]   = round(BASE["s6"]["turbidity"]    + delta*0.75, 1)
        state["s6"]["flocculant_gt"]= round(BASE["s6"]["flocculant_gt"] + delta*0.55, 0)
        state["s6"]["bed_pct"]     = round(min(92, BASE["s6"]["bed_pct"] + delta*0.38), 0)
        state["s7"]["crystal_um"]  = round(max(55, BASE["s7"]["crystal_um"] - delta*0.45), 1)
        state["s7"]["yield_gl"]    = round(BASE["s7"]["yield_gl"] + delta*0.18, 1)
        state["s8"]["feed_tph"]    = round(BASE["s8"]["feed_tph"] + delta*0.04, 1)
        if temp > 160:
            affected = {"s5","s6","s7","s8"}
            msgs = {
                "s5": (RED,   f"Digester at {temp}°C (target 145°C). Pressure {state['s5']['pressure_bar']} bar. Caustic depleting to {state['s5']['caustic_gl']:.0f} g/L. Steam +{round(state['s5']['steam_gjt']-BASE['s5']['steam_gjt'],1)} GJ/t"),
                "s6": (RED,   f"Silica dissolution elevated. Turbidity {state['s6']['turbidity']} NTU. Flocculant demand {state['s6']['flocculant_gt']:.0f} g/t. Bed level {state['s6']['bed_pct']}%"),
                "s7": (AMBER, f"Crystal size reduced to {state['s7']['crystal_um']} µm (target 70-90). Caustic carryover affecting purity"),
                "s8": (CYAN,  f"Marginally higher feed from better extraction. Monitor alpha/gamma Al₂O₃ phase ratio"),
            }
        elif temp > 150:
            affected = {"s5","s6"}
            msgs = {
                "s5": (AMBER, f"Digester at {temp}°C — above optimal. Monitor caustic & pipe corrosion"),
                "s6": (AMBER, f"Turbidity {state['s6']['turbidity']} NTU — trending up. Increase monitoring"),
            }

    elif scenario == "poor_flocculant":
        fp = value / 100
        state["s6"]["flocculant_gt"] = round(BASE["s6"]["flocculant_gt"] * fp, 0)
        sf = max(0.3, fp**0.4)
        state["s6"]["turbidity"]   = round(BASE["s6"]["turbidity"] / sf, 1)
        state["s6"]["bed_pct"]     = round(min(96, BASE["s6"]["bed_pct"] / sf), 0)
        state["s6"]["rake_torq"]   = round(min(95, BASE["s6"]["rake_torq"] / sf), 0)
        state["s6"]["liquor_m3h"]  = round(BASE["s6"]["liquor_m3h"] * sf * 0.9, 0)
        state["s7"]["crystal_um"]  = round(BASE["s7"]["crystal_um"] * sf, 1)
        state["s7"]["yield_gl"]    = round(BASE["s7"]["yield_gl"]    * sf, 1)
        state["s8"]["feed_tph"]    = round(BASE["s8"]["feed_tph"]    * sf, 1)
        state["s8"]["moisture_pct"]= round(BASE["s8"]["moisture_pct"] / sf, 3)
        state["s9"]["prod_moisture"]= round(BASE["s9"]["prod_moisture"] / sf, 3)
        if fp < 0.5:
            affected = {"s6","s7","s8","s9"}
            msgs = {
                "s6": (RED,   f"Flocculant at {int(value)}% of target. Turbidity {state['s6']['turbidity']} NTU. Bed level CRITICAL {state['s6']['bed_pct']}%. Rake torque {state['s6']['rake_torq']}%"),
                "s7": (RED,   f"Contaminated green liquor. Crystal size {state['s7']['crystal_um']} µm — too fine. Yield {state['s7']['yield_gl']} g/L"),
                "s8": (AMBER, f"Lower quality hydrate feed. Product moisture risk {state['s8']['moisture_pct']}%"),
                "s9": (AMBER, f"Product moisture {state['s9']['prod_moisture']}% — approaching 0.5% shipping hazard threshold"),
            }
        else:
            affected = {"s6","s7"}
            msgs = {
                "s6": (AMBER, f"Reduced flocculant. Turbidity {state['s6']['turbidity']} NTU — monitor closely"),
                "s7": (AMBER, f"Minor crystal reduction to {state['s7']['crystal_um']} µm"),
            }

    elif scenario == "vessel_delay":
        delay = value
        state["s9"]["vessel_eta"]  = BASE["s9"]["vessel_eta"] + delay
        state["s9"]["silo_pct"]    = min(98, BASE["s9"]["silo_pct"] + int(delay*6))
        state["s9"]["port_stock_t"]= min(200000, int(BASE["s9"]["port_stock_t"] + delay*11500))
        if state["s9"]["silo_pct"] > 90:
            thr = max(0.4, 1 - (state["s9"]["silo_pct"]-85)/100)
            state["s8"]["feed_tph"]  = round(BASE["s8"]["feed_tph"]  * thr, 1)
            state["s7"]["yield_gl"]  = round(BASE["s7"]["yield_gl"]  * (0.78+0.22*thr), 1)
            state["s5"]["feed_tph"]  = int(BASE["s5"]["feed_tph"]    * thr)
            state["s3"]["haul_tph"]  = int(BASE["s3"]["haul_tph"]    * (0.68+0.32*thr))
            affected = {"s9","s8","s7","s5","s3"}
            msgs = {
                "s9": (RED,   f"Vessel delayed +{delay:.0f} days (ETA {state['s9']['vessel_eta']:.1f} days). Silos CRITICAL at {state['s9']['silo_pct']}%. Port stock {state['s9']['port_stock_t']:,} t"),
                "s8": (RED,   f"Production throttled to {state['s8']['feed_tph']} t/hr to prevent silo overflow. Kiln energy waste"),
                "s7": (AMBER, f"Precipitation rate reduced. Hydrate accumulating in tanks"),
                "s5": (AMBER, f"Digestion throughput cut to {state['s5']['feed_tph']} t/hr. Caustic circuit rebalancing needed"),
                "s3": (AMBER, f"Mine output throttled to {state['s3']['haul_tph']:,} t/hr. Opportunity for maintenance"),
            }
        elif delay > 2:
            affected = {"s9"}
            msgs = {"s9": (AMBER, f"Vessel delayed +{delay:.0f} days. Silo at {state['s9']['silo_pct']}% — begin throttle plan")}

    return state, affected, msgs

# ── OPTIMISE PLANS ────────────────────────────────────────────────────────────
OPT = {
    "reduced_trucks": {
        "title": "Fleet Optimisation — Reduced Haulage Capacity",
        "actions": [
            ("S3 Haulage",    "Maximise remaining truck payloads to rated 185 t. One fully-loaded truck outperforms two under-loaded. Brief operators immediately.",            "immediate"),
            ("S3 Routing",    "Consolidate dig faces to shortest-cycle routes. Reassign loaders to reduce travel-loaded time by ~15%. Reduce queue time at ROM pad.",          "immediate"),
            ("S4 Crushing",   "Reduce primary crusher gap 10% to improve throughput per tonne on reduced feed. Accept slightly coarser output temporarily.",                  "short_term"),
            ("S5 Digestion",  "If feed drops >15%, reduce digestion temperature to 140°C conserving steam and caustic while throughput is constrained.",                      "short_term"),
            ("S8 Calcination","Idle one kiln train at 600°C standby — allows rapid restart without full heat-up cycle. Run single train at full capacity.",                   "short_term"),
            ("S9 Port",       "Notify port operator and vessel agent of 48-72 hr production delay. Resequence berth to avoid demurrage charges.",                             "immediate"),
            ("S2 Blast Prep", "Advance the next planned blast to build ROM stockpile buffer before truck return to full fleet.",                                               "medium_term"),
        ],
    },
    "oversized_rock": {
        "title": "Fragmentation Optimisation — Oversized Rock Event",
        "actions": [
            ("S2 Blast Design",      "Halt new production blasts. Engage blast engineer to redesign drill pattern — reduce burden/spacing 10-15%, increase explosive energy per hole.",      "immediate"),
            ("S2 Secondary Blast",   "Deploy rock-breaker or secondary blast on identified oversized zones before excavation resumes. Photo-document fragment distribution.",               "immediate"),
            ("S4 Crusher Gap",       "Widen jaw crusher gap from 150 mm to 180 mm to pass material without jamming. Accept coarser output, compensate at screen.",                        "immediate"),
            ("S4 Feed Rate",         "Reduce primary crusher feed rate 20% to protect bearings and prevent motor overload. Monitor vibration sensors continuously.",                       "immediate"),
            ("S5 Digestion Adjust",  "Extend residence time 10% and raise caustic to 245 g/L to compensate for coarser particles reducing surface area.",                                  "short_term"),
            ("S3 Truck Payload",     "Reduce truck payload to 165 t to prevent tyre damage from irregular large rock. Increase cycle frequency to partially compensate.",                  "immediate"),
            ("S4 Maintenance",       "Schedule unplanned bearing inspection and liner wear measurement after event. Replace if wear exceeds 20 mm.",                                       "short_term"),
        ],
    },
    "high_dig_temp": {
        "title": "Digestion Temperature Recovery",
        "actions": [
            ("S5 Temperature",   "Reduce steam supply pressure gradually (−0.2 bar per 30 min) to bring digester to 144°C. Avoid rapid cooldown — thermal shock risks pipe cracking.",  "immediate"),
            ("S5 Caustic",       "Increase caustic make-up feed rate to restore NaOH to 235 g/L. Verify caustic meter calibration — sensor drift is common cause of oversteering.",       "immediate"),
            ("S5 Pipe Integrity","Schedule ultrasonic wall-thickness inspection on digester outlet lines and flash tanks within 48 hrs. High temp accelerates erosion-corrosion.",        "short_term"),
            ("S6 Flocculant",    "Increase flocculant dosage +15-20 g/t immediately to counter elevated silica in liquor. Switch to high-performance starch flocculant if NTU >25.",     "immediate"),
            ("S6 Thickener",     "Monitor thickener bed levels hourly. If bed >75%, increase underflow pump speed to prevent overflow contamination into green liquor.",                   "immediate"),
            ("S7 Seeding",       "Lower seed addition rate 10% to promote crystal growth over new nucleation. This restores D50 crystal size to spec range.",                             "short_term"),
            ("S5 PID Tuning",    "Root cause: PID controller overshoot. Schedule re-tuning of temperature control loop during next planned outage.",                                      "medium_term"),
        ],
    },
    "poor_flocculant": {
        "title": "Clarification Recovery — Flocculant Failure",
        "actions": [
            ("S6 Dosing Emergency",  "Restore flocculant to minimum 45 g/t immediately. Check dosing line blockage, pump failure, and reagent tank levels.",                              "immediate"),
            ("S6 Backup Reagent",    "If primary flocculant unavailable, switch to backup polyacrylamide (tank C2) at 60 g/t. Log reagent consumption for root cause.",                  "immediate"),
            ("S6 Feed Reduction",    "Reduce thickener feed 30% to extend residence time and allow bed to settle. Accept throughput reduction over contaminated product.",                "immediate"),
            ("S6 Red Mud",           "Increase underflow pump speed to draw down elevated bed. Do not exceed 1,600 kg/m³ — pipeline blockage risk at higher density.",                    "immediate"),
            ("S7 Hold Precipitators","If turbidity >25 NTU, halt green liquor transfer to precipitators. Do not contaminate the crystal batch with solids.",                              "immediate"),
            ("S8 Quality Sampling",  "Increase alumina product sampling to 1-hr intervals. Check LOI and soda content — flag any batch exceeding smelter specification.",                 "short_term"),
            ("S9 Product Hold",      "Place last 8 hrs of alumina output on quality hold pending lab analysis before rail loading. Alert vessel agent of possible delay.",                "short_term"),
        ],
    },
    "vessel_delay": {
        "title": "Supply Chain Recovery — Vessel Delay",
        "actions": [
            ("S9 Port Coord",       "Contact vessel agent and port authority. Explore: alternate berth, vessel acceleration, or partial load onto available smaller vessel.",            "immediate"),
            ("S9 Storage",          "Activate all 4 silo trains and any emergency bulk storage at refinery. Target max 85% fill across all silos to maintain buffer.",                   "immediate"),
            ("S8 Calcination",      "Reduce calcination feed to 35 t/hr on one train. Maintain second train at full rate to blend product grades and preserve quality.",                 "immediate"),
            ("S7 Precipitation",    "Extend precipitator residence time 36→42 hr — produces larger crystals, better filtration, buying ~6 hrs of downstream capacity.",                 "short_term"),
            ("S5 Digestion",        "Reduce digestion throughput 15%. Use saved steam for energy recovery. Communicate downstream constraint to mine operations.",                        "short_term"),
            ("S3 Mine Schedule",    "Reduce haulage to shift-minimum. Advance maintenance, road grading, and drill pattern prep for next blast during idle time.",                       "short_term"),
            ("S9 Commercial",       "Alert commercial team to explore spot vessel charter. Calculate demurrage cost vs. production hold to determine optimal financial response.",        "immediate"),
        ],
    },
}

# ── HELPER CHARTS ─────────────────────────────────────────────────────────────
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=4, r=4, t=40, b=4),
    font=dict(color=TXT, size=13),
)

def _layout(**overrides):
    d = dict(**CHART_LAYOUT)
    d.update(overrides)
    return d

def _ax(show_grid=True):
    base = dict(tickfont=dict(color=MUTED, size=11), gridcolor=BORDER, showline=False)
    if not show_grid:
        base["showgrid"] = False
    return base

def trend_fig(df, col, title, color=BLUE, height=195):
    r, g, b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
    fig = go.Figure(go.Scatter(
        x=df["ts"], y=df[col], mode="lines",
        line=dict(color=color, width=2),
        fill="tozeroy", fillcolor=f"rgba({r},{g},{b},0.08)",
    ))
    fig.update_layout(**CHART_LAYOUT, height=height,
        title=dict(text=title, font=dict(size=15, color=TXT)),
        xaxis=_ax(False) | dict(showticklabels=False),
        yaxis=_ax(),
        showlegend=False,
    )
    return fig

def gauge_fig(val, title, lo, hi, warn_lo, warn_hi, unit="", crit_lo=None, crit_hi=None, height=155):
    crit_lo = crit_lo or lo
    crit_hi = crit_hi or hi
    c = RED if (val <= crit_lo or val >= crit_hi) else AMBER if (val <= warn_lo or val >= warn_hi) else GREEN
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        number=dict(suffix=f" {unit}", font=dict(color=c, size=22)),
        title=dict(text=title, font=dict(color=TXT, size=13)),
        gauge=dict(
            axis=dict(range=[lo, hi], tickcolor=MUTED, tickfont=dict(color=MUTED, size=10)),
            bar=dict(color=c, thickness=0.22),
            bgcolor=CARD, bordercolor=BORDER,
            steps=[
                dict(range=[lo,    warn_lo], color="rgba(239,68,68,0.12)"),
                dict(range=[warn_lo,warn_hi],color="rgba(16,185,129,0.1)"),
                dict(range=[warn_hi, hi],    color="rgba(239,68,68,0.12)"),
            ],
            threshold=dict(line=dict(color=c, width=2), thickness=0.72, value=val),
        ),
    ))
    fig.update_layout(**CHART_LAYOUT, height=height)
    return fig

def pipeline_fig(affected=set(), height=115):
    ids  = [s["id"]  for s in STAGES]
    nums = [s["num"] for s in STAGES]
    xs   = [i * 1.22 for i in range(9)]
    fig  = go.Figure()
    for i in range(8):
        fig.add_annotation(
            x=xs[i]+0.82, y=0, ax=xs[i]+0.42, ay=0,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=2, arrowsize=1.4,
            arrowwidth=2, arrowcolor=BORDER,
        )
    labels = ["1\nLand\nClearing","2\nDrill\n& Blast","3\nHaulage","4\nCrushing",
              "5\nDigestion","6\nClarific.","7\nPrecip.","8\nCalcin.","9\nPort"]
    for i, (sid, lbl) in enumerate(zip(ids, labels)):
        hit   = sid in affected
        fc    = "rgba(239,68,68,0.18)" if hit else "rgba(0,87,168,0.2)"
        bc    = RED if hit else BLUE
        fig.add_shape(type="rect", x0=xs[i]-0.38, y0=-0.58, x1=xs[i]+0.38, y1=0.58,
                      fillcolor=fc, line=dict(color=bc, width=2))
        fig.add_annotation(x=xs[i], y=0, text=lbl.replace("\n","<br>"),
                           showarrow=False, font=dict(color=TXT, size=11), align="center")
    fig.update_layout(**_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8),
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False, range=[-0.55, 10.2]),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False, range=[-1, 1]),
    ))
    return fig

def sankey_fig(s):
    h_rate = s["s3"]["haul_tph"]
    cr_out = s["s4"]["throughput"]
    dig_fd = s["s5"]["feed_tph"]
    red_mu = int(dig_fd * 0.34)
    g_liq  = int(dig_fd * 0.66)
    hydrat = s["s8"]["feed_tph"] * 1.1
    al2o3  = round(s["s8"]["feed_tph"] * 0.87)
    nodes  = ["Bauxite\nMined","Crushed\nOre","Digestion\nFeed","Green\nLiquor",
              "Hydrate\nCrystals","Alumina\nAl₂O₃","Red\nMud"]
    colors = [CYAN, BLUE, "#0066cc", GREEN, AMBER, "#10B981", "#92400E"]
    fig = go.Figure(go.Sankey(
        node=dict(label=nodes, color=colors, pad=22, thickness=22,
                  line=dict(color="rgba(0,0,0,0)"),
                  hoverlabel=dict(font=dict(size=13))),

        link=dict(
            source=[0,1,2,2,3,4],
            target=[1,2,3,6,4,5],
            value =[h_rate, cr_out, g_liq, red_mu, hydrat, al2o3],
            color =["rgba(0,180,216,.28)","rgba(0,87,168,.28)","rgba(16,185,129,.25)",
                    "rgba(146,64,14,.25)","rgba(245,158,11,.25)","rgba(16,185,129,.25)"],
        ),
    ))
    fig.update_layout(**_layout(
        title=dict(text="Material flow — bauxite to alumina (t/hr)", font=dict(color=TXT, size=15)),
        height=320, margin=dict(l=8, r=8, t=46, b=8),
        font=dict(color=TXT, size=14),
    ))
    return fig

def energy_fig(s):
    labels = ["S4 Crushing","S5 Digestion","S7 Precipitation","S8 Calcination"]
    vals = [
        s["s4"]["throughput"] * 0.0038,
        s["s5"]["feed_tph"]   * s["s5"]["steam_gjt"] * 0.029,
        s["s7"]["agitator_pct"] * 0.77,
        s["s8"]["feed_tph"]   * s["s8"]["energy_gjt"] * 0.48,
    ]
    fig = go.Figure(go.Bar(
        x=labels, y=[round(v,1) for v in vals],
        marker_color=[CYAN, BLUE, "#7C3AED", RED],
        text=[f"{v:.1f}" for v in vals], textposition="auto", textfont=dict(color="white", size=11),
    ))
    fig.update_layout(**CHART_LAYOUT,
        title=dict(text="Energy consumption by stage (MW)", font=dict(color=TXT, size=15)),
        height=240, xaxis=_ax(False), yaxis=_ax() | dict(title=dict(text="MW", font=dict(color=MUTED, size=12))),
    )
    return fig

def compare_fig(sim, affected):
    keys = [
        ("s3","haul_tph",  "S3 Haulage"),
        ("s4","throughput","S4 Crusher"),
        ("s5","feed_tph",  "S5 Digestion"),
        ("s6","liquor_m3h","S6 Liquor"),
        ("s7","yield_gl",  "S7 Yield×10"),
        ("s8","feed_tph",  "S8 Calciner"),
    ]
    scale = [1,1,1,1,10,1]
    lbls  = [k[2] for k in keys]
    base  = [BASE[k[0]][k[1]] * sc for k,sc in zip(keys,scale)]
    simv  = [sim [k[0]][k[1]] * sc for k,sc in zip(keys,scale)]
    colors = [RED if sv < bv*0.95 else GREEN for sv,bv in zip(simv, base)]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Baseline",  x=lbls, y=base,  marker_color=BLUE, opacity=0.65))
    fig.add_trace(go.Bar(name="Simulated", x=lbls, y=simv,  marker_color=colors))
    fig.update_layout(**CHART_LAYOUT,
        barmode="group", height=270,
        title=dict(text="Stage throughput — baseline vs simulated", font=dict(color=TXT, size=15)),
        xaxis=_ax(False), yaxis=_ax(),
        legend=dict(font=dict(color=TXT, size=12), bgcolor="rgba(0,0,0,0)"),
    )
    return fig

def frag_dist_fig(d50=185):
    sizes   = np.array([25,50,75,100,150,200,250,300,400], dtype=float)
    k       = d50 / 185
    passing = np.clip(np.array([5,12,22,36,56,74,87,95,100]) * (1/k)**0.35, 0, 100)
    passing[-1] = 100
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sizes, y=passing, mode="lines+markers",
        line=dict(color=BLUE, width=2), fill="tozeroy", fillcolor="rgba(0,87,168,0.1)"))
    fig.add_vline(x=d50, line_dash="dash", line_color=GREEN,
        annotation_text=f"D50={d50:.0f}mm", annotation_font=dict(color=GREEN, size=10))
    fig.update_layout(**CHART_LAYOUT,
        title=dict(text="Post-blast fragment size distribution", font=dict(color=TXT, size=15)),
        height=210,
        xaxis=_ax(False)|dict(title=dict(text="Fragment size (mm)", font=dict(color=MUTED, size=12))),
        yaxis=_ax()     |dict(title=dict(text="% Passing",          font=dict(color=MUTED, size=12))),
    )
    return fig

def crystal_dist_fig(d50=78):
    xs  = np.linspace(10, 200, 60)
    ys  = np.exp(-((xs - d50)**2) / (2*18**2))
    fig = go.Figure(go.Bar(x=xs, y=ys, marker_color=CYAN, opacity=0.75))
    fig.add_vline(x=d50, line_dash="dash", line_color=GREEN,
        annotation_text=f"D50={d50}µm", annotation_font=dict(color=GREEN, size=10))
    fig.update_layout(**CHART_LAYOUT,
        title=dict(text="Crystal size distribution (µm)", font=dict(color=TXT, size=15)),
        height=205,
        xaxis=_ax(False)|dict(title=dict(text="Crystal size (µm)", font=dict(color=MUTED, size=12))),
        yaxis=_ax()     |dict(showticklabels=False),
    )
    return fig

def kiln_temp_fig():
    zones = ["Inlet","Zone 1\n(drying)","Zone 2\n(dehydration)","Zone 3\n(calcination)","Discharge"]
    temps = [45, 450, 850, 1050, 280]
    cols  = [CYAN, AMBER, AMBER, RED, CYAN]
    fig = go.Figure(go.Scatter(
        x=zones, y=temps, mode="lines+markers",
        line=dict(color=RED, width=2.5),
        marker=dict(size=9, color=cols),
        fill="tozeroy", fillcolor="rgba(239,68,68,0.07)",
    ))
    fig.add_hrect(y0=1000, y1=1100, fillcolor="rgba(16,185,129,0.1)", line_width=0,
        annotation_text="Target zone", annotation_font=dict(color=GREEN, size=11))
    fig.update_layout(**CHART_LAYOUT,
        title=dict(text="Kiln temperature profile (°C)", font=dict(color=TXT, size=15)),
        height=230,
        xaxis=_ax(False), yaxis=_ax(),
    )
    return fig

def silo_fig():
    silos  = ["Silo A","Silo B","Silo C","Silo D"]
    levels = [81, 74, 82, 75]
    cols   = [RED if l>90 else AMBER if l>85 else GREEN for l in levels]
    fig = go.Figure(go.Bar(
        x=silos, y=levels, marker_color=cols,
        text=[f"{l}%" for l in levels], textposition="inside", textfont=dict(color="white", size=12),
    ))
    fig.add_hline(y=85, line_dash="dash", line_color=AMBER,
        annotation_text="85% warning", annotation_font=dict(color=AMBER, size=11))
    fig.add_hline(y=95, line_dash="dash", line_color=RED,
        annotation_text="95% critical", annotation_font=dict(color=RED, size=11))
    fig.update_layout(**CHART_LAYOUT,
        title=dict(text="Alumina silo levels (%)", font=dict(color=TXT, size=15)),
        height=250, xaxis=_ax(False), yaxis=_ax()|dict(range=[0,105]), showlegend=False,
    )
    return fig

def fleet_fig():
    names   = [f"T{i:02d}" for i in range(1,16)]
    status  = ["Active"]*12 + ["Maintenance"]*2 + ["Standby"]*1
    payload = [round(185+np.random.randn()*7) for _ in range(12)] + [0,0,0]
    cols    = [GREEN if s=="Active" else RED if s=="Maintenance" else AMBER for s in status]
    fig = go.Figure(go.Bar(x=names, y=payload, marker_color=cols, showlegend=False,
        text=[f"{p}t" if p>0 else "" for p in payload],
        textposition="inside", textfont=dict(color="white", size=9),
    ))
    fig.update_layout(**CHART_LAYOUT,
        title=dict(text="Fleet payload (t) — green=active, red=maintenance", font=dict(color=TXT, size=15)),
        height=230, xaxis=_ax(False), yaxis=_ax()|dict(range=[0,220]),
    )
    return fig

# ── SNOWFLAKE CORTEX HELPERS ──────────────────────────────────────────────────
try:
    import snowflake.connector as _sf_module
    _SNOWFLAKE_AVAILABLE = True
except ImportError:
    _SNOWFLAKE_AVAILABLE = False

@st.cache_resource
def _sf_conn():
    if not _SNOWFLAKE_AVAILABLE:
        return None
    return _sf_module.connect(
        connection_name=os.getenv("SNOWFLAKE_CONNECTION_NAME") or "sfcogsops-snowhouse_aws_us_west_2"
    )

def cortex_complete(prompt: str) -> str:
    if not _SNOWFLAKE_AVAILABLE:
        return (
            "**Cortex AI is not available in this deployment.**\n\n"
            "This feature requires a Snowflake connection. "
            "You can still use the scenario sliders above to explore process impacts manually."
        )
    for model in ["claude-3-5-sonnet", "mistral-large2", "llama3.1-70b"]:
        try:
            conn = _sf_conn()
            cur  = conn.cursor()
            cur.execute("SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)", (model, prompt))
            row = cur.fetchone()
            if row and row[0]:
                return row[0].strip()
        except Exception:
            continue
    return "_Cortex AI unavailable — please check your Snowflake connection._"

def parse_question(text: str):
    """Map free-text question → (scenario_key, slider_value)."""
    t = text.lower()
    # Vessel / port delay
    if any(w in t for w in ["vessel", "ship", "port delay", "berth", "delayed"]):
        hours = re.search(r'(\d+)\s*h(our)?s?', t)
        days  = re.search(r'(\d+)\s*day', t)
        delay = 1.0
        if hours: delay = int(hours.group(1)) / 24
        elif days: delay = float(days.group(1))
        return "vessel_delay", min(10, max(0, round(delay)))
    # Reduced trucks / fleet
    if any(w in t for w in ["truck", "fleet", "haul", "vehicle", "fewer truck", "less truck"]):
        for n in re.findall(r'\d+', t):
            if 2 <= int(n) <= 15:
                return "reduced_trucks", int(n)
        return "reduced_trucks", 7
    # Oversized rock / blast
    if any(w in t for w in ["rock", "blast", "fragment", "oversize", "large rock", "d50"]):
        for n in re.findall(r'\d+', t):
            if 100 <= int(n) <= 600:
                return "oversized_rock", int(n)
        return "oversized_rock", 300
    # High digestion temperature
    if any(w in t for w in ["digestion temp", "digester", "caustic", "high temp", "temperature spike"]):
        for n in re.findall(r'\d+', t):
            if 140 <= int(n) <= 185:
                return "high_dig_temp", int(n)
        return "high_dig_temp", 168
    # Poor flocculant / clarification
    if any(w in t for w in ["flocculant", "clarif", "turbid", "settling", "thickener"]):
        for n in re.findall(r'\d+', t):
            if 10 <= int(n) <= 100:
                return "poor_flocculant", int(n)
        return "poor_flocculant", 30
    return "none", 0

def build_prompt(question: str, scenario: str, value: float,
                 sim_state: dict, affected: set, msgs: dict) -> str:
    b = BASE
    baseline = (
        f"CURRENT PLANT STATE:\n"
        f"- S2 Drill & Blast: fragment D50 {b['s2']['frag_d50']}mm, blast efficiency {b['s2']['blast_eff']}%\n"
        f"- S3 Haulage: {b['s3']['trucks']}/{b['s3']['max_trucks']} trucks active, {b['s3']['haul_tph']:,} t/hr, cycle {b['s3']['cycle_min']} min\n"
        f"- S4 Crushing: {b['s4']['throughput']:,} t/hr, motor {b['s4']['motor_pct']}%, particle D80 {b['s4']['particle_d80']}mm\n"
        f"- S5 Digestion: {b['s5']['temp_c']}°C, {b['s5']['pressure_bar']} bar, caustic {b['s5']['caustic_gl']} g/L, Al₂O₃ extraction {b['s5']['al2o3_pct']}%\n"
        f"- S6 Clarification: {b['s6']['turbidity']} NTU turbidity, flocculant {b['s6']['flocculant_gt']} g/t, bed {b['s6']['bed_pct']}%\n"
        f"- S7 Precipitation: crystal D50 {b['s7']['crystal_um']}µm, yield {b['s7']['yield_gl']} g/L, residence {b['s7']['res_time_h']} hr\n"
        f"- S8 Calcination: Zone 3 {b['s8']['temp_z3']}°C, feed {b['s8']['feed_tph']} t/hr, energy {b['s8']['energy_gjt']} GJ/t\n"
        f"- S9 Port: silos {b['s9']['silo_pct']}% full, stockpile {b['s9']['port_stock_t']:,} t, vessel ETA {b['s9']['vessel_eta']} days\n"
    )
    sim_block = ""
    if scenario != "none" and affected:
        alumina_base = round(b["s8"]["feed_tph"] * 0.87 * 24)
        alumina_sim  = round(sim_state["s8"]["feed_tph"] * 0.87 * 24)
        sim_block = (
            f"\nSIMULATED IMPACT FROM THIS SCENARIO:\n"
            + "".join(
                f"- Stage {int(sid[1])} ({STAGES[int(sid[1])-1]['name']}): {msg}\n"
                for sid, (_, msg) in msgs.items()
            )
            + f"\nQuantified output delta: daily alumina {alumina_sim:,} t "
              f"(baseline {alumina_base:,} t, change {alumina_sim-alumina_base:+,} t/day). "
              f"Haulage: {sim_state['s3']['haul_tph']:,} t/hr. "
              f"Al₂O₃ extraction: {sim_state['s5']['al2o3_pct']}%. "
              f"Clarifier turbidity: {sim_state['s6']['turbidity']} NTU.\n"
        )
    actions_block = ""
    if scenario in OPT:
        actions_block = "\nPRE-CALCULATED RECOVERY ACTIONS:\n" + "".join(
            f"- [{t.upper().replace('_',' ')}] {lbl}: {act}\n"
            for lbl, act, t in OPT[scenario]["actions"]
        )
    return (
        "You are a senior operations advisor for Alcoa Australia's Huntly bauxite mine and Pinjarra alumina refinery. "
        "You have deep expertise in the Bayer Process and the full pit-to-port value chain.\n\n"
        f"{baseline}{sim_block}{actions_block}\n"
        f"Operator question: \"{question}\"\n\n"
        "Write a comprehensive yet concise response in exactly 4 short paragraphs:\n"
        "1. Briefly explain what is happening and the root cause.\n"
        "2. Which stages are affected and the quantified impact on production — use the numbers from the data above.\n"
        "3. Prioritised actions the operator must take, starting with immediate steps.\n"
        "4. Key metrics to watch and escalation triggers.\n"
        "Be direct and operational. Reference specific numbers. No markdown headers. Australian English."
    )

# ── MINE / PORT COORDINATES ───────────────────────────────────────────────────
MINE_LAT,  MINE_LON  = -32.524, 116.063   # Huntly Mine centre (Darling Range, WA)
PORT_LAT,  PORT_LON  = -32.192, 115.762   # Kwinana Bulk Terminal

# ── FLEET DEFINITIONS ─────────────────────────────────────────────────────────
# (type_key, label, icon, hex_color, count, marker_size)
FLEET_DEF = [
    ("haul_truck",  "Haul Trucks",       "🚛", "#F59E0B", 20, 13),
    ("excavator",   "Excavators",        "⛏️",  "#EF4444",  5, 20),
    ("drill_rig",   "Drill Rigs",        "🔩",  "#8B5CF6",  6, 16),
    ("water_truck", "Water Trucks",      "💧",  "#06B6D4",  4, 14),
    ("bulldozer",   "Bulldozers",        "🏗️",  "#10B981",  7, 18),
    ("grader",      "Graders",           "🛤️",  "#F97316",  3, 14),
    ("service",     "Service Vehicles",  "🔧",  "#94A3B8",  8, 10),
    ("blast_unit",  "Blast Units",       "💥",  "#F43F5E",  3, 16),
]

@st.cache_data(ttl=20)
def _vehicle_df(time_slot: int) -> pd.DataFrame:
    rows = []
    for eq_type, label, icon, color, count, sz in FLEET_DEF:
        for i in range(count):
            rng_b = np.random.default_rng(99 + abs(hash(eq_type)) % 9999 + i)
            rng_t = np.random.default_rng(time_slot + abs(hash(eq_type)) % 999 + i * 7)
            lat = MINE_LAT + float(rng_b.normal(0, 0.025)) + float(rng_t.normal(0, 0.0016))
            lon = MINE_LON + float(rng_b.normal(0, 0.030)) + float(rng_t.normal(0, 0.0019))
            spd = float(rng_t.uniform(0, 33 if eq_type == "haul_truck" else 11))
            r   = float(rng_t.random())
            sts = "Maintenance" if r > 0.95 else "Idle" if r > 0.80 else "Operating"
            rows.append(dict(
                vid=f"{eq_type[:3].upper()}-{i+1:03d}",
                type=eq_type, label=label, icon=icon, color=color, sz=sz,
                lat=round(lat, 6), lon=round(lon, 6),
                speed=round(spd, 1), heading=int(rng_t.integers(0, 360)),
                status=sts,
                operator=f"OP-{int(rng_t.integers(1000, 9999))}",
                fuel=round(float(rng_b.uniform(30, 100)), 1),
                hours=round(float(rng_t.uniform(0, 11.5)), 1),
                payload=round(float(rng_t.uniform(0, 295)), 0) if eq_type == "haul_truck" else 0,
            ))
    return pd.DataFrame(rows)

# ── SHIP DATA ─────────────────────────────────────────────────────────────────
# Approximate great-circle dest coords for route lines
_DEST_COORDS = {
    "Kwinana, Australia": (PORT_LAT, PORT_LON),
    "Yokohama, Japan":    (35.44,  139.63),
    "Osaka, Japan":       (34.65,  135.43),
    "Tianjin, China":     (39.00,  117.70),
    "Singapore":          ( 1.28,  103.83),
}

SHIPS = [
    dict(name="MV Cape Peron",      flag="🇦🇺", type="Bulk Carrier",
         status="Loading at berth",   direction="at_berth",
         lat=PORT_LAT, lon=PORT_LON,  heading=0,   speed_kn=0.0,
         dest="Yokohama, Japan",      dist_nm=4870, eta_h=None, etd_h=6,
         cargo="Alumina",             volume_t=86_400, capacity_t=89_000,
         draft_m=12.1, loa_m=233, imo="IMO9345678", callsign="VMCU4",
         flag_country="Australia", built=2009, owner="Alcoa Shipping",
         last_port="Kwinana",         next_port="Yokohama"),
    dict(name="MV Alcoa Pacific",   flag="🇦🇺", type="Bulk Carrier",
         status="Underway",           direction="outbound",
         lat=-28.4, lon=111.2,        heading=335,  speed_kn=13.5,
         dest="Osaka, Japan",         dist_nm=3240, eta_h=4*24+18, etd_h=None,
         cargo="Alumina",             volume_t=82_100, capacity_t=84_000,
         draft_m=11.8, loa_m=228, imo="IMO9187654", callsign="VMAP2",
         flag_country="Australia", built=2006, owner="Alcoa Shipping",
         last_port="Kwinana",         next_port="Osaka"),
    dict(name="MV Southern Cross",  flag="🇸🇬", type="Bulk Carrier",
         status="Underway",           direction="outbound",
         lat=-22.5, lon=106.8,        heading=350,  speed_kn=12.8,
         dest="Tianjin, China",       dist_nm=5100, eta_h=8*24+6, etd_h=None,
         cargo="Alumina",             volume_t=77_900, capacity_t=80_000,
         draft_m=11.5, loa_m=224, imo="IMO9276543", callsign="9VRC8",
         flag_country="Singapore", built=2011, owner="Pacific Bulk Carriers",
         last_port="Kwinana",         next_port="Tianjin"),
    dict(name="MV Indian Endeavour",flag="🇸🇬", type="Bulk Carrier",
         status="Underway",           direction="inbound",
         lat=-26.8, lon=109.3,        heading=158,  speed_kn=13.1,
         dest="Kwinana, Australia",   dist_nm=1890, eta_h=2*24+22, etd_h=None,
         cargo="Ballast (empty)",     volume_t=0,   capacity_t=86_500,
         draft_m=5.2, loa_m=230, imo="IMO9312487", callsign="9VGT4",
         flag_country="Singapore", built=2008, owner="Eastern Pacific Shipping",
         last_port="Yokohama",        next_port="Kwinana"),
    dict(name="MV Fremantle Bulker",flag="🇬🇷", type="Bulk Carrier",
         status="Underway",           direction="inbound",
         lat=-30.9, lon=111.5,        heading=145,  speed_kn=12.2,
         dest="Kwinana, Australia",   dist_nm=790,  eta_h=1*24+15, etd_h=None,
         cargo="Ballast (empty)",     volume_t=0,   capacity_t=82_000,
         draft_m=4.8, loa_m=225, imo="IMO9403219", callsign="SVMX3",
         flag_country="Greece", built=2014, owner="Angelicoussis Group",
         last_port="Singapore",       next_port="Kwinana"),
    dict(name="MV Geraldton Spirit",flag="🇵🇦", type="Bulk Carrier",
         status="At anchor",          direction="at_anchor",
         lat=-32.285, lon=115.690,    heading=312,  speed_kn=0.0,
         dest="Kwinana, Australia",   dist_nm=8,    eta_h=4, etd_h=None,
         cargo="Ballast (empty)",     volume_t=0,   capacity_t=78_000,
         draft_m=4.5, loa_m=218, imo="IMO9445123", callsign="3FDK7",
         flag_country="Panama", built=2012, owner="Pacific Carriers Ltd",
         last_port="Qingdao",         next_port="Kwinana"),
]

def _eta_str(eta_h):
    if eta_h is None: return "N/A"
    d, h = divmod(int(eta_h), 24)
    return f"{d}d {h}h" if d else f"{h}h"

def _ship_color(direction):
    return {"outbound": "#F59E0B", "inbound": "#06B6D4",
            "at_berth": "#10B981", "at_anchor": "#0057A8"}.get(direction, MUTED)

# ── SIDEBAR NAVIGATION ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding:22px 0 14px 0;">
      <div style="font-size:2.2rem; margin-bottom:4px;">⛏️</div>
      <div style="font-size:1.25rem; font-weight:800; letter-spacing:1.5px; color:white;">ALCOA AUSTRALIA</div>
      <div style="font-size:0.78rem; color:rgba(255,255,255,0.6); margin-top:3px; letter-spacing:0.5px;">Operations Control Platform</div>
    </div>
    <hr style="border-color:rgba(255,255,255,0.18); margin:0 0 16px 0;">
    """, unsafe_allow_html=True)

    page = st.radio(
        "nav",
        [
            ":material/dashboard: Operations dashboard",
            ":material/science: Process simulator",
            ":material/gps_fixed: Vehicle tracker",
            ":material/directions_boat: Ship tracker",
        ],
        label_visibility="collapsed",
    )

    st.markdown("<hr style='border-color:rgba(255,255,255,0.18); margin:16px 0;'>", unsafe_allow_html=True)
    now = datetime.now()
    st.markdown(f"""
    <div style="text-align:center; font-size:0.78rem; color:rgba(255,255,255,0.55); line-height:1.9;">
      📍 Huntly Mine · Pinjarra Refinery<br>
      🕐 {now.strftime('%H:%M')} AWST &nbsp;|&nbsp; {now.strftime('%d %b %Y')}<br>
      <span style="color:rgba(255,255,255,0.35);">Powered by Snowflake</span>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 1 — OPERATIONS DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if ":material/dashboard:" in page:

    st.markdown(
        "<h1 style='margin:0; font-size:1.75rem;'>Operations Dashboard</h1>"
        "<p style='color:#94A3B8; margin:0 0 20px 0;'>Bauxite mining & alumina processing — live sensor overview · Huntly / Pinjarra</p>",
        unsafe_allow_html=True,
    )

    # ── Top KPI strip ──
    with st.container(horizontal=True):
        st.metric("Daily alumina output",  "11,520 t", "▲ +2.3% vs target",    border=True,
                  chart_data=list(HIST["alumina_tph"].tail(12)), chart_type="line")
        st.metric("Haulage rate",          "2,280 t/hr","▲ +1.2%",              border=True,
                  chart_data=list(HIST["haul_tph"].tail(12)),    chart_type="line")
        st.metric("Al₂O₃ extraction",      "91.2%",     "▲ Excellent",          border=True,
                  chart_data=list(HIST["caustic_gl"].tail(12)),  chart_type="line")
        st.metric("Crystal size D50",      "78 µm",     "● In spec",            border=True,
                  chart_data=list(HIST["crystal_um"].tail(12)),  chart_type="line")
        st.metric("Silo inventory",        "78%",       "● Good",               border=True,
                  chart_data=[78]*12,                            chart_type="bar")
        st.metric("System status",         "Nominal",   "1 advisory",           border=True)

    st.space("small")

    # ── Pipeline overview ──
    with st.container(border=True):
        st.markdown("**Pipeline flow overview**")
        st.plotly_chart(pipeline_fig(), use_container_width=True, config={"displayModeBar": False})

    # ── 24-hour trends ──
    st.subheader("24-hour trends")
    tc1, tc2, tc3, tc4 = st.columns(4)
    with tc1:
        with st.container(border=True):
            st.plotly_chart(trend_fig(HIST,"haul_tph","Haulage rate (t/hr)", CYAN), use_container_width=True, config={"displayModeBar":False})
    with tc2:
        with st.container(border=True):
            st.plotly_chart(trend_fig(HIST,"crusher_tph","Crusher output (t/hr)", BLUE), use_container_width=True, config={"displayModeBar":False})
    with tc3:
        with st.container(border=True):
            st.plotly_chart(trend_fig(HIST,"alumina_tph","Alumina production (t/hr)", GREEN), use_container_width=True, config={"displayModeBar":False})
    with tc4:
        with st.container(border=True):
            st.plotly_chart(trend_fig(HIST,"energy_mw","Total energy (MW)", AMBER), use_container_width=True, config={"displayModeBar":False})

    # ── Sankey + Energy ──
    sc1, sc2 = st.columns([3,2])
    with sc1:
        with st.container(border=True):
            st.plotly_chart(sankey_fig(BASE), use_container_width=True, config={"displayModeBar":False})
    with sc2:
        with st.container(border=True):
            st.plotly_chart(energy_fig(BASE), use_container_width=True, config={"displayModeBar":False})

    # ── Stage detail — button grid ──
    st.subheader("Stage-by-stage detail")
    st.caption("Select a stage to view live sensor data")

    if "active_stage" not in st.session_state:
        st.session_state["active_stage"] = 0

    # CSS for stage buttons — uniform look, primary type handles active highlight
    st.markdown("""
    <style>
      .stage-btn-wrap button {
        background: #0D2137 !important;
        border: 1px solid #1E3A5F !important;
        color: #94A3B8 !important;
        border-radius: 10px !important;
        font-size: 0.82rem !important;
        padding: 0.6em 0.4em !important;
        line-height: 1.5 !important;
      }
      .stage-btn-wrap button:hover {
        border-color: #0057A8 !important;
        color: #E2E8F0 !important;
        background: #0F2848 !important;
      }
    </style>
    """, unsafe_allow_html=True)

    # Stage metadata for buttons
    STAGE_BTN = [
        ("S1", "🌿", "Land\nClearing"),
        ("S2", "💥", "Drill\n& Blast"),
        ("S3", "🚛", "Excavation\n& Haulage"),
        ("S4", "⚙️", "Crushing\n& Screening"),
        ("S5", "🧪", "Digestion"),
        ("S6", "💧", "Clarification"),
        ("S7", "❄️", "Precipitation"),
        ("S8", "🔥", "Calcination"),
        ("S9", "🚢", "Port &\nShipping"),
    ]

    # Render 3 rows × 3 cols of stage buttons
    for row_start in range(0, 9, 3):
        cols = st.columns(3, gap="small")
        for col_i, col in enumerate(cols):
            idx = row_start + col_i
            num_lbl, icon, name = STAGE_BTN[idx]
            with col:
                is_active = st.session_state["active_stage"] == idx
                label = f"{icon}  **{num_lbl}**  {name.replace(chr(10), ' · ')}"
                if is_active:
                    if st.button(label, key=f"sbtn_{idx}", use_container_width=True, type="primary"):
                        pass
                else:
                    st.markdown('<div class="stage-btn-wrap">', unsafe_allow_html=True)
                    if st.button(label, key=f"sbtn_{idx}", use_container_width=True):
                        st.session_state["active_stage"] = idx
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

    # Stage detail content
    active = st.session_state["active_stage"]
    num_lbl, icon, name = STAGE_BTN[active]
    st.space("small")
    with st.container(border=True):
        st.markdown(f"**{icon} Stage {active+1}: {STAGES[active]['name']}**")

        if active == 0:  # S1 Land Clearing
            with st.container(horizontal=True):
                st.metric("Hectares cleared today","3.2 ha",  "On schedule",       border=True)
                st.metric("Soil moisture",          "18.5%",  "● Seed bank safe",  border=True)
                st.metric("Wind speed",             "12.3 km/h","✓ Safe",           border=True)
                st.metric("Ambient temp",           "24.1°C", "",                  border=True)
                st.metric("Dozer utilisation",      "78%",    "+3%",               border=True)
            st.success("3× Cat D10 dozers operational. Topsoil stockpile moisture optimal. Next LiDAR survey 06:00 AWST.", icon=":material/check_circle:")

        elif active == 1:  # S2 Drill & Blast
            with st.container(horizontal=True):
                st.metric("Fragment size D50","185 mm",  "✓ Target",              border=True)
                st.metric("Blast efficiency","87%",      "+2%",                   border=True)
                st.metric("Ground vib (PPV)","8.2 mm/s", "✓ Well below 20 limit",border=True)
                st.metric("Holes drilled",  "124",       "On plan",               border=True)
            st.plotly_chart(frag_dist_fig(185), use_container_width=True, config={"displayModeBar":False})

        elif active == 2:  # S3 Haulage
            with st.container(horizontal=True):
                st.metric("Active trucks",  "12 / 15",   "3 in maintenance",border=True)
                st.metric("Avg payload",    "185 t",      "✓ Optimal",       border=True)
                st.metric("Cycle time",     "28 min",     "−1 min",          border=True)
                st.metric("Haul rate",      "2,280 t/hr", "▲ +1.2%",        border=True)
                st.metric("Fuel rate",      "142 L/hr",   "",                border=True)
            st.plotly_chart(fleet_fig(), use_container_width=True, config={"displayModeBar":False})

        elif active == 3:  # S4 Crushing
            with st.container(horizontal=True):
                st.metric("Throughput",     "2,150 t/hr","▲ On target",  border=True)
                st.metric("Motor current",  "82%",        "● Normal",    border=True)
                st.metric("Particle D80",   "48 mm",      "✓ <50mm",    border=True)
                st.metric("Bearing vib",    "3.2 mm/s",   "● Good",     border=True)
                st.metric("Dust PM10",      "42 µg/m³",   "✓ Safe",     border=True)
            gc1, gc2, gc3 = st.columns(3)
            with gc1: st.plotly_chart(gauge_fig(82,  "Motor current (%)",     0,100,30,90,"%",  15,98), use_container_width=True, config={"displayModeBar":False})
            with gc2: st.plotly_chart(gauge_fig(48,  "Particle size D80 (mm)",0,100,10,50,"mm", 5, 80), use_container_width=True, config={"displayModeBar":False})
            with gc3: st.plotly_chart(gauge_fig(3.2, "Bearing vibration",     0,15, 0, 7,"mm/s",0,12), use_container_width=True, config={"displayModeBar":False})

        elif active == 4:  # S5 Digestion
            with st.container(horizontal=True):
                st.metric("Temperature",     "145°C",    "✓ 140-150 range",  border=True)
                st.metric("Pressure",        "3.8 bar",  "● Normal",          border=True)
                st.metric("Caustic NaOH",    "235 g/L",  "✓ Optimal",        border=True)
                st.metric("Al₂O₃ extraction","91.2%",    "▲ Excellent",       border=True)
                st.metric("Steam intensity", "8.4 GJ/t", "",                  border=True)
            gd1, gd2, gd3, gd4 = st.columns(4)
            with gd1: st.plotly_chart(gauge_fig(145, "Temperature (°C)",    100,200,140,150,"°C", 120,165), use_container_width=True, config={"displayModeBar":False})
            with gd2: st.plotly_chart(gauge_fig(3.8, "Pressure (bar)",      0,  10, 3.0,5.5,"bar",2.0,7.0), use_container_width=True, config={"displayModeBar":False})
            with gd3: st.plotly_chart(gauge_fig(235, "Caustic (g/L NaOH)", 150,300,220,250,"g/L",180,270), use_container_width=True, config={"displayModeBar":False})
            with gd4: st.plotly_chart(gauge_fig(91.2,"Al₂O₃ extraction (%)",75,100,88,95,"%",   82, 98), use_container_width=True, config={"displayModeBar":False})

        elif active == 5:  # S6 Clarification
            with st.container(horizontal=True):
                st.metric("Turbidity",         "12 NTU",   "✓ <20 target", border=True)
                st.metric("Flocculant",         "45 g/t",   "● Optimal",    border=True)
                st.metric("Thickener bed",      "62%",      "● Normal",     border=True)
                st.metric("Rake torque",        "35%",      "● Normal",     border=True)
                st.metric("Green liquor flow",  "545 m³/hr","",             border=True)
            ge1, ge2, ge3 = st.columns(3)
            with ge1: st.plotly_chart(gauge_fig(12, "Turbidity (NTU)",   0,80, 0, 20,"NTU",0,40), use_container_width=True, config={"displayModeBar":False})
            with ge2: st.plotly_chart(gauge_fig(62, "Thickener bed (%)", 0,100,20,80,"%",  10,92), use_container_width=True, config={"displayModeBar":False})
            with ge3: st.plotly_chart(gauge_fig(35, "Rake torque (%)",   0,100,10,65,"%",  5, 85), use_container_width=True, config={"displayModeBar":False})

        elif active == 6:  # S7 Precipitation
            with st.container(horizontal=True):
                st.metric("Crystal size D50","78 µm",  "✓ 70-90 target",border=True)
                st.metric("Yield",           "68 g/L", "▲ Good",         border=True)
                st.metric("Temperature",     "55°C",   "● Cooling OK",   border=True)
                st.metric("Residence time",  "36 hr",  "✓ Optimal",      border=True)
                st.metric("Agitator power",  "72%",    "",               border=True)
            st.plotly_chart(crystal_dist_fig(78), use_container_width=True, config={"displayModeBar":False})

        elif active == 7:  # S8 Calcination
            with st.container(horizontal=True):
                st.metric("Zone 3 temp",     "1,050°C",   "✓ 1000-1100 target",border=True)
                st.metric("Energy intensity","3.2 GJ/t",  "● Optimal",          border=True)
                st.metric("NOx emissions",   "180 mg/Nm³","✓ <500 limit",       border=True)
                st.metric("Product moisture","0.08%",     "✓ <0.5% spec",       border=True)
            st.plotly_chart(kiln_temp_fig(), use_container_width=True, config={"displayModeBar":False})

        elif active == 8:  # S9 Port & Shipping
            with st.container(horizontal=True):
                st.metric("Silo capacity",    "78%",        "● Good",            border=True)
                st.metric("Port stockpile",   "85,000 t",   "▲ Well stocked",    border=True)
                st.metric("Ship loading rate","2,400 t/hr", "● On target",       border=True)
                st.metric("Next vessel ETA",  "2.3 days",   "MV Pacific Star",   border=True)
                st.metric("Product moisture", "0.06%",      "✓ Well below 0.5%", border=True)
            st.plotly_chart(silo_fig(), use_container_width=True, config={"displayModeBar":False})


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 2 — PROCESS SIMULATOR
# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 2 — PROCESS SIMULATOR
# ══════════════════════════════════════════════════════════════════════════════
elif ":material/science:" in page:
    st.markdown(
        "<h1 style='margin:0; font-size:1.75rem;'>Process Simulator</h1>"
        "<p style='color:#94A3B8; margin:0 0 20px 0;'>Adjust operational parameters and observe cascading effects across the processing chain</p>",
        unsafe_allow_html=True,
    )

    # ── AI QUESTION PANEL ─────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            f"<div style='display:flex; align-items:center; gap:10px; margin-bottom:4px;'>"
            f"<span style='font-size:1.3rem;'>🤖</span>"
            f"<span style='font-weight:700; font-size:1rem; color:{TXT};'>Ask Cortex AI</span>"
            f"<span style='font-size:0.78rem; color:{MUTED}; margin-left:4px;'>Powered by Snowflake Cortex · claude-3-5-sonnet</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.caption("Describe any operational scenario in plain English — Cortex will simulate the impact with live plant data and advise on next steps.")

        q_col, btn_col = st.columns([5, 1], vertical_alignment="bottom")
        with q_col:
            user_q = st.text_area(
                "question",
                placeholder=(
                    'e.g. "The next vessel has been delayed by 24 hours, what do we need to adjust in the '
                    'processing plant to keep operations running smoothly?"'
                ),
                height=82,
                label_visibility="collapsed",
                key="ai_question_input",
            )
        with btn_col:
            ask_clicked = st.button(
                ":material/send: Ask Cortex",
                use_container_width=True,
                type="primary",
                key="ask_cortex_btn",
            )

        if ask_clicked and user_q.strip():
            with st.spinner("Simulating scenario and generating response…"):
                det_scenario, det_value = parse_question(user_q)
                det_state, det_affected, det_msgs = compute_state(det_scenario, det_value)
                prompt   = build_prompt(user_q, det_scenario, det_value, det_state, det_affected, det_msgs)
                response = cortex_complete(prompt)
            st.session_state["ai_response"]  = response
            st.session_state["ai_question"]  = user_q
            st.session_state["ai_scenario"]  = det_scenario
            st.session_state["ai_value"]     = det_value
            st.session_state["ai_affected"]  = det_affected

        if st.session_state.get("ai_response"):
            det_sc  = st.session_state.get("ai_scenario", "none")
            det_val = st.session_state.get("ai_value", 0)
            det_aff = st.session_state.get("ai_affected", set())

            SCENARIO_LABELS = {
                "none":            None,
                "reduced_trucks":  f"Reduced fleet → {int(det_val)} trucks active",
                "oversized_rock":  f"Oversized rock → D50 {int(det_val)} mm",
                "high_dig_temp":   f"High digestion temp → {int(det_val)}°C",
                "poor_flocculant": f"Poor flocculant → {int(det_val)}% of normal",
                "vessel_delay":    f"Vessel delayed → +{int(det_val)} day(s)",
            }
            lbl = SCENARIO_LABELS.get(det_sc)
            if lbl:
                st.markdown(
                    f"<div style='display:flex; align-items:center; gap:8px; margin:10px 0 2px 0;'>"
                    f"<span style='font-size:0.72rem; font-weight:700; letter-spacing:0.8px; color:{MUTED};'>CORTEX DETECTED SCENARIO</span>"
                    f"<span style='background:rgba(0,87,168,0.25); border:1px solid {BLUE}; color:{CYAN}; "
                    f"font-size:0.78rem; font-weight:600; padding:2px 10px; border-radius:10px;'>{lbl}</span>"
                    f"<span style='color:{MUTED}; font-size:0.72rem;'>· {len(det_aff)} stage(s) affected</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            resp_html = st.session_state["ai_response"].replace("\n\n", "</p><p>").replace("\n", " ")
            st.markdown(
                f"""
                <div style="background:rgba(0,87,168,0.08); border-left:3px solid {CYAN};
                            border-radius:0 10px 10px 0; padding:16px 20px; margin-top:10px;">
                  <p style="color:{TXT}; font-size:0.9rem; line-height:1.75; margin:0;">{resp_html}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(":material/close: Clear response", key="clear_ai"):
                for k in ("ai_response","ai_question","ai_scenario","ai_value","ai_affected"):
                    st.session_state.pop(k, None)
                st.rerun()

    st.space("small")

    ctrl_col, result_col = st.columns([1, 2.2], gap="large")

    with ctrl_col:
        with st.container(border=True):
            st.markdown("**⚙️ Simulation controls**")
            scenario = st.selectbox(
                "Select scenario",
                options=["none","reduced_trucks","oversized_rock","high_dig_temp","poor_flocculant","vessel_delay"],
                format_func=lambda x: {
                    "none":            "— Baseline (no change) —",
                    "reduced_trucks":  "S3 · Reduced haul truck fleet",
                    "oversized_rock":  "S2 · Oversized rock fragments",
                    "high_dig_temp":   "S5 · Digestion temperature spike",
                    "poor_flocculant": "S6 · Poor flocculant performance",
                    "vessel_delay":    "S9 · Port vessel delay",
                }[x],
            )

            slider_val = 0.0
            if scenario == "reduced_trucks":
                slider_val = st.slider("Active trucks", 4, 15, 8, 1)
                st.caption(f"Baseline 12 trucks · Simulating {slider_val} ({int(slider_val/15*100)}% of fleet)")
            elif scenario == "oversized_rock":
                slider_val = st.slider("Fragment D50 (mm)", 150, 400, 280, 10)
                st.caption(f"Baseline 185 mm · Simulating {slider_val} mm ({int((slider_val-185)/185*100):+d}%)")
            elif scenario == "high_dig_temp":
                slider_val = st.slider("Digestion temp (°C)", 140, 185, 165, 1)
                st.caption(f"Baseline 145°C · Simulating {slider_val}°C ({slider_val-145:+d}°C)")
            elif scenario == "poor_flocculant":
                slider_val = st.slider("Flocculant dosage (% of normal)", 20, 100, 35, 5)
                st.caption(f"Baseline 100% · Simulating {slider_val}%")
            elif scenario == "vessel_delay":
                slider_val = st.slider("Additional vessel delay (days)", 0, 10, 5, 1)
                st.caption(f"Baseline ETA 2.3 days · Simulating {2.3+slider_val:.1f} days")

        sim_state, affected, msgs = compute_state(scenario, slider_val)

        if scenario != "none" and affected:
            st.space("small")
            with st.container(border=True):
                st.markdown("**Affected stages**")
                for s in STAGES:
                    sid   = s["id"]
                    hit   = sid in affected
                    dot   = f"<span style='color:{RED};'>●</span>" if hit else f"<span style='color:{GREEN}; opacity:0.5;'>●</span>"
                    style = f"color:{TXT};" if hit else f"color:{MUTED}; opacity:0.55;"
                    st.markdown(f"<div style='{style} font-size:0.83rem; padding:2px 0;'>{dot} S{s['num']}: {s['name']}</div>", unsafe_allow_html=True)

    with result_col:
        if scenario == "none":
            with st.container(border=True):
                st.markdown("""
                <div style="text-align:center; padding:50px 20px;">
                  <div style="font-size:3rem; margin-bottom:12px;">🏭</div>
                  <div style="color:#E2E8F0; font-size:1.1rem; font-weight:600;">All systems nominal</div>
                  <div style="color:#94A3B8; margin-top:8px; font-size:0.9rem;">
                    Select a scenario from the controls panel to simulate operational changes<br>
                    and observe cascading effects across the processing chain.
                  </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            # Pipeline impact map
            with st.container(border=True):
                st.markdown("**Pipeline impact map**")
                st.plotly_chart(pipeline_fig(affected), use_container_width=True, config={"displayModeBar":False})

            # Throughput comparison
            with st.container(border=True):
                st.plotly_chart(compare_fig(sim_state, affected), use_container_width=True, config={"displayModeBar":False})

            # KPI delta row
            alumina_base = BASE["s8"]["feed_tph"] * 0.87 * 24
            alumina_sim  = sim_state["s8"]["feed_tph"] * 0.87 * 24
            with st.container(horizontal=True):
                st.metric("Daily alumina Δ",
                    f"{alumina_sim:,.0f} t",
                    f"{alumina_sim-alumina_base:+,.0f} t/day vs baseline",
                    border=True)
                haul_pct = (sim_state["s3"]["haul_tph"] - BASE["s3"]["haul_tph"]) / BASE["s3"]["haul_tph"] * 100
                st.metric("Haulage rate",
                    f"{sim_state['s3']['haul_tph']:,} t/hr",
                    f"{haul_pct:+.1f}%",
                    border=True)
                ext_delta = sim_state["s5"]["al2o3_pct"] - BASE["s5"]["al2o3_pct"]
                st.metric("Al₂O₃ extraction",
                    f"{sim_state['s5']['al2o3_pct']}%",
                    f"{ext_delta:+.1f}pp",
                    border=True)
                turb_delta = sim_state["s6"]["turbidity"] - BASE["s6"]["turbidity"]
                st.metric("Clarifier turbidity",
                    f"{sim_state['s6']['turbidity']} NTU",
                    f"{turb_delta:+.1f} NTU",
                    border=True)

            # Stage impact messages
            if msgs:
                st.subheader("Stage impact analysis")
                for sid, (col, msg) in msgs.items():
                    snum  = int(sid[1])
                    sname = STAGES[snum-1]["name"]
                    sev   = "CRITICAL" if col == RED else "WARNING" if col == AMBER else "INFO"
                    sev_c = RED if col == RED else AMBER if col == AMBER else CYAN
                    st.markdown(f"""
                    <div style="background:rgba({('239,68,68' if col==RED else '245,158,11' if col==AMBER else '0,180,216')},0.08);
                                border-left:3px solid {sev_c}; border-radius:0 8px 8px 0;
                                padding:10px 14px; margin:6px 0;">
                      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span style="color:{TXT}; font-weight:700; font-size:0.83rem;">Stage {snum}: {sname}</span>
                        <span style="color:{sev_c}; font-size:0.68rem; font-weight:800; letter-spacing:1px;
                                     background:rgba({('239,68,68' if col==RED else '245,158,11' if col==AMBER else '0,180,216')},0.15);
                                     padding:2px 8px; border-radius:10px;">{sev}</span>
                      </div>
                      <div style="color:#CBD5E1; font-size:0.84rem;">{msg}</div>
                    </div>
                    """, unsafe_allow_html=True)

            # ── OPTIMISE BUTTON ──
            st.space("small")
            if "show_opt" not in st.session_state:
                st.session_state["show_opt"] = False
            if scenario != "none":
                if st.button("🎯  Generate optimisation plan", type="primary", use_container_width=True):
                    st.session_state["show_opt"] = True

            if st.session_state.get("show_opt") and scenario != "none":
                rec = OPT.get(scenario)
                if rec:
                    st.space("small")
                    with st.container(border=True):
                        st.markdown(f"""
                        <div style="display:flex; align-items:center; gap:10px; margin-bottom:16px;">
                          <span style="font-size:1.4rem;">✅</span>
                          <span style="color:{GREEN}; font-size:1.05rem; font-weight:700;">{rec['title']}</span>
                        </div>
                        """, unsafe_allow_html=True)

                        timing_meta = {
                            "immediate":   (RED,   "⚡ Immediate"),
                            "short_term":  (AMBER, "📋 Short-term  (24-48 hr)"),
                            "medium_term": (CYAN,  "📅 Medium-term (1-2 wk)"),
                        }
                        for stage_lbl, action, timing in rec["actions"]:
                            tc, tl = timing_meta[timing]
                            st.markdown(f"""
                            <div style="border-left:3px solid {tc};
                                        border-radius:0 8px 8px 0;
                                        padding:10px 14px; margin:7px 0;
                                        background:rgba(0,0,0,0.22);">
                              <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="color:{TXT}; font-weight:700; font-size:0.84rem;">{stage_lbl}</span>
                                <span style="color:{tc}; font-size:0.69rem; font-weight:800;
                                             background:rgba(255,255,255,0.06); padding:2px 8px;
                                             border-radius:10px; white-space:nowrap;">{tl}</span>
                              </div>
                              <div style="color:#CBD5E1; font-size:0.83rem; margin-top:5px; line-height:1.5;">{action}</div>
                            </div>
                            """, unsafe_allow_html=True)

                        st.space("small")
                        if st.button(":material/close: Dismiss plan", key="dismiss_opt"):
                            st.session_state["show_opt"] = False
                            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 3 — VEHICLE TRACKER
# ══════════════════════════════════════════════════════════════════════════════
elif ":material/gps_fixed:" in page:
    st.markdown(
        "<h1 style='margin:0; font-size:1.75rem;'>Vehicle Tracker</h1>"
        "<p style='color:#94A3B8; margin:0 0 16px 0;'>Live equipment positions across the Huntly Mine — Darling Range, Western Australia</p>",
        unsafe_allow_html=True,
    )

    # ── FILTER BAR ────────────────────────────────────────────────────────────
    PILL_LABELS = ["All 🔍"] + [f"{icon} {label}" for _, label, icon, *_ in FLEET_DEF]
    PILL_KEYS   = ["all"]    + [t for t, *_ in FLEET_DEF]

    if "veh_filter" not in st.session_state:
        st.session_state["veh_filter"] = "all"

    with st.container(border=True):
        p_col, r_col = st.columns([11, 1], vertical_alignment="center")
        with p_col:
            sel_pill = st.pills(
                "Equipment filter",
                PILL_LABELS,
                default="All 🔍",
                key="veh_pills",
                label_visibility="collapsed",
            )
        with r_col:
            if st.button(":material/refresh:", key="veh_refresh", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

    if sel_pill and sel_pill in PILL_LABELS:
        veh_filter_key = PILL_KEYS[PILL_LABELS.index(sel_pill)]
    else:
        veh_filter_key = "all"

    # ── LIVE DATA ─────────────────────────────────────────────────────────────
    ts   = int(datetime.now().timestamp() // 20)
    df_v = _vehicle_df(ts)
    df_f = df_v if veh_filter_key == "all" else df_v[df_v["type"] == veh_filter_key]

    # ── KPI ROW ───────────────────────────────────────────────────────────────
    n_op  = (df_f["status"] == "Operating").sum()
    n_id  = (df_f["status"] == "Idle").sum()
    n_mx  = (df_f["status"] == "Maintenance").sum()
    with st.container(horizontal=True):
        with st.container(border=True):
            st.metric("🟢 Operating",   f"{n_op}",  delta=None)
        with st.container(border=True):
            st.metric("🟡 Idle",        f"{n_id}",  delta=None)
        with st.container(border=True):
            st.metric("🔴 Maintenance", f"{n_mx}",  delta=None)
        with st.container(border=True):
            st.metric("📍 Total shown", f"{len(df_f)}", delta=None)
        with st.container(border=True):
            avg_fuel = round(df_f["fuel"].mean(), 1) if len(df_f) else 0
            st.metric("⛽ Avg fuel",    f"{avg_fuel}%", delta=None)
        with st.container(border=True):
            avg_spd  = round(df_f[df_f["speed"] > 0]["speed"].mean(), 1) if (df_f["speed"] > 0).any() else 0
            st.metric("🚀 Avg speed",   f"{avg_spd} km/h", delta=None)

    # ── MAP ───────────────────────────────────────────────────────────────────
    ESRI_SAT = [{
        "below": "traces",
        "sourcetype": "raster",
        "sourceattribution": "Esri World Imagery",
        "source": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
    }]
    ESRI_LABELS = [{
        "below": "",
        "sourcetype": "raster",
        "sourceattribution": "Esri Reference",
        "source": ["https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"],
    }]

    map_traces = []
    groups = df_f.groupby("type")
    for eq_type, grp in groups:
        meta = {t: (lbl, icon, col, sz) for t, lbl, icon, col, _, sz in FLEET_DEF}
        label, icon, color, sz = meta.get(eq_type, ("Unknown", "⚙️", MUTED, 12))

        cdata = list(zip(
            grp["vid"], grp["label"],
            grp["status"], grp["speed"].astype(str),
            grp["heading"].astype(str), grp["operator"],
            grp["fuel"].astype(str), grp["hours"].astype(str),
            grp["payload"].astype(str),
        ))

        htpl = (
            "<b>%{customdata[0]}</b>  %{customdata[1]}<br>"
            "Status: <b>%{customdata[2]}</b><br>"
            "Speed: %{customdata[3]} km/h  ·  Heading: %{customdata[4]}°<br>"
            "Operator: %{customdata[5]}<br>"
            "Fuel: %{customdata[6]}%  ·  Hours today: %{customdata[7]} h<br>"
            "Payload: %{customdata[8]} t<extra></extra>"
        )

        marker_sizes   = [sz + 2 if s == "Operating" else sz - 1 if s == "Idle" else sz - 3 for s in grp["status"]]
        marker_opacity = [0.95  if s == "Operating" else 0.65  if s == "Idle" else 0.45  for s in grp["status"]]

        map_traces.append(go.Scattermapbox(
            name=f"{icon} {label}",
            lat=grp["lat"], lon=grp["lon"],
            mode="markers",
            marker=go.scattermapbox.Marker(
                size=marker_sizes,
                color=color,
                opacity=0.9,
            ),
            customdata=cdata,
            hovertemplate=htpl,
        ))

    fig_veh = go.Figure(map_traces)
    fig_veh.update_layout(
        mapbox=dict(
            style="white-bg",
            layers=ESRI_SAT + ESRI_LABELS,
            center=dict(lat=MINE_LAT, lon=MINE_LON),
            zoom=12.5,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=580,
        legend=dict(
            bgcolor="rgba(10,22,40,0.85)",
            bordercolor=BORDER,
            borderwidth=1,
            font=dict(color=TXT, size=12),
            orientation="v",
            x=0.01, y=0.99, xanchor="left", yanchor="top",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        uirevision="vehicle_map",
    )
    st.plotly_chart(fig_veh, use_container_width=True, config={"scrollZoom": True, "displayModeBar": True})

    # ── EQUIPMENT BREAKDOWN TABLE ──────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("**Equipment breakdown**")
        summary_rows = []
        for eq_type, label, icon, color, count, _ in FLEET_DEF:
            grp_d = df_f[df_f["type"] == eq_type]
            if len(grp_d) == 0:
                continue
            summary_rows.append({
                "Type": f"{icon}  {label}",
                "Total": len(grp_d),
                "Operating": int((grp_d["status"] == "Operating").sum()),
                "Idle": int((grp_d["status"] == "Idle").sum()),
                "Maintenance": int((grp_d["status"] == "Maintenance").sum()),
                "Avg fuel %": f"{grp_d['fuel'].mean():.0f}%",
                "Avg speed km/h": f"{grp_d[grp_d['speed']>0]['speed'].mean():.1f}" if (grp_d["speed"]>0).any() else "0.0",
            })
        if summary_rows:
            st.dataframe(
                pd.DataFrame(summary_rows),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Type":            st.column_config.TextColumn(width="medium"),
                    "Total":           st.column_config.NumberColumn(width="small"),
                    "Operating":       st.column_config.NumberColumn(width="small"),
                    "Idle":            st.column_config.NumberColumn(width="small"),
                    "Maintenance":     st.column_config.NumberColumn(width="small"),
                    "Avg fuel %":      st.column_config.TextColumn(width="small"),
                    "Avg speed km/h":  st.column_config.TextColumn(width="small"),
                },
            )

    st.caption(f"⏱ Data refreshes every 20 s  ·  Showing {len(df_f)} of {len(df_v)} vehicles  ·  Huntly Mine, WA")

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 4 — SHIP TRACKER
# ══════════════════════════════════════════════════════════════════════════════
elif ":material/directions_boat:" in page:
    st.markdown(
        "<h1 style='margin:0; font-size:1.75rem;'>Ship Tracker</h1>"
        "<p style='color:#94A3B8; margin:0 0 16px 0;'>Inbound and outbound vessels for the Alcoa alumina export fleet — Kwinana Bulk Terminal, WA</p>",
        unsafe_allow_html=True,
    )

    if "selected_ship" not in st.session_state:
        st.session_state["selected_ship"] = None

    # ── STATS ROW ─────────────────────────────────────────────────────────────
    n_out    = sum(1 for s in SHIPS if s["direction"] == "outbound")
    n_in     = sum(1 for s in SHIPS if s["direction"] == "inbound")
    n_berth  = sum(1 for s in SHIPS if s["direction"] == "at_berth")
    n_anchor = sum(1 for s in SHIPS if s["direction"] == "at_anchor")
    cargo_out_kt = sum(s["volume_t"] for s in SHIPS if s["direction"] == "outbound") / 1000

    with st.container(horizontal=True):
        with st.container(border=True):
            st.metric("🟠 Outbound",     f"{n_out} vessels",  delta=f"{cargo_out_kt:.0f} kt alumina")
        with st.container(border=True):
            st.metric("🔵 Inbound",      f"{n_in} vessels",   delta=None)
        with st.container(border=True):
            st.metric("🟢 At berth",     f"{n_berth} vessel", delta="Loading")
        with st.container(border=True):
            st.metric("⚓ At anchor",    f"{n_anchor} vessel",delta="Awaiting berth")
        with st.container(border=True):
            st.metric("📦 Total fleet",  f"{len(SHIPS)} vessels", delta=None)

    # ── MAP ───────────────────────────────────────────────────────────────────
    ESRI_NATGEO = [{
        "below": "traces",
        "sourcetype": "raster",
        "sourceattribution": "Esri | National Geographic",
        "source": ["https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}"],
    }]

    ship_traces = []
    route_traces = []

    for i, s in enumerate(SHIPS):
        col  = _ship_color(s["direction"])
        sel  = st.session_state["selected_ship"] == i
        sz   = 22 if sel else 16
        eta  = _eta_str(s["eta_h"])
        etd  = _eta_str(s["etd_h"])
        dir_label = {"outbound": "Outbound", "inbound": "Inbound",
                     "at_berth": "At Berth", "at_anchor": "At Anchor"}.get(s["direction"], "")

        htpl = (
            f"<b>{s['name']}</b>  {s['flag']}<br>"
            f"<span style='color:gray'>{s['type']} · {dir_label}</span><br>"
            f"Status: <b>{s['status']}</b><br>"
            f"Speed: {s['speed_kn']} kn  ·  Heading: {s['heading']}°<br>"
            f"Destination: {s['dest']}<br>"
            f"{'ETA: ' + eta if s['eta_h'] is not None else 'ETD: ' + etd}<br>"
            f"Cargo: {s['cargo']}"
            + (f"  ({s['volume_t']:,} t)" if s["volume_t"] else "")
            + f"<br>Draft: {s['draft_m']} m<extra></extra>"
        )

        ship_traces.append(go.Scattermapbox(
            name=f"{s['flag']} {s['name']}",
            lat=[s["lat"]], lon=[s["lon"]],
            mode="markers+text",
            marker=go.scattermapbox.Marker(size=sz, color=col, opacity=0.95),
            text=["▶" if s["direction"] in ("outbound","inbound") else "⚓"],
            textfont=dict(size=9, color="white"),
            textposition="middle center",
            hovertemplate=htpl,
            customdata=[[i, s["name"], s["direction"]]],
            showlegend=True,
        ))

        if s["direction"] in ("outbound", "inbound") and s["dest"] in _DEST_COORDS:
            dlat, dlon = _DEST_COORDS[s["dest"]]
            route_traces.append(go.Scattermapbox(
                lat=[s["lat"], dlat], lon=[s["lon"], dlon],
                mode="lines",
                line=dict(width=1.5, color=col),
                opacity=0.35,
                hoverinfo="skip",
                showlegend=False,
            ))

    fig_ship = go.Figure(route_traces + ship_traces)

    fig_ship.update_layout(
        mapbox=dict(
            style="white-bg",
            layers=ESRI_NATGEO,
            center=dict(lat=-28.5, lon=112.5),
            zoom=4.4,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=560,
        legend=dict(
            bgcolor="rgba(10,22,40,0.88)",
            bordercolor=BORDER,
            borderwidth=1,
            font=dict(color=TXT, size=12),
            orientation="v",
            x=0.01, y=0.99, xanchor="left", yanchor="top",
            title=dict(text="Fleet", font=dict(color=MUTED, size=11)),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        uirevision="ship_map",
    )

    event = st.plotly_chart(
        fig_ship,
        key="ship_map",
        on_select="rerun",
        use_container_width=True,
        config={"scrollZoom": True, "displayModeBar": True},
    )

    if event and event.selection and event.selection.get("points"):
        pt = event.selection["points"][0]
        raw = pt.get("customdata") or pt.get("custom_data") or []
        if raw:
            st.session_state["selected_ship"] = int(raw[0])
            st.rerun()

    # ── MAP LEGEND ─────────────────────────────────────────────────────────────
    st.markdown(
        f"<div style='display:flex; gap:20px; font-size:0.8rem; color:{MUTED}; margin:-8px 0 12px 0;'>"
        f"<span><span style='color:#F59E0B;'>●</span> Outbound (alumina)</span>"
        f"<span><span style='color:#06B6D4;'>●</span> Inbound (ballast)</span>"
        f"<span><span style='color:#10B981;'>●</span> At berth</span>"
        f"<span><span style='color:#0057A8;'>●</span> At anchor</span>"
        f"<span style='margin-left:12px;'>Click a vessel on the map or card below to see full details</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── SHIP CARDS ─────────────────────────────────────────────────────────────
    card_cols = st.columns(3, gap="small")
    for i, s in enumerate(SHIPS):
        col_idx = i % 3
        with card_cols[col_idx]:
            sel     = st.session_state["selected_ship"] == i
            col     = _ship_color(s["direction"])
            dir_lbl = {"outbound":"Outbound ↗","inbound":"Inbound ↙","at_berth":"At Berth","at_anchor":"At Anchor ⚓"}.get(s["direction"],"")
            border_col = col if sel else BORDER
            st.markdown(
                f"""<div style="background:rgba(255,255,255,0.04); border:1.5px solid {border_col};
                           border-radius:10px; padding:12px 14px; margin-bottom:8px;">
                  <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-weight:700; font-size:0.92rem; color:{TXT};">{s['flag']} {s['name']}</span>
                    <span style="font-size:0.72rem; font-weight:600; padding:2px 8px;
                          background:rgba(0,0,0,0.25); border:1px solid {col};
                          color:{col}; border-radius:8px;">{dir_lbl}</span>
                  </div>
                  <div style="color:{MUTED}; font-size:0.78rem; margin-top:4px;">{s['status']} · {s['speed_kn']} kn</div>
                  <div style="color:{TXT}; font-size:0.82rem; margin-top:6px;">
                    {'→ ' + s['dest'] + ' · ETA ' + _eta_str(s['eta_h']) if s['eta_h'] is not None else
                     ('Loading · ETD ' + _eta_str(s['etd_h'])) if s['etd_h'] is not None else s['dest']}
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button("View details", key=f"ship_card_{i}", use_container_width=True,
                         type="primary" if sel else "secondary"):
                st.session_state["selected_ship"] = i
                st.rerun()

    # ── SHIP DETAIL PANEL ──────────────────────────────────────────────────────
    sel_idx = st.session_state.get("selected_ship")
    if sel_idx is not None and 0 <= sel_idx < len(SHIPS):
        s   = SHIPS[sel_idx]
        col = _ship_color(s["direction"])

        st.markdown("<hr style='border-color:rgba(255,255,255,0.1); margin:8px 0 16px 0;'>", unsafe_allow_html=True)
        st.markdown(
            f"<h3 style='margin:0 0 4px 0; font-size:1.3rem; color:{TXT};'>{s['flag']}  {s['name']}</h3>"
            f"<p style='color:{MUTED}; margin:0 0 14px 0; font-size:0.85rem;'>{s['type']}  ·  IMO {s['imo']}  ·  {s['callsign']}  ·  Flag: {s['flag_country']}  ·  Built {s['built']}</p>",
            unsafe_allow_html=True,
        )

        d1, d2, d3 = st.columns(3, gap="medium")

        with d1:
            with st.container(border=True):
                st.markdown("**🧭 Navigation**")
                st.metric("Status",    s["status"])
                st.metric("Speed",     f"{s['speed_kn']} kn  ({s['speed_kn']*1.852:.1f} km/h)")
                st.metric("Heading",   f"{s['heading']}°")
                st.metric("Draft",     f"{s['draft_m']} m")
                st.metric("LOA",       f"{s['loa_m']} m")

        with d2:
            with st.container(border=True):
                st.markdown("**📦 Cargo & Voyage**")
                st.metric("Cargo type",   s["cargo"])
                if s["volume_t"]:
                    st.metric("Cargo volume", f"{s['volume_t']:,} t")
                    st.metric("Utilisation",  f"{s['volume_t']/s['capacity_t']*100:.1f}%")
                else:
                    st.metric("Cargo volume", "Ballast (empty)")
                    st.metric("Capacity",     f"{s['capacity_t']:,} t")
                st.metric("Last port",    s["last_port"])
                st.metric("Next port",    s["next_port"])

        with d3:
            with st.container(border=True):
                st.markdown("**⏱ Schedule**")
                if s["eta_h"] is not None:
                    d, h = divmod(int(s["eta_h"]), 24)
                    st.metric("ETA",       f"{d}d {h}h")
                    st.metric("Distance",  f"{s['dist_nm']:,} nm")
                    spd_kmh = s["speed_kn"] * 1.852
                    fuel_est = round(s["dist_nm"] * 1.852 / max(spd_kmh, 1) * 28, 0) if s["speed_kn"] > 0 else 0
                    st.metric("Est. fuel", f"{fuel_est:,.0f} t IFO")
                elif s["etd_h"] is not None:
                    st.metric("ETD",       _eta_str(s["etd_h"]))
                    st.metric("Dest",      s["dest"])
                    st.metric("Voyage nm", f"{s['dist_nm']:,} nm")
                else:
                    st.metric("Distance to berth", f"{s['dist_nm']} nm")
                    st.metric("Wait time", _eta_str(s["eta_h"]))
                st.metric("Owner",     s["owner"])

        if st.button(":material/close: Close detail", key="close_ship_detail"):
            st.session_state["selected_ship"] = None
            st.rerun()

