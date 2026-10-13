# जनशक्ति (JanaShakti) — Citizen River Intelligence & Action Platform

> **Participatory River Monitoring, Offline Civic Observations, and Automated Rejuvenation Action Planning**

JanaShakti is an offline-first civic intelligence and river conservation platform. It empowers citizens, field volunteers, and environmental administrators to record river pollution symptoms (with multilingual audio prompts and offline synchronization), automatically classify environmental risks using machine learning, and generate actionable multi-stakeholder rejuvenation roadmaps.

---

## 🏗️ Architecture

```
janashakti/
├── app/
│   └── main.py                     # FastAPI: sync, dashboard, classify, plan + static hosting
├── static/
│   ├── index.html                  # PWA single-page interface
│   ├── style.css                   # Eco-intelligence dark mode theme
│   ├── app.js                      # PWA controller, offline queue, GIS map interaction
│   ├── sw.js                       # Service worker with offline asset caching & sync
│   ├── manifest.json               # Web App Manifest for mobile installation
│   ├── map.svg                     # Interactive vector SVG river basin network map
│   ├── content/
│   │   └── rivers.json             # 14 Indian river reaches with water quality telemetry
│   └── audio/
│       └── M1.opus                 # Module 1 field survey audio prompt
├── train/
│   ├── answers.csv                 # 60 citizen observations across Indian river basins
│   ├── train_classifier.py         # Scikit-learn TF-IDF & categorical feature pipeline
│   ├── cooccur.py                  # Pairwise symptom co-occurrence & conditional risk analyzer
│   └── cooccurrence_matrix.json    # Computed symptom correlations & associations
├── model/
│   └── clf.joblib                  # Serialized ML pipeline bundle
├── requirements.txt                # Python package dependencies
└── Dockerfile                      # Production container deployment configuration
```

---

## 🌟 Core Features

- **🗺️ Interactive River Basin GIS Map**: Vector SVG map of major Indian river networks (*Ganga, Yamuna, Godavari, Krishna, Narmada, Mahanadi, Cauvery, Sabarmati, Brahmaputra*). Click any station to inspect live telemetry (Dissolved Oxygen, BOD, pH, Turbidity).
- **📝 Citizen Field Survey with Audio Guidance**: Offline-safe multi-step observation form with spoken voice guidance (`M1.opus` with Web Speech API browser fallback) and real-time debounced AI classification.
- **📶 Offline PWA & Background Sync**: Automatically saves survey reports locally when offline (`localStorage` / IndexedDB) and synchronizes with the central server upon reconnection.
- **🧠 Machine Learning Classifier**: Scikit-learn classification pipeline predicting 5 pollution categories and 4 severity tiers with high confidence.
- **🔗 Co-occurrence Engine**: Calculates statistical symptom correlation signals (e.g., chemical foam + pungent odor) to detect systemic industrial or ecological pressures.
- **📋 Phased Action Planner**: Synthesizes telemetry, ML predictions, and co-occurrence insights into a 3-tier rejuvenation roadmap (0–48h Emergency Containment, 30-Day Community Remediation, 1-Year Systemic Policy).

---

## 🚀 Quickstart

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/saloni234812/janshakti.git
cd janshakti

# Install dependencies
pip install -r requirements.txt
```

### 2. Train Model (Optional - Pre-trained model included)
```bash
python train/train_classifier.py
python train/cooccur.py
```

### 3. Launch Application
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Open [http://localhost:8000](http://localhost:8000) in your browser.  
Interactive OpenAPI documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 🐳 Docker Deployment

```bash
docker build -t janashakti:latest .
docker run -p 8000:8000 janashakti:latest
```

---

## 📄 License

MIT License. Designed for civic water stewardship and ecological revival.
