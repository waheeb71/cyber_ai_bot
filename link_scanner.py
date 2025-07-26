import requests
import json
import aiohttp
import asyncio

googleSafeBrowsing = 'AIzaSyA8QPfUZyVkXZW4N6URMCJwx936I0rcs20'
virusTotal = 'b22b4647dbc721e344e3e4c4e66ba01ec2f8abb08fa608d3eabb9b32bc2d163e'
urlScan = '01959437-0353-7001-ad40-722bc7dfd395'
alienVaultOTX = 'ead0b8ef9672a4f6dcdbaf79c6ef2cdc30595ef81a906848875b4388f6c3356e'
rapidApiKey = "77289a4b46msh5b6bce0543333c4p1a6572jsn4be28ab7f5a1"
hunterApiKey = "d2149e36df9fce40edc61154e6a6a6e8260ddf97"

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

async def scan_url_all(url):
    raw_results = await asyncio.gather(
        scan_url_google_safe_browsing(url),
        scan_url_virustotal(url),
        scan_url_urlscan(url),
        scan_url_alienvault_otx(url)
    )

    # تصفية الردود الناجحة فقط (لا تحتوي على كلمة "❌")
    successful_results = [result for result in raw_results if "❌" not in result]

    if not successful_results:
        # كل الردود فشلت، لا نعرض شيء للمستخدم
        return None

    # تنسيق الإخراج بشكل منظم
    response_message = "📊 نتائج فحص الرابط:\n\n"
    for res in successful_results:
        response_message += f"{res}\n\n"
    return response_message.strip()

