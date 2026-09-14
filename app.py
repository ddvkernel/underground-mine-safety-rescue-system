import os
from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO
import serial
import serial.tools.list_ports
import threading
import queue
import time
import math

# ============================================================
# CONFIGURATION
# ============================================================
SERIAL_PORT = os.environ.get("SERIAL_PORT", "COM5")
BAUD_RATE = int(os.environ.get("BAUD_RATE", "115200"))
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))

CALIBRATION_SAMPLES = 3          # was 15 — cut for demo speed
CALIBRATION_TIMEOUT_S = 5        # force-complete calibration after this long, no matter what
GAS_WARNING_DEVIATION = 0.25
GAS_CRITICAL_DEVIATION = 0.60
VIB_WARNING = 0.5
VIB_CRITICAL = 1.0
RSSI_CHANGE_THRESHOLD = 3.0
WORKER_OFFLINE_TIMEOUT = 10.0

# ============================================================
# FLASK
# ============================================================
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading",
                     ping_interval=10, ping_timeout=30, logger=False, engineio_logger=False)

# ============================================================
# LATEST DATA
# ============================================================
latest_data = {
    "zone1": {"mq7": None, "mq4": None, "ax": None, "ay": None, "az": None, "rssi": None,
              "co_ppm": None, "ch4_ppm": None, "vibration": None,
              "risk": "CALIBRATING", "risk_status": "CALIBRATING",
              "movement": "UNKNOWN", "buzzer": False,
              "calibration_progress": 0, "last_seen": None},
    "zone2": {"mq7": None, "mq4": None, "ax": None, "ay": None, "az": None, "rssi": None,
              "co_ppm": None, "ch4_ppm": None, "vibration": None,
              "risk": "CALIBRATING", "risk_status": "CALIBRATING",
              "movement": "UNKNOWN", "buzzer": False,
              "calibration_progress": 0, "last_seen": None}
}

sos_state = {"active": False, "zone": None, "timestamp": None}
worker_state = {"online": False, "last_heartbeat": None, "estimated_zone": "UNKNOWN"}

previous_rssi = {1: None, 2: None}
previous_acceleration = {1: None, 2: None}

# Hysteresis so the worker's "which zone am I near" guess doesn't
# flip back and forth every second from RSSI noise.
ZONE_SWITCH_MIN_INTERVAL_S = 4.0
ZONE_RSSI_DEADBAND = 6.0   # r1 and r2 must differ by more than this to switch at all
last_zone_switch_time = 0.0

calibration_samples = {1: {"mq7": [], "mq4": []}, 2: {"mq7": [], "mq4": []}}
baseline = {1: {"mq7": None, "mq4": None}, 2: {"mq7": None, "mq4": None}}
calibration_done = {1: False, 2: False}
calibration_start_time = {1: None, 2: None}

# Track whether each zone has received at least one real packet yet
# (used only for the "waiting for hardware" status shown on dashboard).
zone_ever_seen_real_data = {1: False, 2: False}
server_start_time = time.time()

# Manual override: when set, this risk is forced for the zone until cleared.
manual_override = {1: None, 2: None}

serial_connection = None
serial_connection_lock = threading.Lock()
command_queue = queue.Queue()
sensor_queue = queue.Queue()
data_lock = threading.Lock()

last_command_signature = {1: None, 2: None}
last_command_time = {1: 0.0, 2: 0.0}
COMMAND_MIN_INTERVAL = 1.0


