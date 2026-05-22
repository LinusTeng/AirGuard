import requests
import urllib3
import csv
import os
import sys

# 嘗試讀取本地的 .env 檔案（如果有的話）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # 雲端環境不需要 python-dotenv，因為 GitHub Actions 會直接注入環境變數
    pass

# 核心安全修改：絕對不寫出明文字串，只從系統環境變數讀取
MY_API_KEY = os.getenv("MY_API_KEY")

if not MY_API_KEY:
    print("❌ 錯誤：找不到 API 金鑰 (MY_API_KEY)！")
    print("本地開發：請確保已建立 .env 檔案並設定金鑰。")
    print("雲端執行：請確保 GitHub Settings -> Secrets 中已設定 MY_API_KEY。")
    sys.exit(1) # 強制停止程式

CSV_FILE = "airguard_all_taiwan_data.csv"

def save_to_csv(data_list):
    file_exists = os.path.isfile(CSV_FILE)
    # 我們定義 AirGuard 需要的核心欄位
    fieldnames = ['publishtime', 'sitename', 'county', 'aqi', 'pm2.5', 'status', 'latitude', 'longitude']
    
    existing_keys = set()
    if file_exists:
        try:
            with open(CSV_FILE, mode='r', encoding='utf-8-sig') as f_read:
                reader = csv.DictReader(f_read)
                for row in reader:
                    existing_keys.add((row['publishtime'], row['sitename']))
        except Exception:
            pass # 如果讀取失敗（如檔案損壞），就當作空檔案處理

    with open(CSV_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        
        added_count = 0
        for row in data_list:
            # 建立檢查鍵值
            pub_time = row.get('publishtime')
            site_name = row.get('sitename')
            
            if pub_time and site_name and (pub_time, site_name) not in existing_keys:
                # 建立要儲存的字典，並處理可能的欄位名稱差異
                filtered_row = {
                    'publishtime': pub_time,
                    'sitename': site_name,
                    'county': row.get('county', '未知'),
                    'aqi': row.get('aqi', '0'),
                    'pm2.5': row.get('pm2.5', '0'),
                    'status': row.get('status', '未知'),
                    'latitude': row.get('latitude', row.get('lat', '0')),
                    'longitude': row.get('longitude', row.get('lon', '0'))
                }
                writer.writerow(filtered_row)
                added_count += 1
        return added_count

def run_airguard_sync():
    params = {"api_key": MY_API_KEY, "format": "json"}
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🛡️ AirGuard 全台數據同步啟動...")
    
    try:
        response = requests.get(API_URL, params=params, verify=False, timeout=20)
        
        if response.status_code == 200:
            res_data = response.json()
            
            # --- 核心修復：判斷回傳結構 ---
            if isinstance(res_data, dict):
                records = res_data.get('records', [])
            elif isinstance(res_data, list):
                records = res_data
            else:
                print("❌ 無法辨識的 API 資料格式")
                return

            if records:
                new_data_count = save_to_csv(records)
                print(f"✅ 同步成功！本次新增 {new_data_count} 筆數據至資料庫。")
            else:
                print("⚠️ API 回傳資料為空。")
        else:
            print(f"❌ 連線失敗，伺服器回傳狀態碼：{response.status_code}")
            
    except Exception as e:
        print(f"⚠️ AirGuard 運行錯誤: {e}")

if __name__ == "__main__":
    run_airguard_sync()
