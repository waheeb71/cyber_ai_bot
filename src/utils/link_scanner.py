import requests
import json
import aiohttp
import asyncio

import os

googleSafeBrowsing = os.getenv("GOOGLE_SAFE_BROWSING")
virusTotal = os.getenv("VIRUSTOTAL_API_KEY")
urlScan = os.getenv("URLSCAN_API_KEY")
alienVaultOTX = os.getenv("ALIENVAULT_OTX_KEY")
rapidApiKey = os.getenv("RAPIDAPI_KEY")
hunterApiKey = os.getenv("HUNTER_API_KEY")

async def scan_url_google_safe_browsing(url):
    api_url = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={googleSafeBrowsing}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "client": {
            "clientId": "your-company-name",
            "clientVersion": "1.5.2"
        },
        "threatInfo": {
            "threatTypes": [
                "MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE",
                "POTENTIALLY_HARMFUL_APPLICATION", "THREAT_TYPE_UNSPECIFIED"
            ],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "url": url
        }
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and "matches" in data:
                        return f"Google Safe Browsing: ⚠️ تم العثور على تهديدات: {data['matches'][0]['threatType']}"
                    else:
                        return "Google Safe Browsing: ✅ لا توجد تهديدات معروفة."
                else:
                    return f"Google Safe Browsing: ❌ خطأ في API: {response.status} - {await response.text()}"
    except Exception as e:
        return f"Google Safe Browsing: ❌ حدث خطأ: {e}"

async def scan_url_virustotal(url):
    api_url = "https://www.virustotal.com/api/v3/urls"
    headers = {
        "x-apikey": virusTotal,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {"url": url}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, headers=headers, data=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    analysis_id = data['data']['id']
                    await asyncio.sleep(10)
                    report_url = f"https://www.virustotal.com/api/v3/analyses/{analysis_id}"
                    async with session.get(report_url, headers=headers) as report_response:
                        if report_response.status == 200:
                            report_data = await report_response.json()
                            stats = report_data['data']['attributes']['stats']
                            if stats['malicious'] > 0 or stats['suspicious'] > 0:
                                return f"VirusTotal: ⚠️ تم العثور على {stats['malicious']} تهديدات خبيثة و {stats['suspicious']} تهديدات مشبوهة."
                            else:
                                return "VirusTotal: ✅ لا توجد تهديدات معروفة."
                        else:
                            return f"VirusTotal: ❌ خطأ في جلب التقرير: {report_response.status} - {await report_response.text()}"
                else:
                    return f"VirusTotal: ❌ خطأ في API: {response.status} - {await response.text()}"
    except Exception as e:
        return f"VirusTotal: ❌ حدث خطأ: {e}"

async def scan_url_urlscan(url):
    api_url = "https://urlscan.io/api/v1/scan/"
    headers = {
        "API-Key": urlScan,
        "Content-Type": "application/json"
    }
    payload = {"url": url, "visibility": "public"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return f"URLScan.io: ✅ تم إرسال الرابط للفحص. التقرير متاح على: {data['result']}"
                else:
                    return f"URLScan.io: ❌ خطأ في API: {response.status} - {await response.text()}"
    except Exception as e:
        return f"URLScan.io: ❌ حدث خطأ: {e}"

async def scan_url_alienvault_otx(url):
    api_url = f"https://otx.alienvault.com/api/v1/indicators/url/{url}"
    headers = {"X-OTX-API-KEY": alienVaultOTX}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and "detections" in data and len(data["detections"]) > 0:
                        return f"AlienVault OTX: ⚠️ تم العثور على تهديدات: {len(data['detections'])} اكتشافات."
                    else:
                        return "AlienVault OTX: ✅ لا توجد تهديدات معروفة."
                elif response.status == 404:
                    return "AlienVault OTX: ✅ لا توجد معلومات عن هذا الرابط."
                else:
                    return f"AlienVault OTX: ❌ خطأ في API: {response.status} - {await response.text()}"
    except Exception as e:
        return f"AlienVault OTX: ❌ حدث خطأ: {e}"

async def scan_link(url):
    raw_results = await asyncio.gather(
        scan_url_google_safe_browsing(url),
        scan_url_virustotal(url),
        scan_url_urlscan(url),
        scan_url_alienvault_otx(url)
    )

  
    successful_results = [result for result in raw_results if "❌" not in result]

    if not successful_results:
       
        return None

  
    response_message = "📊 نتائج فحص الرابط:\n\n"
    for res in successful_results:
        response_message += f"{res}\n\n"
    return response_message.strip()

