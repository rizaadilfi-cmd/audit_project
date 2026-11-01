import requests
import json
import pandas as pd

def send_n8n_high_risk_alert(webhook_url: str, finding_data: dict) -> bool:
    if not webhook_url:
        return False
    payload = {
        "event": "HIGH_RISK_AUDIT_FINDING",
        "area": finding_data.get("area", "Unknown"),
        "risk_level": finding_data.get("risk_level", "HIGH"),
        "condition": finding_data.get("condition", ""),
        "effect": finding_data.get("effect", ""),
        "recommendation": finding_data.get("recommendation", ""),
        "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S WIB")
    }
    try:
        res = requests.post(webhook_url, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=5)
        return res.status_code == 200
    except Exception:
        return False