# ============================================================
# CALIBRATION — capped at CALIBRATION_TIMEOUT_S no matter what
# ============================================================
def calibrate_zone(zone, mq7, mq4):
    if calibration_done[zone]:
        return True

    if calibration_start_time[zone] is None:
        calibration_start_time[zone] = time.time()

    calibration_samples[zone]["mq7"].append(mq7)
    calibration_samples[zone]["mq4"].append(mq4)
    progress = len(calibration_samples[zone]["mq7"])

    with data_lock:
        zone_key = f"zone{zone}"
        latest_data[zone_key]["calibration_progress"] = progress

    elapsed = time.time() - calibration_start_time[zone]

    # Force-finish calibration either when we hit the sample count,
    # OR when the timeout expires — whichever comes first. This is
    # the fix for indefinite "CALIBRATING" hangs.
    if progress >= CALIBRATION_SAMPLES or elapsed >= CALIBRATION_TIMEOUT_S:
        samples_mq7 = calibration_samples[zone]["mq7"] or [mq7]
        samples_mq4 = calibration_samples[zone]["mq4"] or [mq4]
        baseline[zone]["mq7"] = sum(samples_mq7) / len(samples_mq7)
        baseline[zone]["mq4"] = sum(samples_mq4) / len(samples_mq4)
        calibration_done[zone] = True
        print(f"[CALIBRATION COMPLETE] Zone {zone} — "
              f"MQ7 baseline={baseline[zone]['mq7']:.1f}, MQ4 baseline={baseline[zone]['mq4']:.1f} "
              f"(after {progress} samples, {elapsed:.1f}s)")
        return True

    return False


def deviation_ratio(current, base):
    if base is None or base == 0:
        return 0.0
    return max(0.0, (current - base) / base)


def calculate_vibration(zone, ax, ay, az):
    try:
        ax, ay, az = float(ax), float(ay), float(az)
    except Exception:
        return 0.0
    previous = previous_acceleration[zone]
    if previous is None:
        previous_acceleration[zone] = (ax, ay, az)
        return 0.0
    dax, day, daz = ax - previous[0], ay - previous[1], az - previous[2]
    vibration = math.sqrt(dax**2 + day**2 + daz**2)
    previous_acceleration[zone] = (ax, ay, az)
    return vibration


def calculate_risk(zone, mq7, mq4, ax, ay, az):
    vibration = calculate_vibration(zone, ax, ay, az)
    if not calibrate_zone(zone, mq7, mq4):
        return ("CALIBRATING", 0.0, 0.0, vibration)

    mq7_dev = deviation_ratio(mq7, baseline[zone]["mq7"])
    mq4_dev = deviation_ratio(mq4, baseline[zone]["mq4"])
    co_display = mq7_dev * 100
    ch4_display = mq4_dev * 100

    if (mq7_dev >= GAS_CRITICAL_DEVIATION or mq4_dev >= GAS_CRITICAL_DEVIATION
            or vibration >= VIB_CRITICAL):
        return ("CRITICAL", co_display, ch4_display, vibration)
    if (mq7_dev >= GAS_WARNING_DEVIATION or mq4_dev >= GAS_WARNING_DEVIATION
            or vibration >= VIB_WARNING):
        return ("WARNING", co_display, ch4_display, vibration)
    return ("SAFE", co_display, ch4_display, vibration)


def calculate_movement(zone, current_rssi):
    if current_rssi is None:
        return "UNKNOWN"
    try:
        current_rssi = float(current_rssi)
    except Exception:
        return "UNKNOWN"
    if current_rssi <= -900:
        return "UNKNOWN"
    old_rssi = previous_rssi[zone]
    if old_rssi is None:
        previous_rssi[zone] = current_rssi
        return "UNKNOWN"
    difference = current_rssi - old_rssi
    previous_rssi[zone] = current_rssi
    if difference >= RSSI_CHANGE_THRESHOLD:
        return "APPROACHING"
    if difference <= -RSSI_CHANGE_THRESHOLD:
        return "AWAY"
    return "STATIONARY"


def update_estimated_worker_zone():
    global last_zone_switch_time
    r1, r2 = previous_rssi[1], previous_rssi[2]

    if r1 is None and r2 is None:
        worker_state["estimated_zone"] = "UNKNOWN"
        return

    # If we only have one zone's RSSI, that's the obvious answer.
    if r1 is None:
        candidate = "ZONE2"
    elif r2 is None:
        candidate = "ZONE1"
    else:
        diff = r1 - r2
        if abs(diff) < ZONE_RSSI_DEADBAND:
            # Too close to call — keep whatever we already believe,
            # don't let tiny noise decide this.
            return
        candidate = "ZONE1" if diff > 0 else "ZONE2"

    now = time.time()
    if candidate != worker_state["estimated_zone"]:
        if now - last_zone_switch_time < ZONE_SWITCH_MIN_INTERVAL_S:
            return  # too soon since last switch, ignore this flip
        last_zone_switch_time = now
        print(f"[WORKER ZONE] Switched estimate to {candidate}")
        worker_state["estimated_zone"] = candidate


