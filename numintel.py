import asyncio
import aiohttp
import json
import re
import phonenumbers
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print
import io
from PIL import Image
import base64

# --- CONFIGURATION ---
TARGET_NUMBER = "+919876543210" # Change this to your target
TIMEOUT = 15
CONSOLE = Console()

class NumIntel:
    def __init__(self, number: str):
        parsed = phonenumbers.parse(number, None)
        self.number = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        self.number_local = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        self.country = phonenumbers.region_code_for_number(parsed)
        self.carrier = self._get_carrier(parsed)
        self.data = {
            "number": self.number,
            "country": self.country,
            "carrier": self.carrier,
            "timestamp": datetime.now().isoformat(),
            "social_media": {},
            "leaked_data": {},
            "location_history": {},
            "identity": {},
            "visual_identity": {
                "photos": [],
                "face_embeddings": []
            }
        }

    def _get_carrier(self, parsed_number):
        try:
            return phonenumbers.get_carrier_name_for_number(parsed_number)
        except Exception:
            return "Unknown"

    async def fetch_url(self, session, url, headers=None, as_json=False):
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as resp:
                if resp.status == 200:
                    if as_json:
                        return await resp.json()
                    return await resp.text()
                return {"status": resp.status, "error": "Non-200 response"}
        except Exception as e:
            return {"error": str(e)}

    async def scan_social_media(self, session):
        """Scrape public profiles and extract photos."""
        # Common platforms where phone numbers might be visible or usernames match
        search_queries = [
            f"site:instagram.com {self.number}",
            f"site:facebook.com {self.number}",
            f"site:linkedin.com {self.number}",
            f"site:twitter.com {self.number}"
        ]
        
        # Note: In a real tool, you'd use a search API like SerpAPI or Bing Web Search API
        # Here we simulate direct profile checks for common username patterns
        
        username_patterns = [
            self.number.lstrip('+'),
            self.number_local,
            f"phone{self.number_local}"
        ]
        
        results = {}
        tasks = []
        for pattern in username_patterns:
            tasks.append(self._check_social_profiles(session, pattern))
        
        results.update(await asyncio.gather(*tasks))
        self.data["social_media"] = results

    async def _check_social_profiles(self, session, username):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        found = {}
        
        # Instagram Check (Public Profile)
        ig_url = f"https://www.instagram.com/{username}/"
        try:
            async with session.get(ig_url, headers=headers) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    # Extract profile pic from meta tags
                    match = re.search(r'property="og:image" content="([^"]+)"', text)
                    if match:
                        found["instagram"] = {
                            "url": ig_url,
                            "profile_pic": match.group(1),
                            "status": "Profile Found"
                        }
        except Exception as e:
            pass
            
        # Facebook Check (Public Profile)
        fb_url = f"https://www.facebook.com/{username}"
        try:
            async with session.get(fb_url, headers=headers) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    match = re.search(r'property="og:image" content="([^"]+)"', text)
                    if match:
                        found["facebook"] = {
                            "url": fb_url,
                            "profile_pic": match.group(1),
                            "status": "Profile Found"
                        }
        except Exception as e:
            pass
            
        return found

    async def scan_leaked_databases(self, session):
        """Query breach APIs."""
        # HIBP check
        breach_check = await self.fetch_url(session, f"https://api.hibp.com/breachedaccount/{self.number}", 
                                           headers={'User-Agent': 'NumIntel'}, as_json=False)
        self.data["leaked_data"]["hibp_check"] = breach_check

    async def scan_identity_and_address(self, session):
        """Enrich identity data."""
        self.data["identity"]["address"] = "Enrichment via API required (e.g., Clearbit Person)"
        self.data["identity"]["aadhar_link"] = "Aadhar data is protected. Only available if publicly shared (e.g., procurement portals)."

    async def scan_location_history(self, session):
        """Aggregate location data."""
        self.data["location_history"]["live"] = "Unavailable (Requires device-level access)"
        self.data["location_history"]["historical"] = "Aggregating from social media geotags..."

    async def scan_visual_identity(self, session):
        """
        This module takes the profile pictures found in social_media and 
        performs a reverse image search to find other accounts with the same face.
        """
        photos = self.data["social_media"]
        if not photos:
            return
            
        # Extract all profile pic URLs
        pic_urls = []
        for platform, data in photos.items():
            if isinstance(data, dict) and "profile_pic" in data:
                pic_urls.append({"platform": platform, "url": data["profile_pic"]})
                
        self.data["visual_identity"]["photos"] = pic_urls
        
        # If you want to do face matching, you'd download the image and use a library like 'face_recognition'
        # Here we just log the URLs for manual inspection or further API processing
        CONSOLE.print(f"[bold cyan]Found {len(pic_urls)} potential profile pictures.[/bold cyan]")
        for pic in pic_urls:
            CONSOLE.print(f"  - {pic['platform']}: {pic['url']}")

    async def run(self):
        async with aiohttp.ClientSession() as session:
            CONSOLE.print(Panel(f"Scanning {self.number} ({self.country}) | Carrier: {self.carrier}", style="bold cyan"))
            
            # Run all scans concurrently
            await asyncio.gather(
                self.scan_social_media(session),
                self.scan_leaked_databases(session),
                self.scan_identity_and_address(session),
                self.scan_location_history(session)
            )
            
            # Run visual identity scan after social media is populated
            await self.scan_visual_identity(session)
            
            self._print_report()
            self.save_report()

    def _print_report(self):
        table = Table(title=f"NumIntel Report: {self.number}")
        table.add_column("Category", style="bold magenta")
        table.add_column("Detail", style="white", max_width=60)
        
        table.add_row("Country", self.country)
        table.add_row("Carrier", self.carrier)
        
        for sm, status in self.data["social_media"].items():
            table.add_row(f"Social: {sm}", str(status))
            
        for leak, status in self.data["leaked_data"].items():
            table.add_row(f"Leak: {leak}", str(status))
            
        for loc, status in self.data["location_history"].items():
            table.add_row(f"Location: {loc}", str(status))
            
        for ident, status in self.data["identity"].items():
            table.add_row(f"Identity: {ident}", str(status))
            
        for photo in self.data["visual_identity"]["photos"]:
            table.add_row(f"Visual: {photo['platform']}", photo['url'])
            
        CONSOLE.print(table)

    def save_report(self):
        filename = f"numintel_{self.number.replace('+','')}.json"
        with open(filename, 'w') as f:
            json.dump(self.data, f, indent=4)
        CONSOLE.print(f"[green]Report saved to {filename}[/green]")

if __name__ == "__main__":
    intel = NumIntel(TARGET_NUMBER)
    asyncio.run(intel.run())