# app/core/mqtt.py

import ssl
import logging
import os
from datetime import datetime
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)
mqtt_client = None

# ✅ Tạo đường dẫn tuyệt đối đến thư mục logs
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # trỏ tới app/
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ✅ Đường dẫn tới file Excel log
EXCEL_FILE = os.path.join(LOG_DIR, "mqtt_data.xlsx")

def get_mqtt_client():
    global mqtt_client
    if mqtt_client is None:
        from paho.mqtt.client import Client
        mqtt_client = Client()

        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message

        # Đường dẫn đến ca.pem
        cert_path = os.path.join(os.path.dirname(__file__), "certs", "emqxsl_ca.pem")

        # Thiết lập TLS chỉ dùng CA
        mqtt_client.tls_set(
            ca_certs=cert_path,
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLSv1_2,
        )
        mqtt_client.tls_insecure_set(False)

        # Kết nối đến broker
        mqtt_client.connect("scalemodelvn.com", port=8883)
        mqtt_client.loop_start()

    return mqtt_client

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("✅ MQTT connected securely with CA cert only")
        client.subscribe("secure/topic")  # Thay topic nếu cần
    else:
        logger.error(f"❌ MQTT connection failed with code {rc}")

def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    topic = msg.topic
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info(f"📩 MQTT Message: {topic} → {payload}")
    log_to_excel(timestamp, topic, payload)

def log_to_excel(timestamp: str, topic: str, payload: str):
    # Tạo mới file nếu chưa tồn tại
    if not os.path.exists(EXCEL_FILE):
        wb = Workbook()
        ws = wb.active
        ws.title = "MQTT Logs"
        ws.append(["Timestamp", "Topic", "Payload"])
    else:
        wb = load_workbook(EXCEL_FILE)
        ws = wb.active

    # Thêm dòng dữ liệu mới
    ws.append([timestamp, topic, payload])

    # Auto-resize cột
    for col in ws.columns:
        max_len = max(len(str(cell.value)) if cell.value else 0 for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max_len + 2

    wb.save(EXCEL_FILE)