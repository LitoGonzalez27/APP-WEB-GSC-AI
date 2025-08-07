import schedule
import time
import requests
import os

def daily_analysis():
       try:
           app_url = os.environ.get('APP_URL', 'https://clicandseo.up.railway.app')
           endpoint = f"{app_url}/manual-ai/api/cron/daily-analysis"
           
           print(f"🚀 Executing cron for: {endpoint}")
           
           response = requests.post(
               endpoint,
               headers={'Content-Type': 'application/json'},
               timeout=600  # 10 minutos
           )
           
           print(f"📊 Response status: {response.status_code}")
           
           if response.status_code == 200:
               data = response.json()
               print(f"✅ Cron completed successfully: {data}")
           else:
               print(f"❌ Cron failed with status: {response.status_code}")
               
       except Exception as e:
           print(f"💥 Error: {str(e)}")

   # Schedule diario
schedule.every().day.at("02:00").do(daily_analysis)

print("🕒 Cron worker started. Waiting for schedule...")

while True:
       schedule.run_pending()
       time.sleep(60)