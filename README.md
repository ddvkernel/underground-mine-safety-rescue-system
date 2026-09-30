# KHANRAKSHAK  
**AI-Enabled Surface Deformation Digital Twin, Adaptive LoRa Mesh & Risk-Aware Worker Early-Warning System for Underground Coal Mines**

> **Smart India Hackathon (SIH) Project**  
> Real-time subsidence monitoring + mesh networking + edge AI + worker safety alerts

---

## 🚨 The Problem

Surface subsidence above underground coal panels develops progressively through small changes in:
- Tilt
- Ground displacement
- Vibration
- Crack formation
- Water accumulation in depressions

When these signals are observed separately, manually, or only after visible failure, mine operators lose valuable time to:
- Identify the affected zone
- Assess risk severity
- Warn and evacuate workers safely

Existing monitoring is often:
- Periodic/manual (survey-based)
- Point-sensor only (no spatial risk view)
- Dashboard-only (no physical worker alert)
- Lacking trend analysis and neighbour correlation

---

## 💡 Our Solution: KHANRAKSHAK

**KHANRAKSHAK** is a low-cost, indigenous, AI-enabled surface monitoring network deployed above underground coal panels. It combines:

- Distributed deformation sensor nodes (ESP32 + LoRa + MEMS + crack + moisture)
- Adaptive LoRa mesh communication
- Edge-based risk intelligence (trend + spatial correlation + hysteresis)
- GIS heatmap + 3D deformation digital twin
- Worker-specific LoRa buzzer/LED alerts with safe exit recommendations

It turns distributed sensor observations into a complete safety loop:

> **Detect → Understand → Warn → Respond**

---

## ✨ Key Innovations

- **From Point Sensors to Spatial Risk**  
  Converts individual deformation readings into an evolving subsidence-risk zone using neighbour agreement and trend persistence.

- **From Dashboard Alarm to Physical Worker Warning**  
  Sends real LoRa buzzer and LED alerts to workers near the affected zone, not just a control-room notification.

- **AI-Driven Progressive Risk Detection**  
  Tracks deformation trend, rate, acceleration, and neighbouring-node agreement to distinguish noise from genuine risk.

- **3D Digital Twin + GIS**  
  Shows both the location of risk and the physical change in terrain over time for intuitive situational awareness.

- **Water-Aware Safe Routing**  
  Avoids crack zones, deformation zones, low-elevation water pockets, and weak communication paths when recommending evacuation routes.

- **Hysteresis-Based Recovery**  
  Prevents unsafe instant “all-clear” after a single normal reading; risk reduces only after sustained stable measurements.

---

## 🧠 Technical Approach

### Hardware Stack

- **ESP32 + LoRa Sensor Node**
  - Low-cost indigenous node for continuous surface deformation monitoring
- **MPU6050**
  - Tilt magnitude, direction, and rate of change
- **Accelerometer**
  - Vibration RMS, peak events, unusual ground activity
- **Displacement Sensor**
  - Relative stretch/movement between anchored surface points
- **Crack Strip Sensor**
  - Crack initiation or conductive-path break detection
- **Moisture Sensor**
  - Water accumulation in low-elevation subsidence depressions
- **LoRa Gateway**
  - Collects sensor data, stores events locally, runs risk logic, triggers worker alerts
- **Worker Safety Tag**
  - LoRa-enabled buzzer, LED warning, SOS button
- **Web Dashboard**
  - Live GIS map, 3D deformation twin, sensor trends, mesh health, safe exit route

### Software & Intelligence

- **Edge AI Engine**
  - Anomaly detection
  - Temporal trend analysis (tilt/disp/vib over time)
  - Spatial correlation across neighbouring nodes
  - Explainable risk scoring (SAFE → WATCH → WARNING → CRITICAL)
- **Adaptive Power Management**
  - Deep sleep in stable conditions
  - Increased sampling during abnormal movement
- **Offline-First Architecture**
  - Gateway stores data and events locally
  - Cloud sync when connectivity is available
- **Mesh Health Monitoring**
  - RSSI, packet delivery %, hop count, route changes

---

## 🏗 System Architecture (3-Layer)

1. **感知 Layer (Sensing)**
   - Distributed ESP32+LoRa nodes with multi-sensor fusion
2. **Network Layer (Communication)**
   - Adaptive LoRa mesh with gateway as hub
   - Dynamic routing, store-and-forward, retry logic
3. **Intelligence Layer (Edge + Cloud)**
   - Risk engine, digital twin, GIS visualization, worker-alert logic

*(Architecture diagram can be added in `docs/` as you refine the repo.)*

---

## 🖥 Dashboard Features

The KHANRAKSHAK command center provides:

