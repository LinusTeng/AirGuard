import os
import sys
import requests
import urllib3
import csv
from datetime import datetime # ✅ 補上這個，解決 NameError 報錯

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 安全讀取環境變數 (絕對不寫明文)
MY_API_KEY = os.getenv("MY_API_KEY")

if not MY_API_KEY:
    print("❌ 錯誤：找不到 API 金鑰 (MY_API_KEY)！")
    sys.exit(1)

API_URL = "https://data.moenv.gov.tw/api/v2/aqx_p_432"
CSV_FILE = "airguard_all_taiwan_data.csv"

def run_airguard_sync():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🛡️ AirGuard 全台數據同步啟動...")
    params = {
        "api_key": MY_API_KEY,
        "format": "json",
        "limit": 1000,
        "sort": "publishtime desc"
    }
    
    try:
        response = requests.get(API_URL, params=params, verify=False, timeout=20)
        if response.status_code == 200:
            res_data = response.json()
            records = res_data.get('records', []) if isinstance(res_data, dict) else res_data
            
            if not records:
                print("⚠️ API 沒有回傳任何紀錄。")
                return

            file_exists = os.path.isfile(CSV_FILE)
            fieldnames = ['publishtime', 'sitename', 'county', 'aqi', 'pm2.5', 'status', 'latitude', 'longitude']
            
            existing_keys = set()
            if file_exists:
                with open(CSV_FILE, mode='r', encoding='utf-8-sig') as f_read:
                    reader = csv.DictReader(f_read)
                    for row in reader:
                        existing_keys.add((row.get('publishtime'), row.get('sitename')))

            added_count = 0
            with open(CSV_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                
                for row in records:
                    if not isinstance(row, dict): continue
                    p_time = row.get('publishtime')
                    s_name = row.get('sitename')
                    
                    if p_time and s_name and (p_time, s_name) not in existing_keys:
                        filtered_row = {
                            'publishtime': p_time,
                            'sitename': s_name,
                            'county': row.get('county', '未知'),
                            'aqi': row.get('aqi', '0'),
                            'pm2.5': row.get('pm2.5', '0'),
                            'status': row.get('status', '未知'),
                            'latitude': row.get('latitude', row.get('lat', '0')),
                            'longitude': row.get('longitude', row.get('lon', '0'))
                        }
                        writer.writerow(filtered_row)
                        added_count += 1
                        existing_keys.add((p_time, s_name))
            
            print(f"✅ 同步完成！成功新增 {added_count} 筆數據。")
        else:
            print(f"❌ API 連線失敗，代碼：{response.status_code}")
    except Exception as e:
        print(f"⚠️ 發生錯誤: {e}")

if __name__ == "__main__":
    run_airguard_sync()
