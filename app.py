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

    st.markdown("""
<style>
[data-testid="stRadio"] label { font-size: 0.82rem !important; }
</style>
<div style='font-size:0.6rem;font-weight:700;letter-spacing:1.2px;color:rgba(255,255,255,0.35);text-transform:uppercase;padding:4px 8px 2px;'>Operations</div>
""", unsafe_allow_html=True)

    page = st.radio(
        "nav",
        [
            "📊 Operations dashboard",
            "🔬 Process simulator",
            "📍 Vehicle tracker",
            "🚂 Train tracker",
            "🚢 Ship tracker",
            "📋 Production Superintendent",
            "🗺️ Mine Planning Engineer",
            "⚗️ Process / Met Engineer",
            "🪨 Geologist",
            "🚛 Maintenance — Mobile Fleet",
            "🔧 Reliability Engineer",
            "📦 Supply Chain Planner",
            "⚓ Train / Port Coordinator",
            "🛒 Procurement / Warehouse",
            "🌿 Environmental Advisor",
            "🛡️ Safety / HSE Manager",
            "⚡ Energy / Sustainability",
        ],
        label_visibility="collapsed",
        captions=[
            "",
            "──── Logistics ────",
            "","",
            "──── Persona Dashboards ────",
            "","","","","","","","","","","","",
        ],
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

def _srng2(seed):
    s = [seed | 0]
    def _r():
        s[0] = (s[0] ^ (s[0] >> 15)) * (1 | s[0]) & 0xFFFFFFFF
        s[0] = (s[0] ^ (s[0] + (s[0] ^ (s[0] >> 7)) * 61)) & 0xFFFFFFFF
        return ((s[0] ^ (s[0] >> 14)) & 0xFFFFFFFF) / 4294967296
    return _r

def _metrics(*items):
    cols = st.columns(len(items))
    for col, (label, value, delta) in zip(cols, items):
        col.metric(label, value, delta, border=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 1 — OPERATIONS DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if "Operations dashboard" in page:

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
elif "Process simulator" in page:
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
elif "Vehicle tracker" in page:
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
elif "Ship tracker" in page:
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



# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 5 — TRAIN TRACKER
# ══════════════════════════════════════════════════════════════════════════════
elif "Train tracker" in page:
    PINJARRA_LAT, PINJARRA_LON = -32.524, 115.963
    WAGERUP_LAT,  WAGERUP_LON  = -33.304, 115.897
    PORT_LAT,     PORT_LON     = -33.327, 115.637

    st.markdown(
        "<h1 style='margin:0;font-size:1.75rem;'>Train Tracker</h1>"
        "<p style='color:#94A3B8;margin:0 0 20px 0;'>Alumina rail movements — Pinjarra & Wagerup → Port of Bunbury (~2,100 t/train)</p>",
        unsafe_allow_html=True,
    )

    def _srng(seed, slot):
        s = [(seed + slot * 3) | 0]
        def _r():
            s[0] = (s[0] ^ (s[0] >> 15)) * (1 | s[0]) & 0xFFFFFFFF
            s[0] = (s[0] ^ (s[0] + (s[0] ^ (s[0] >> 7)) * 61)) & 0xFFFFFFFF
            return ((s[0] ^ (s[0] >> 14)) & 0xFFFFFFFF) / 4294967296
        return _r

    slot = int(datetime.now().timestamp() / 30)
    ROUTES_T = {
        "pinjarra": dict(oLat=PINJARRA_LAT, oLon=PINJARRA_LON, dLat=PORT_LAT, dLon=PORT_LON, dist_km=80, color=CYAN,  label="Pinjarra → Bunbury"),
        "wagerup":  dict(oLat=WAGERUP_LAT,  oLon=WAGERUP_LON,  dLat=PORT_LAT, dLon=PORT_LON, dist_km=25, color=AMBER, label="Wagerup → Bunbury"),
    }
    TRAIN_CFGS = [
        ("PJR-001","pinjarra",101),("PJR-002","pinjarra",202),("PJR-003","pinjarra",303),
        ("WGR-001","wagerup",401),("WGR-002","wagerup",502),
    ]
    STATUS_TC = {"Running":GREEN,"Loading":CYAN,"Unloading":AMBER,"Delayed":RED}

    trains = []
    for tid, route_id, seed in TRAIN_CFGS:
        rd = ROUTES_T[route_id]; rng = _srng(seed, slot)
        prog = rng(); lat = rd["oLat"] + (rd["dLat"]-rd["oLat"])*prog
        lon  = rd["oLon"] + (rd["dLon"]-rd["oLon"])*prog
        r2   = rng()
        st_  = "Loading" if prog < 0.05 else "Unloading" if prog > 0.95 else ("Delayed" if r2 > 0.9 else "Running")
        spd  = 60 + rng()*20 if st_ == "Running" else 5 + rng()*15 if st_ == "Delayed" else 0
        eta  = int((1-prog)*rd["dist_km"]/spd*60) if spd > 0 else 999
        trains.append(dict(id=tid, route=route_id, lat=round(lat,5), lon=round(lon,5),
                           status=st_, speed=round(spd), payload=round(1800+rng()*300),
                           moisture=round((0.03+rng()*0.06)*1000)/1000,
                           wagons=21+round(rng()*3), eta=eta))

    running = sum(1 for t in trains if t["status"]=="Running")
    delayed = sum(1 for t in trains if t["status"]=="Delayed")
    payload = sum(t["payload"] for t in trains if t["status"] in ("Running","Delayed"))

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Trains running",     running,     border=True)
    c2.metric("Delayed",            delayed,     border=True)
    c3.metric("In-transit payload", f"{payload/1000:.1f}kt", border=True)
    c4.metric("Pinjarra trains",    sum(1 for t in trains if t["route"]=="pinjarra"), border=True)
    c5.metric("Wagerup trains",     sum(1 for t in trains if t["route"]=="wagerup"),  border=True)
    c6.metric("Annual throughput",  "~6 Mtpa",   border=True)

    fig = go.Figure()
    for rid, rd in ROUTES_T.items():
        fig.add_trace(go.Scattermapbox(
            lat=[rd["oLat"],rd["dLat"]], lon=[rd["oLon"],rd["dLon"]],
            mode="lines", line=dict(width=3,color=rd["color"]), opacity=0.7,
            hoverinfo="skip", showlegend=False))
    for name, lat, lon, col in [
        ("Pinjarra Refinery",PINJARRA_LAT,PINJARRA_LON,CYAN),
        ("Wagerup Refinery",WAGERUP_LAT,WAGERUP_LON,AMBER),
        ("Port of Bunbury",PORT_LAT,PORT_LON,GREEN)
    ]:
        fig.add_trace(go.Scattermapbox(
            lat=[lat], lon=[lon], mode="markers+text",
            marker=dict(size=16,color=col),
            text=["⚓ Port of Bunbury" if "Port" in name else f"🏭 {name.split()[0]}"],
            hovertemplate=f"<b>{name}</b><extra></extra>",
            textfont=dict(size=11,color="white"), showlegend=False))
    for rid, rd in ROUTES_T.items():
        rt = [t for t in trains if t["route"]==rid]
        if rt:
            fig.add_trace(go.Scattermapbox(
                lat=[t["lat"] for t in rt], lon=[t["lon"] for t in rt],
                mode="markers", name=rd["label"],
                marker=dict(size=14,color=[STATUS_TC[t["status"]] for t in rt],opacity=0.95),
                customdata=[[t["id"],t["status"],t["speed"],t["payload"],t["eta"],t["wagons"]] for t in rt],
                hovertemplate="<b>🚂 %{customdata[0]}</b><br>Status: %{customdata[1]}<br>Speed: %{customdata[2]} km/h<br>Payload: %{customdata[3]} t<br>ETA: %{customdata[4]} min<extra></extra>"))
    fig.update_layout(**CHART_LAYOUT, height=460,
                      mapbox=dict(style="carto-positron",
                                  center=dict(lat=-33.1, lon=115.76), zoom=8.5),
                      legend=dict(font=dict(color=TXT,size=11),bgcolor="rgba(13,33,55,0.85)"))
    st.plotly_chart(fig, use_container_width=True, config=dict(scrollZoom=True))

    cols = st.columns(5)
    for i, t in enumerate(trains):
        rd = ROUTES_T[t["route"]]
        with cols[i % 5]:
            with st.container(border=True):
                sc = STATUS_TC[t["status"]]
                st.markdown(f"**🚂 {t['id']}** &nbsp;<span style='background:{sc}22;color:{sc};padding:1px 8px;border-radius:10px;font-size:0.72rem;font-weight:700;'>{t['status']}</span>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:0.72rem;color:{rd['color']};font-weight:600;'>{t['route'].capitalize()} Refinery</div>", unsafe_allow_html=True)
                eta_str = "At terminal" if t['eta'] >= 999 else f"{t['eta']} min"
                moist_flag = "⚠️" if t['moisture'] > 0.5 else "✓"
                st.markdown(f"<div style='font-size:0.78rem;color:#94A3B8;line-height:1.9;'>📦 {t['payload']:,} t<br>⚡ {t['speed']} km/h · {t['wagons']} wagons<br>⏱ ETA: {eta_str}<br>💧 {t['moisture']}% {moist_flag}</div>", unsafe_allow_html=True)

    st.caption("⏱ Auto-refreshes every 30s · Port of Bunbury: 3×50,000t storage bins · ~6 Mtpa annual throughput")

# ══════════════════════════════════════════════════════════════════════════════
#  PRODUCTION SUPERINTENDENT
# ══════════════════════════════════════════════════════════════════════════════
elif "Production Superintendent" in page:
    st.markdown("<h1 style='margin:0;font-size:1.75rem;'>Production Superintendent</h1><p style='color:#94A3B8;margin:0 0 20px 0;'>Morning briefing — overnight shift summary · Huntly Mine</p>", unsafe_allow_html=True)
    r = _srng2(77)
    now = datetime.now()
    hrs12 = [now - timedelta(hours=11-i) for i in range(12)]
    mined  = [round(1800 + r()*600) for _ in range(12)]
    crusher= [round(v*(0.88+r()*0.08)) for v in mined]
    futl   = [round(72 + r()*20) for _ in range(12)]

    st.info("🤖 **AUTO-GENERATED 06:00 AWST** — Ready for 07:00 production meeting")
    _metrics(
        ("Tonnes mined (night)","19,120 t","▲ +720t vs plan"),
        ("Fleet utilisation","87%","▲ +5% vs target"),
        ("Crusher availability","91%","▼ −4% vs 95% target"),
        ("Ore grade Al₂O₃","28.8%","▼ −0.6% vs model"),
        ("Active incidents","0","✓ Clean shift"),
        ("Env. exceedances","1","PM10 Monitor 3"),
    )

    c1,c2 = st.columns([2,1])
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hrs12,y=mined,  mode="lines",name="Tonnes mined/hr",line=dict(color=CYAN,width=2),fill="tozeroy",fillcolor="rgba(0,180,216,0.07)"))
        fig.add_trace(go.Scatter(x=hrs12,y=crusher,mode="lines",name="Crusher output", line=dict(color=BLUE,width=2)))
        fig.update_layout(**CHART_LAYOUT,height=220,title=dict(text="Overnight haulage & crusher (t/hr)",font=dict(color=TXT,size=13)),
                          xaxis=dict(**_ax(False),showticklabels=False),yaxis=_ax(),
                          legend=dict(font=dict(color=TXT,size=11),bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig,use_container_width=True,config=dict(displayModeBar=False))
    with c2:
        fc=[GREEN if v>85 else AMBER if v>75 else RED for v in futl]
        fig2=go.Figure(go.Bar(x=list(range(12)),y=futl,marker_color=fc))
        fig2.update_layout(**CHART_LAYOUT,height=220,title=dict(text="Fleet utilisation %",font=dict(color=TXT,size=13)),
                           xaxis=dict(**_ax(False),showticklabels=False),yaxis=dict(**_ax(),range=[0,105]),showlegend=False)
        st.plotly_chart(fig2,use_container_width=True,config=dict(displayModeBar=False))

    with st.container(border=True):
        st.markdown("**📊 Shift vs Plan**")
        for label,plan,actual,unit in [
            ("Tonnes mined",18400,19120,"t"),("Fleet utilisation",82,87,"%"),
            ("Crusher availability",95,91,"%"),("Ore grade Al₂O₃",29.4,28.8,"%"),
            ("Safety incidents",0,0,""),("Env. exceedances",0,1,""),
        ]:
            pct=actual/plan if plan>0 else 1
            col=GREEN if actual>=plan else AMBER
            status="Above plan" if actual>=plan else ("On plan" if actual==plan else "Below plan")
            ca,cb,cc,cd=st.columns([3,2,2,2])
            ca.markdown(label)
            cb.markdown(f"<span style='color:{MUTED}'>Plan: {plan}{unit}</span>",unsafe_allow_html=True)
            cc.markdown(f"<span style='color:{col};font-weight:700;'>Actual: {actual}{unit}</span>",unsafe_allow_html=True)
            cd.markdown(f"<span style='background:{col}22;color:{col};padding:1px 10px;border-radius:10px;font-size:0.75rem;font-weight:700;'>{status}</span>",unsafe_allow_html=True)
            st.progress(min(1.0,pct))

    with st.container(border=True):
        st.markdown("**⚡ Actions for Morning Meeting**")
        for p,item,owner in [
            ("🔴","Crusher 2 bearing alert — schedule maintenance window","Reliability"),
            ("🟡","Haul road PM10 exceedance at Monitor 3 — water cart deployed","Environmental"),
            ("🟡","Ore grade below model in Block 5A — notify Geologist","Mine Planning"),
            ("🟢","Rail dispatch on schedule — 3 consists to Bunbury by 18:00","Train/Port"),
            ("🟢","Caustic inventory confirmed — 8,200t in port storage","Supply Chain"),
        ]:
            ca,cb,cc=st.columns([0.5,8,2])
            ca.markdown(p)
            cb.markdown(item)
            cc.markdown(f"<span style='color:{MUTED}'>→ {owner}</span>",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  MINE PLANNING ENGINEER
# ══════════════════════════════════════════════════════════════════════════════
elif "Mine Planning Engineer" in page:
    st.markdown("<h1 style='margin:0;font-size:1.75rem;'>Mine Planning Engineer</h1><p style='color:#94A3B8;margin:0 0 20px 0;'>Weekly mine plan · Block selection · Equipment availability — Huntly Mine</p>",unsafe_allow_html=True)
    BLOCKS=[
        dict(id="B-42A",al2o3=38.2,rsi=2.1,dist=0.8,area=4.2,status="Cleared", equip="Available",approved=True),
        dict(id="B-42B",al2o3=36.8,rsi=2.8,dist=1.1,area=3.8,status="Cleared", equip="Available",approved=True),
        dict(id="B-43A",al2o3=34.1,rsi=3.4,dist=1.6,area=5.1,status="Cleared", equip="Partial",  approved=True),
        dict(id="B-43B",al2o3=39.4,rsi=1.9,dist=2.2,area=4.7,status="Drilled", equip="Available",approved=False),
        dict(id="B-44A",al2o3=37.6,rsi=2.3,dist=2.8,area=3.3,status="Planned", equip="Available",approved=True),
        dict(id="B-44B",al2o3=32.4,rsi=4.1,dist=3.4,area=6.0,status="Planned", equip="Partial",  approved=False),
        dict(id="B-45A",al2o3=40.1,rsi=1.7,dist=1.4,area=4.9,status="Cleared", equip="Available",approved=True),
        dict(id="B-45B",al2o3=35.5,rsi=2.6,dist=1.8,area=3.6,status="Cleared", equip="Available",approved=True),
    ]
    qual=[b for b in BLOCKS if b["al2o3"]>=35 and b["dist"]<=2 and b["approved"]]
    avg_g=sum(b["al2o3"] for b in qual)/len(qual) if qual else 0
    _metrics(
        (f"Qualified blocks",len(qual),"Ready to schedule"),
        ("Avg Al₂O₃ (qualified)",f"{avg_g:.1f}%","vs 29% overall avg"),
        ("Refinery feed target","620 t/hr","Pinjarra digestion demand"),
        ("Clearing approvals due","2 blocks","DMIRS pending — B-43B, B-44B"),
        ("Plan prep time saved","70%","2 days → 0.5 day (CoCo)"),
    )
    c1,c2=st.columns(2)
    with c1:
        colors=[GREEN if b["al2o3"]>=35 and b["dist"]<=2 and b["approved"] else AMBER if b["al2o3"]>=35 else RED for b in BLOCKS]
        fig=go.Figure(go.Scatter(x=[b["dist"] for b in BLOCKS],y=[b["al2o3"] for b in BLOCKS],
                                   mode="markers",marker=dict(size=[b["area"]*8 for b in BLOCKS],color=colors,opacity=0.85),
                                   text=[b["id"] for b in BLOCKS],
                                   hovertemplate="<b>%{text}</b><br>Al₂O₃: %{y:.1f}%<br>Distance: %{x:.1f} km<extra></extra>"))
        fig.add_hline(y=35,line_dash="dash",line_color=AMBER,line_width=1.5)
        fig.add_vline(x=2, line_dash="dash",line_color=AMBER,line_width=1.5)
        fig.update_layout(**CHART_LAYOUT,height=260,title=dict(text="Block grade vs distance (bubble = area ha)",font=dict(color=TXT,size=13)),
                          xaxis=dict(**_ax(),title=dict(text="Distance from crusher (km)",font=dict(color=MUTED,size=10))),
                          yaxis=dict(**_ax(),title=dict(text="Al₂O₃ grade (%)",font=dict(color=MUTED,size=10))),showlegend=False)
        st.plotly_chart(fig,use_container_width=True,config=dict(displayModeBar=False))
    with c2:
        ids=[b["id"] for b in BLOCKS]
        fig2=go.Figure()
        fig2.add_trace(go.Bar(name="Al₂O₃ %",x=ids,y=[b["al2o3"] for b in BLOCKS],marker_color=[GREEN if b["al2o3"]>=35 else AMBER for b in BLOCKS]))
        fig2.add_trace(go.Bar(name="RSi %×5",x=ids,y=[b["rsi"]*5 for b in BLOCKS], marker_color=[RED if b["rsi"]>3 else AMBER for b in BLOCKS],opacity=0.7))
        fig2.update_layout(**CHART_LAYOUT,barmode="group",height=260,title=dict(text="Block grade — Al₂O₃ vs reactive silica",font=dict(color=TXT,size=13)),
                           xaxis=_ax(False),yaxis=_ax(),legend=dict(font=dict(color=TXT,size=11),bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig2,use_container_width=True,config=dict(displayModeBar=False))
    with st.container(border=True):
        st.markdown("**📋 Block schedule — next 7 days**")
        for b in BLOCKS:
            sc=GREEN if b["status"]=="Cleared" else CYAN if b["status"]=="Drilled" else AMBER
            ca,cb,cc,cd,ce,cf,cg,ch=st.columns([1,1,1,1,1,1.2,1,1])
            ca.markdown(f"**{b['id']}**")
            cb.markdown(f"<span style='color:{CYAN}'>{b['al2o3']}%</span>",unsafe_allow_html=True)
            cc.markdown(f"<span style='color:{RED if b['rsi']>3 else MUTED}'>RSi {b['rsi']}%</span>",unsafe_allow_html=True)
            cd.markdown(f"<span style='color:{MUTED}'>{b['dist']} km</span>",unsafe_allow_html=True)
            ce.markdown(f"<span style='color:{MUTED}'>{b['area']} ha</span>",unsafe_allow_html=True)
            cf.markdown(f"<span style='background:{sc}22;color:{sc};padding:1px 8px;border-radius:10px;font-size:0.75rem;font-weight:700;'>{b['status']}</span>",unsafe_allow_html=True)
            cg.markdown(f"<span style='color:{GREEN if b['equip']=='Available' else AMBER}'>{b['equip']}</span>",unsafe_allow_html=True)
            ch.markdown(f"<span style='color:{GREEN if b['approved'] else RED}'>{'✓ Approved' if b['approved'] else '⚠ Pending'}</span>",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PROCESS / MET ENGINEER
# ══════════════════════════════════════════════════════════════════════════════
elif "Process / Met Engineer" in page:
    st.markdown("<h1 style='margin:0;font-size:1.75rem;'>Process / Metallurgical Engineer</h1><p style='color:#94A3B8;margin:0 0 20px 0;'>Bayer Process optimisation — ore grade correlation · LIMS vs DCS historian · Digestion parameters</p>",unsafe_allow_html=True)
    r=_srng2(55); now=datetime.now()
    hrs24=[now-timedelta(hours=23-i) for i in range(24)]
    turb=[max(4,min(28,12+(r()-0.5)*8)) for _ in range(24)]
    rsi_f=[round((2.4+(r()-0.5)*1.2)*10)/10 for _ in range(24)]
    al2=[round((91+(r()-0.5)*3)*10)/10 for _ in range(24)]
    r2=_srng2(66)
    cx=[round((1.5+r2()*3)*10)/10 for _ in range(20)]
    cy=[round((8+r2()*18)*10)/10 for _ in range(20)]
    _metrics(
        ("Al₂O₃ extraction","91.2%","▲ Above 90% target"),
        ("Reactive silica (feed)","2.8%","⚠ Trending up from 2.1%"),
        ("Turbidity (overflow)","14.2 NTU","↑ from 12 NTU baseline"),
        ("Caustic efficiency","94.1%","✓ Normal range"),
        ("Analysis time saved","80%","6 hrs → 1 hr (CoCo)"),
    )
    c1,c2,c3=st.columns(3)
    with c1:
        fig=go.Figure(go.Scatter(x=cx,y=cy,mode="markers",marker=dict(size=8,color=CYAN,opacity=0.8),
                                   hovertemplate="RSi: %{x}%<br>Turbidity: %{y} NTU<extra></extra>"))
        fig.update_layout(**CHART_LAYOUT,height=235,title=dict(text="RSi in feed vs clarifier turbidity (r=0.82)",font=dict(color=TXT,size=12)),
                          xaxis=dict(**_ax(),title=dict(text="Reactive silica % in feed",font=dict(color=MUTED,size=10))),
                          yaxis=dict(**_ax(),title=dict(text="Turbidity (NTU)",font=dict(color=MUTED,size=10))),showlegend=False)
        st.plotly_chart(fig,use_container_width=True,config=dict(displayModeBar=False))
    with c2:
        fig2=go.Figure(go.Scatter(x=hrs24,y=turb,mode="lines",line=dict(color=AMBER,width=2),fill="tozeroy",fillcolor="rgba(245,158,11,0.08)"))
        fig2.add_hline(y=20,line_dash="dash",line_color=RED,line_width=1.5)
        fig2.update_layout(**CHART_LAYOUT,height=235,title=dict(text="Clarifier turbidity — 24h trend",font=dict(color=TXT,size=12)),
                           xaxis=dict(**_ax(False),showticklabels=False),yaxis=_ax(),showlegend=False)
        st.plotly_chart(fig2,use_container_width=True,config=dict(displayModeBar=False))
    with c3:
        fig3=go.Figure()
        fig3.add_trace(go.Scatter(x=hrs24,y=al2,mode="lines",name="Al₂O₃ extraction %",line=dict(color=GREEN,width=2)))
        fig3.add_trace(go.Scatter(x=hrs24,y=rsi_f,mode="lines",name="RSi feed %",yaxis="y2",line=dict(color=RED,width=1.5,dash="dot")))
        fig3.update_layout(**CHART_LAYOUT,height=235,title=dict(text="Al₂O₃ extraction vs reactive silica",font=dict(color=TXT,size=12)),
                           xaxis=dict(**_ax(False),showticklabels=False),yaxis=_ax(),
                           yaxis2=dict(overlaying="y",side="right",tickfont=dict(color=MUTED,size=9),showgrid=False),
                           legend=dict(font=dict(color=TXT,size=10),bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig3,use_container_width=True,config=dict(displayModeBar=False))
    with st.container(border=True):
        st.markdown("**🤖 AI Parameter Recommendations**")
        for param,current,rec,reason,impact in [
            ("Digestion temperature","145°C","147°C","RSi 3.1% in feed — increase temp to maintain extraction","+0.8% Al₂O₃"),
            ("Caustic concentration","235 g/L","240 g/L","Elevated reactive silica depleting NaOH faster than nominal","Maintains >90% extraction"),
            ("Flocculant dose","45 g/t","52 g/t","Turbidity trending up — increase to maintain clarity spec","Turbidity <15 NTU"),
        ]:
            with st.container(border=True):
                ca,cb,cc,cd=st.columns([2,1.5,1.5,2])
                ca.markdown(f"**{param}**")
                cb.markdown(f"Current: **{current}**")
                cc.markdown(f"→ Rec: <span style='color:{GREEN};font-weight:700;'>{rec}</span>",unsafe_allow_html=True)
                cd.markdown(f"<span style='background:rgba(16,185,129,0.15);color:{GREEN};padding:2px 10px;border-radius:10px;font-size:0.75rem;font-weight:700;'>{impact}</span>",unsafe_allow_html=True)
                st.caption(reason)

# ══════════════════════════════════════════════════════════════════════════════
#  GEOLOGIST
# ══════════════════════════════════════════════════════════════════════════════
elif "Geologist" in page:
    st.markdown("<h1 style='margin:0;font-size:1.75rem;'>Geologist / Resource Modeller</h1><p style='color:#94A3B8;margin:0 0 20px 0;'>Block model grade reconciliation · F1/F2/F3 accuracy · Mine-to-mill tracking — Huntly Mine</p>",unsafe_allow_html=True)
    GBLOCKS=[
        dict(id="B-42A",pred=38.4,bh=38.2,crush=37.8,ref=37.1,pred_rsi=2.0,bh_rsi=2.1,f1=0.995,f2=0.983,f3=0.967),
        dict(id="B-42B",pred=36.5,bh=36.8,crush=36.2,ref=35.7,pred_rsi=2.9,bh_rsi=2.8,f1=1.008,f2=0.993,f3=0.978),
        dict(id="B-43A",pred=34.8,bh=34.1,crush=33.5,ref=32.9,pred_rsi=3.2,bh_rsi=3.4,f1=0.980,f2=0.963,f3=0.945),
        dict(id="B-43B",pred=40.1,bh=39.4,crush=38.8,ref=38.1,pred_rsi=1.8,bh_rsi=1.9,f1=0.983,f2=0.967,f3=0.950),
        dict(id="B-45A",pred=38.0,bh=40.1,crush=39.4,ref=38.6,pred_rsi=2.2,bh_rsi=1.7,f1=1.055,f2=1.037,f3=1.016),
        dict(id="B-45B",pred=35.2,bh=35.5,crush=34.9,ref=34.3,pred_rsi=2.5,bh_rsi=2.6,f1=1.009,f2=0.991,f3=0.974),
    ]
    ids=[b["id"] for b in GBLOCKS]
    avg_f1=sum(b["f1"] for b in GBLOCKS)/len(GBLOCKS)
    flagged=sum(1 for b in GBLOCKS if abs(b["f1"]-1)>0.03)
    qtrs=["Q3 2025","Q4 2025","Q1 2026","Q2 2026"]
    _metrics(
        ("Avg model F1 factor",f"{avg_f1:.3f}","F1=1.000 = perfect"),
        ("Blocks flagged",flagged,"|F1−1.0| >3% = systematic bias"),
        ("Reconciliation cycle","1.5 days","70% faster vs 5-day manual"),
        ("Active drill blocks","6","Current quarter schedule"),
    )
    c1,c2=st.columns(2)
    with c1:
        fig=go.Figure()
        for ys,nm,col in [([b["pred"] for b in GBLOCKS],"Predicted",MUTED),
                           ([b["bh"] for b in GBLOCKS],"Blast-hole",CYAN),
                           ([b["crush"] for b in GBLOCKS],"Crusher",AMBER),
                           ([b["ref"] for b in GBLOCKS],"Refinery head",GREEN)]:
            fig.add_trace(go.Scatter(x=ids,y=ys,mode="lines+markers",name=nm,line=dict(color=col,width=2),marker=dict(size=7)))
        fig.update_layout(**CHART_LAYOUT,height=260,title=dict(text="Al₂O₃ grade reconciliation",font=dict(color=TXT,size=13)),
                          xaxis=_ax(False),yaxis=dict(**_ax(),title=dict(text="Al₂O₃ %",font=dict(color=MUTED,size=10))),
                          legend=dict(font=dict(color=TXT,size=10),bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig,use_container_width=True,config=dict(displayModeBar=False))
    with c2:
        fig2=go.Figure()
        for ys,nm,col in [([0.988,0.992,0.985,0.994],"F1 (mine/model)",CYAN),
                           ([0.971,0.978,0.968,0.976],"F2 (mill/mine)",AMBER),
                           ([0.952,0.961,0.949,0.958],"F3 (refinery/mill)",GREEN)]:
            fig2.add_trace(go.Scatter(x=qtrs,y=ys,mode="lines+markers",name=nm,line=dict(color=col,width=2),marker=dict(size=8)))
        fig2.add_hline(y=1.0,line_dash="dot",line_color=MUTED,line_width=1)
        fig2.update_layout(**CHART_LAYOUT,height=260,title=dict(text="F1/F2/F3 factors — quarterly trend",font=dict(color=TXT,size=13)),
                           xaxis=_ax(False),yaxis=dict(**_ax(),range=[0.93,1.07]),
                           legend=dict(font=dict(color=TXT,size=10),bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig2,use_container_width=True,config=dict(displayModeBar=False))
    with st.container(border=True):
        st.markdown("**📊 Block grade reconciliation table — Q2 2026**")
        hdr=st.columns([1,1,1,1,1,1,1,1,1,1,1])
        for col,h in zip(hdr,["Block","Pred Al₂O₃","BH Al₂O₃","Crusher","Refinery","Pred RSi","BH RSi","F1","F2","F3","Flag"]):
            col.markdown(f"<span style='color:{MUTED};font-size:0.72rem;font-weight:700;text-transform:uppercase;'>{h}</span>",unsafe_allow_html=True)
        for b in GBLOCKS:
            flag=abs(b["f1"]-1)>0.03
            row=st.columns([1,1,1,1,1,1,1,1,1,1,1])
            fc=RED if flag else TXT
            vals=[
                (f"**{b['id']}**",fc),(f"{b['pred']}%",MUTED),(f"{b['bh']}%",TXT),
                (f"{b['crush']}%",TXT),(f"{b['ref']}%",TXT),(f"{b['pred_rsi']}%",MUTED),
                (f"{b['bh_rsi']}%",RED if b['bh_rsi']>3 else TXT),
                (f"{b['f1']:.3f}",RED if abs(b['f1']-1)>0.03 else AMBER if abs(b['f1']-1)>0.015 else GREEN),
                (f"{b['f2']:.3f}",MUTED),(f"{b['f3']:.3f}",MUTED),
                ("⚠ Review" if flag else "✓",RED if flag else GREEN),
            ]
            for col,(txt,c) in zip(row,vals):
                col.markdown(f"<span style='color:{c};font-weight:700;'>{txt}</span>",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  MAINTENANCE — MOBILE FLEET
# ══════════════════════════════════════════════════════════════════════════════
elif "Maintenance" in page:
    st.markdown("<h1 style='margin:0;font-size:1.75rem;'>Maintenance Supervisor — Mobile Fleet</h1><p style='color:#94A3B8;margin:0 0 20px 0;'>Haul trucks · Excavators · Drill rigs · Preventive maintenance scheduling — Huntly Mine</p>",unsafe_allow_html=True)
    FLEET=[
        dict(id="T-01",tp="Haul Truck",hrs=482,iv=500,oil="Pass",vib="Normal",status="Monitor",next=3),
        dict(id="T-02",tp="Haul Truck",hrs=498,iv=500,oil="Pass",vib="Normal",status="Service due",next=1),
        dict(id="T-03",tp="Haul Truck",hrs=314,iv=500,oil="Pass",vib="Normal",status="Normal",next=37),
        dict(id="T-07",tp="Haul Truck",hrs=256,iv=500,oil="Fail",vib="Normal",status="Oil alert",next=14),
        dict(id="T-11",tp="Haul Truck",hrs=461,iv=500,oil="Pass",vib="Elevated",status="Monitor",next=8),
        dict(id="EX-01",tp="Excavator",hrs=1840,iv=2000,oil="Pass",vib="Normal",status="Normal",next=32),
        dict(id="EX-02",tp="Excavator",hrs=1974,iv=2000,oil="Pass",vib="Normal",status="Monitor",next=4),
        dict(id="DR-01",tp="Drill Rig",hrs=720,iv=750,oil="Pass",vib="Normal",status="Monitor",next=10),
        dict(id="DR-02",tp="Drill Rig",hrs=748,iv=750,oil="Pass",vib="Elevated",status="Service due",next=1),
        dict(id="WC-01",tp="Water Cart",hrs=312,iv=400,oil="Pass",vib="Normal",status="Normal",next=22),
    ]
    SC4={"Normal":GREEN,"Monitor":AMBER,"Service due":RED,"Oil alert":RED}
    urgent=sum(1 for f in FLEET if f["next"]<=7)
    _metrics(
        ("Service due ≤7 days",urgent,"Across all mobile fleet"),
        ("Fleet active","38/42","4 in planned maintenance"),
        ("Oil analysis alerts","1","T-07 — sample failure"),
        ("Vib alerts","2","T-11, DR-02 elevated"),
        ("Planning time saved","60%","3 hrs → 1 hr/week"),
    )
    sf=sorted(FLEET,key=lambda f:f["next"])
    c1,c2=st.columns(2)
    with c1:
        ds=[f["next"] for f in sf]; aids=[f["id"] for f in sf]
        fig=go.Figure(go.Bar(y=aids,x=ds,orientation="h",
                               marker_color=[RED if d<=3 else AMBER if d<=7 else GREEN for d in ds],
                               text=[f"{d}d" for d in ds],textposition="outside",textfont=dict(color=TXT,size=10)))
        fig.add_vline(x=7,line_dash="dash",line_color=AMBER,line_width=1.5)
        fig.update_layout(**CHART_LAYOUT,height=280,title=dict(text="Days until next service interval",font=dict(color=TXT,size=13)),
                          xaxis=dict(**_ax(),range=[0,45]),yaxis=_ax(False),showlegend=False)
        st.plotly_chart(fig,use_container_width=True,config=dict(displayModeBar=False))
    with c2:
        f8=FLEET[:8]
        fig2=go.Figure()
        fig2.add_trace(go.Bar(name="Engine hours",x=[f["id"] for f in f8],y=[f["hrs"] for f in f8],
                               marker_color=[RED if f["hrs"]/f["iv"]>0.95 else AMBER if f["hrs"]/f["iv"]>0.85 else GREEN for f in f8]))
        fig2.add_trace(go.Scatter(name="Service interval",x=[f["id"] for f in f8],y=[f["iv"] for f in f8],
                                   mode="lines",line=dict(color=MUTED,dash="dash",width=1.5)))
        fig2.update_layout(**CHART_LAYOUT,barmode="overlay",height=280,title=dict(text="Engine hours vs service interval",font=dict(color=TXT,size=13)),
                           xaxis=_ax(False),yaxis=_ax(),legend=dict(font=dict(color=TXT,size=11),bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig2,use_container_width=True,config=dict(displayModeBar=False))
    with st.container(border=True):
        st.markdown("**🔧 Fleet maintenance register**")
        for f in FLEET:
            pct=f["hrs"]/f["iv"]; sc=SC4[f["status"]]
            ca,cb,cc,cd,ce,cf,cg=st.columns([1,1.5,1.5,3,1,1.2,1])
            ca.markdown(f"**{f['id']}**")
            cb.markdown(f"<span style='color:{MUTED}'>{f['tp']}</span>",unsafe_allow_html=True)
            cc.markdown(f"<span style='color:{MUTED}'>{f['hrs']}/{f['iv']} hrs</span>",unsafe_allow_html=True)
            cd.progress(min(1.0,pct))
            ce.markdown(f"<span style='color:{RED if f['oil']=='Fail' else GREEN}'>Oil:{f['oil']}</span>",unsafe_allow_html=True)
            cf.markdown(f"<span style='background:{sc}22;color:{sc};padding:1px 8px;border-radius:10px;font-size:0.75rem;font-weight:700;'>{f['status']}</span>",unsafe_allow_html=True)
            cg.markdown(f"<span style='color:{RED if f['next']<=7 else AMBER if f['next']<=14 else MUTED}'>{f['next']}d</span>",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  RELIABILITY ENGINEER
# ══════════════════════════════════════════════════════════════════════════════
elif "Reliability Engineer" in page:
    st.markdown("<h1 style='margin:0;font-size:1.75rem;'>Reliability Engineer</h1><p style='color:#94A3B8;margin:0 0 20px 0;'>Asset health · Vibration trending · Predictive maintenance — Huntly & Pinjarra</p>",unsafe_allow_html=True)
    def _gvib(seed,base,drift):
        rng=_srng2(seed); v=[base]
        for _ in range(89):
            v.append(max(1.5,min(12,v[-1]+(rng()-0.48)*0.12+drift*0.01)))
        return [round(x*100)/100 for x in v]
    now=datetime.now(); d90=[now-timedelta(days=89-i) for i in range(90)]
    vib_c2=_gvib(42,3.2,1.2); vib_c1=_gvib(55,2.8,0.3); vib_kln=_gvib(66,4.1,0.5)
    ASSETS=[
        dict(id="C1",name="Primary Crusher 1",tp="Jaw Crusher",loc="Huntly Mine",health=92,vib=round(vib_c1[-1],2),motor=79,liner=68,next="14 days",mtbf=142,last="94 days ago",status="Normal",risk=12),
        dict(id="C2",name="Primary Crusher 2",tp="Jaw Crusher",loc="Huntly Mine",health=61,vib=round(vib_c2[-1],2),motor=88,liner=91,next="3 days", mtbf=142,last="41 days ago",status="Warning",risk=68),
        dict(id="KLN1",name="Rotary Kiln 1",  tp="Calcination Kiln",loc="Pinjarra",health=85,vib=4.1,motor=82,liner=54,next="28 days",mtbf=210,last="188 days ago",status="Normal",risk=18),
        dict(id="KLN2",name="Rotary Kiln 2",  tp="Calcination Kiln",loc="Pinjarra",health=78,vib=5.8,motor=85,liner=77,next="9 days", mtbf=210,last="64 days ago", status="Monitor",risk=41),
        dict(id="OC1",name="Overland Conveyor",tp="Belt Conveyor",loc="Huntly→Pinjarra",health=96,vib=1.8,motor=71,liner=22,next="45 days",mtbf=380,last="312 days ago",status="Normal",risk=4),
        dict(id="THK1",name="Primary Thickener",tp="Gravity Thickener",loc="Pinjarra",health=88,vib=2.3,motor=68,liner=45,next="21 days",mtbf=95,last="78 days ago",status="Normal",risk=9),
    ]
    SC5={"Normal":GREEN,"Monitor":AMBER,"Warning":RED,"Critical":RED}
    critical=sum(1 for a in ASSETS if a["status"] in ("Warning","Critical"))
    _metrics(
        ("Asset health avg",f"{sum(a['health'] for a in ASSETS)//len(ASSETS)}%","Across all critical fixed plant"),
        ("Maint. due ≤14 days",sum(1 for a in ASSETS if any(d in a['next'] for d in ['3','9'])),"Scheduled windows"),
        ("Est. unplanned cost","$68K","If C2 fails unplanned"),
        ("MTBF improvement","+23%","vs prior 12 months"),
    )
    if critical>0:
        st.error(f"⚠️ **Crusher 2 Main Bearing — Predicted failure in 8–14 days.** Vibration at {vib_c2[-1]} mm/s. Liner wear 91%. Recommend planned shutdown within 72 hrs.")
    c1,c2=st.columns(2)
    with c1:
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=d90,y=vib_c2, mode="lines",name="Crusher 2",   line=dict(color=RED,width=2)))
        fig.add_trace(go.Scatter(x=d90,y=vib_c1, mode="lines",name="Crusher 1",   line=dict(color=GREEN,width=1.5)))
        fig.add_trace(go.Scatter(x=d90,y=vib_kln,mode="lines",name="Kiln 1 drive",line=dict(color=AMBER,width=1.5)))
        fig.add_hline(y=7,line_dash="dash",line_color=RED,line_width=1.5,annotation_text="Alert threshold",annotation_font=dict(color=RED,size=10))
        fig.update_layout(**CHART_LAYOUT,height=250,title=dict(text="Bearing vibration — 90-day trend (mm/s)",font=dict(color=TXT,size=13)),
                          xaxis=dict(**_ax(False),showticklabels=False),yaxis=_ax(),
                          legend=dict(font=dict(color=TXT,size=11),bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig,use_container_width=True,config=dict(displayModeBar=False))
    with c2:
        fig2=go.Figure(go.Bar(y=[a["id"] for a in ASSETS],x=[a["health"] for a in ASSETS],orientation="h",
                               marker_color=[GREEN if a["health"]>85 else AMBER if a["health"]>70 else RED for a in ASSETS],
                               text=[f"{a['health']}%" for a in ASSETS],textposition="inside",textfont=dict(color="white",size=11)))
        fig2.add_vline(x=75,line_dash="dash",line_color=AMBER,line_width=1.5)
        fig2.update_layout(**CHART_LAYOUT,height=250,title=dict(text="Asset health index (%)",font=dict(color=TXT,size=13)),
                           xaxis=dict(**_ax(),range=[0,105]),yaxis=_ax(False),showlegend=False)
        st.plotly_chart(fig2,use_container_width=True,config=dict(displayModeBar=False))
    with st.container(border=True):
        st.markdown("**🔧 Asset Health Register**")
        for a in ASSETS:
            sc=SC5[a["status"]]
            with st.container(border=True):
                ca,cb=st.columns([4,1])
                with ca:
                    st.markdown(f"**{a['name']}** &nbsp;<span style='color:{MUTED};font-size:0.78rem;'>{a['tp']} · {a['loc']}</span> &nbsp;<span style='background:{sc}22;color:{sc};padding:1px 8px;border-radius:10px;font-size:0.72rem;font-weight:700;'>{a['status']}</span>",unsafe_allow_html=True)
                    cols=st.columns(6)
                    for col,(lbl,val,c) in zip(cols,[
                        ("Health",f"{a['health']}%",GREEN if a['health']>85 else AMBER if a['health']>70 else RED),
                        ("Vibration",f"{a['vib']} mm/s",RED if a['vib']>6 else AMBER if a['vib']>4 else GREEN),
                        ("Motor",f"{a['motor']}%",MUTED),("Liner",f"{a['liner']}%",RED if a['liner']>85 else AMBER if a['liner']>70 else GREEN),
                        ("MTBF",f"{a['mtbf']}d",CYAN),("Next maint",a['next'],MUTED),
                    ]):
                        col.markdown(f"<div style='font-size:0.7rem;color:{MUTED};text-transform:uppercase;'>{lbl}</div><div style='color:{c};font-weight:600;'>{val}</div>",unsafe_allow_html=True)
                with cb:
                    rc=RED if a["risk"]>50 else AMBER if a["risk"]>25 else GREEN
                    st.markdown(f"Last fail: {a['last']}<br><span style='color:{rc};font-weight:700;'>Risk: {a['risk']}/100</span>",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  SUPPLY CHAIN PLANNER
# ══════════════════════════════════════════════════════════════════════════════
elif "Supply Chain Planner" in page:
    st.markdown("<h1 style='margin:0;font-size:1.75rem;'>Supply Chain / Logistics Planner</h1><p style='color:#94A3B8;margin:0 0 20px 0;'>Refinery output · Rail schedule · Port stockpile · Vessel schedule · Demurrage risk — Bunbury</p>",unsafe_allow_html=True)
    r=_srng2(33); now=datetime.now()
    days7=[(now-timedelta(days=6-i)).strftime("%a") for i in range(7)]
    siloP=[round(72+r()*18) for _ in range(7)]; siloW=[round(68+r()*20) for _ in range(7)]
    portBin=[41200,38800,46100]
    VESSELS=[
        dict(name="MV Pinjarra Star", eta="6h",    vol=86400,cap=89000,status="Loading",  dem=False),
        dict(name="MV Alcoa Pacific", eta="4d 18h",vol=82100,cap=84000,status="En route", dem=False),
        dict(name="MV Bunbury Bulker",eta="1d 15h",vol=0,    cap=82000,status="Inbound",  dem=False),
        dict(name="MV Southern Cross",eta="8d 6h", vol=77900,cap=80000,status="En route", dem=False),
        dict(name="MV Wagerup Spirit",eta="4h",    vol=0,    cap=78000,status="At anchor",dem=True),
    ]
    tp=sum(portBin); demR=sum(1 for v in VESSELS if v["dem"])
    _metrics(
        ("Port stockpile total",f"{tp/1000:.1f}kt","3 bins × 50,000t capacity"),
        ("Bin utilisation",f"{round(tp/150000*100)}%","Combined 150,000t"),
        ("Demurrage risk",f"{demR} vessel" if demR>0 else "None","⚠ ~$10K/day" if demR>0 else "All on schedule"),
        ("Rail on schedule","3/3 consists","All dispatch windows met"),
        ("Demurrage savings","40%","vs pre-CoCo baseline"),
    )
    if demR>0:
        st.error("⚠️ **Demurrage accruing — MV Wagerup Spirit at anchor 4h+.** Est. ~$10,000/day.")
    c1,c2=st.columns([2,1])
    with c1:
        fig=go.Figure()
        fig.add_trace(go.Bar(name="Pinjarra silo %",x=days7,y=siloP,marker_color=CYAN,opacity=0.8))
        fig.add_trace(go.Bar(name="Wagerup silo %", x=days7,y=siloW,marker_color=AMBER,opacity=0.8))
        fig.add_hline(y=85,line_dash="dash",line_color=RED,line_width=1.5)
        fig.update_layout(**CHART_LAYOUT,barmode="group",height=230,title=dict(text="Refinery silo levels — 7-day trend (%)",font=dict(color=TXT,size=13)),
                          xaxis=_ax(False),yaxis=dict(**_ax(),range=[0,105]),legend=dict(font=dict(color=TXT,size=11),bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig,use_container_width=True,config=dict(displayModeBar=False))
    with c2:
        fig2=go.Figure(go.Bar(x=["Bin A","Bin B","Bin C"],y=portBin,
                               marker_color=[RED if v>45000 else AMBER if v>40000 else GREEN for v in portBin],
                               text=[f"{v/1000:.0f}kt" for v in portBin],textposition="inside",textfont=dict(color="white",size=11)))
        fig2.add_hline(y=50000,line_dash="dash",line_color=RED,line_width=1.5)
        fig2.update_layout(**CHART_LAYOUT,height=230,title=dict(text="Bunbury port bins (t)",font=dict(color=TXT,size=13)),
                           xaxis=_ax(False),yaxis=dict(**_ax(),range=[0,52000]),showlegend=False)
        st.plotly_chart(fig2,use_container_width=True,config=dict(displayModeBar=False))
    with st.container(border=True):
        st.markdown("**🚢 Vessel schedule — next 14 days**")
        for v in VESSELS:
            sc=RED if v["dem"] else GREEN
            ca,cb,cc,cd,ce=st.columns([2,1,2,1.5,1.5])
            ca.markdown(f"**{v['name']}**")
            cb.markdown(f"<span style='color:{MUTED}'>ETA: {v['eta']}</span>",unsafe_allow_html=True)
            vol_str = f"{v['vol']/1000:.0f}kt alumina" if v['vol']>0 else 'Ballast'
            vol_col = GREEN if v['vol']>0 else MUTED
            cc.markdown(f"<span style='color:{vol_col}'>{vol_str}</span>",unsafe_allow_html=True)
            ce.markdown(f"<span style='background:{sc}22;color:{sc};padding:1px 8px;border-radius:10px;font-size:0.75rem;font-weight:700;'>{'⚠ Demurrage' if v['dem'] else v['status']}</span>",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  TRAIN / PORT COORDINATOR
# ══════════════════════════════════════════════════════════════════════════════
elif "Train / Port Coordinator" in page:
    st.markdown("<h1 style='margin:0;font-size:1.75rem;'>Train / Port Loadout Coordinator</h1><p style='color:#94A3B8;margin:0 0 20px 0;'>Silo levels · Rail dispatch · Port stockpile · 48-hour schedule — Pinjarra, Wagerup & Bunbury</p>",unsafe_allow_html=True)
    r=_srng2(88); now=datetime.now()
    hrs48=[now-timedelta(hours=47-i) for i in range(48)]
    sp48=[round(70+r()*20) for _ in range(48)]; sw48=[round(65+r()*25) for _ in range(48)]
    pf=[round(82000+r()*10000) for _ in range(48)]
    DISP=[
        dict(id="PJR-001",orig="Pinjarra",dep="06:00",arr="07:30",pay=2110,mois=0.05,stat="Departed"),
        dict(id="PJR-002",orig="Pinjarra",dep="09:45",arr="11:15",pay=2085,mois=0.06,stat="Loading"),
        dict(id="PJR-003",orig="Pinjarra",dep="13:30",arr="15:00",pay=2100,mois=0.04,stat="Scheduled"),
        dict(id="WGR-001",orig="Wagerup", dep="07:15",arr="07:55",pay=2090,mois=0.07,stat="Arrived"),
        dict(id="WGR-002",orig="Wagerup", dep="10:00",arr="10:40",pay=2075,mois=0.06,stat="Loading"),
        dict(id="WGR-003",orig="Wagerup", dep="14:00",arr="14:40",pay=0,   mois=None,stat="Scheduled"),
    ]
    dispatched=sum(1 for d in DISP if d["stat"] in ("Departed","Arrived"))
    totalPay=sum(d["pay"] for d in DISP if d["pay"]>0)
    _metrics(
        ("Trains dispatched today",f"{dispatched}/6","Pinjarra + Wagerup"),
        ("Total payload today",f"{totalPay/1000:.1f}kt","Alumina dispatched"),
        ("Port bin utilisation","83%","124,000t of 150,000t"),
        ("Moisture compliance","6/6 ✓","All below 0.5% IMO limit"),
        ("Rail idle time saved","50%","vs whiteboard scheduling"),
    )
    x48=hrs48[::4]
    c1,c2=st.columns(2)
    with c1:
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=x48,y=sp48[::4],mode="lines",name="Pinjarra silo %",line=dict(color=CYAN,width=2)))
        fig.add_trace(go.Scatter(x=x48,y=sw48[::4],mode="lines",name="Wagerup silo %", line=dict(color=AMBER,width=2)))
        fig.add_hline(y=85,line_dash="dash",line_color=RED,line_width=1.5)
        fig.update_layout(**CHART_LAYOUT,height=220,title=dict(text="Silo levels — 48h trend (%)",font=dict(color=TXT,size=13)),
                          xaxis=dict(**_ax(False),showticklabels=False),yaxis=dict(**_ax(),range=[50,100]),
                          legend=dict(font=dict(color=TXT,size=11),bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig,use_container_width=True,config=dict(displayModeBar=False))
    with c2:
        fig2=go.Figure(go.Scatter(x=x48,y=pf[::4],mode="lines",line=dict(color=GREEN,width=2),fill="tozeroy",fillcolor="rgba(16,185,129,0.08)"))
        fig2.add_hline(y=150000,line_dash="dash",line_color=RED,line_width=1.5)
        fig2.update_layout(**CHART_LAYOUT,height=220,title=dict(text="Bunbury port inventory (t)",font=dict(color=TXT,size=13)),
                           xaxis=dict(**_ax(False),showticklabels=False),yaxis=_ax(),showlegend=False)
        st.plotly_chart(fig2,use_container_width=True,config=dict(displayModeBar=False))
    with st.container(border=True):
        st.markdown("**🚂 48-hour dispatch schedule**")
        for d in DISP:
            sc={"Arrived":GREEN,"Departed":CYAN,"Loading":AMBER,"Scheduled":MUTED}[d["stat"]]
            oc=CYAN if d["orig"]=="Pinjarra" else AMBER
            ca,cb,cc,cd,ce,cf,cg=st.columns([1,1,1,1,1.2,1,1.2])
            ca.markdown(f"**{d['id']}**")
            cb.markdown(f"<span style='color:{oc}'>{d['orig']}</span>",unsafe_allow_html=True)
            cc.markdown(f"<span style='color:{MUTED}'>Dep:{d['dep']}</span>",unsafe_allow_html=True)
            cd.markdown(f"<span style='color:{MUTED}'>Arr:{d['arr']}</span>",unsafe_allow_html=True)
            pay_str=f"{d['pay']:,}t" if d["pay"]>0 else "Returning"
            ce.markdown(f"<span style='color:{TXT if d['pay']>0 else MUTED}'>{pay_str}</span>",unsafe_allow_html=True)
            mois_str=f"H₂O:{d['mois']}%" if d["mois"] is not None else "—"
            mois_col=GREEN if d["mois"] is not None and d["mois"]<0.5 else RED if d["mois"] is not None else MUTED
            cf.markdown(f"<span style='color:{mois_col}'>{mois_str}</span>",unsafe_allow_html=True)
            cg.markdown(f"<span style='background:{sc}22;color:{sc};padding:1px 8px;border-radius:10px;font-size:0.75rem;font-weight:700;'>{d['stat']}</span>",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PROCUREMENT / WAREHOUSE
# ══════════════════════════════════════════════════════════════════════════════
elif "Procurement" in page:
    st.markdown("<h1 style='margin:0;font-size:1.75rem;'>Procurement / Warehouse Manager</h1><p style='color:#94A3B8;margin:0 0 20px 0;'>Critical spares · Predictive reorder · Wear-based consumption · Supplier lead times</p>",unsafe_allow_html=True)
    SPARES=[
        dict(part="Jaw crusher liner set",        stock=1,mn=2,lead=14,wear=91,  reorder="Overdue",  cost=28000,status="Order now"),
        dict(part="Haul truck engine filter kit", stock=4,mn=4,lead=3, wear=None,reorder="11 Jun",  cost=480,  status="Low"),
        dict(part="Conveyor belt splice kit (×2)",stock=3,mn=2,lead=7, wear=22,  reorder="15 Jul",  cost=3200, status="OK"),
        dict(part="Pump impeller (Warman 4/3)",   stock=2,mn=2,lead=10,wear=58,  reorder="28 Jun",  cost=4800, status="OK"),
        dict(part="Calciner refractory brick (t)",stock=4,mn=3,lead=21,wear=54,  reorder="20 Jul",  cost=6200, status="OK"),
        dict(part="Haul truck tyre 27.00R49",     stock=0,mn=1,lead=21,wear=None,reorder="Critical",cost=32000,status="Critical"),
        dict(part='Drill bit tricone 9⅞"',        stock=8,mn=4,lead=5, wear=None,reorder="2 Aug",   cost=1100, status="OK"),
        dict(part="Thickener rake arm bearing",   stock=1,mn=1,lead=14,wear=45,  reorder="4 Jul",   cost=2400, status="OK"),
    ]
    SC6={"Critical":RED,"Order now":RED,"Low":AMBER,"OK":GREEN}
    critical=sum(1 for s in SPARES if s["status"] in ("Critical","Order now"))
    totalVal=sum(s["stock"]*s["cost"] for s in SPARES)
    months=["Jan","Feb","Mar","Apr","May","Jun"]
    _metrics(
        ("Critical stockouts",critical,"⚠ Production risk" if critical>0 else "✓ No stockout risk"),
        ("Spares inventory value",f"${totalVal/1000:.0f}K","On-hand stock"),
        ("Items below min stock",sum(1 for s in SPARES if s["stock"]<s["mn"]),"Reorder triggered"),
        ("Cost reduction","30%","vs reactive ordering baseline"),
    )
    if critical>0:
        with st.container(border=True):
            st.markdown(f"<span style='color:{RED};font-weight:700;'>🚨 {critical} critical spare issue(s)</span>",unsafe_allow_html=True)
            for s in SPARES:
                if s["status"] in ("Critical","Order now"):
                    st.markdown(f"• **{s['part']}** — Stock: {s['stock']} (min: {s['mn']}) · Lead: {s['lead']}d · ${s['cost']:,}")
    c1,c2=st.columns(2)
    with c1:
        labels=[s["part"][:28]+"…" if len(s["part"])>28 else s["part"] for s in SPARES]
        vals=[s["stock"]/s["mn"]*100 for s in SPARES]
        fig=go.Figure(go.Bar(y=labels,x=vals,orientation="h",
                               marker_color=[SC6[s["status"]] for s in SPARES],
                               text=[f"{s['stock']}/{s['mn']}" for s in SPARES],textposition="outside",textfont=dict(color=TXT,size=9)))
        fig.add_vline(x=100,line_dash="dash",line_color=AMBER,line_width=1.5)
        fig.update_layout(**CHART_LAYOUT,height=300,title=dict(text="Stock level vs minimum (% of min)",font=dict(color=TXT,size=13)),
                          xaxis=dict(**_ax(),range=[0,220]),yaxis=dict(**_ax(False),tickfont=dict(color=MUTED,size=9)),showlegend=False)
        st.plotly_chart(fig,use_container_width=True,config=dict(displayModeBar=False))
    with c2:
        fig2=go.Figure()
        fig2.add_trace(go.Bar(name="Planned spend",x=months,y=[v*1000 for v in [42,38,51,44,48,53]],marker_color=CYAN,opacity=0.7))
        fig2.add_trace(go.Bar(name="Actual spend", x=months,y=[v*1000 for v in [38,41,49,46,52,58]],marker_color=AMBER,opacity=0.9))
        fig2.update_layout(**CHART_LAYOUT,barmode="group",height=300,title=dict(text="Monthly procurement spend ($)",font=dict(color=TXT,size=13)),
                           xaxis=_ax(False),yaxis=_ax(),legend=dict(font=dict(color=TXT,size=11),bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig2,use_container_width=True,config=dict(displayModeBar=False))
    with st.container(border=True):
        st.markdown("**📦 Critical spares register**")
        for s in SPARES:
            sc=SC6[s["status"]]
            ca,cb,cc,cd,ce,cf=st.columns([3,1.5,1,1.5,1,1.2])
            ca.markdown(s["part"])
            cb.markdown(f"Stock:<span style='color:{GREEN if s['stock']>=s['mn'] else RED};font-weight:700;'>{s['stock']}</span>/{s['mn']}",unsafe_allow_html=True)
            cc.markdown(f"<span style='color:{MUTED}'>Lead:{s['lead']}d</span>",unsafe_allow_html=True)
            if s["wear"] is not None: cd.progress(s["wear"]/100)
            ce.markdown(f"<span style='color:{MUTED}'>${s['cost']:,}</span>",unsafe_allow_html=True)
            cf.markdown(f"<span style='background:{sc}22;color:{sc};padding:1px 8px;border-radius:10px;font-size:0.75rem;font-weight:700;'>{s['status']}</span>",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  ENVIRONMENTAL ADVISOR
# ══════════════════════════════════════════════════════════════════════════════
elif "Environmental Advisor" in page:
    st.markdown("<h1 style='margin:0;font-size:1.75rem;'>Environmental Advisor</h1><p style='color:#94A3B8;margin:0 0 20px 0;'>EPA licence compliance · Dust, noise, water, rehabilitation — Huntly Mine, WA</p>",unsafe_allow_html=True)
    r=_srng2(11); now=datetime.now()
    hrs24=[now-timedelta(hours=23-i) for i in range(24)]
    pm10=[max(8,min(85,38+(r()-0.5)*36)) for _ in range(24)]
    pm25=[max(3,min(35,14+(r()-0.5)*16)) for _ in range(24)]
    noise=[max(42,min(98,72+(r()-0.5)*28)) for _ in range(24)]
    water=[max(140,min(420,280+(r()-0.5)*120)) for _ in range(24)]
    REHAB=[
        dict(zone="Zone 4A",target=65,done=62,status="On track"),
        dict(zone="Zone 4B",target=40,done=44,status="Ahead"),
        dict(zone="Zone 5A",target=80,done=68,status="Behind"),
        dict(zone="Zone 5B",target=30,done=30,status="Complete"),
        dict(zone="Zone 6A",target=55,done=41,status="Behind"),
        dict(zone="Zone 6B",target=20,done=20,status="Complete"),
    ]
    EPA=[
        dict(param="PM10 (24-hr avg)",      limit=50, current=38.2,unit="µg/m³",status="Compliant"),
        dict(param="PM2.5 (24-hr avg)",     limit=25, current=14.1,unit="µg/m³",status="Compliant"),
        dict(param="Blast noise (dBL)",     limit=115,current=94,  unit="dBL",  status="Compliant"),
        dict(param="Ground vib (PPV)",      limit=20, current=8.2, unit="mm/s", status="Compliant"),
        dict(param="Water extraction",      limit=520,current=484, unit="ML/mo",status="Compliant"),
        dict(param="Rehab ha YTD",          limit=550,current=285, unit="ha",   status="On track"),
        dict(param="Clearing approval buf.",limit=10, current=8.4, unit="%",    status="Monitor"),
        dict(param="Haul road dust PM10",   limit=50, current=62,  unit="µg/m³",status="Exceedance"),
    ]
    exceedances=sum(1 for e in EPA if e["status"]=="Exceedance")
    avgPM10=sum(pm10)/len(pm10)
    totalRehab=sum(r["done"] for r in REHAB); totalTarget=sum(r["target"] for r in REHAB)
    _metrics(
        ("EPA exceedances",exceedances,"⚠️ Action required" if exceedances>0 else "✓ All within limits"),
        ("PM10 24-hr avg",f"{avgPM10:.1f} µg/m³","Limit: 50 µg/m³"),
        ("Rehab YTD",f"{totalRehab} ha",f"Target: {totalTarget} ha"),
        ("Water use MTD","484 ML","Limit: 520 ML/month"),
        ("Fauna detections","3","Last 24 hrs"),
        ("Active blast notices","1","Zone 5A — 14:00 today"),
    )
    if exceedances>0:
        st.error("⚠️ **EPA Exceedance — Haul Road PM10:** 62 µg/m³ (limit 50). Water cart dispatched. If sustained >2 hrs, blast program must be suspended.")
    c1,c2=st.columns(2)
    with c1:
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=hrs24,y=pm10,mode="lines",name="PM10", line=dict(color=AMBER,width=2),fill="tozeroy",fillcolor="rgba(245,158,11,0.08)"))
        fig.add_trace(go.Scatter(x=hrs24,y=pm25,mode="lines",name="PM2.5",line=dict(color=CYAN,width=2)))
        fig.add_hline(y=50,line_dash="dash",line_color=RED,line_width=1.5,annotation_text="EPA limit 50",annotation_font=dict(color=RED,size=10))
        fig.update_layout(**CHART_LAYOUT,height=220,title=dict(text="Dust — PM10/PM2.5 (µg/m³)",font=dict(color=TXT,size=13)),
                          xaxis=dict(**_ax(False),showticklabels=False),yaxis=_ax(),legend=dict(font=dict(color=TXT,size=11),bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig,use_container_width=True,config=dict(displayModeBar=False))
    with c2:
        fig2=go.Figure(go.Scatter(x=hrs24,y=noise,mode="lines",line=dict(color="#7C3AED",width=2),fill="tozeroy",fillcolor="rgba(124,58,237,0.08)"))
        fig2.add_hline(y=115,line_dash="dash",line_color=RED,line_width=1.5,annotation_text="EPA limit",annotation_font=dict(color=RED,size=10))
        fig2.update_layout(**CHART_LAYOUT,height=220,title=dict(text="Community noise (dBL)",font=dict(color=TXT,size=13)),
                           xaxis=dict(**_ax(False),showticklabels=False),yaxis=_ax(),showlegend=False)
        st.plotly_chart(fig2,use_container_width=True,config=dict(displayModeBar=False))
    c1,c2=st.columns([2,1])
    with c1:
        fig3=go.Figure()
        fig3.add_trace(go.Bar(name="Completed",x=[r["zone"] for r in REHAB],y=[r["done"] for r in REHAB],
                               marker_color=[GREEN if r["done"]>=r["target"] else AMBER if r["done"]/r["target"]>0.85 else RED for r in REHAB]))
        fig3.add_trace(go.Bar(name="Target",   x=[r["zone"] for r in REHAB],y=[r["target"] for r in REHAB],marker_color="rgba(148,163,184,0.25)"))
        fig3.update_layout(**CHART_LAYOUT,barmode="overlay",height=230,title=dict(text="Rehabilitation progress by zone (ha)",font=dict(color=TXT,size=13)),
                           xaxis=_ax(False),yaxis=_ax(),legend=dict(font=dict(color=TXT,size=11),bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig3,use_container_width=True,config=dict(displayModeBar=False))
    with c2:
        fig4=go.Figure(go.Bar(x=hrs24[::4],y=water[::4],marker_color=BLUE,opacity=0.8))
        fig4.update_layout(**CHART_LAYOUT,height=230,title=dict(text="Haul road water use (kL/hr)",font=dict(color=TXT,size=13)),
                           xaxis=dict(**_ax(False),showticklabels=False),yaxis=_ax(),showlegend=False)
        st.plotly_chart(fig4,use_container_width=True,config=dict(displayModeBar=False))
    with st.container(border=True):
        st.markdown("**📋 EPA Licence Compliance**")
        SC7={"Compliant":(GREEN,"✓"),"On track":(GREEN,"✓"),"Ahead":(CYAN,"▲"),"Monitor":(AMBER,"⚠"),"Behind":(AMBER,"↓"),"Exceedance":(RED,"✗"),"Complete":(BLUE,"●")}
        for e in EPA:
            col,sym=SC7.get(e["status"],(MUTED,"?"))
            ca,cb,cc,cd,ce=st.columns([3,2,1.5,2,1.5])
            ca.markdown(e["param"])
            cb.progress(min(1.0,e["current"]/e["limit"]))
            cc.markdown(f"{e['current']} {e['unit']}")
            cd.markdown(f"<span style='color:{MUTED}'>limit: {e['limit']} {e['unit']}</span>",unsafe_allow_html=True)
            ce.markdown(f"<span style='background:{col}22;color:{col};padding:1px 8px;border-radius:10px;font-size:0.75rem;font-weight:700;'>{sym} {e['status']}</span>",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  SAFETY / HSE MANAGER
# ══════════════════════════════════════════════════════════════════════════════
elif "Safety" in page:
    st.markdown("<h1 style='margin:0;font-size:1.75rem;'>Safety / HSE Manager</h1><p style='color:#94A3B8;margin:0 0 20px 0;'>Incident tracking · Fatigue management · Proximity alerts · Training compliance — Huntly Mine</p>",unsafe_allow_html=True)
    months=["Jan","Feb","Mar","Apr","May","Jun"]
    inc_m=[1,0,2,1,0,1]; nm_m=[3,2,4,2,1,3]; dl=[1,0,3,1,0,0]
    INCIDENTS=[
        dict(id="INC-2026-047",sev="High",  tp="Near-miss",date="2026-06-09",time="10:34",loc="Pit 4 haul road",
             desc="Haul truck T07 vs water cart — <3m clearance at blind crest. Operator fatigue 82%.",status="Investigation open",dl=0),
        dict(id="INC-2026-041",sev="Medium",tp="Spill",    date="2026-06-03",time="14:22",loc="S5 digestion area",
             desc="NaOH caustic spill — 20L from cracked pipe coupling. Contained within bund.",status="Closed",dl=0),
        dict(id="INC-2026-038",sev="Low",   tp="LTI",      date="2026-05-28",time="09:15",loc="Maintenance workshop",
             desc="Hand laceration — chip from angle grinder. 1 day lost time.",status="Closed",dl=1),
        dict(id="INC-2026-031",sev="High",  tp="Near-miss",date="2026-05-14",time="16:48",loc="ROM pad",
             desc="Excavator swing hazard — GRD-01 in blind spot during face-cleaning pass.",status="Closed",dl=0),
    ]
    SC8={"High":RED,"Medium":AMBER,"Low":MUTED}; SC9={"Investigation open":RED,"Closed":GREEN}
    openInc=sum(1 for i in INCIDENTS if i["status"]=="Investigation open")
    PERSONNEL=[dict(name=f"Operator {i:03d}",role="Haul Truck",zone="Pit 4",fatigue=50+i%45,hours=i%12+6) for i in range(42)]
    HIGH_FAT=[p for p in PERSONNEL if p["fatigue"]>70]
    _metrics(
        ("Days since LTI","41","Last: 1-day laceration (May 28)"),
        ("Open investigations",openInc,"⚠️ INC-2026-047 critical" if openInc>0 else "✓ All closed"),
        ("High-fatigue personnel",len(HIGH_FAT),"Score >70% on fatigue index"),
        ("Training overdue","6","Hazard awareness & certs"),
        ("Proximity alerts today","7","3 high-severity"),
        ("Active personnel",len(PERSONNEL),f"{len(PERSONNEL)} on site"),
    )
    st.error("🚨 **Open Investigation — INC-2026-047.** Haul truck T07 vs water cart — Pit 4, 10:34 AWST. Operator fatigue 82%. Report due 2026-06-10.")
    c1,c2=st.columns(2)
    with c1:
        fig=go.Figure()
        fig.add_trace(go.Bar(name="Recordable incidents",x=months,y=inc_m,marker_color=RED,opacity=0.8))
        fig.add_trace(go.Bar(name="Near-misses",         x=months,y=nm_m, marker_color=AMBER,opacity=0.8))
        fig.update_layout(**CHART_LAYOUT,barmode="group",height=240,title=dict(text="2026 incident trend",font=dict(color=TXT,size=13)),
                          xaxis=_ax(False),yaxis=_ax(),legend=dict(font=dict(color=TXT,size=11),bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig,use_container_width=True,config=dict(displayModeBar=False))
    with c2:
        fig2=go.Figure(go.Bar(x=months,y=dl,marker_color=[RED if d>3 else AMBER if d>1 else GREEN for d in dl],
                               text=[str(d) for d in dl],textposition="outside",textfont=dict(color=TXT,size=11)))
        fig2.update_layout(**CHART_LAYOUT,height=240,title=dict(text="Lost time days by month",font=dict(color=TXT,size=13)),
                           xaxis=_ax(False),yaxis=_ax(),showlegend=False)
        st.plotly_chart(fig2,use_container_width=True,config=dict(displayModeBar=False))
    with st.container(border=True):
        st.markdown("**📋 Incident Register (last 30 days)**")
        for inc in INCIDENTS:
            sc=SC8[inc["sev"]]; st2=SC9[inc["status"]]
            with st.container(border=True):
                ca,cb=st.columns([5,1])
                ca.markdown(f"**{inc['id']}** &nbsp;<span style='background:{sc}22;color:{sc};padding:1px 8px;border-radius:10px;font-size:0.72rem;font-weight:700;'>{inc['sev']} · {inc['tp']}</span> &nbsp;<span style='color:{MUTED};font-size:0.78rem;'>{inc['date']} {inc['time']} · {inc['loc']}</span>",unsafe_allow_html=True)
                ca.markdown(inc["desc"])
                cb.markdown(f"<span style='color:{st2};font-weight:600;'>{'🔴' if inc['status']=='Investigation open' else '🟢'} {inc['status']}</span>",unsafe_allow_html=True)
                if inc["dl"]>0: cb.markdown(f"<span style='color:{RED}'>{inc['dl']} day(s) lost</span>",unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown(f"**😴 Fatigue Management — {len(HIGH_FAT)} flagged**")
            shown=0
            for p in PERSONNEL:
                if p["fatigue"]>55 and shown<6:
                    fc=RED if p["fatigue"]>70 else AMBER
                    st.markdown(f"<span style='color:{TXT}'>{p['name']}</span> &nbsp;<span style='color:{MUTED};font-size:0.78rem;'>{p['role']} · {p['hours']}h</span>",unsafe_allow_html=True)
                    st.progress(p["fatigue"]/100)
                    shown+=1
            if HIGH_FAT: st.error(f"⚠️ {len(HIGH_FAT)} operator(s) above 70% — mandatory rest required")
    with c2:
        with st.container(border=True):
            st.markdown("**📍 Proximity Alerts Today**")
            for time_,assets,loc,sev,dist in [
                ("10:34","T07 + WC-03","Pit 4 crest","High","< 3m"),
                ("08:12","T03 + EX-02","Pit 3 access","Medium","8m"),
                ("07:45","GRD-01 + T11","ROM pad entry","Low","12m"),
            ]:
                sc=RED if sev=="High" else AMBER if sev=="Medium" else MUTED
                ca,cb,cc,cd=st.columns([1,1.5,2,1])
                ca.markdown(f"<span style='color:{MUTED}'>{time_}</span>",unsafe_allow_html=True)
                cb.markdown(f"<span style='color:{sc};font-weight:700;'>{sev}</span>",unsafe_allow_html=True)
                cc.markdown(f"{assets} · {loc}")
                cd.markdown(f"<span style='color:{sc};font-weight:700;'>{dist}</span>",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  ENERGY / SUSTAINABILITY
# ══════════════════════════════════════════════════════════════════════════════
elif "Energy" in page:
    st.markdown("<h1 style='margin:0;font-size:1.75rem;'>Energy / Sustainability Manager</h1><p style='color:#94A3B8;margin:0 0 20px 0;'>Scope 1 & 2 emissions · 2030 reduction pathway · ESG reporting — Alcoa Australia</p>",unsafe_allow_html=True)
    months=["Jan","Feb","Mar","Apr","May","Jun"]
    s1m=[1820,1740,1890,1810,1960,1840]; s1c=[4200,4050,4380,4190,4420,4280]
    s2e=[2100,2080,2140,2090,2160,2110]; s2r=[380,365,392,378,401,385]
    tgt=[round(9500-i*120) for i in range(6)]
    tot=[s1m[i]+s1c[i]+s2e[i]+s2r[i] for i in range(6)]
    mtd=tot[5]; vs30=round((mtd-tgt[5])/tgt[5]*100)
    _metrics(
        ("Total Scope 1+2 MTD",f"{mtd/1000:.1f}kt CO₂e",f"{'▲ +' if vs30>0 else '▼ '}{abs(vs30)}% vs 2030 target path"),
        ("Mine diesel (Scope 1)",f"{s1m[5]}t CO₂e","Haul fleet + plant"),
        ("Calciner gas (Scope 1)",f"{s1c[5]}t CO₂e","Largest single source (49%)"),
        ("Grid electricity (Sc2)",f"{s2e[5]}t CO₂e","Refinery + conveyor"),
        ("Rail transport (Sc2)",f"{s2r[5]}t CO₂e","Pinjarra/Wagerup → Bunbury"),
        ("Reporting cycle saved","85%","3 weeks → 2-3 days (CoCo)"),
    )
    c1,c2=st.columns(2)
    with c1:
        fig=go.Figure()
        for ys,nm,col in [(s1m,"Mine diesel",AMBER),(s1c,"Calciner gas",RED),(s2e,"Grid electricity",CYAN),(s2r,"Rail transport",BLUE)]:
            fig.add_trace(go.Bar(name=nm,x=months,y=ys,marker_color=col,opacity=0.9))
        fig.add_trace(go.Scatter(name="2030 target pathway",x=months,y=tgt,mode="lines+markers",
                                  line=dict(color=GREEN,width=2,dash="dash"),marker=dict(size=6)))
        fig.update_layout(**CHART_LAYOUT,barmode="stack",height=280,title=dict(text="Monthly Scope 1+2 emissions vs 2030 target (t CO₂e)",font=dict(color=TXT,size=13)),
                          xaxis=_ax(False),yaxis=_ax(),legend=dict(font=dict(color=TXT,size=10),bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig,use_container_width=True,config=dict(displayModeBar=False))
    with c2:
        fig2=go.Figure(go.Pie(labels=["Calciner gas (S1)","Grid electricity (S2)","Mine diesel (S1)","Rail transport (S2)"],
                               values=[s1c[5],s2e[5],s1m[5],s2r[5]],
                               marker_colors=[RED,CYAN,AMBER,BLUE],hole=0.4,
                               textinfo="percent+label",textfont=dict(color=TXT,size=10)))
        fig2.update_layout(**CHART_LAYOUT,height=280,title=dict(text="Emissions breakdown — June MTD",font=dict(color=TXT,size=13)),showlegend=False)
        st.plotly_chart(fig2,use_container_width=True,config=dict(displayModeBar=False))
    with st.container(border=True):
        st.markdown("**🎯 Top 3 reduction opportunities**")
        for rank,action,saving,effort,timeline,cost in [
            (1,"Calciner fuel switch — natural gas to green hydrogen blend (20%)","−856t CO₂e/month","High","2027","$12M capex"),
            (2,"Haul fleet electrification — pilot 3× electric haul trucks at Huntly","−320t CO₂e/month","Medium","2026","$8M"),
            (3,"Solar PV + battery at Pinjarra refinery (10 MW)","−185t CO₂e/month","Low","2025","$14M"),
        ]:
            with st.container(border=True):
                ca,cb,cc=st.columns([0.3,6,1.5])
                ca.markdown(f"**{rank}**")
                cb.markdown(f"**{action}**")
                cc.markdown(f"<span style='color:{GREEN};font-weight:700;'>{saving}</span>",unsafe_allow_html=True)
                st.caption(f"Effort: {effort} · Timeline: {timeline} · Investment: {cost}")

