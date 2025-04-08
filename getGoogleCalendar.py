import os
import json
from datetime import datetime, timedelta, UTC
from googleapiclient.discovery import build
from google.oauth2 import service_account
from dotenv import load_dotenv

# 載入 .env 檔案
load_dotenv()

# 配置 Google Calendar API
SCOPES = ["https://www.googleapis.com/auth/calendar"]
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
CALENDAR_ID = os.getenv("CALENDAR_ID")

def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=creds)

def get_raw_calendar_events():
    service = get_calendar_service()
    
    # 設定時間範圍（過去一週到未來一週）
    now = datetime.now(UTC)
    time_min = (now - timedelta(days=7)).isoformat()
    time_max = (now + timedelta(days=7)).isoformat()
    
    try:
        # 獲取事件
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        # 輸出原始回應
        print(json.dumps(events_result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f'發生錯誤：{str(e)}')

if __name__ == "__main__":
    get_raw_calendar_events()