# ============================================================
# PARSE — SENSOR DATA
# ============================================================
def parse_python_data(line):
    line = line.strip()
    if not line.startswith("PYTHON_DATA:"):
        return None
    try:
        payload = line.split("PYTHON_DATA:", 1)[1]
        fields = {}
        for item in payload.split(","):
            item = item.strip()
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            fields[key.strip().upper()] = value.strip()

        required = ["ZONE", "MQ7", "MQ4", "AX", "AY", "AZ"]
        missing = [k for k in required if k not in fields]
        if missing:
            print(f"[PARSE ERROR] Zone packet missing fields {missing} — raw line: {line}")
            return None

        zone = int(fields["ZONE"])
        if zone not in (1, 2):
            print(f"[PARSE ERROR] Invalid zone number: {zone}")
            return None

        rssi_raw = fields.get("WRSSI")
        rssi = float(rssi_raw) if rssi_raw is not None else None

        data = {
            "mq7": float(fields["MQ7"]),
            "mq4": float(fields["MQ4"]),
            "ax": float(fields["AX"]),
            "ay": float(fields["AY"]),
            "az": float(fields["AZ"]),
            "rssi": rssi,
        }
        return (zone, data)

    except Exception as error:
        print("[PARSE ERROR]", error, "| raw line:", line)
        return None


def parse_worker_line(line):
    line = line.strip()

    if line.startswith("WORKER_SOS:"):
        payload = line.split("WORKER_SOS:", 1)[1]
        fields = dict(item.split("=", 1) for item in payload.split(",") if "=" in item)
        state = fields.get("STATE", "0") == "1"
        update_estimated_worker_zone()
        with data_lock:
            sos_state["active"] = state
            sos_state["zone"] = worker_state["estimated_zone"] if state else None
            sos_state["timestamp"] = time.time() if state else None
        emit_dashboard_state()
        return True

    if line.startswith("WORKER_HEARTBEAT:"):
        with data_lock:
            worker_state["online"] = True
            worker_state["last_heartbeat"] = time.time()
        return True

    return False


def worker_offline_watchdog():
    while True:
        time.sleep(2)
        with data_lock:
            if (worker_state["last_heartbeat"] is not None
                    and time.time() - worker_state["last_heartbeat"] > WORKER_OFFLINE_TIMEOUT):
                if worker_state["online"]:
                    print("[WORKER OFFLINE] No heartbeat received recently")
                worker_state["online"] = False
        emit_dashboard_state()


# ============================================================
# EMIT DASHBOARD STATE
# ============================================================
def emit_dashboard_state():
    try:
        with data_lock:
            payload = {
                "zone1": dict(latest_data["zone1"]),
                "zone2": dict(latest_data["zone2"]),
                "sos": dict(sos_state),
                "worker": dict(worker_state),
            }
        socketio.emit("sensor_update", payload)
    except Exception as error:
        print("[DASHBOARD EMIT ERROR]", error)


# ============================================================
# PROCESS ONE ZONE
# ============================================================
def process_zone(zone, data):
    # Manual override wins over everything — instant control for demo.
    if manual_override[zone] is not None:
        risk = manual_override[zone]
        co_display, ch4_display, vibration = data.get("mq7", 0), data.get("mq4", 0), data.get("vibration", 0.3)
        movement = calculate_movement(zone, data.get("rssi"))
        buzzer = risk in ("WARNING", "CRITICAL")
    else:
        risk, co_display, ch4_display, vibration = calculate_risk(
            zone, data["mq7"], data["mq4"], data["ax"], data["ay"], data["az"])
        movement = calculate_movement(zone, data["rssi"])
        buzzer = (movement == "APPROACHING" and risk in ("WARNING", "CRITICAL")) or risk == "CRITICAL"

    update_estimated_worker_zone()

    zone_key = "zone1" if zone == 1 else "zone2"
    with data_lock:
        latest_data[zone_key].update({
            "mq7": data["mq7"], "mq4": data["mq4"],
            "ax": data["ax"], "ay": data["ay"], "az": data["az"],
            "rssi": data["rssi"],
            "co_ppm": co_display, "ch4_ppm": ch4_display,
            "co": co_display, "ch4": ch4_display,
            "vibration": vibration,
            "risk": risk, "risk_status": risk,
            "movement": movement, "buzzer": buzzer,
            "last_seen": time.time(),
        })

    print(f"ZONE {zone} | RISK={risk} | CO={co_display:.1f} | CH4={ch4_display:.1f} | "
          f"VIB={vibration:.3f} | RSSI={data['rssi']} | BUZZER={'ON' if buzzer else 'OFF'}")

    # Only forward this zone's command to the worker if the worker is
    # currently estimated to be near THIS zone (stops cross-zone
    # flicker) — the worker only ever hears the zone it's near.
    zone_label = "ZONE1" if zone == 1 else "ZONE2"
    is_relevant_to_worker = (worker_state["estimated_zone"] == zone_label
                              or worker_state["estimated_zone"] == "UNKNOWN")

    if is_relevant_to_worker:
        send_worker_command(zone, risk, data["rssi"], buzzer)
    emit_dashboard_state()


