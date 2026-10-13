"""
JanaShakti Platform - River Observation Classifier Training Pipeline
Trains an ML pipeline on citizen survey answers and exports model/clf.joblib.
"""

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import OneHotEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score
import joblib

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "train" / "answers.csv"
MODEL_DIR = BASE_DIR / "model"
MODEL_PATH = MODEL_DIR / "clf.joblib"


def load_dataset(csv_path: Path) -> pd.DataFrame:
    """Loads and validates answers.csv."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Training dataset not found at {csv_path}")
    df = pd.read_csv(csv_path)
    required_cols = [
        "id", "river_id", "text", "symptoms", "water_clarity", 
        "flow_rate", "surrounding_activity", "severity", "category", "recommended_action"
    ]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column in dataset: {col}")
    
    # Combined text representation for vectorizer
    df["full_text"] = df["text"].fillna("") + " " + df["symptoms"].fillna("").str.replace(";", " ")
    return df


def build_pipeline():
    """Builds a scikit-learn ColumnTransformer + Classifier pipeline."""
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "text",
                TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=1200),
                "full_text",
            ),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                ["water_clarity", "flow_rate", "surrounding_activity"],
            ),
        ]
    )

    clf = LogisticRegression(max_iter=1000, C=2.0, random_state=42)

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", clf),
        ]
    )
    return pipeline


def train_models():
    """Trains the category and severity classifiers, bundles them, and saves to model/clf.joblib."""
    print("=" * 60)
    print("[JanaShakti] Training River Observation Classifier")
    print("=" * 60)

    df = load_dataset(DATA_PATH)
    print(f"Loaded {len(df)} survey answer records from {DATA_PATH.name}")

    X = df[["full_text", "water_clarity", "flow_rate", "surrounding_activity"]]
    y_cat = df["category"]
    y_sev = df["severity"]

    # 1. Category Classifier
    cat_pipeline = build_pipeline()
    cat_pipeline.fit(X, y_cat)
    cat_preds = cat_pipeline.predict(X)
    cat_acc = accuracy_score(y_cat, cat_preds)
    print(f"\n[Category Classifier] Training Accuracy: {cat_acc:.2%}")

    # 2. Severity Classifier
    sev_pipeline = build_pipeline()
    sev_pipeline.fit(X, y_sev)
    sev_preds = sev_pipeline.predict(X)
    sev_acc = accuracy_score(y_sev, sev_preds)
    print(f"[Severity Classifier] Training Accuracy: {sev_acc:.2%}")

    # 3. Action mapping by category
    action_map = (
        df.groupby("category")["recommended_action"]
        .agg(lambda s: s.mode().iloc[0] if not s.empty else "Site Inspection")
        .to_dict()
    )

    # 4. Save bundled artifact
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    bundle = {
        "cat_model": cat_pipeline,
        "sev_model": sev_pipeline,
        "categories": sorted(list(df["category"].unique())),
        "severities": ["Low", "Medium", "High", "Critical"],
        "action_map": action_map,
        "metadata": {
            "training_samples": len(df),
            "category_accuracy": float(cat_acc),
            "severity_accuracy": float(sev_acc),
            "source_dataset": "train/answers.csv",
        },
    }

    joblib.dump(bundle, MODEL_PATH)
    print(f"\n[OK] Serialized model bundle saved to: {MODEL_PATH}")
    print(f"File size: {MODEL_PATH.stat().st_size / 1024:.1f} KB")

    print("\n--- Category Classification Report ---")
    print(classification_report(y_cat, cat_preds, zero_division=0))
    print("=" * 60)


if __name__ == "__main__":
    train_models()
