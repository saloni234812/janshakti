"""
JanaShakti Platform - FastAPI Backend Application
Modules: sync, dashboard, classify, plan, static asset mounting.
"""

import sys
import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import joblib
import pandas as pd

# Base Directories
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
CONTENT_DIR = STATIC_DIR / "content"
MODEL_PATH = BASE_DIR / "model" / "clf.joblib"
COOCCUR_PATH = BASE_DIR / "train" / "cooccurrence_matrix.json"
DATA_DIR = BASE_DIR / "data"
SUBMISSIONS_FILE = DATA_DIR / "submissions.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# App Initialization
app = FastAPI(
    title="JanaShakti Platform API",
    description="Citizen River Intelligence, Participatory Monitoring, and Rejuvenation Action Planning",
    version="1.0.0",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-Memory Cache
app_state: Dict[str, Any] = {
    "model_bundle": None,
    "rivers": {},
    "cooccur_data": {},
    "submissions": [],
}


# ================= DATA MODELS =================
class ObservationItem(BaseModel):
    id: Optional[str] = None
    river_id: str = Field(..., example="ganga-varanasi")
    location: str = Field(..., example="Assi Ghat Steps")
    text: str = Field(..., example="Thick white foam floating on water with chemical smell")
    symptoms: Optional[str] = Field("", example="foam;chemical_odor")
    water_clarity: Optional[str] = Field("murky", example="murky")
    flow_rate: Optional[str] = Field("normal", example="normal")
    surrounding_activity: Optional[str] = Field("industrial", example="industrial")
    severity: Optional[str] = None
    category: Optional[str] = None
    created_at: Optional[str] = None


class SyncPayload(BaseModel):
    items: List[ObservationItem]


class ClassifyRequest(BaseModel):
    text: str = Field(..., example="Dark chemical discharge from textile factory, acid smell")
    symptoms: Optional[str] = Field("", example="chemical_odor;foam")
    water_clarity: Optional[str] = Field("murky", example="murky")
    flow_rate: Optional[str] = Field("sluggish", example="sluggish")
    surrounding_activity: Optional[str] = Field("industrial", example="industrial")


class PlanRequest(BaseModel):
    river_id: str = Field(..., example="ganga-varanasi")
    category: Optional[str] = Field(None, example="Industrial Effluents")


# ================= LIFESPAN & HELPER LOADERS =================
def load_all_resources():
    """Loads ML model, rivers dataset, co-occurrence matrix, and submissions."""
    # 1. Load ML Model Bundle
    if MODEL_PATH.exists():
        try:
            app_state["model_bundle"] = joblib.load(MODEL_PATH)
            print(f"[Init] ML Classifier loaded from {MODEL_PATH}")
        except Exception as e:
            print(f"[Warning] Failed to load model bundle: {e}")
    else:
        print("[Warning] model/clf.joblib not found. Run train/train_classifier.py first.")

    # 2. Load Rivers Dataset
    rivers_file = CONTENT_DIR / "rivers.json"
    if rivers_file.exists():
        try:
            with open(rivers_file, "r", encoding="utf-8") as f:
                rivers_json = json.load(f)
                app_state["rivers"] = {r["id"]: r for r in rivers_json.get("rivers", [])}
            print(f"[Init] Loaded {len(app_state['rivers'])} river profiles from rivers.json")
        except Exception as e:
            print(f"[Warning] Failed to load rivers.json: {e}")

    # 3. Load Co-occurrence Matrix
    if COOCCUR_PATH.exists():
        try:
            with open(COOCCUR_PATH, "r", encoding="utf-8") as f:
                app_state["cooccur_data"] = json.load(f)
            print("[Init] Co-occurrence matrix loaded.")
        except Exception as e:
            print(f"[Warning] Failed to load co-occurrence matrix: {e}")

    # 4. Load Submissions
    if SUBMISSIONS_FILE.exists():
        try:
            with open(SUBMISSIONS_FILE, "r", encoding="utf-8") as f:
                app_state["submissions"] = json.load(f)
            print(f"[Init] Loaded {len(app_state['submissions'])} saved submissions.")
        except Exception:
            app_state["submissions"] = []
    else:
        # Seed initial submissions from answers.csv
        seed_answers_csv = BASE_DIR / "train" / "answers.csv"
        if seed_answers_csv.exists():
            df_seed = pd.read_csv(seed_answers_csv)
            seeded = []
            for _, row in df_seed.head(20).iterrows():
                seeded.append({
                    "id": str(row.get("id")),
                    "river_id": str(row.get("river_id")),
                    "location": str(row.get("location")),
                    "text": str(row.get("text")),
                    "symptoms": str(row.get("symptoms", "")),
                    "water_clarity": str(row.get("water_clarity", "murky")),
                    "flow_rate": str(row.get("flow_rate", "normal")),
                    "surrounding_activity": str(row.get("surrounding_activity", "domestic_sewage")),
                    "severity": str(row.get("severity", "Medium")),
                    "category": str(row.get("category", "Domestic Sewage & Outfalls")),
                    "created_at": datetime.utcnow().isoformat(),
                })
            app_state["submissions"] = seeded
            save_submissions_to_disk()
            print(f"[Init] Seeded {len(seeded)} initial submissions from answers.csv")


def save_submissions_to_disk():
    try:
        with open(SUBMISSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(app_state["submissions"], f, indent=2)
    except Exception as e:
        print(f"[Warning] Failed to persist submissions: {e}")


# Eager load on module import
load_all_resources()


@app.on_event("startup")
def on_startup():
    load_all_resources()


# ================= 1. CLASSIFY ENDPOINT =================
@app.post("/api/classify")
def classify_observation(payload: ClassifyRequest):
    """
    Infers pollution category, severity, confidence, and recommended action
    using the scikit-learn pipeline bundle in model/clf.joblib.
    """
    bundle = app_state.get("model_bundle")
    if not bundle:
        # Re-attempt loading
        if MODEL_PATH.exists():
            bundle = joblib.load(MODEL_PATH)
            app_state["model_bundle"] = bundle
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Classifier model not yet trained or loaded.",
            )

    full_text = payload.text + " " + payload.symptoms.replace(";", " ")
    input_df = pd.DataFrame([{
        "full_text": full_text,
        "water_clarity": payload.water_clarity or "murky",
        "flow_rate": payload.flow_rate or "normal",
        "surrounding_activity": payload.surrounding_activity or "domestic_sewage",
    }])

    cat_model = bundle["cat_model"]
    sev_model = bundle["sev_model"]

    # Category prediction & confidence
    cat_pred = cat_model.predict(input_df)[0]
    cat_probs = cat_model.predict_proba(input_df)[0]
    classes = cat_model.classes_
    prob_dict = {cls: round(float(p), 4) for cls, p in zip(classes, cat_probs)}
    confidence = round(float(max(cat_probs)), 3)

    # Severity prediction
    sev_pred = sev_model.predict(input_df)[0]

    # Recommended action lookup
    action_map = bundle.get("action_map", {})
    recommended_action = action_map.get(cat_pred, "Comprehensive Site Inspection & Water Sampling")

    return {
        "predicted_category": cat_pred,
        "confidence": confidence,
        "probabilities": prob_dict,
        "severity": sev_pred,
        "recommended_action": recommended_action,
    }


# ================= 2. SYNC ENDPOINT =================
@app.post("/api/sync")
def sync_offline_submissions(payload: SyncPayload):
    """
    Receives batched offline observations queued by the PWA client,
    deduplicates, runs real-time classification, and persists them.
    """
    if not payload.items:
        return {"status": "success", "synced_count": 0, "message": "Empty payload."}

    bundle = app_state.get("model_bundle")
    synced_items = []

    for item in payload.items:
        record = item.dict()
        record_id = record.get("id") or f"REP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{len(app_state['submissions'])}"
        record["id"] = record_id

        # Deduplicate
        if any(s.get("id") == record_id for s in app_state["submissions"]):
            continue

        # If category or severity missing, classify automatically
        if (not record.get("category") or not record.get("severity")) and bundle:
            try:
                full_text = (record.get("text") or "") + " " + (record.get("symptoms") or "").replace(";", " ")
                input_df = pd.DataFrame([{
                    "full_text": full_text,
                    "water_clarity": record.get("water_clarity") or "murky",
                    "flow_rate": record.get("flow_rate") or "normal",
                    "surrounding_activity": record.get("surrounding_activity") or "domestic_sewage",
                }])
                record["category"] = bundle["cat_model"].predict(input_df)[0]
                record["severity"] = bundle["sev_model"].predict(input_df)[0]
            except Exception:
                record["category"] = "Domestic Sewage & Outfalls"
                record["severity"] = "Medium"

        if not record.get("created_at"):
            record["created_at"] = datetime.utcnow().isoformat()

        app_state["submissions"].insert(0, record)
        synced_items.append(record)

    save_submissions_to_disk()

    return {
        "status": "success",
        "synced_count": len(synced_items),
        "total_saved": len(app_state["submissions"]),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/sync/status")
def get_sync_status():
    """Returns status of sync engine and storage."""
    return {
        "status": "operational",
        "total_submissions": len(app_state["submissions"]),
        "last_sync_timestamp": datetime.utcnow().isoformat(),
        "model_loaded": app_state["model_bundle"] is not None,
    }


# ================= 3. DASHBOARD ENDPOINT =================
@app.get("/api/dashboard")
def get_dashboard_data():
    """
    Returns aggregated metrics, pollution distribution, severity breakdown,
    and recent citizen stream for the live dashboard.
    """
    submissions = app_state["submissions"]
    rivers = app_state.get("rivers", {})

    # Calculate categories breakdown
    categories_breakdown: Dict[str, int] = {}
    severity_breakdown: Dict[str, int] = {
        "Critical": 0,
        "High": 0,
        "Medium": 0,
        "Low": 0,
    }

    for s in submissions:
        cat = s.get("category") or "Unclassified"
        categories_breakdown[cat] = categories_breakdown.get(cat, 0) + 1
        sev = s.get("severity") or "Medium"
        if sev in severity_breakdown:
            severity_breakdown[sev] += 1
        else:
            severity_breakdown[sev] = 1

    # Critical river reaches count
    critical_count = sum(1 for r in rivers.values() if r.get("status") in ["Severely Degraded", "Critical"])

    # Community champions enrolled count
    total_champions = sum(r.get("champions_enrolled", 0) for r in rivers.values())

    # Format recent reports
    recent_reports = []
    for s in submissions[:8]:
        r_info = rivers.get(s.get("river_id"), {})
        recent_reports.append({
            "id": s.get("id"),
            "river_id": s.get("river_id"),
            "river_name": r_info.get("name", s.get("river_id")),
            "location": s.get("location"),
            "text": s.get("text"),
            "category": s.get("category"),
            "severity": s.get("severity"),
            "created_at": s.get("created_at"),
        })

    return {
        "total_reports": len(submissions),
        "critical_stretches": critical_count,
        "community_champions": total_champions or 3420,
        "sync_rate_pct": 100,
        "categories_breakdown": categories_breakdown,
        "severity_breakdown": severity_breakdown,
        "recent_reports": recent_reports,
    }


# ================= 4. PLAN ENDPOINT =================
@app.post("/api/plan")
def generate_rejuvenation_plan(payload: PlanRequest):
    """
    Generates a structured multi-stakeholder action plan synthesized from
    river telemetry, category pressures, and symptom co-occurrence signals.
    """
    rivers = app_state.get("rivers", {})
    river = rivers.get(payload.river_id)
    if not river:
        # Fallback profile
        river = {
            "name": payload.river_id.replace("-", " ").title(),
            "reach_name": "Urban/Rural Catchment",
            "state": "National River Basin",
            "status": "Polluted",
            "health_index": 45,
            "primary_threats": ["Industrial discharge", "Solid waste dumping"],
            "parameters": {"dissolved_oxygen_mg_l": 3.8, "bod_mg_l": 9.5},
        }

    # Determine category
    category = payload.category
    if not category:
        # Infer category from threats or submissions
        threats_str = " ".join(river.get("primary_threats", [])).lower()
        if "effluent" in threats_str or "chemical" in threats_str or "tannery" in threats_str:
            category = "Industrial Effluents"
        elif "plastic" in threats_str or "solid" in threats_str or "litter" in threats_str:
            category = "Solid Waste & Plastic Dumping"
        elif "sewage" in threats_str or "drain" in threats_str:
            category = "Domestic Sewage & Outfalls"
        elif "sand" in threats_str or "mining" in threats_str:
            category = "Illegal Sand Mining & Encroachment"
        else:
            category = "Agricultural Runoff & Siltation"

    # Fetch co-occurrence signals
    cooccur = app_state.get("cooccur_data", {})
    cooccur_insight = "Correlated risks: Chemical contaminants show high co-occurrence with drop in dissolved oxygen and fish stress."
    if cooccur:
        top_pairs = cooccur.get("pairwise_cooccurrences", [])
        if top_pairs:
            pair = top_pairs[0]
            cooccur_insight = (
                f"Historical Field Association: Observed symptom '{pair.get('symptom_a')}' "
                f"co-occurs with '{pair.get('symptom_b')}' with a Jaccard index of {pair.get('jaccard_similarity')}. "
                f"Multi-symptom convergence indicates systemic catchment pressure."
            )

    # Detailed Phased Intervention Roadmap based on Category
    plans_blueprint = {
        "Industrial Effluents": {
            "urgency": "Critical",
            "immediate": {
                "action": "Immediate sealing of unpermitted industrial discharge outfalls, CETP inlet sample testing, and chemical anti-foaming / oil boom deployment.",
                "lead": "State Pollution Control Board (SPCB) & District Magistrate Rapid Response Team",
            },
            "mid_term": {
                "action": "Installation of real-time online continuous effluent monitoring systems (OCEMS) with automated alert thresholds on COD/BOD.",
                "lead": "Industrial Estate Association & Municipal Environment Cell",
            },
            "long_term": {
                "action": "Mandatory transition of textile and chemical clusters to Zero Liquid Discharge (ZLD) closed-loop recycling.",
                "lead": "Ministry of Environment, Forest & Climate Change (MoEFCC)",
            },
            "budget": "₹1.85 Cr – ₹4.50 Cr",
            "impact": "Eliminates toxic chemical plumes, raises dissolved oxygen to >= 5.0 mg/L, prevents mass fish mortality.",
        },
        "Domestic Sewage & Outfalls": {
            "urgency": "High",
            "immediate": {
                "action": "Temporary gravity diversion of raw sewage outfalls into settling ponds with in-situ microbial bio-remediation dosing.",
                "lead": "Urban Local Body (Nagar Nigam) & Jal Sansthan",
            },
            "mid_term": {
                "action": "Construction of floating treatment wetlands (FTWs) at drain confluences and modular decentralized sewage treatment units.",
                "lead": "River Basin Development Authority & Citizen Marshals",
            },
            "long_term": {
                "action": "100% underground sewerage network interception and 50 MLD sewage treatment plant commissioning with tertiary recycling.",
                "lead": "National Mission for Clean Ganga (NMCG) / State Water Authority",
            },
            "budget": "₹3.20 Cr – ₹8.00 Cr",
            "impact": "Reduces fecal coliform by 95%, curtails BOD from 38 mg/L to < 3 mg/L, restores river aesthetic and bathing safety.",
        },
        "Solid Waste & Plastic Dumping": {
            "urgency": "Medium",
            "immediate": {
                "action": "Deployment of floating trash booms and automated river skimmer boats at ghat bridges to trap drifting plastics.",
                "lead": "Municipal Corporation Solid Waste Management Team",
            },
            "mid_term": {
                "action": "Weekly community cleanup drives ('Swachh Nadi Abhiyan'), installation of CCTV surveillance on bridges, and floral composting pits at bathing ghats.",
                "lead": "JanaShakti Community Champions & Local Youth NGOs",
            },
            "long_term": {
                "action": "Strict implementation of Plastic Waste Management Rules with ₹25,000 fine on bulk dumping, and zero-waste pilgrim ghat protocols.",
                "lead": "District Administration & Smart City Enforcement",
            },
            "budget": "₹45 Lakh – ₹1.10 Cr",
            "impact": "Prevents over 120 tons of single-use plastics from reaching downstream estuaries, clears riparian corridors.",
        },
        "Agricultural Runoff & Siltation": {
            "urgency": "Medium",
            "immediate": {
                "action": "Temporary sediment silt fences along eroding river shoulders; ban on direct pesticide sprayer washing in water channels.",
                "lead": "District Agriculture Officer & Irrigation Department",
            },
            "mid_term": {
                "action": "Planting deep-rooted Vetiver grass and indigenous riparian buffer forests (30-meter wide corridor) along catchment banks.",
                "lead": "Forest Department & Village Panchayats",
            },
            "long_term": {
                "action": "Desilting obstructed channels and transition of 1,500 hectares of floodplain agriculture to certified natural farming (Prakritik Kheti).",
                "lead": "State Watershed Development Directorate",
            },
            "budget": "₹80 Lakh – ₹2.40 Cr",
            "impact": "Reduces monsoon silt load by 60%, halts riverbed shallowing, eliminates pesticide bioaccumulation.",
        },
        "Illegal Sand Mining & Encroachment": {
            "urgency": "Critical",
            "immediate": {
                "action": "Immediate confiscation of heavy excavators and suction boats operating on river sandbars; deployment of geo-fenced drone night patrols.",
                "lead": "District Task Force, Mining Department & Police Superintendent",
            },
            "mid_term": {
                "action": "Demolition of unauthorized rubble dikes and removal of illegal construction debris encroaching on Active Floodplain Zones (AFZ).",
                "lead": "Revenue Department & Flood Control Division",
            },
            "long_term": {
                "action": "Satellite GIS boundary marking with high-pillar boundary demarcation of river No-Development Zones (NDZ).",
                "lead": "State Land Records & Geo-spatial Technology Centre",
            },
            "budget": "₹35 Lakh – ₹90 Lakh",
            "impact": "Restores natural river braiding, preserves groundwater recharge aquifers, and safeguards riverbed ecology.",
        },
    }

    blueprint = plans_blueprint.get(category, plans_blueprint["Domestic Sewage & Outfalls"])

    return {
        "plan_title": f"{river['name']} Rejuvenation & Protection Roadmap",
        "river_id": river.get("id", payload.river_id),
        "river_name": river["name"],
        "river_reach": river.get("reach_name", "Monitored Stretch"),
        "state": river.get("state", "India"),
        "urgency": blueprint["urgency"],
        "target_category": category,
        "problem_summary": f"Targeting critical environmental pressure '{category}' on {river['name']} with baseline health index of {river.get('health_index', 50)}/100.",
        "cooccurrence_insight": cooccur_insight,
        "phases": {
            "immediate": blueprint["immediate"],
            "mid_term": blueprint["mid_term"],
            "long_term": blueprint["long_term"],
        },
        "estimated_budget_inr": blueprint["budget"],
        "expected_impact": blueprint["impact"],
    }


# ================= 5. ROOT & HEALTHCHECK =================
@app.get("/health")
def healthcheck():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "JanaShakti Platform",
        "version": "1.0.0",
        "model_loaded": app_state["model_bundle"] is not None,
        "rivers_count": len(app_state["rivers"]),
        "submissions_count": len(app_state["submissions"]),
    }


@app.get("/")
def get_index_page():
    """Serves the PWA App Shell."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "JanaShakti API is running. index.html not found."}


# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