def send_worker_command(zone, risk, rssi, buzzer):
    buzzer_value = "ON" if buzzer else "OFF"
    rssi_str = f"{rssi:.0f}" if rssi is not None else "NA"
    command = f"PYTHON_COMMAND:ZONE={zone},RISK={risk},ALERT={risk},WRSSI={rssi_str},BUZZER={buzzer_value}"

    signature = (risk, buzzer_value)
    now = time.monotonic()
    if (signature == last_command_signature[zone]
            and (now - last_command_time[zone]) < COMMAND_MIN_INTERVAL):
        return

    last_command_signature[zone] = signature
    last_command_time[zone] = now
    command_queue.put(command)
    print("[TO GATEWAY]", command)


def clear_sos():
    with data_lock:
        sos_state["active"] = False
        sos_state["zone"] = None
        sos_state["timestamp"] = None
    emit_dashboard_state()


# ============================================================
# DIAGNOSTIC WATCHDOG
# Prints a loud, explicit warning if no real sensor packet has
# arrived within a few seconds of startup — this is what used to
# be silently masked by the simulator. No fake data is generated;
# this only prints guidance so you can fix the actual connection.
# ============================================================
def no_data_watchdog():
    time.sleep(6)
    while True:
        with data_lock:
            missing = [z for z in (1, 2) if not zone_ever_seen_real_data[z]]
        if missing:
            print()
            print("############################################################")
            print(f"[NO DATA WARNING] Zone(s) {missing} have NOT sent a single")
            print("real PYTHON_DATA packet since startup. Dashboard will stay")
            print("on CALIBRATING until real data arrives. Check:")
            print(f"  1. Is the gateway ESP32 actually plugged in via USB?")
            print(f"  2. Is {SERIAL_PORT} still the correct COM port? (it can")
            print("     change after unplug/replug — check Device Manager)")
            print("  3. Is the gateway's own Serial Monitor closed? Only ONE")
            print("     program (this script OR Arduino/PlatformIO monitor)")
            print("     can hold a COM port open at a time.")
            print("  4. Do you see '[SERIAL] PYTHON_DATA:...' lines printing")
            print("     above? If nothing at all is printing under [SERIAL],")
            print("     the port opened but the gateway isn't sending data —")
            print("     check the gateway's own LoRa receive logic/wiring.")
            print("############################################################")
            print()
        time.sleep(10)


# ============================================================
# THREADS
# ============================================================
def serial_writer():
    global serial_connection
    while True:
        command = command_queue.get()
        try:
            sent = False
            for _ in range(10):
                with serial_connection_lock:
                    ser = serial_connection
                    if ser is not None and ser.is_open:
                        try:
                            ser.write((command + "\n").encode("utf-8"))
                            sent = True
                        except Exception as error:
                            print("[COMMAND WRITE ERROR]", error)
                        break
                time.sleep(0.1)
            print("[COMMAND SENT]" if sent else "[COMMAND DROPPED]", command)
        except Exception as error:
            print("[WRITER ERROR]", error)
        finally:
            command_queue.task_done()


def dashboard_emitter():
    while True:
        try:
            emit_dashboard_state()
        except Exception as error:
            print("[DASHBOARD ERROR]", error)
        time.sleep(0.5)