- **Live Hardware Health**
  - Node status (N1, N2, N3)
  - Gateway online/offline, primary route, hop count, delivery %
- **GIS Deformation & Risk Field**
  - Surface monitoring grid
  - Underground coal panel overlay
  - Risk heatmap (Safe / Watch / Warning / Critical)
  - Worker and exit markers
- **AI Risk Assessment**
  - Overall risk score (%)
  - Tilt trend, displacement trend
  - Crack sensor status
  - Neighbour agreement (x / 3)
  - Moisture context (Dry / Wet)
- **Node Telemetry Table**
  - Tilt, displacement, vibration, crack, moisture
  - Battery %, RSSI, mode (SAFE/WATCH/WARNING/CRITICAL), risk level
- **Response & Worker Safety**
  - Active emergency status
  - Recommended evacuation path (e.g., `W07 → Access B → South Exit`)
  - Worker tag status (zone, heartbeat, buzzer/LED state)

The UI is designed to look and feel like a **live hardware-connected control room**, suitable for SIH demos and evaluator presentations.

---

## 📦 Repository Structure

```text
.
├── README.md
├── docs/                 # Architecture diagrams, reports, demo notes
├── hardware/
│   ├── schematics/       # ESP32+LoRa node schematics (if available)
│   └── firmware/         # Node & gateway firmware (Arduino/PlatformIO)
├── software/
│   ├── edge_ai/          # Risk engine, trend analysis, neighbour logic
│   ├── gateway/          # Gateway server, LoRa handling, local storage
│   └── dashboard/        # Web dashboard (HTML/CSS/JS)
└── simulations/          # Any simulation scripts or datasets
```

*(Adjust paths as per your actual repo layout.)*

---

## 🚀 Getting Started

### Prerequisites

- ESP32 development setup (Arduino IDE or PlatformIO)
- LoRa modules (e.g., SX1278/RFM95)
- Sensors: MPU6050, displacement, crack strip, moisture
- Python 3.x (for edge AI / gateway, if applicable)
- A modern web browser for the dashboard

### Hardware Setup (Overview)

1. Assemble ESP32 + LoRa + sensor node as per schematics.
2. Flash node firmware.
3. Set up LoRa gateway (ESP32/PC-based) and flash gateway firmware.
4. Place nodes in a grid above the target panel area (or lab rig).

### Software Setup (Overview)

1. Clone the repository:
   ```bash
   git clone https://github.com/<your-username>/khanrakshak.git
   cd khanrakshak
   ```
2. Set up edge AI / gateway environment (if using Python):
   ```bash
   python -m venv venv
   source venv/bin/activate  # or `venv\\Scripts\\activate` on Windows
   pip install -r software/gateway/requirements.txt
   ```
3. Run the gateway server (example):
   ```bash
   python software/gateway/main.py
   ```
4. Open the dashboard:
   - Either via Live Server in VS Code:
     - Open `software/dashboard/index.html` → Right-click → “Open with Live Server”
   - Or directly in a browser.

*(Customize these steps to match your actual stack.)*

---


## 📊 Impact & Benefits

### For Mine Workers
- Immediate physical warning via LoRa buzzer + LED when near an affected zone.
- Clear, safer exit guidance instead of generic alarms.

### For Safety Officers & Managers
- Continuous trend visibility instead of periodic manual checks.
- Area-level risk picture, not disconnected sensor readings.

### For Survey & Emergency Teams
- Sensor trends that complement manual inspections and surveys.
- Faster identification of affected zones and route restrictions.

### Strategic & Economic Benefits
- Low-cost, modular, indigenous architecture.
- Phased deployment in high-risk zones.
- Offline-first operation for remote mines.
- Future-ready platform for predictive subsidence models.

---

## 📚 References & Policy Context

- Designed to complement DGMS-compliant monitoring, certified mine maps, and approved emergency procedures.
- Aligns with India’s focus on real-time safety reporting, digital monitoring, and rapid mitigation in mining operations.

*(Add specific DGMS / ministry links here if required for SIH documentation.)*

---

## 🏆 Team

- **Team Name:** KHANRAKSHAK
- **Institution:** VIT UNIVERSITY, VELLORE
- **SIH Problem Statement ID:** SIH26025

---

## 📄 License

This project is intended for academic and research use.  
If you plan to open-source it fully, consider adding an MIT/Apache/GPL license file.

---

## 🤝 Contributing

Contributions in the form of:
- Improved risk models
- Better visualization
- Additional sensor support
- Field testing feedback  

are welcome. Please open an issue or pull request with details.

---


> **KHANRAKSHAK** – Protecting the Earth above, so those below can work safely.