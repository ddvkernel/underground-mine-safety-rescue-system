# ⛏️ IoT-Based Underground Mine Safety & Worker Tracking System

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Socket.IO](https://img.shields.io/badge/Socket.IO-Realtime-010101?style=flat&logo=socket.io&logoColor=white)](https://socket.io/)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-ML%20Forecasting-F7931E?style=flat&logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![Hardware](https://img.shields.io/badge/Hardware-ESP32%20|%20LoRa%20|%20Sensors-FF6F00?style=flat&logo=espressif&logoColor=white)](https://www.espressif.com/)

A comprehensive real-time environmental monitoring, predictive hazard analytics, and worker localization platform designed for underground mines (developed for Smart India Hackathon). 

The system interfaces with IoT sensor nodes deployed across mine zones and worker wearables, analyzes toxic gases ($\text{CO}$, $\text{CH}_4$) and seismic vibrations, estimates miner positions via differential RF/RSSI signal strength, predicts impending risks using Random Forest machine learning models, and triggers bidirectional acoustic and visual alarms.

---

## 📌 Key Highlights

- **Multi-Zone Environmental Telemetry**: Real-time acquisition of hazardous gases (Methane $\text{CH}_4$, Carbon Monoxide $\text{CO}$) and 3-axis seismic vibration data ($ax, ay, az$).
- **Predictive Machine Learning Module (`sih_model.py`)**:
  - Trained on gas sensor array time-series datasets.
  - Generates rolling window features with future horizon lookaheads ($20$ timesteps ahead).
  - Uses `RandomForestClassifier` to forecast hazard escalations before gas reaches critical levels.
  - Automatically logs live sensor metrics and predictions into an Excel audit log (`insights/mine_safety_data.xlsx`).
- **Dynamic Hardware Calibration Engine**:
  - Fast auto-calibration against baseline air quality with drift mitigation.
  - Configurable timeout fallback to eliminate startup freezes if hardware connectivity lags.
- **Worker Localization & Proximity Tracking**:
  - Continuous position estimation across mine tunnels using dual-zone differential RSSI.
  - Hysteresis ($4.0\text{s}$) and deadband filtering ($6\text{ dBm}$) to suppress RF multipath fading and signal flutter.
  - Directional vector classification (`APPROACHING`, `AWAY`, `STATIONARY`).
- **Bidirectional Alerting & Smart Wearable Buzzer**:
  - Automated warning dispatch to worker wearables when miners approach active hazard zones.
  - Heartbeat watchdog detecting miner node disconnection or communication dropout within $10\text{s}$.
  - Instant worker panic button (`WORKER_SOS`) detection with zone assignment.
- **Interactive Control Room Dashboard (`app.py`)**:
  - Low-latency dark-mode operations interface built with Flask, HTML5, CSS3, and Socket.IO.
  - Dynamic 2D SVG tunnel visualization with color-coded safety boundaries and live worker indicator.
- **Hackathon Presentation / Demo Controls**: Dedicated REST API endpoints to simulate danger states, test buzzer responses, and showcase UI reactivity on demand.

---

## 🏗️ Architecture Overview

```
 ┌──────────────────────┐      ┌──────────────────────┐      ┌──────────────────────┐
 │ Zone 1 Sensor Node   │      │   Worker Wearable    │      │ Zone 2 Sensor Node   │
 │ • MQ-7 (CO Gas)      │      │ • Buzzer / Alarm     │      │ • MQ-7 (CO Gas)      │
 │ • MQ-4 (CH4 Gas)     │      │ • Panic SOS Button   │      │ • MQ-4 (CH4 Gas)     │
 │ • ADXL345 (Vibration)│      │ • Heartbeat & RSSI   │      │ • ADXL345 (Vibration)│
 └──────────┬───────────┘      └──────────┬───────────┘      └──────────┬───────────┘
            │                             │                             │
            └─────────────────────────────┼─────────────────────────────┘
                                          │ Sub-GHz RF / LoRa
                                          ▼
                            ┌───────────────────────────┐
                            │    ESP32 Gateway Node     │
                            └─────────────┬─────────────┘
                                          │ USB UART Serial (115200 Baud)
                                          ▼
                ┌───────────────────────────────────────────────────┐
                │             Python Processing Core                │
                │                                                   │
                │ ┌──────────────────────┐ ┌──────────────────────┐ │
                │ │    app.py (Server)   │ │  sih_model.py (ML)   │ │
                │ │ • Serial UART Bridge │ │ • Time-Series Window │ │
                │ │ • Baseline Calib.    │ │ • Random Forest Clf  │ │
                │ │ • RSSI Localization  │ │ • Predictive Hazard  │ │
                │ │ • SocketIO Stream    │ │ • Excel Data Logger  │ │
                │ └──────────┬───────────┘ └──────────────────────┘ │
                └────────────┼──────────────────────────────────────┘
                             │ WebSockets
                             ▼
                ┌───────────────────────────────────────────────────┐
                │          Control Room Web Dashboard               │
                │ • Real-time PPM / Vibration Telemetry             │
                │ • 2D Interactive Mine Tunnel & Miner Position     │
                │ • Visual Warning Banners & SOS Broadcasts         │
                └───────────────────────────────────────────────────┘
```

---

## 📡 Serial Protocol Specification

Communication between the ESP32 Gateway and the Python runtime uses structured text frames over UART serial (`115200` baud):

### 1. Inbound Telemetry (Hardware ➔ Python)

- **Environmental Sensor Packet**:
  ```text
  PYTHON_DATA:ZONE=1,MQ7=450.5,MQ4=310.2,AX=0.02,AY=-0.01,AZ=0.98,WRSSI=-68.0
  ```
  | Field | Meaning |
  | :--- | :--- |
  | `ZONE` | Target mine zone ID (`1` or `2`) |
  | `MQ7` | Analog reading from Carbon Monoxide sensor |
  | `MQ4` | Analog reading from Methane sensor |
  | `AX, AY, AZ` | 3-axis accelerometer readings (in $g$) |
  | `WRSSI` | Received signal strength of the worker node (in $\text{dBm}$) |

- **Worker Panic Alert (SOS)**:
  ```text
  WORKER_SOS:STATE=1
  ```
- **Worker Heartbeat (Liveness)**:
  ```text
  WORKER_HEARTBEAT:
  ```

### 2. Outbound Commands (Python ➔ Gateway)

- **Actuator & Alert Frame**:
  ```text
  PYTHON_COMMAND:ZONE=1,RISK=WARNING,ALERT=WARNING,WRSSI=-68,BUZZER=ON
  ```
  *Commands are throttled and deduplicated to protect RF bandwidth.*

---

## 📂 Project Structure

```text
underground-mine-safety-rescue-system/
├── app.py                     # Flask + SocketIO control server, serial bridge, & web UI
├── insights/                  # Analytical logs and telemetry reports
│   └── mine_safety_data.xlsx  # Multi-zone environmental and hazard audit log
├── templates/                 # Web interface templates
│   └── index.html             # Real-time control room dashboard with 2D tunnel view
├── .gitignore                 # Excludes heavy datasets (data/), cache, & virtualenvs
├── LICENSE                    # MIT License
└── README.md                  # System documentation
```

---

## ⚡ Getting Started

### Prerequisites

- Python 3.8 or higher.
- An ESP32 or compatible gateway connected via USB serial (optional for demonstration mode).

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/<repo-name>.git
   cd <repo-name>
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # macOS / Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## ⚙️ Configuration

Both [`app.py`](app.py) and [`sih_model.py`](sih_model.py) expose hardware settings near the top of each script:

```python
# Hardware Serial Port & Baud Rate
SERIAL_PORT = "COM5"        # Set to match your ESP32's COM port (e.g. 'COM3' or '/dev/ttyUSB0')
BAUD_RATE = 115200

# app.py Calibration & Risk Settings
CALIBRATION_SAMPLES = 3       # Number of samples for air baseline
CALIBRATION_TIMEOUT_S = 5     # Maximum calibration time before auto-completing
GAS_WARNING_DEVIATION = 0.25   # +25% baseline increase triggers WARNING
GAS_CRITICAL_DEVIATION = 0.60  # +60% baseline increase triggers CRITICAL
VIB_WARNING = 0.5             # 0.5g acceleration delta triggers WARNING
VIB_CRITICAL = 1.0            # 1.0g acceleration delta triggers CRITICAL
WORKER_OFFLINE_TIMEOUT = 10.0 # Heartbeat timeout in seconds
```

> [!TIP]
> When `app.py` launches, it scans all connected serial ports on your computer and displays them in the console with indicators showing whether the configured port is recognized.

---

## 🖥️ Running the System

### Option A: Run the Live Dashboard (`app.py`)

Starts the WebSockets server, serial communications thread, and control room UI:
```bash
python app.py
```
Open your browser at:
```text
http://127.0.0.1:5000
```

### Option B: Run the Predictive ML Classifier (`sih_model.py`)

Trains the Random Forest model on gas dataset sequences, connects to the gateway, evaluates live readings every 5 seconds, and logs to `insights/mine_safety_data.xlsx`:
```bash
python sih_model.py
```

---

## 🎯 Demo & Presentation Mode

During presentations or when hardware is unavailable, simulate live hazard scenarios and test dashboard responsiveness using these endpoints:

| Action | URL / Method | Description |
| :--- | :--- | :--- |
| **Simulate Critical State** | `GET http://127.0.0.1:5000/api/demo/2/CRITICAL` | Sets Zone 2 to CRITICAL, triggers alarms |
| **Simulate Warning State** | `GET http://127.0.0.1:5000/api/demo/2/WARNING` | Sets Zone 2 to WARNING |
| **Simulate Safe State** | `GET http://127.0.0.1:5000/api/demo/2/SAFE` | Resets Zone 2 to SAFE |
| **Clear Manual Override** | `GET http://127.0.0.1:5000/api/demo/2/CLEAR` | Resumes listening to physical sensor data |
| **Clear SOS Panic State** | `POST http://127.0.0.1:5000/api/clear_sos` | Dismisses worker emergency alert |
| **Export Current State** | `GET http://127.0.0.1:5000/api/data` | Returns current state dictionary as JSON |

*(Replace `2` with `1` to test Zone 1)*

---

## 🛡️ Sensor & Component Overview

| Component | Role | Interface |
| :--- | :--- | :--- |
| **ESP32 MCU** | Edge controller, LoRa/RF receiver, UART gateway bridge | Wi-Fi / LoRa / UART |
| **MQ-7 Sensor** | Carbon Monoxide ($\text{CO}$) toxic gas detection | Analog ADC |
| **MQ-4 Sensor** | Methane ($\text{CH}_4$) combustible gas detection | Analog ADC |
| **ADXL345** | 3-axis accelerometer for structural & seismic shifts | I2C / SPI |
| **Wearable Node** | Worker badge with panic button, heartbeat, & buzzer | RF Sub-GHz / LoRa |

---

## 📄 License

Developed for the Smart India Hackathon (SIH). Distributed under the MIT License.