def serial_reader():
    global serial_connection
    while True:
        ser = None
        try:
            print(f"CONNECTING TO GATEWAY on {SERIAL_PORT}")
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.2, write_timeout=0.2)
            with serial_connection_lock:
                serial_connection = ser
            print("GATEWAY CONNECTED — WAITING FOR LIVE DATA...")

            while True:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                print("[SERIAL]", line)

                if parse_worker_line(line):
                    continue

                result = parse_python_data(line)
                if result is None:
                    continue
                zone, data = result
                zone_ever_seen_real_data[zone] = True
                sensor_queue.put((zone, data))

        except serial.SerialException as error:
            print("SERIAL ERROR:", error, "— retrying in 2s")
            time.sleep(2)
        except Exception as error:
            print("SERIAL READER ERROR:", error)
            time.sleep(2)
        finally:
            with serial_connection_lock:
                serial_connection = None
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass


def sensor_processor():
    while True:
        zone, data = sensor_queue.get()
        try:
            process_zone(zone, data)
        except Exception as error:
            print("[SENSOR PROCESSOR ERROR]", error)
        finally:
            sensor_queue.task_done()


# ============================================================
# API
# ============================================================
@app.route("/api/data")
def get_data():
    with data_lock:
        return jsonify(latest_data)

@app.route("/api/clear_sos", methods=["POST"])
def api_clear_sos():
    clear_sos()
    return jsonify({"status": "cleared"})

@app.route("/api/demo/<int:zone>/<risk>", methods=["POST", "GET"])
def api_demo_override(zone, risk):
    """
    LIVE DEMO CONTROL — open these URLs in a browser tab during the
    presentation to force a zone's risk instantly:
      http://127.0.0.1:5000/api/demo/2/CRITICAL
      http://127.0.0.1:5000/api/demo/2/WARNING
      http://127.0.0.1:5000/api/demo/2/SAFE
      http://127.0.0.1:5000/api/demo/2/CLEAR   -> back to real hardware data
    """
    zone = int(zone)
    risk = risk.upper()
    if zone not in (1, 2):
        return jsonify({"status": "error", "message": "zone must be 1 or 2"}), 400
    if risk == "CLEAR":
        manual_override[zone] = None
        return jsonify({"status": "override cleared", "zone": zone})
    if risk not in ("SAFE", "WARNING", "CRITICAL"):
        return jsonify({"status": "error", "message": "risk must be SAFE/WARNING/CRITICAL/CLEAR"}), 400
    manual_override[zone] = risk
    process_zone(zone, {"mq7": 1650, "mq4": 400, "ax": 0, "ay": 0, "az": 0.98,
                         "vibration": 0.3, "rssi": -55})
    return jsonify({"status": "override set", "zone": zone, "risk": risk})

@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    print("MINE SAFETY SYSTEM — real hardware only (no simulator)")
    print(f"Calibration: max {CALIBRATION_SAMPLES} samples OR {CALIBRATION_TIMEOUT_S}s timeout, whichever first")
    print("Manual demo override still available: visit /api/demo/<zone>/<SAFE|WARNING|CRITICAL|CLEAR> in a browser tab")

    print()
    print("Available serial ports on this machine right now:")
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("  (none detected — check the gateway's USB cable/power)")
    for p in ports:
        marker = "  <-- configured SERIAL_PORT" if p.device == SERIAL_PORT else ""
        print(f"  {p.device} — {p.description}{marker}")
    if SERIAL_PORT not in [p.device for p in ports]:
        print(f"  WARNING: configured SERIAL_PORT '{SERIAL_PORT}' is not in the list above!")
    print()

    threading.Thread(target=sensor_processor, daemon=True).start()
    threading.Thread(target=serial_reader, daemon=True).start()
    threading.Thread(target=serial_writer, daemon=True).start()
    threading.Thread(target=dashboard_emitter, daemon=True).start()
    threading.Thread(target=worker_offline_watchdog, daemon=True).start()
    threading.Thread(target=no_data_watchdog, daemon=True).start()

    socketio.run(app, host=HOST, port=PORT, debug=False, allow_unsafe_werkzeug=True)