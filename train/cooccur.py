"""
JanaShakti Platform - Symptom and Risk Co-occurrence Analyzer
Calculates co-occurrence patterns, conditional association probabilities,
and correlation signals between observed water symptoms and pollution categories.
"""

import sys
import json
from pathlib import Path
from collections import defaultdict
import pandas as pd
import numpy as np

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "train" / "answers.csv"
OUTPUT_JSON = BASE_DIR / "train" / "cooccurrence_matrix.json"


def compute_cooccurrence(csv_path: Path = DATA_PATH) -> dict:
    """Computes pairwise symptom co-occurrence and symptom-to-category associations."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Training dataset not found at {csv_path}")

    df = pd.read_csv(csv_path)

    # 1. Parse individual symptoms
    symptom_lists = []
    for item in df["symptoms"].dropna():
        tokens = [s.strip() for s in str(item).split(";") if s.strip()]
        symptom_lists.append(tokens)

    unique_symptoms = sorted(list({s for sublist in symptom_lists for s in sublist}))

    # 2. Symptom Pairwise Co-occurrence
    pair_counts = defaultdict(int)
    single_counts = defaultdict(int)

    for symptoms in symptom_lists:
        unique_in_row = list(set(symptoms))
        for s in unique_in_row:
            single_counts[s] += 1
        for i in range(len(unique_in_row)):
            for j in range(i + 1, len(unique_in_row)):
                s1, s2 = sorted([unique_in_row[i], unique_in_row[j]])
                pair_counts[(s1, s2)] += 1

    # Format pairwise results
    pairwise_results = []
    for (s1, s2), count in sorted(pair_counts.items(), key=lambda x: x[1], reverse=True):
        jaccard = count / (single_counts[s1] + single_counts[s2] - count)
        pairwise_results.append({
            "symptom_a": s1,
            "symptom_b": s2,
            "cooccurrence_count": count,
            "jaccard_similarity": round(float(jaccard), 3)
        })

    # 3. Symptom-to-Category Association: P(Category | Symptom)
    sym_cat_counts = defaultdict(lambda: defaultdict(int))
    for _, row in df.iterrows():
        cat = row["category"]
        tokens = [s.strip() for s in str(row.get("symptoms", "")).split(";") if s.strip()]
        for s in tokens:
            sym_cat_counts[s][cat] += 1

    sym_to_cat_probs = {}
    for s, cat_counts in sym_cat_counts.items():
        total = sum(cat_counts.values())
        sym_to_cat_probs[s] = {
            cat: round(count / total, 3) for cat, count in cat_counts.items()
        }

    # 4. Activity-to-Severity Association
    act_sev_counts = defaultdict(lambda: defaultdict(int))
    for _, row in df.iterrows():
        act = row["surrounding_activity"]
        sev = row["severity"]
        act_sev_counts[act][sev] += 1

    act_to_sev_probs = {}
    for act, sev_counts in act_sev_counts.items():
        total = sum(sev_counts.values())
        act_to_sev_probs[act] = {
            sev: round(count / total, 3) for sev, count in sev_counts.items()
        }

    result = {
        "unique_symptoms_count": len(unique_symptoms),
        "total_records_analyzed": len(df),
        "pairwise_cooccurrences": pairwise_results[:25],  # top 25 associations
        "symptom_category_probabilities": sym_to_cat_probs,
        "activity_severity_probabilities": act_to_sev_probs
    }

    # Save to file
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result


def main():
    print("=" * 60)
    print("[JanaShakti] Computing Symptom Co-occurrence Matrix")
    print("=" * 60)
    data = compute_cooccurrence()
    print(f"Analyzed {data['total_records_analyzed']} records across {data['unique_symptoms_count']} distinct symptoms.")
    print(f"\nTop 5 Co-occurring Symptom Pairs:")
    for item in data["pairwise_cooccurrences"][:5]:
        print(f"  * {item['symptom_a']} + {item['symptom_b']}: {item['cooccurrence_count']} times (Jaccard: {item['jaccard_similarity']})")
    print(f"\nSaved co-occurrence matrix to: {OUTPUT_JSON}")
    print("=" * 60)


if __name__ == "__main__":
    main()
