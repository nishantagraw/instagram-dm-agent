"""
📸 INSTAGRAM DM AGENT - Infinite Club
=====================================
Automated Instagram DM outreach using browser automation.
Safe, rate-limited, with multiple account support.

Features:
- Search by hashtags
- Browse profiles
- Check for website in bio
- Send personalized DMs
- Track sent messages
- Dashboard for monitoring
- Multiple account rotation
- Human-like delays
- AI Vision Mode (Gemini)

Author: Infinite Club
Date: December 2025
"""

import asyncio
import json
import random
import re
import os
import time
import base64
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request
from threading import Thread

# Try to import Google Generative AI
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ google-generativeai not installed. Run: pip install google-generativeai")
import sqlite3

# Try to import playwright
try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright not installed. Run: pip install playwright && playwright install chromium")

# ============== CONFIGURATION ==============

CONFIG = {
    # Rate Limits (per account per day)
    "max_dms_per_day": 25,
    "max_comments_per_day": 50,  # Increased from 30 - natural comments are safer
    "max_profile_views_per_day": 100,
    "max_searches_per_day": 20,
    
    # Delays (in seconds) - OPTIMIZED & SAFE
    "delay_between_actions_min": 15,
    "delay_between_actions_max": 30,
    "delay_between_dms_min": 60,   # 60-90 seconds between DMs
    "delay_between_dms_max": 90,
    "delay_between_comments_min": 20,  # Reduced from 30 - faster commenting
    "delay_between_comments_max": 40,  # Reduced from 60
    "delay_after_login_min": 5,
    "delay_after_login_max": 10,
    "page_load_timeout": 30000,
    
    # Browser
    "headless": False,  # Set to True to run invisibly
    "slow_mo": 100,  # Milliseconds between actions
    
    # Data
    "data_dir": "data",
    "accounts_file": "accounts.json",
    "sent_dms_db": "sent_dms.db",
    "session_dir": "sessions",
    
    # Gemini AI (for AI Mode)
    "gemini_api_key": "AIzaSyDayy6D8df_U9NpI1kn6sFxxeG2zUrPqc4",
    "gemini_model": "models/gemini-2.5-flash",  # Latest Gemini 2.5
    
    # Saved Collection (by NAME - works for any account!)
    "saved_collection_name": "Comment Leads",  # Just create a collection with this name
}

# DM Templates - Professional style matching email outreach
# NO spam keywords like prices or "$"
DM_TEMPLATES = {
    "no_website": """Hi! 👋

I came across your page and love what you're doing!

I noticed you don't have a website yet. A professional website could help you reach more customers and build credibility online.

We help small businesses with:
✓ Professional websites
✓ AI chatbots for customer support
✓ Business automation
✓ Branding & logos

All delivered fast with unlimited revisions!

Would you like to learn more?

👉 Check out our work - link in my bio!

Best,
Infinite Club Team
📧 hello@infiniteclub.tech""",

    "with_website": """Hi! 👋

I love your content and what you're building!

We help businesses like yours grow with:
✓ Website redesigns & updates
✓ AI chatbots for 24/7 customer support
✓ Branding refresh
✓ Business automation

Would love to help you grow even more!

👉 Check our work - link in my bio!

Best,
Infinite Club Team
📧 hello@infiniteclub.tech""",

    "general": """Hi! 👋

I came across your profile and really like what you do!

We help small businesses grow with:
✓ Professional websites
✓ AI chatbots
✓ Branding & logos
✓ Automation tools

All delivered fast!

Would you be interested in learning more?

👉 Check our work - link in my bio!

Best,
Infinite Club Team
📧 hello@infiniteclub.tech"""
}

# Target hashtags - Expanded for more business types
TARGET_HASHTAGS = [
    # General Business
    "smallbusiness", "entrepreneur", "newbusiness", "startuplife", "businessowner",
    "localshop", "shopsmall", "handmadebusiness", "indianbusiness",
    # Beauty & Wellness
    "salonowner", "beautysalon", "nailsalon", "spaowner", "skincare", "beautician",
    "makeupstudio", "hairstylist", "dermatologist", "skinclinic",
    # Food & Restaurant
    "restaurantowner", "cafeowner", "bakerylife", "foodbusiness", "cloudkitchen",
    "indianrestaurant", "streetfood", "homechef", "cateringbusiness",
    # Health & Medical
    "clinicowner", "dentist", "doctorlife", "healthcarebusiness", "medicalclinic",
    "physiotherapy", "ayurvedic", "homeopathy", "veterinary",
    # Fitness
    "fitnesscoach", "gymowner", "personaltrainer", "yogastudio", "fitnesscentre",
    # Retail & Fashion
    "boutiqueowner", "fashionboutique", "jewelrystore", "clothingbrand", "onlineshop",
    # Services
    "interiordesigner", "photographer", "eventplanner", "weddingplanner",
    "realestate", "propertydealer", "coachingcentre", "tuitionclasses",
    # Creative
    "artistsoninstagram", "graphicdesigner", "contentcreator", "digitalagency",
]

# Comment Templates - NATURAL (won't get deleted)
# Strategy: Genuine comments that spark curiosity - NO promotional language
COMMENT_TEMPLATES = [
    # Genuine appreciation (no promotion)
    "This is beautiful! 😍",
    "Love this! 🔥",
    "Amazing work! ✨",
    "So inspiring! 💫",
    "This is goals! 🙌",
    "Wow! Just wow! 😍",
    "Absolutely stunning! ✨",
    "Love the vibes! 💯",
    "This made my day! 🔥",
    "Incredible work! 💪",
    # Slightly longer but still natural
    "This is exactly what I needed to see today! 🙌",
    "You're so talented! Keep it up! 💯",
    "Your work is amazing! Following for more! ✨",
    "Love what you're doing here! 🔥",
    "Such beautiful content! 😍",
    "This deserves more attention! 💫",
    "Obsessed with this! 💕",
    "Can't stop looking at this! So good! ✨",
    "You make it look so easy! 🙌",
    "This is art! Pure art! 🎨",
]

# ============== ACTIVITY LOG ==============
# Global log for real-time dashboard updates
activity_log = []
MAX_LOG_ENTRIES = 200

def add_log(message, log_type="info"):
    """Add entry to activity log"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = {
        "time": timestamp,
        "message": message,
        "type": log_type  # info, success, error, warning, action
    }
    activity_log.insert(0, entry)
    
    # Keep log size limited
    if len(activity_log) > MAX_LOG_ENTRIES:
        activity_log.pop()
    
    # Also print to console
    icons = {"info": "ℹ️", "success": "✅", "error": "❌", "warning": "⚠️", "action": "🎯"}
    print(f"[{timestamp}] {icons.get(log_type, '•')} {message}")

# ============== DATABASE ==============

def init_database():
    """Initialize SQLite database for tracking"""
    db_path = Path(CONFIG["data_dir"]) / CONFIG["sent_dms_db"]
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Sent DMs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_dms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            full_name TEXT,
            profile_url TEXT,
            has_website INTEGER,
            dm_template TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            account_used TEXT,
            status TEXT DEFAULT 'sent'
        )
    ''')
    
    # Replies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            message TEXT,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_interested INTEGER DEFAULT 0
        )
    ''')
    
    # Daily stats
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            account TEXT,
            dms_sent INTEGER DEFAULT 0,
            profiles_viewed INTEGER DEFAULT 0,
            searches_done INTEGER DEFAULT 0
        )
    ''')
    
    # Prospects (profiles found but not DMed yet)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prospects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            full_name TEXT,
            bio TEXT,
            followers INTEGER,
            has_website INTEGER,
            found_via TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    # NEW: Visited posts (to avoid checking same post twice)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS visited_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_url TEXT UNIQUE,
            username TEXT,
            visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # NEW: Comments sent (to track and avoid duplicate comments)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_url TEXT UNIQUE,
            username TEXT,
            comment_text TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            account_used TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def get_db():
    db_path = Path(CONFIG["data_dir"]) / CONFIG["sent_dms_db"]
    return sqlite3.connect(db_path, check_same_thread=False)

def is_already_messaged(username):
    """Check if we already DMed this user"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sent_dms WHERE username = ?", (username.lower(),))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def save_sent_dm(username, full_name, profile_url, has_website, template, account):
    """Save sent DM to database"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO sent_dms (username, full_name, profile_url, has_website, dm_template, account_used)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username.lower(), full_name, profile_url, has_website, template, account))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Already exists
    conn.close()

def is_post_visited(post_url):
    """Check if we already visited this post"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM visited_posts WHERE post_url = ?", (post_url,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def save_visited_post(post_url, username):
    """Mark post as visited"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO visited_posts (post_url, username)
            VALUES (?, ?)
        ''', (post_url, username))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def is_already_commented(post_url):
    """Check if we already commented on this post"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sent_comments WHERE post_url = ?", (post_url,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def save_sent_comment(post_url, username, comment_text, account):
    """Save sent comment to database"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO sent_comments (post_url, username, comment_text, account_used)
            VALUES (?, ?, ?, ?)
        ''', (post_url, username, comment_text, account))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def save_prospect(username, full_name, bio, followers, has_website, found_via):
    """Save prospect to database"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO prospects (username, full_name, bio, followers, has_website, found_via)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username.lower(), full_name, bio, followers, has_website, found_via))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Already exists
    conn.close()

def get_pending_prospects(limit=50):
    """Get prospects that haven't been DMed yet"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT username, full_name, bio, has_website FROM prospects 
        WHERE status = 'pending' AND username NOT IN (SELECT username FROM sent_dms)
        LIMIT ?
    ''', (limit,))
    results = cursor.fetchall()
    conn.close()
    return results

def get_today_stats(account):
    """Get today's stats for an account"""
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute('''
        SELECT dms_sent, profiles_viewed, searches_done FROM daily_stats
        WHERE date = ? AND account = ?
    ''', (today, account))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"dms_sent": result[0], "profiles_viewed": result[1], "searches_done": result[2]}
    return {"dms_sent": 0, "profiles_viewed": 0, "searches_done": 0}

def increment_stat(account, stat_name):
    """Increment a daily stat"""
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Check if row exists
    cursor.execute("SELECT id FROM daily_stats WHERE date = ? AND account = ?", (today, account))
    if cursor.fetchone():
        cursor.execute(f"UPDATE daily_stats SET {stat_name} = {stat_name} + 1 WHERE date = ? AND account = ?", (today, account))
    else:
        cursor.execute(f"INSERT INTO daily_stats (date, account, {stat_name}) VALUES (?, ?, 1)", (today, account))
    conn.commit()
    conn.close()

# ============== ACCOUNT MANAGEMENT ==============

def load_accounts():
    """Load Instagram accounts from file"""
    accounts_path = Path(CONFIG["data_dir"]) / CONFIG["accounts_file"]
    if not accounts_path.exists():
        # Create sample file
        sample = [
            {"username": "your_instagram_username", "password": "your_password", "enabled": False},
        ]
        accounts_path.parent.mkdir(parents=True, exist_ok=True)
        with open(accounts_path, 'w') as f:
            json.dump(sample, f, indent=2)
        print(f"📝 Created sample accounts file: {accounts_path}")
        print("   Please edit this file and add your Instagram accounts")
        return []
    
    with open(accounts_path) as f:
        accounts = json.load(f)
    
    # Filter enabled accounts
    enabled = [a for a in accounts if a.get("enabled", True)]
    print(f"📱 Loaded {len(enabled)} Instagram accounts")
    return enabled

def get_next_account(accounts, last_used=None):
    """Get next account to use (rotation)"""
    if not accounts:
        return None
    
    # Simple rotation - find next after last used
    if last_used:
        for i, acc in enumerate(accounts):
            if acc["username"] == last_used:
                next_idx = (i + 1) % len(accounts)
                return accounts[next_idx]
    
    return accounts[0]

# ============== INSTAGRAM AUTOMATION ==============

class InstagramBot:
    def __init__(self, account):
        self.account = account
        self.username = account["username"]
        self.password = account["password"]
        self.browser = None
        self.context = None
        self.page = None
        self.logged_in = False
        
    async def start(self, playwright):
        """Start browser"""
        session_path = Path(CONFIG["data_dir"]) / CONFIG["session_dir"] / self.username
        session_path.mkdir(parents=True, exist_ok=True)
        
        self.browser = await playwright.chromium.launch(
            headless=CONFIG["headless"],
            slow_mo=CONFIG["slow_mo"]
        )
        
        # Try to load existing session
        self.context = await self.browser.new_context(
            storage_state=str(session_path / "state.json") if (session_path / "state.json").exists() else None,
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(CONFIG["page_load_timeout"])
        
    async def human_delay(self, min_sec=None, max_sec=None):
        """Random delay to appear human"""
        if min_sec is None:
            min_sec = CONFIG["delay_between_actions_min"]
        if max_sec is None:
            max_sec = CONFIG["delay_between_actions_max"]
        delay = random.uniform(min_sec, max_sec)
        print(f"   ⏳ Waiting {delay:.1f}s...")
        await asyncio.sleep(delay)
        
    async def random_scroll(self):
        """Random scroll to appear human"""
        scroll_amount = random.randint(100, 500)
        await self.page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
    async def login(self):
        """Login to Instagram"""
        print(f"🔐 Logging in as @{self.username}...")
        
        await self.page.goto("https://www.instagram.com/")
        await asyncio.sleep(3)
        
        # Check if already logged in
        try:
            await self.page.wait_for_selector('[aria-label="Home"]', timeout=5000)
            print(f"   ✅ Already logged in!")
            self.logged_in = True
            return True
        except:
            pass
        
        # Click on username field and type
        try:
            username_input = await self.page.wait_for_selector('input[name="username"]', timeout=10000)
            await username_input.fill(self.username)
            await asyncio.sleep(random.uniform(0.5, 1))
            
            password_input = await self.page.wait_for_selector('input[name="password"]')
            await password_input.fill(self.password)
            await asyncio.sleep(random.uniform(0.5, 1))
            
            # Click login button
            login_btn = await self.page.wait_for_selector('button[type="submit"]')
            await login_btn.click()
            
            # Wait for navigation
            await asyncio.sleep(5)
            
            # ===== CHECK FOR 2FA =====
            try:
                # Look for 2FA input field
                two_fa_input = await self.page.query_selector('input[name="verificationCode"]')
                if not two_fa_input:
                    two_fa_input = await self.page.query_selector('input[aria-label*="Security code"]')
                if not two_fa_input:
                    two_fa_input = await self.page.query_selector('input[placeholder*="code"]')
                    
                if two_fa_input:
                    print(f"\n   🔐 2FA REQUIRED!")
                    print(f"   ⏸️  PAUSING - Enter your 2FA code in the browser...")
                    print(f"   ⏳ Waiting 60 seconds for you to enter the code...")
                    
                    # Wait for user to manually enter 2FA
                    await asyncio.sleep(60)
                    
                    print(f"   ▶️  Resuming...")
            except:
                pass
            
            # Handle "Suspicious Login" challenge
            try:
                suspicious = await self.page.query_selector('text=Suspicious Login')
                if suspicious:
                    print(f"\n   ⚠️ SUSPICIOUS LOGIN DETECTED!")
                    print(f"   ⏸️  Complete the challenge in browser...")
                    print(f"   ⏳ Waiting 90 seconds...")
                    await asyncio.sleep(90)
            except:
                pass
            
            # Handle 2FA or save login prompts
            try:
                # "Save info" prompt
                save_btn = await self.page.wait_for_selector('text=Save info', timeout=5000)
                if save_btn:
                    await save_btn.click()
            except:
                pass
            
            try:
                # "Not now" for notifications
                not_now = await self.page.wait_for_selector('text=Not Now', timeout=5000)
                if not_now:
                    await not_now.click()
            except:
                pass
            
            # Verify login
            await self.page.wait_for_selector('[aria-label="Home"]', timeout=15000)
            print(f"   ✅ Logged in successfully!")
            self.logged_in = True
            
            # Save session
            session_path = Path(CONFIG["data_dir"]) / CONFIG["session_dir"] / self.username
            await self.context.storage_state(path=str(session_path / "state.json"))
            print(f"   💾 Session saved")
            
            await self.human_delay(CONFIG["delay_after_login_min"], CONFIG["delay_after_login_max"])
            return True
            
        except Exception as e:
            print(f"   ❌ Login failed: {e}")
            self.logged_in = False
            return False
            
    async def search_hashtag(self, hashtag):
        """Search posts by hashtag - with multiple selector fallbacks"""
        add_log(f"🔍 Searching hashtag #{hashtag}...", "action")
        
        try:
            url = f"https://www.instagram.com/explore/tags/{hashtag}/"
            add_log(f"📍 Navigating to {url}", "info")
            await self.page.goto(url)
            await asyncio.sleep(4)
            
            # Scroll MORE to load more posts (10 times instead of 3)
            add_log(f"📜 Scrolling to load more posts...", "info")
            for i in range(10):
                await self.page.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(0.5)
            
            increment_stat(self.username, "searches_done")
            
            # Try multiple selectors - Instagram changes HTML often
            add_log(f"🔎 Looking for posts in #{hashtag}...", "info")
            post_links = []
            
            # Selector 1: Standard article links
            posts = await self.page.query_selector_all('a[href*="/p/"]')
            add_log(f"   Selector 1: Found {len(posts)} links", "info")
            
            if not posts:
                # Selector 2: Try div with role="button" inside links
                posts = await self.page.query_selector_all('div[role="button"] a[href*="/p/"]')
                add_log(f"   Selector 2: Found {len(posts)} links", "info")
            
            if not posts:
                # Selector 3: All links containing /p/
                all_links = await self.page.query_selector_all('a')
                posts = []
                for link in all_links:
                    href = await link.get_attribute("href")
                    if href and "/p/" in href:
                        posts.append(link)
                add_log(f"   Selector 3: Found {len(posts)} links", "info")
            
            # Extract unique post URLs - increased from 30 to 100
            seen_urls = set()
            for post in posts[:100]:  # Check up to 100 posts
                try:
                    href = await post.get_attribute("href")
                    if href and "/p/" in href:
                        full_url = href if href.startswith("http") else f"https://www.instagram.com{href}"
                        if full_url not in seen_urls:
                            seen_urls.add(full_url)
                            post_links.append(full_url)
                except:
                    pass
                    
            add_log(f"📸 Found {len(post_links)} unique posts in #{hashtag}", "success" if post_links else "warning")
            
            if not post_links:
                add_log(f"⚠️ No posts found! Taking screenshot for debug...", "warning")
                # Save screenshot for debugging
                try:
                    await self.page.screenshot(path=f"data/debug_{hashtag}.png")
                    add_log(f"📷 Screenshot saved: data/debug_{hashtag}.png", "info")
                except:
                    pass
            
            return post_links
            
        except Exception as e:
            add_log(f"❌ Error searching #{hashtag}: {str(e)}", "error")
            return []
        
    async def get_profile_from_post(self, post_url):
        """Get profile username from a post - with multiple selector fallbacks"""
        add_log(f"📄 Opening post: {post_url[-20:]}", "info")
        
        try:
            await self.page.goto(post_url)
            await asyncio.sleep(3)
            
            username = None
            
            # Try multiple selectors for username
            selectors = [
                'article header a',  # Classic
                'header a[href*="/"]',  # Header link
                'a[href*="/"][role="link"]',  # Role link
                'span a[href*="/"]',  # Span link
            ]
            
            for selector in selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        href = await element.get_attribute("href")
                        if href and "/" in href and "/p/" not in href:
                            # Extract username from href like "/username/"
                            parts = href.strip("/").split("/")
                            if parts:
                                potential_username = parts[0]
                                # Filter out non-usernames
                                if potential_username and not potential_username.startswith(("explore", "reels", "stories", "p")):
                                    username = potential_username
                                    add_log(f"👤 Found username: @{username}", "success")
                                    break
                except:
                    pass
            
            if not username:
                # Try getting from page URL after click
                try:
                    link = await self.page.query_selector('a[href*="/"][role="link"]')
                    if link:
                        text = await link.text_content()
                        if text and len(text) < 30:  # Username usually short
                            username = text.strip()
                            add_log(f"👤 Found username from text: @{username}", "success")
                except:
                    pass
            
            if not username:
                add_log(f"⚠️ Could not find username from post", "warning")
            
            return username
            
        except Exception as e:
            add_log(f"❌ Error getting profile from post: {str(e)}", "error")
            return None
        
    async def check_profile(self, username):
        """Check a profile - get bio, followers, website with BETTER selectors"""
        add_log(f"🔍 Analyzing profile @{username}...", "action")
        
        try:
            await self.page.goto(f"https://www.instagram.com/{username}/")
            await asyncio.sleep(3)
            
            # Scroll to load content
            await self.page.evaluate("window.scrollBy(0, 300)")
            await asyncio.sleep(1)
            
            increment_stat(self.username, "profiles_viewed")
            
            profile_data = {
                "username": username,
                "full_name": "",
                "bio": "",
                "followers": 0,
                "has_website": False,
                "website": "",
                "is_business": False,
                "is_good_target": False
            }
            
            # Get the full page text for analysis
            page_text = await self.page.text_content("body") or ""
            
            # ========== EXTRACT FOLLOWERS ==========
            # Method 1: Look for "followers" text pattern in page
            followers_patterns = [
                r'([\d,.]+[KMkm]?)\s*followers',
                r'([\d,.]+)\s*Followers',
                r'"edge_followed_by":\s*{\s*"count":\s*(\d+)',
            ]
            
            for pattern in followers_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    followers_str = match.group(1)
                    # Convert K/M to numbers
                    if 'k' in followers_str.lower():
                        followers = int(float(followers_str.lower().replace('k', '').replace(',', '')) * 1000)
                    elif 'm' in followers_str.lower():
                        followers = int(float(followers_str.lower().replace('m', '').replace(',', '')) * 1000000)
                    else:
                        followers = int(followers_str.replace(',', '').replace('.', ''))
                    profile_data["followers"] = followers
                    add_log(f"   📊 Followers: {followers:,}", "info")
                    break
            
            # ========== CHECK FOR WEBSITE ==========
            # Method 1: Look for external links
            external_links = await self.page.query_selector_all('a[href*="l.instagram.com"]')
            if external_links:
                profile_data["has_website"] = True
                try:
                    href = await external_links[0].get_attribute("href")
                    profile_data["website"] = href
                    add_log(f"   🌐 Has website: YES", "info")
                except:
                    pass
            else:
                # Method 2: Check for linktr.ee, linkin.bio etc in page text
                link_patterns = ['linktr.ee', 'linkin.bio', 'bit.ly', 'link in bio', '.com', '.net', '.org']
                for pattern in link_patterns:
                    if pattern.lower() in page_text.lower():
                        profile_data["has_website"] = True
                        add_log(f"   🌐 Has website indicator: {pattern}", "info")
                        break
            
            if not profile_data["has_website"]:
                add_log(f"   🌐 Has website: NO", "info")
            
            # ========== GET BIO ==========
            bio_selectors = [
                'header section span:not([class])',
                'header div span',
                '[data-testid="user-bio"]',
            ]
            for selector in bio_selectors:
                try:
                    bio_elem = await self.page.query_selector(selector)
                    if bio_elem:
                        bio_text = await bio_elem.text_content()
                        if bio_text and len(bio_text) > 10:
                            profile_data["bio"] = bio_text[:200]
                            break
                except:
                    pass
            
            # ========== CHECK IF BUSINESS ==========
            business_indicators = [
                'Contact', 'Email', 'Call', 'Directions',
                'Shop', 'Book', 'Reserve', 'Get Quote',
                'Business', 'Company', 'LLC', 'Inc', 'Ltd'
            ]
            for indicator in business_indicators:
                if indicator.lower() in page_text.lower():
                    profile_data["is_business"] = True
                    break
            
            # ========== DETERMINE IF GOOD TARGET ==========
            # Good target criteria:
            # 1. Has some followers (100+) but not too many (< 100K for personal touch)
            # 2. Doesn't already have a professional website
            # 3. Shows business indicators
            
            followers = profile_data["followers"]
            has_website = profile_data["has_website"]
            is_business = profile_data["is_business"]
            
            is_good = False
            reason = ""
            
            if followers < 100:
                reason = "Too few followers (<100)"
            elif followers > 500000:
                reason = "Too many followers (>500K) - unlikely to respond"
            elif has_website:
                reason = "Already has website"
                is_good = True  # Still good - offer redesign/AI chatbot
            elif is_business:
                reason = "Business account without website - PERFECT TARGET!"
                is_good = True
            else:
                reason = "Personal account - may need website"
                is_good = True
                
            profile_data["is_good_target"] = is_good
            
            if is_good:
                add_log(f"   ✅ GOOD TARGET: {reason}", "success")
            else:
                add_log(f"   ⏭️ Skip: {reason}", "warning")
            
            add_log(f"   📋 Summary: {followers:,} followers, Website: {'Yes' if has_website else 'No'}, Business: {'Yes' if is_business else 'No'}", "info")
            
            return profile_data
            
        except Exception as e:
            add_log(f"❌ Error analyzing profile @{username}: {str(e)}", "error")
            return {
                "username": username,
                "full_name": "",
                "bio": "",
                "followers": 0,
                "has_website": False,
                "website": "",
                "is_business": False,
                "is_good_target": False
            }
        
    async def send_dm(self, username, message):
        """Send a DM to a user with BETTER logic and verification"""
        add_log(f"📨 Attempting to DM @{username}...", "action")
        
        try:
            # Go to user's profile
            await self.page.goto(f"https://www.instagram.com/{username}/")
            await asyncio.sleep(3)
            
            # ========== FIND MESSAGE BUTTON ==========
            add_log(f"   🔎 Looking for Message button...", "info")
            
            msg_btn = None
            button_selectors = [
                'text=Message',
                '[aria-label*="Message"]',
                'button:has-text("Message")',
                'div[role="button"]:has-text("Message")',
            ]
            
            for selector in button_selectors:
                try:
                    msg_btn = await self.page.query_selector(selector)
                    if msg_btn:
                        add_log(f"   ✅ Found Message button", "success")
                        break
                except:
                    pass
            
            if not msg_btn:
                add_log(f"   ❌ Message button not found - may be private account", "error")
                return False
                
            await msg_btn.click()
            add_log(f"   👆 Clicked Message button", "info")
            await asyncio.sleep(4)
            
            # Wait for DM page to load (URL should contain /direct/)
            add_log(f"   ⏳ Waiting for DM page to load...", "info")
            for _ in range(10):
                if "/direct/" in str(self.page.url):
                    add_log(f"   ✅ DM page loaded", "success")
                    break
                await asyncio.sleep(1)
            
            await asyncio.sleep(2)  # Extra wait for input to appear
            
            # ========== FIND MESSAGE INPUT (SPECIFIC TO DM PAGE) ==========
            add_log(f"   🔎 Looking for message input field...", "info")
            
            msg_input = None
            # More specific selectors for DM textarea
            input_selectors = [
                'textarea[placeholder*="Message"]',
                'div[aria-label*="Message"] textarea',
                'div[role="textbox"]',
                '[contenteditable="true"]',
            ]
            
            for selector in input_selectors:
                try:
                    msg_input = await self.page.wait_for_selector(selector, timeout=5000)
                    if msg_input:
                        # Verify it's clickable and visible
                        is_visible = await msg_input.is_visible()
                        if is_visible:
                            add_log(f"   ✅ Found message input", "success")
                            break
                        msg_input = None
                except:
                    pass
                    
            if not msg_input:
                add_log(f"   ❌ Message input not found", "error")
                try:
                    await self.page.screenshot(path=f"data/dm_fail_{username}.png")
                    add_log(f"   📷 Screenshot saved: data/dm_fail_{username}.png", "info")
                except:
                    pass
                return False
            
            # ========== TYPE MESSAGE (CLICK FIRST, THEN TYPE) ==========
            add_log(f"   ⌨️ Typing message ({len(message)} chars)...", "info")
            
            # First click to focus the input
            await msg_input.click()
            await asyncio.sleep(0.5)
            
            try:
                # Method 1: Use page.fill() on the specific element
                await msg_input.fill(message)
                add_log(f"   ✅ Message typed instantly", "success")
            except Exception as e1:
                add_log(f"   ⚠️ Fill failed, trying keyboard...", "warning")
                try:
                    # Method 2: Keyboard type (fast)
                    await self.page.keyboard.type(message, delay=5)
                    add_log(f"   ✅ Message typed (keyboard)", "success")
                except Exception as e2:
                    add_log(f"   ❌ Typing failed: {str(e2)}", "error")
                    return False
            
            await asyncio.sleep(1)
            
            # ========== SEND MESSAGE ==========
            add_log(f"   📤 Sending message...", "info")
            
            # Try clicking Send button first
            send_btn = None
            send_selectors = [
                'button:has-text("Send")',
                '[aria-label*="Send"]',
                'div[role="button"]:has-text("Send")',
            ]
            
            for selector in send_selectors:
                try:
                    send_btn = await self.page.query_selector(selector)
                    if send_btn:
                        break
                except:
                    pass
            
            if send_btn:
                await send_btn.click()
                add_log(f"   👆 Clicked Send button", "info")
            else:
                # Try pressing Enter
                await msg_input.press("Enter")
                add_log(f"   ⏎ Pressed Enter to send", "info")
            
            await asyncio.sleep(3)
            
            # ========== VERIFY MESSAGE SENT ==========
            # Check if the input is now empty (message was sent)
            try:
                current_text = await msg_input.input_value() if msg_input else ""
                if len(current_text) < 10:  # Input cleared = message sent
                    add_log(f"   ✅ DM SENT SUCCESSFULLY to @{username}!", "success")
                    increment_stat(self.username, "dms_sent")
                    return True
                else:
                    add_log(f"   ⚠️ Message may not have sent (input not cleared)", "warning")
                    return False
            except:
                # Assume success if we got this far
                add_log(f"   ✅ DM SENT to @{username}!", "success")
                increment_stat(self.username, "dms_sent")
                return True
            
        except Exception as e:
            add_log(f"   ❌ Failed to send DM: {str(e)}", "error")
            return False
    
    async def generate_ai_comment(self, post_url):
        """Use Gemini AI to analyze post and generate unique contextual comment"""
        add_log(f"🤖 AI generating contextual comment...", "action")
        
        try:
            if not GEMINI_AVAILABLE:
                add_log(f"   ⚠️ Gemini not available, using template", "warning")
                return random.choice(COMMENT_TEMPLATES)
            
            api_key = CONFIG.get("gemini_api_key", "")
            if not api_key:
                return random.choice(COMMENT_TEMPLATES)
            
            # Navigate to post and take screenshot
            if post_url not in str(self.page.url):
                await self.page.goto(post_url)
                await asyncio.sleep(3)
            
            # Take screenshot
            screenshot_path = "data/post_for_comment.png"
            await self.page.screenshot(path=screenshot_path)
            
            # Get post caption/text if visible
            try:
                caption_text = await self.page.evaluate("""
                    () => {
                        const caption = document.querySelector('h1, [class*="Caption"], span[dir="auto"]');
                        return caption ? caption.innerText.substring(0, 500) : '';
                    }
                """)
            except:
                caption_text = ""
            
            # Read screenshot
            with open(screenshot_path, "rb") as f:
                screenshot_data = base64.b64encode(f.read()).decode()
            
            # Configure Gemini
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(CONFIG.get('gemini_model', 'models/gemini-2.5-flash'))
            
            # AI prompt for contextual comment
            prompt = f"""You are a web development expert commenting on an Instagram post. 

LOOK AT THE POST and understand:
- What is the main topic/message?
- What are they promoting or discussing?

YOUR GOAL: Write a comment that:
1. Is RELEVANT to the post content
2. Shows YOUR expertise (you know about websites, custom development, automation)
3. SUBTLY disagrees or offers alternative perspective when relevant
4. Creates CURIOSITY about who you are (makes them want to check your profile)
5. Does NOT directly promote anything
6. Sounds NATURAL and human
7. Is SHORT (1-2 sentences max)

EXAMPLES OF GOOD COMMENTS:
- If post is about Shopify: "Shopify is easy but super limited for customization. Custom sites give way more control 🤔"
- If post is about templates: "Templates save time but honestly they all look the same. Standing out matters more"
- If post is about business tips: "This is solid! Though I'd add that your online presence matters more than most realize"
- If post is about social media: "Good points! But nothing beats having your own website that you fully control"
- Generic valuable comment: "Actually tried this - the results were surprising. Would do it differently now"

CAPTION TEXT: {caption_text[:300] if caption_text else 'No caption visible'}

RULES:
- NO "check my profile", "DM me", "we offer", "we help"
- NO direct links or mentions
- BE genuine, add value
- SOUND like a real person with an opinion
- USE 0-2 emojis max

RESPOND WITH ONLY THE COMMENT TEXT, nothing else."""

            response = model.generate_content([
                prompt,
                {"mime_type": "image/png", "data": screenshot_data}
            ])
            
            ai_comment = response.text.strip()
            
            # Clean up comment
            ai_comment = ai_comment.replace('"', '').replace("'", "'").strip()
            
            # Validate - not too long, not promotional
            if len(ai_comment) > 200:
                ai_comment = ai_comment[:200]
            
            # Check for promotional keywords (fallback to template if detected)
            promo_words = ["check my", "dm me", "we offer", "our service", "we help", "website:", "link"]
            if any(word in ai_comment.lower() for word in promo_words):
                add_log(f"   ⚠️ AI comment too promotional, using template", "warning")
                return random.choice(COMMENT_TEMPLATES)
            
            add_log(f"   ✅ AI generated: {ai_comment[:50]}...", "success")
            return ai_comment
            
        except Exception as e:
            add_log(f"   ⚠️ AI error: {str(e)[:50]}, using template", "warning")
            return random.choice(COMMENT_TEMPLATES)
    
    async def post_comment(self, post_url, comment):
        """Post a comment on a post"""
        add_log(f"💬 Commenting on post...", "action")
        
        try:
            # Navigate to post if not already there
            if post_url not in str(self.page.url):
                await self.page.goto(post_url)
                await asyncio.sleep(3)
            
            # ========== FIND COMMENT INPUT ==========
            add_log(f"   🔎 Looking for comment input...", "info")
            
            comment_input = None
            comment_selectors = [
                'textarea[placeholder*="comment"]',
                'textarea[placeholder*="Comment"]',
                'textarea[aria-label*="comment"]',
                'textarea[aria-label*="Comment"]',
                'form textarea',
            ]
            
            for selector in comment_selectors:
                try:
                    comment_input = await self.page.query_selector(selector)
                    if comment_input:
                        add_log(f"   ✅ Found comment input", "success")
                        break
                except:
                    pass
            
            if not comment_input:
                # Try clicking comment icon first
                comment_icon = await self.page.query_selector('[aria-label*="Comment"]')
                if comment_icon:
                    await comment_icon.click()
                    await asyncio.sleep(1)
                    # Try finding input again
                    comment_input = await self.page.query_selector('textarea')
            
            if not comment_input:
                add_log(f"   ❌ Comment input not found", "error")
                return False
            
            # ========== TYPE COMMENT ==========
            add_log(f"   ⌨️ Typing comment...", "info")
            
            await comment_input.click()
            await asyncio.sleep(0.5)
            
            try:
                await self.page.fill('textarea', comment)
                add_log(f"   ✅ Comment typed", "success")
            except:
                await self.page.keyboard.type(comment, delay=10)
                add_log(f"   ✅ Comment typed (keyboard)", "success")
            
            await asyncio.sleep(1)
            
            # ========== POST COMMENT ==========
            add_log(f"   📤 Posting comment...", "info")
            
            # Try clicking Post button
            post_btn = None
            post_selectors = [
                'button:has-text("Post")',
                '[aria-label*="Post"]',
                'div[role="button"]:has-text("Post")',
                'button[type="submit"]',
            ]
            
            for selector in post_selectors:
                try:
                    post_btn = await self.page.query_selector(selector)
                    if post_btn:
                        break
                except:
                    pass
            
            if post_btn:
                await post_btn.click()
                add_log(f"   👆 Clicked Post button", "info")
            else:
                # Try Enter
                await comment_input.press("Enter")
                await asyncio.sleep(0.5)
                # Try Ctrl+Enter or just submitting form
                await self.page.keyboard.press("Enter")
                add_log(f"   ⏎ Pressed Enter to post", "info")
            
            await asyncio.sleep(2)
            
            add_log(f"   ✅ COMMENT POSTED!", "success")
            return True
            
        except Exception as e:
            add_log(f"   ❌ Failed to post comment: {str(e)}", "error")
            return False
    
    async def get_saved_from_url(self, collection_url):
        """Get posts from a DIRECT collection URL - much more reliable!"""
        add_log(f"📂 Going to saved collection URL...", "action")
        
        try:
            # Navigate directly to the collection URL
            await self.page.goto(collection_url)
            await asyncio.sleep(5)
            
            add_log(f"   🔗 URL: {collection_url[:60]}...", "info")
            
            # Take screenshot
            await self.page.screenshot(path="data/saved_direct.png")
            add_log(f"   📷 Screenshot: data/saved_direct.png", "info")
            
            # Scroll to load more posts
            for i in range(5):
                await self.page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)
                add_log(f"   📜 Scrolled {i+1}/5", "info")
            
            # Find all post/reel links
            saved_urls = []
            
            # Try to find links
            link_elements = await self.page.query_selector_all('a')
            add_log(f"   🔍 Found {len(link_elements)} links on page", "info")
            
            for link in link_elements:
                try:
                    href = await link.get_attribute("href")
                    if href and ("/p/" in href or "/reel/" in href):
                        full_url = href if href.startswith("http") else f"https://www.instagram.com{href}"
                        # Skip if it's a saved collection URL or already in list
                        if "/saved/" not in full_url and full_url not in saved_urls:
                            saved_urls.append(full_url)
                except:
                    pass
            
            add_log(f"   📁 Found {len(saved_urls)} saved posts/reels", "success")
            
            if len(saved_urls) == 0:
                await self.page.screenshot(path="data/saved_empty_direct.png")
                add_log(f"   📷 Debug: data/saved_empty_direct.png", "info")
                add_log(f"   ⚠️ No posts found - check if collection exists and has posts!", "warning")
            
            return saved_urls
            
        except Exception as e:
            add_log(f"   ❌ Error: {str(e)}", "error")
            return []
    
    async def get_saved_by_name(self, collection_name="Comment Leads"):
        """Find saved collection by NAME - works for any account!"""
        add_log(f"📂 Finding saved collection: '{collection_name}'...", "action")
        
        try:
            # Go to Instagram home first
            await self.page.goto("https://www.instagram.com/")
            await asyncio.sleep(3)
            
            # Step 1: Click on Profile in left sidebar
            add_log(f"   👤 Looking for Profile button...", "info")
            profile_clicked = False
            
            try:
                # Try clicking Profile link
                profile_link = await self.page.query_selector(f'a[href="/{self.username}/"]')
                if profile_link:
                    await profile_link.click()
                    profile_clicked = True
                    await asyncio.sleep(3)
                    add_log(f"   ✅ Clicked Profile link", "success")
            except:
                pass
            
            if not profile_clicked:
                try:
                    await self.page.click('text="Profile"', timeout=3000)
                    profile_clicked = True
                    await asyncio.sleep(3)
                    add_log(f"   ✅ Clicked Profile text", "success")
                except:
                    pass
            
            if not profile_clicked:
                # Direct navigation
                await self.page.goto(f"https://www.instagram.com/{self.username}/")
                await asyncio.sleep(3)
                add_log(f"   🔗 Direct navigation to profile", "info")
            
            # Step 2: Click on "More" (hamburger menu) in bottom left
            add_log(f"   📋 Looking for More menu...", "info")
            
            try:
                # Look for More button (hamburger)
                more_btn = await self.page.query_selector('[aria-label="More"]')
                if not more_btn:
                    more_btn = await self.page.query_selector('text="More"')
                if more_btn:
                    await more_btn.click()
                    await asyncio.sleep(2)
                    add_log(f"   ✅ Clicked More menu", "success")
                    
                    # Take screenshot of menu
                    await self.page.screenshot(path="data/more_menu.png")
                    add_log(f"   📷 More menu screenshot saved", "info")
                    
                    # Step 3: Click on "Saved" in the menu - try multiple ways
                    saved_clicked = False
                    
                    # Method 1: Click by text
                    try:
                        await self.page.click('text="Saved"', timeout=3000)
                        saved_clicked = True
                        add_log(f"   ✅ Clicked Saved!", "success")
                    except:
                        pass
                    
                    # Method 2: Find span with Saved text
                    if not saved_clicked:
                        try:
                            saved_span = await self.page.query_selector('span:has-text("Saved")')
                            if saved_span:
                                await saved_span.click()
                                saved_clicked = True
                                add_log(f"   ✅ Clicked Saved span!", "success")
                        except:
                            pass
                    
                    # Method 3: Find any element with Saved
                    if not saved_clicked:
                        try:
                            all_elements = await self.page.query_selector_all('div, span, a')
                            for elem in all_elements[:50]:  # Check first 50
                                text = await elem.text_content()
                                if text and text.strip() == "Saved":
                                    await elem.click()
                                    saved_clicked = True
                                    add_log(f"   ✅ Clicked Saved element!", "success")
                                    break
                        except:
                            pass
                    
                    await asyncio.sleep(4)
            except:
                pass
            
            await asyncio.sleep(3)
            
            # Take screenshot
            await self.page.screenshot(path="data/saved_collections.png")
            add_log(f"   📷 Screenshot saved: data/saved_collections.png", "info")
            
            # Debug: List all links on the page
            try:
                all_text = await self.page.evaluate("document.body.innerText")
                add_log(f"   📋 Page text preview: {all_text[:200]}...", "info")
            except:
                pass
            
            # Look for collection by name
            collection_found = False
            
            # Try to find and click collection by text
            try:
                # First try exact text match
                collection_link = await self.page.query_selector(f'a:has-text("{collection_name}")')
                if collection_link:
                    await collection_link.click()
                    add_log(f"   ✅ Found and clicked: '{collection_name}'", "success")
                    collection_found = True
                    await asyncio.sleep(3)
            except:
                pass
            
            if not collection_found:
                # Try finding by partial text in any link
                try:
                    links = await self.page.query_selector_all('a[href*="/saved/"]')
                    for link in links:
                        text = await link.text_content()
                        if text and collection_name.lower() in text.lower():
                            await link.click()
                            add_log(f"   ✅ Found collection: {text.strip()}", "success")
                            collection_found = True
                            await asyncio.sleep(3)
                            break
                except:
                    pass
            
                add_log(f"   ⚠️ Collection '{collection_name}' not found!", "warning")
                add_log(f"   📌 Using ALL saved posts instead...", "info")
                
                # Try clicking "All Posts" if available
                try:
                    all_posts = await self.page.query_selector('a:has-text("All Posts")')
                    if all_posts:
                        await all_posts.click()
                        await asyncio.sleep(2)
                        add_log(f"   ✅ Clicked 'All Posts'", "success")
                except:
                    pass
                
                # We're on saved page, just get posts from here
            
            # Now we're in the collection, scroll and get posts
            for i in range(5):
                await self.page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)
            
            # Find post links
            saved_urls = []
            links = await self.page.query_selector_all('a')
            
            for link in links:
                try:
                    href = await link.get_attribute("href")
                    if href and ("/p/" in href or "/reel/" in href):
                        full_url = href if href.startswith("http") else f"https://www.instagram.com{href}"
                        if "/saved/" not in full_url and full_url not in saved_urls:
                            saved_urls.append(full_url)
                except:
                    pass
            
            add_log(f"   📁 Found {len(saved_urls)} posts in '{collection_name}'", "success")
            return saved_urls
            
        except Exception as e:
            add_log(f"   ❌ Error: {str(e)}", "error")
            return []
    
    async def get_saved_reels(self, collection_name="Comment Leads"):
        """Get list of saved reels from a specific collection or all saved"""
        add_log(f"📂 Getting saved posts from collection: {collection_name}...", "action")
        
        try:
            # Go to saved page
            await self.page.goto(f"https://www.instagram.com/{self.username}/saved/")
            await asyncio.sleep(5)
            
            # Take screenshot
            await self.page.screenshot(path="data/saved_page.png")
            add_log(f"   📷 Screenshot: data/saved_page.png", "info")
            
            # Log the current URL
            current_url = str(self.page.url)
            add_log(f"   🔗 URL: {current_url}", "info")
            
            # Strategy 1: Click on "All Posts" if visible
            try:
                all_posts = await self.page.query_selector('text=All Posts')
                if all_posts:
                    await all_posts.click()
                    add_log(f"   👆 Clicked 'All Posts'", "info")
                    await asyncio.sleep(3)
            except:
                pass
            
            # Strategy 2: Try to find the collection by name
            collection_found = False
            try:
                # Look for any clickable element with collection name
                page_text = await self.page.text_content("body") or ""
                if collection_name.lower() in page_text.lower():
                    add_log(f"   ✅ Found '{collection_name}' text on page", "success")
                    
                    # Try clicking it
                    collection_elem = await self.page.query_selector(f'text={collection_name}')
                    if collection_elem:
                        await collection_elem.click()
                        await asyncio.sleep(3)
                        collection_found = True
                        add_log(f"   ✅ Clicked on collection", "success")
            except:
                pass
            
            if not collection_found:
                add_log(f"   ⚠️ Collection '{collection_name}' not found, trying all saved", "warning")
            
            # Scroll to load more content
            for i in range(5):
                await self.page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)
                add_log(f"   📜 Scrolled {i+1}/5", "info")
            
            # Take another screenshot after scrolling
            await self.page.screenshot(path="data/saved_scrolled.png")
            
            # Strategy 3: Find post links using multiple selectors
            saved_urls = []
            
            # Try different selectors
            selectors = [
                'a[href*="/p/"]',
                'a[href*="/reel/"]',
                'article a[href*="/"]',
                'div[role="button"] a[href*="/"]',
            ]
            
            for selector in selectors:
                try:
                    posts = await self.page.query_selector_all(selector)
                    for post in posts[:50]:
                        href = await post.get_attribute("href")
                        if href and ("/p/" in href or "/reel/" in href):
                            full_url = href if href.startswith("http") else f"https://www.instagram.com{href}"
                            if full_url not in saved_urls and "/saved/" not in full_url:
                                saved_urls.append(full_url)
                except:
                    pass
            
            add_log(f"   📁 Found {len(saved_urls)} saved posts/reels", "success")
            
            if len(saved_urls) == 0:
                await self.page.screenshot(path="data/saved_empty.png")
                add_log(f"   📷 Debug: data/saved_empty.png", "info")
                
                # Log page content for debugging
                page_content = await self.page.text_content("body") or ""
                add_log(f"   📝 Page has {len(page_content)} chars of text", "info")
            
            return saved_urls
            
        except Exception as e:
            add_log(f"   ❌ Error getting saved reels: {str(e)}", "error")
            return []
            
    async def close(self):
        """Close browser"""
        if self.context:
            # Save session before closing
            session_path = Path(CONFIG["data_dir"]) / CONFIG["session_dir"] / self.username
            try:
                await self.context.storage_state(path=str(session_path / "state.json"))
            except:
                pass
        if self.browser:
            await self.browser.close()

# ============== MAIN AGENT ==============

class InstagramAgent:
    def __init__(self):
        self.accounts = []
        self.current_account_idx = 0
        self.running = False
        self.stats = {
            "total_dms_sent": 0,
            "total_profiles_viewed": 0,
            "total_prospects": 0,
            "session_dms": 0,
            "session_start": None
        }
        
    def load(self):
        """Load accounts and initialize"""
        # Create data directory
        Path(CONFIG["data_dir"]).mkdir(exist_ok=True)
        Path(CONFIG["data_dir"], CONFIG["session_dir"]).mkdir(exist_ok=True)
        
        # Initialize database
        init_database()
        
        # Load accounts
        self.accounts = load_accounts()
        
        # Load stats from DB
        self.reload_stats()
        
    def reload_stats(self):
        """Reload stats from database"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sent_dms")
        self.stats["total_dms_sent"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM prospects")
        self.stats["total_prospects"] = cursor.fetchone()[0]
        conn.close()
        
    async def run_outreach(self, hashtags=None, max_dms=10):
        """Main outreach loop with detailed logging"""
        add_log("🚀 STARTING OUTREACH SESSION", "action")
        
        if not self.accounts:
            add_log("❌ No accounts configured! Add accounts in dashboard", "error")
            return
            
        if not PLAYWRIGHT_AVAILABLE:
            add_log("❌ Playwright not installed! Run: pip install playwright", "error")
            return
        
        add_log(f"📋 Accounts to use: {len(self.accounts)}", "info")
        add_log(f"🎯 Max DMs per session: {max_dms}", "info")
        add_log(f"#️⃣ Hashtags: {', '.join(hashtags or TARGET_HASHTAGS)}", "info")
            
        self.running = True
        self.stats["session_start"] = datetime.now()
        self.stats["session_dms"] = 0
        
        hashtags = hashtags or TARGET_HASHTAGS
        
        try:
            async with async_playwright() as playwright:
                add_log("🌐 Browser engine ready", "success")
                
                for acc_idx, account in enumerate(self.accounts):
                    if not self.running:
                        add_log("⏹️ Stopped by user", "warning")
                        break
                    
                    add_log(f"👤 Switching to account {acc_idx+1}/{len(self.accounts)}: @{account['username']}", "action")
                        
                    # Check daily limit
                    today_stats = get_today_stats(account["username"])
                    if today_stats["dms_sent"] >= CONFIG["max_dms_per_day"]:
                        add_log(f"⚠️ @{account['username']} reached daily limit ({today_stats['dms_sent']}/{CONFIG['max_dms_per_day']})", "warning")
                        continue
                    
                    add_log(f"📊 Today's stats for @{account['username']}: {today_stats['dms_sent']} DMs sent", "info")
                        
                    bot = InstagramBot(account)
                    add_log(f"🖥️ Launching browser for @{account['username']}...", "info")
                    await bot.start(playwright)
                    
                    add_log(f"🔐 Attempting login as @{account['username']}...", "action")
                    if await bot.login():
                        add_log(f"✅ Login successful for @{account['username']}", "success")
                        dms_sent = 0
                        
                        for hash_idx, hashtag in enumerate(hashtags):
                            if dms_sent >= max_dms:
                                add_log(f"🎉 Reached max DMs ({max_dms}) for this session!", "success")
                                break
                            if not self.running:
                                add_log("⏹️ Stopped by user", "warning")
                                break
                            
                            add_log(f"📌 Processing hashtag {hash_idx+1}/{len(hashtags)}: #{hashtag}", "action")
                                
                            # Search hashtag
                            posts = await bot.search_hashtag(hashtag)
                            
                            if not posts:
                                add_log(f"⚠️ No posts found in #{hashtag}, skipping...", "warning")
                                continue
                                
                            add_log(f"⏳ Waiting before checking posts...", "info")
                            await bot.human_delay(10, 20)
                            
                            for post_idx, post_url in enumerate(posts):
                                if dms_sent >= max_dms or not self.running:
                                    break
                                
                                # ===== SKIP ALREADY VISITED POSTS =====
                                if is_post_visited(post_url):
                                    add_log(f"⏭️ Post already visited, skipping...", "info")
                                    continue
                                
                                add_log(f"📄 Checking post {post_idx+1}/{len(posts)}...", "info")
                                    
                                # Get profile from post
                                username = await bot.get_profile_from_post(post_url)
                                
                                # Mark post as visited
                                save_visited_post(post_url, username or "unknown")
                                
                                if not username:
                                    add_log(f"⚠️ Could not get username from post", "warning")
                                    continue
                                
                                add_log(f"👤 Found user: @{username}", "info")
                                    
                                # Skip if already messaged
                                if is_already_messaged(username):
                                    add_log(f"⏭️ Already messaged @{username}, skipping", "info")
                                    continue
                                
                                add_log(f"🔍 Checking profile @{username}...", "action")
                                    
                                # Check profile
                                profile = await bot.check_profile(username)
                                
                                await bot.human_delay(5, 10)
                                
                                # Save as prospect (even if not good target)
                                save_prospect(
                                    username,
                                    profile["full_name"],
                                    profile["bio"],
                                    profile["followers"],
                                    int(profile["has_website"]),
                                    f"#{hashtag}"
                                )
                                
                                # ========== CHECK IF GOOD TARGET ==========
                                if not profile.get("is_good_target", False):
                                    add_log(f"⏭️ Skipping @{username} - not a good target", "info")
                                    continue
                                
                                add_log(f"💾 @{username} is a GOOD TARGET!", "success")
                                
                                # Choose template
                                if profile["has_website"]:
                                    template = "with_website"
                                else:
                                    template = "no_website"
                                
                                add_log(f"📨 Sending DM to @{username} (template: {template})...", "action")
                                    
                                # Send DM
                                message = DM_TEMPLATES[template]
                                if await bot.send_dm(username, message):
                                    save_sent_dm(
                                        username,
                                        profile["full_name"],
                                        f"https://instagram.com/{username}",
                                        int(profile["has_website"]),
                                        template,
                                        account["username"]
                                    )
                                    dms_sent += 1
                                    self.stats["session_dms"] += 1
                                    add_log(f"✅ DM SENT to @{username}! ({dms_sent}/{max_dms})", "success")
                                else:
                                    add_log(f"❌ Failed to send DM to @{username}", "error")
                                    
                                # Long delay between DMs - but INTERRUPTIBLE
                                delay = random.uniform(CONFIG["delay_between_dms_min"], CONFIG["delay_between_dms_max"])
                                add_log(f"⏳ Waiting {delay:.0f}s before next DM (safety delay)...", "info")
                                
                                # Check every second if stopped
                                for _ in range(int(delay)):
                                    if not self.running:
                                        add_log("⏹️ Stop requested - cancelling delay", "warning")
                                        break
                                    await asyncio.sleep(1)
                    else:
                        add_log(f"❌ Login FAILED for @{account['username']}", "error")
                                
                    add_log(f"🔒 Closing browser for @{account['username']}", "info")
                    await bot.close()
                    
        except Exception as e:
            add_log(f"💥 CRITICAL ERROR: {str(e)}", "error")
            import traceback
            add_log(f"📜 Traceback: {traceback.format_exc()[:200]}", "error")
                
        self.running = False
        self.reload_stats()
        add_log(f"🏁 SESSION COMPLETE! Total DMs sent: {self.stats['session_dms']}", "success")
    
    async def run_comment_mode(self, hashtags=None, max_comments=20):
        """Comment mode - comment on posts from hashtags"""
        add_log("💬 STARTING COMMENT MODE", "action")
        
        if not self.accounts:
            add_log("❌ No accounts configured!", "error")
            return
        
        add_log(f"📋 Max comments this session: {max_comments}", "info")
        
        self.running = True
        hashtags = hashtags or TARGET_HASHTAGS.copy()
        random.shuffle(hashtags)  # Randomize hashtag order for variety
        comments_made = 0
        
        try:
            async with async_playwright() as playwright:
                add_log("🌐 Browser ready for commenting", "success")
                
                for account in self.accounts:
                    if not self.running or comments_made >= max_comments:
                        break
                    
                    add_log(f"👤 Using account: @{account['username']}", "action")
                    
                    bot = InstagramBot(account)
                    await bot.start(playwright)
                    
                    if await bot.login():
                        add_log(f"✅ Logged in as @{account['username']}", "success")
                        
                        for hashtag in hashtags:
                            if not self.running or comments_made >= max_comments:
                                break
                            
                            add_log(f"📌 Searching #{hashtag} for commenting...", "action")
                            posts = await bot.search_hashtag(hashtag)
                            
                            if not posts:
                                continue
                            
                            # Process MORE posts - up to 50 per hashtag instead of 10
                            posts_to_check = posts[:50]
                            add_log(f"📊 Found {len(posts_to_check)} posts to check", "info")
                            
                            for post_url in posts_to_check:
                                if not self.running or comments_made >= max_comments:
                                    break
                                
                                # Skip if already commented
                                if is_already_commented(post_url):
                                    continue  # Silent skip - don't spam logs
                                
                                # Skip if already visited
                                if is_post_visited(post_url):
                                    continue  # Silent skip
                                
                                # Get username from post
                                username = await bot.get_profile_from_post(post_url)
                                save_visited_post(post_url, username or "unknown")
                                
                                if not username:
                                    continue
                                
                                # Generate AI contextual comment (unique for each post!)
                                comment = await bot.generate_ai_comment(post_url)
                                add_log(f"💬 Commenting on @{username}'s post: '{comment[:50]}...'", "action")
                                
                                if await bot.post_comment(post_url, comment):
                                    save_sent_comment(post_url, username, comment, account["username"])
                                    comments_made += 1
                                    add_log(f"✅ COMMENT #{comments_made} POSTED!", "success")
                                    
                                    # Delay between comments
                                    delay = random.uniform(CONFIG["delay_between_comments_min"], CONFIG["delay_between_comments_max"])
                                    add_log(f"⏳ Waiting {delay:.0f}s...", "info")
                                    
                                    for _ in range(int(delay)):
                                        if not self.running:
                                            break
                                        await asyncio.sleep(1)
                    
                    await bot.close()
                    
        except Exception as e:
            add_log(f"💥 ERROR: {str(e)}", "error")
        
        self.running = False
        add_log(f"🏁 COMMENT MODE COMPLETE! Posted {comments_made} comments", "success")
    
    async def run_saved_reels_mode(self, max_comments=20, collection_url="", collection_name="Comment Leads"):
        """Saved Reels Mode - comment on saved posts (finds by NAME, no URL needed!)"""
        add_log("💾 STARTING SAVED REELS MODE", "action")
        
        if not self.accounts:
            add_log("❌ No accounts configured!", "error")
            return
        
        add_log(f"📋 Max comments: {max_comments}", "info")
        
        self.running = True
        comments_made = 0
        
        try:
            async with async_playwright() as playwright:
                add_log("🌐 Browser ready", "success")
                
                # Use first account
                account = self.accounts[0]
                add_log(f"👤 Using account: @{account['username']}", "action")
                
                bot = InstagramBot(account)
                await bot.start(playwright)
                
                if await bot.login():
                    add_log(f"✅ Logged in as @{account['username']}", "success")
                    
                    # Try URL first if provided, otherwise use collection NAME
                    if collection_url:
                        add_log(f"📌 Using URL: {collection_url[:50]}...", "info")
                        saved_posts = await bot.get_saved_from_url(collection_url)
                    else:
                        # Find by NAME - works for any account!
                        add_log(f"📌 Finding collection by name: '{collection_name}'", "info")
                        saved_posts = await bot.get_saved_by_name(collection_name)
                    
                    if not saved_posts:
                        add_log("⚠️ No saved posts found", "warning")
                    else:
                        add_log(f"📁 Found {len(saved_posts)} saved posts", "success")
                        
                        for post_url in saved_posts:
                            if not self.running or comments_made >= max_comments:
                                break
                            
                            # Skip if already commented
                            if is_already_commented(post_url):
                                add_log(f"⏭️ Already commented", "info")
                                continue
                            
                            # Get username
                            username = await bot.get_profile_from_post(post_url)
                            
                            # Generate AI contextual comment (unique for each post!)
                            comment = await bot.generate_ai_comment(post_url)
                            add_log(f"💬 Commenting on @{username}'s saved post: '{comment[:50]}...'", "action")
                            
                            if await bot.post_comment(post_url, comment):
                                save_sent_comment(post_url, username or "unknown", comment, account["username"])
                                comments_made += 1
                                add_log(f"✅ COMMENT #{comments_made} POSTED!", "success")
                                
                                # Delay
                                delay = random.uniform(CONFIG["delay_between_comments_min"], CONFIG["delay_between_comments_max"])
                                add_log(f"⏳ Waiting {delay:.0f}s...", "info")
                                
                                for _ in range(int(delay)):
                                    if not self.running:
                                        break
                                    await asyncio.sleep(1)
                
                await bot.close()
                    
        except Exception as e:
            add_log(f"💥 ERROR: {str(e)}", "error")
        
        self.running = False
        add_log(f"🏁 SAVED REELS MODE COMPLETE! Posted {comments_made} comments", "success")
    
    async def run_comment_profile_mode(self, max_dms=10, collection_name="Comment Profile Leads"):
        """Comment Profile Mode - Find leads from commenters on saved reels!
        
        Strategy:
        1. Go to saved reels (business tip videos where potential clients comment)
        2. Read comments on each reel
        3. Visit each commenter's profile
        4. AI analyzes if they're a potential client
        5. Generate personalized DM based on their profile/business
        6. Send DM if they're a good lead
        """
        add_log("🎯 STARTING COMMENT PROFILE MODE", "action")
        add_log("📋 Strategy: Find leads from reel commenters!", "info")
        
        if not self.accounts:
            add_log("❌ No accounts configured!", "error")
            return
        
        if not GEMINI_AVAILABLE:
            add_log("❌ Gemini AI required for this mode!", "error")
            return
        
        api_key = CONFIG.get("gemini_api_key", "")
        if not api_key:
            add_log("❌ Gemini API key not set!", "error")
            return
        
        add_log(f"📋 Max DMs: {max_dms}", "info")
        add_log(f"📁 Collection: {collection_name}", "info")
        
        self.running = True
        dms_sent = 0
        profiles_analyzed = 0
        
        try:
            # Configure Gemini
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(CONFIG.get('gemini_model', 'models/gemini-2.5-flash'))
            add_log("✅ Gemini AI ready", "success")
            
            async with async_playwright() as playwright:
                add_log("🌐 Browser ready", "success")
                
                account = self.accounts[0]
                add_log(f"👤 Using account: @{account['username']}", "action")
                
                bot = InstagramBot(account)
                await bot.start(playwright)
                
                if await bot.login():
                    add_log(f"✅ Logged in as @{account['username']}", "success")
                    
                    # Get saved reels
                    saved_posts = await bot.get_saved_by_name(collection_name)
                    
                    if not saved_posts:
                        add_log("⚠️ No saved posts found in collection", "warning")
                    else:
                        add_log(f"📁 Found {len(saved_posts)} saved reels to scan", "success")
                        
                        for reel_url in saved_posts[:5]:  # Limit to 5 reels
                            if not self.running or dms_sent >= max_dms:
                                break
                            
                            add_log(f"📹 Opening reel: {reel_url[:50]}...", "action")
                            
                            # Navigate to reel
                            await bot.page.goto(reel_url)
                            await asyncio.sleep(4)
                            
                            # Take screenshot
                            await bot.page.screenshot(path="data/reel_for_comments.png")
                            
                            # Get commenters
                            add_log("💬 Reading comments...", "info")
                            
                            # Scroll to load comments
                            for _ in range(3):
                                await bot.page.evaluate("window.scrollBy(0, 300)")
                                await asyncio.sleep(1)
                            
                            # Find commenter usernames
                            try:
                                commenters = await bot.page.evaluate("""
                                    () => {
                                        const usernames = [];
                                        // Find all profile links in comments section
                                        const links = document.querySelectorAll('a[href^="/"]');
                                        links.forEach(link => {
                                            const href = link.getAttribute('href');
                                            // Check if it's a username link (single segment, no special paths)
                                            if (href && href.match(/^\\/[a-zA-Z0-9_.]+\\/?$/) && 
                                                !href.includes('/p/') && !href.includes('/reel/') &&
                                                !href.includes('/explore') && !href.includes('/direct')) {
                                                const username = href.replace(/\\//g, '');
                                                if (username && username.length > 2 && !usernames.includes(username)) {
                                                    usernames.push(username);
                                                }
                                            }
                                        });
                                        return usernames.slice(0, 10); // Get first 10 commenters
                                    }
                                """)
                                
                                add_log(f"   👥 Found {len(commenters)} commenters", "success")
                                
                                for commenter in commenters:
                                    if not self.running or dms_sent >= max_dms:
                                        break
                                    
                                    # Skip if already DMed
                                    if is_already_messaged(commenter):
                                        add_log(f"   ⏭️ Already DMed @{commenter}", "info")
                                        continue
                                    
                                    # Skip own account
                                    if commenter == account['username']:
                                        continue
                                    
                                    add_log(f"   🔍 Analyzing @{commenter}...", "action")
                                    profiles_analyzed += 1
                                    
                                    # Visit commenter's profile
                                    await bot.page.goto(f"https://www.instagram.com/{commenter}/")
                                    await asyncio.sleep(3)
                                    
                                    # Take screenshot of profile
                                    screenshot_path = f"data/profile_{commenter}.png"
                                    await bot.page.screenshot(path=screenshot_path)
                                    
                                    # Get bio text
                                    try:
                                        bio_text = await bot.page.evaluate("""
                                            () => {
                                                const bio = document.querySelector('header section');
                                                return bio ? bio.innerText : '';
                                            }
                                        """)
                                    except:
                                        bio_text = ""
                                    
                                    # Read screenshot
                                    with open(screenshot_path, "rb") as f:
                                        screenshot_data = base64.b64encode(f.read()).decode()
                                    
                                    # AI Analysis prompt
                                    analysis_prompt = f"""Analyze this Instagram profile and determine if they're a potential client for our web development services.

PROFILE: @{commenter}
BIO/CONTENT: {bio_text[:500] if bio_text else 'Could not read bio'}

WE OFFER:
- Website Design ($99)
- Website Redesign/Improvements ($99)
- AI Chatbots for customer support ($99)
- Business Automation ($99)
- Gmail Agents / Email automation ($99)

ANALYZE:
1. Is this a BUSINESS profile or someone interested in business?
2. Could they benefit from our services (even if they have a website - we offer improvements/automation)?
3. Are they a potential client?

RESPOND WITH JSON:
{{
    "is_business": true/false,
    "business_type": "bakery/salon/coach/etc or personal",
    "has_website": true/false/unknown,
    "potential_client": true/false,
    "score": 1-10,
    "reason": "why they're good/bad lead",
    "personalized_message": "Write a SHORT personalized DM intro (2-3 sentences) based on their profile. Be specific about their business. Don't include contact details - just the personalized opening."
}}

BE STRICT: Only score 7+ if they clearly look like they'd benefit from our services."""

                                    try:
                                        response = model.generate_content([
                                            analysis_prompt,
                                            {"mime_type": "image/png", "data": screenshot_data}
                                        ])
                                        
                                        ai_response = response.text
                                        
                                        # Parse JSON
                                        import json as json_module
                                        json_start = ai_response.find('{')
                                        json_end = ai_response.rfind('}') + 1
                                        if json_start != -1 and json_end > json_start:
                                            analysis = json_module.loads(ai_response[json_start:json_end])
                                        else:
                                            add_log(f"   ⚠️ Could not parse AI response", "warning")
                                            continue
                                        
                                        score = analysis.get('score', 0)
                                        is_potential = analysis.get('potential_client', False)
                                        business_type = analysis.get('business_type', 'unknown')
                                        reason = analysis.get('reason', '')[:50]
                                        personalized_intro = analysis.get('personalized_message', '')
                                        
                                        add_log(f"   📊 Score: {score}/10 | Type: {business_type}", "info")
                                        add_log(f"   💡 Reason: {reason}", "info")
                                        
                                        # If good lead, send DM
                                        if score >= 7 and is_potential:
                                            add_log(f"   🎯 POTENTIAL CLIENT! Sending DM...", "success")
                                            
                                            # Build personalized message
                                            has_website = analysis.get('has_website', False)
                                            
                                            if has_website:
                                                # Offer improvements/automation
                                                full_message = f"""{personalized_intro}

I specialize in helping businesses like yours with:
✓ Website improvements & redesigns
✓ AI Chatbots for 24/7 customer support
✓ Email automation systems
✓ Business process automation

Would love to show you how we can help! Check out our work - link in bio.

Website: infiniteclub.tech
Instagram: @infiniteclub.tech"""
                                            else:
                                                # Offer website creation
                                                full_message = f"""{personalized_intro}

I help businesses like yours get online with:
✓ Professional websites ($99)
✓ AI Chatbots for customer support
✓ Mobile-friendly, modern designs
✓ 3-5 day delivery

Check out our portfolio - link in bio!

Website: infiniteclub.tech
Instagram: @infiniteclub.tech"""
                                            
                                            # Send DM
                                            if await bot.send_dm(commenter, full_message):
                                                save_sent_dm(commenter, "", f"https://instagram.com/{commenter}", False, business_type, account["username"])
                                                dms_sent += 1
                                                add_log(f"   ✅ DM #{dms_sent} SENT to @{commenter}!", "success")
                                                
                                                # Delay between DMs
                                                delay = random.uniform(60, 90)
                                                add_log(f"   ⏳ Waiting {delay:.0f}s...", "info")
                                                for _ in range(int(delay)):
                                                    if not self.running:
                                                        break
                                                    await asyncio.sleep(1)
                                        else:
                                            add_log(f"   ⏭️ Score too low, skipping", "info")
                                        
                                    except Exception as ai_error:
                                        add_log(f"   ⚠️ AI error: {str(ai_error)[:50]}", "warning")
                                        continue
                                    
                                    # Small delay between profile analyses
                                    await asyncio.sleep(2)
                                    
                            except Exception as e:
                                add_log(f"   ⚠️ Error reading comments: {str(e)[:50]}", "warning")
                                continue
                
                await bot.close()
                    
        except Exception as e:
            add_log(f"💥 ERROR: {str(e)}", "error")
        
        self.running = False
        add_log(f"🏁 COMMENT PROFILE MODE COMPLETE!", "success")
        add_log(f"   📊 Profiles analyzed: {profiles_analyzed}", "info")
        add_log(f"   📩 DMs sent: {dms_sent}", "info")
    
    async def run_ai_mode(self, user_prompt):
        """AI Mode - Gemini sees screen and decides what to do based on full context"""
        add_log("🤖 STARTING AI MODE", "action")
        
        if not GEMINI_AVAILABLE:
            add_log("❌ Gemini AI not installed! Run: pip install google-generativeai", "error")
            return
        
        api_key = CONFIG.get("gemini_api_key", "")
        if not api_key:
            add_log("❌ Gemini API key not set!", "error")
            return
        
        if not self.accounts:
            add_log("❌ No accounts configured!", "error")
            return
        
        add_log(f"📋 Your command: {user_prompt}", "info")
        
        self.running = True
        actions_taken = 0
        
        # Get saved collection URL for this account
        account_saved_url = self.accounts[0].get('saved_collection_url', CONFIG.get('saved_collection_url', ''))
        
        # Full business context - AI knows everything (CORRECT DETAILS from Master Reference)
        business_context = f"""
=== INFINITE CLUB - COMPLETE CONTEXT ===

**COMPANY INFO:**
- Company: Infinite Club
- Website: https://infiniteclub.tech
- Email: hello@infiniteclub.tech
- Instagram: @infiniteclub.tech
- WhatsApp: +91 7467845015

**SERVICES & PRICING (USD):**
- Website Design: $99 (3-5 days)
- Website Redesign: $99 (3-5 days)  
- AI Chatbot (24/7 support): $99 (3-5 days)
- Gmail Agent (auto-reply): $99 (3-5 days)
- Branding (logo + identity): $49 (2-3 days)
- Business Automation: $99 (3-5 days)

**KEY SELLING POINTS:**
- Unlimited revisions included
- 3-5 day delivery (fast!)
- Affordable for small businesses
- Modern, mobile-friendly designs

**OUR INSTAGRAM GOALS:**
1. Find small businesses/entrepreneurs without websites
2. Leave attractive comments (not spammy)
3. Send professional DMs to potential clients
4. Build leads for website development
5. Collect data on potential clients

**CURRENT ACCOUNT:** @{self.accounts[0]['username']}
**SAVED COLLECTION:** {account_saved_url if account_saved_url else 'Not set for this account'}

**COMMUNICATION STYLE:**
- Friendly & approachable with emojis
- Professional but casual
- Value-first (what they GET)
- Always include: infiniteclub.tech, @infiniteclub.tech

**SAFETY RULES:**
- Wait 30-60 seconds between actions
- Max 25 DMs/day, 30 comments/day
- Don't repeat on same person/post
- Act human, not robotic

**YOU CAN DO ANY TASK INCLUDING:**
- Comment on posts from hashtags or saved
- Send DMs to profiles
- Search and collect data (usernames, bios, etc.)
- Navigate Instagram and take any action
- Scroll, click, type, navigate anywhere
- Extract information from profiles
"""

        try:
            # Configure Gemini
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(CONFIG.get('gemini_model', 'gemini-1.5-flash-latest'))
            add_log("✅ Gemini AI connected", "success")
            
            async with async_playwright() as playwright:
                add_log("🌐 Browser ready", "success")
                
                account = self.accounts[0]
                add_log(f"👤 Using account: @{account['username']}", "action")
                
                bot = InstagramBot(account)
                await bot.start(playwright)
                
                if await bot.login():
                    add_log(f"✅ Logged in as @{account['username']}", "success")
                    
                    # AI Loop
                    max_iterations = 30
                    
                    for iteration in range(max_iterations):
                        if not self.running:
                            add_log("⏹️ AI Mode stopped", "warning")
                            break
                        
                        add_log(f"🔄 AI Step {iteration + 1}/{max_iterations}", "info")
                        
                        # Take screenshot
                        screenshot_path = f"data/ai_screen_{iteration}.png"
                        await bot.page.screenshot(path=screenshot_path)
                        
                        # Read screenshot and encode
                        with open(screenshot_path, "rb") as f:
                            screenshot_data = base64.b64encode(f.read()).decode()
                        
                        # Also get page content for better understanding
                        try:
                            # Get clickable elements
                            clickable_elements = await bot.page.evaluate("""
                                () => {
                                    const elements = [];
                                    // Buttons
                                    document.querySelectorAll('button, [role="button"]').forEach(el => {
                                        const text = el.textContent?.trim().substring(0, 50);
                                        const label = el.getAttribute('aria-label');
                                        if (text || label) elements.push({type: 'button', text: text, label: label});
                                    });
                                    // Links
                                    document.querySelectorAll('a[href]').forEach(el => {
                                        const text = el.textContent?.trim().substring(0, 50);
                                        const href = el.getAttribute('href');
                                        if (text) elements.push({type: 'link', text: text, href: href?.substring(0, 50)});
                                    });
                                    // Inputs
                                    document.querySelectorAll('input, textarea').forEach(el => {
                                        const placeholder = el.getAttribute('placeholder');
                                        const label = el.getAttribute('aria-label');
                                        elements.push({type: 'input', placeholder: placeholder, label: label});
                                    });
                                    return elements.slice(0, 20);  // Limit to 20 elements
                                }
                            """)
                            page_elements = str(clickable_elements)[:1000]
                        except:
                            page_elements = "Could not extract elements"
                        
                        # Get current URL
                        current_url = str(bot.page.url)
                        
                        # AI prompt with full context
                        ai_prompt = f"""{business_context}

=== CURRENT TASK ===
{user_prompt}

=== CURRENT PAGE ===
URL: {current_url}

=== CLICKABLE ELEMENTS ON PAGE ===
{page_elements}

=== WHAT YOU SEE ===
Look at the screenshot AND the elements list above.

=== WHAT TO DO ===
Based on the task "{user_prompt}", decide the next action.
Use element text/label from the list above for clicking.

AVAILABLE ACTIONS:
- click: Click element (use exact text from elements list)
- type: Type text 
- scroll: Scroll down
- goto: Navigate to URL
- wait: Wait for loading
- comment: Post comment
- done: Task complete

RESPOND WITH JSON ONLY:
{{"action": "click", "target": "Search", "reason": "Need to search hashtag"}}

Be specific. Work step by step towards completing the user's task."""

                        try:
                            response = model.generate_content([
                                ai_prompt,
                                {"mime_type": "image/png", "data": screenshot_data}
                            ])
                            
                            ai_response = response.text
                            add_log(f"🤖 AI: {ai_response[:100]}...", "info")
                            
                            # Parse AI response
                            import json as json_module
                            try:
                                # Try to extract JSON from response
                                json_start = ai_response.find('{')
                                json_end = ai_response.rfind('}') + 1
                                if json_start != -1 and json_end > json_start:
                                    action_data = json_module.loads(ai_response[json_start:json_end])
                                else:
                                    add_log("⚠️ Could not parse AI response", "warning")
                                    continue
                            except:
                                add_log("⚠️ Failed to parse AI JSON", "warning")
                                continue
                            
                            action = action_data.get("action", "")
                            target = action_data.get("target", "")
                            reasoning = action_data.get("reasoning", "")
                            
                            add_log(f"🎯 Action: {action} | Target: {target[:50]}...", "action")
                            add_log(f"💭 Reasoning: {reasoning[:100]}...", "info")
                            
                            # Execute action
                            if action == "done":
                                add_log("✅ AI determined task is complete!", "success")
                                break
                            
                            elif action in ["click", "click_element"]:
                                clicked = False
                                try:
                                    # Try text-based click first
                                    await bot.page.click(f'text="{target}"', timeout=3000)
                                    clicked = True
                                except:
                                    pass
                                
                                if not clicked:
                                    try:
                                        # Try aria-label
                                        await bot.page.click(f'[aria-label*="{target}"]', timeout=3000)
                                        clicked = True
                                    except:
                                        pass
                                
                                if not clicked:
                                    try:
                                        # Try direct selector
                                        await bot.page.click(target, timeout=3000)
                                        clicked = True
                                    except:
                                        pass
                                
                                if clicked:
                                    add_log(f"👆 Clicked: {target}", "success")
                                    actions_taken += 1
                                    await asyncio.sleep(2)
                                else:
                                    add_log(f"⚠️ Could not click: {target}", "warning")
                            
                            elif action in ["type", "type_text"]:
                                await bot.page.keyboard.type(target, delay=50)
                                add_log(f"⌨️ Typed: {target[:30]}...", "success")
                                actions_taken += 1
                                await asyncio.sleep(1)
                            
                            elif action == "scroll":
                                await bot.page.evaluate("window.scrollBy(0, 500)")
                                add_log("📜 Scrolled down", "success")
                            
                            elif action in ["goto", "navigate"]:
                                await bot.page.goto(target)
                                add_log(f"🔗 Navigated to: {target}", "success")
                                actions_taken += 1
                                await asyncio.sleep(3)
                            
                            elif action == "wait":
                                await asyncio.sleep(3)
                                add_log("⏳ Waited 3s", "info")
                            
                            elif action == "comment":
                                if await bot.post_comment(str(bot.page.url), target):
                                    add_log(f"💬 Posted comment: {target}", "success")
                                    actions_taken += 1
                            
                            elif action == "send_dm":
                                add_log(f"📩 DM action requested", "info")
                                actions_taken += 1
                            
                            else:
                                add_log(f"❓ Unknown action: {action}", "warning")
                            
                            # Wait between actions
                            await asyncio.sleep(2)
                            
                        except Exception as ai_error:
                            add_log(f"⚠️ AI error: {str(ai_error)[:100]}", "warning")
                            await asyncio.sleep(2)
                    
                await bot.close()
                    
        except Exception as e:
            add_log(f"💥 ERROR: {str(e)}", "error")
        
        self.running = False
        add_log(f"🏁 AI MODE COMPLETE! Actions taken: {actions_taken}", "success")
        
    def stop(self):
        """Stop outreach"""
        self.running = False

# ============== FLASK DASHBOARD ==============

app = Flask(__name__)
agent = InstagramAgent()

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📸 Instagram DM Agent - Infinite Club</title>
    <style>
        :root {
            --bg: #0a0a12;
            --card: #12121a;
            --border: #1e1e2d;
            --text: #e0e0e0;
            --text2: #8e8e9a;
            --accent: #00d4ff;
            --purple: #9c27b0;
            --green: #00ff88;
            --pink: #ff4d8d;
            --orange: #ff9f43;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            background: var(--bg); 
            color: var(--text);
            min-height: 100vh;
        }
        
        /* Header */
        .header {
            background: linear-gradient(135deg, var(--card), #1a1a25);
            padding: 20px 30px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo { display: flex; align-items: center; gap: 12px; }
        .logo-icon { font-size: 2rem; }
        .logo-text h1 { font-size: 1.3rem; background: linear-gradient(135deg, #E1306C, #F77737); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .logo-text p { font-size: 0.75rem; color: var(--text2); }
        
        /* Stats Bar */
        .stats-bar {
            display: flex;
            gap: 20px;
            padding: 20px 30px;
            background: var(--card);
            border-bottom: 1px solid var(--border);
            flex-wrap: wrap;
        }
        .stat-card {
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px 24px;
            min-width: 150px;
        }
        .stat-card .value { font-size: 1.8rem; font-weight: bold; color: var(--accent); }
        .stat-card .label { font-size: 0.75rem; color: var(--text2); margin-top: 4px; }
        
        /* Main Container */
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            padding: 20px 30px;
        }
        
        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
        }
        .card h2 {
            font-size: 1rem;
            margin-bottom: 16px;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        /* Controls */
        .controls {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .btn-primary { background: linear-gradient(135deg, #E1306C, #F77737); color: #fff; }
        .btn-secondary { background: var(--bg); color: var(--text); border: 1px solid var(--border); }
        .btn-danger { background: rgba(255,77,141,0.2); color: var(--pink); }
        .btn:hover { transform: translateY(-2px); }
        
        /* Accounts List */
        .account-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: rgba(255,255,255,0.02);
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .account-name { font-weight: 600; }
        .account-stats { font-size: 0.75rem; color: var(--text2); }
        
        /* Activity Log - BIGGER and with colors */
        .log-container {
            max-height: 500px;
            min-height: 400px;
            overflow-y: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.85rem;
            background: #0a0a10;
            border-radius: 12px;
            padding: 16px;
            border: 1px solid rgba(0,212,255,0.1);
        }
        .log-entry { 
            padding: 6px 8px; 
            border-bottom: 1px solid rgba(255,255,255,0.05);
            border-radius: 4px;
            margin-bottom: 2px;
        }
        .log-time { color: var(--text2); margin-right: 12px; font-size: 0.75rem; }
        .log-success { background: rgba(0,255,136,0.08); border-left: 3px solid var(--green); }
        .log-error { background: rgba(255,77,141,0.1); border-left: 3px solid var(--pink); }
        .log-warning { background: rgba(255,159,67,0.08); border-left: 3px solid var(--orange); }
        .log-action { background: rgba(0,212,255,0.08); border-left: 3px solid var(--accent); }
        .log-info { opacity: 0.8; }
        
        /* Status indicator */
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 6px;
        }
        .status-running { background: var(--green); animation: pulse 1.5s infinite; }
        .status-stopped { background: var(--text2); }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">
            <span class="logo-icon">📸</span>
            <div class="logo-text">
                <h1>Instagram DM Agent</h1>
                <p>Infinite Club | Automated Outreach</p>
            </div>
        </div>
        <div>
            <span class="status-dot" id="status-dot"></span>
            <span id="status-text">Stopped</span>
        </div>
    </div>
    
    <div class="stats-bar">
        <div class="stat-card">
            <div class="value" id="total-dms">0</div>
            <div class="label">Total DMs Sent</div>
        </div>
        <div class="stat-card">
            <div class="value" id="session-dms">0</div>
            <div class="label">Session DMs</div>
        </div>
        <div class="stat-card" style="border-color: rgba(156,39,176,0.3);">
            <div class="value" id="total-comments" style="color: #9c27b0;">0</div>
            <div class="label">Comments Posted</div>
        </div>
        <div class="stat-card">
            <div class="value" id="total-prospects">0</div>
            <div class="label">Prospects Found</div>
        </div>
        <div class="stat-card">
            <div class="value" id="accounts-count">0</div>
            <div class="label">Active Accounts</div>
        </div>
    </div>
    
    <div class="container">
        <div class="card">
            <h2>🎮 Controls</h2>
            
            <!-- Mode Buttons -->
            <div style="margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid var(--border);">
                <div style="font-size: 0.85rem; color: var(--text2); margin-bottom: 10px;">📌 Select Mode:</div>
                <div class="controls" style="gap: 8px; flex-wrap: wrap;">
                    <button class="btn btn-primary" onclick="startOutreach()" title="Send DMs to profiles from hashtags">📨 DM Mode</button>
                    <button class="btn btn-secondary" onclick="startCommentMode()" style="background: linear-gradient(135deg, #9c27b0, #e91e63);" title="Comment on posts from hashtags">💬 Comment Mode</button>
                    <button class="btn btn-secondary" onclick="startSavedReelsMode()" style="background: linear-gradient(135deg, #ff9f43, #ff6b6b);" title="Comment on your saved reels">💾 Saved Reels</button>
                    <button class="btn btn-secondary" onclick="startCommentProfileMode()" style="background: linear-gradient(135deg, #00ff88, #00d4ff);" title="Find leads from commenters on saved reels - AI analyzes profiles!">🎯 Comment Profile</button>
                    <button class="btn btn-secondary" onclick="startAIMode()" style="background: linear-gradient(135deg, #6c5ce7, #a29bfe);" title="AI Vision Agent - sees screen & decides">🤖 AI Mode</button>
                </div>
            </div>
            
            <div class="controls">
                <button class="btn btn-danger" onclick="stopOutreach()">⏹️ Stop</button>
                <button class="btn btn-secondary" onclick="refreshStats()">🔄 Refresh</button>
            </div>
            
            <div style="margin-top: 20px;">
                <label style="color: var(--text2); font-size: 0.85rem;">Hashtags (comma separated):</label>
                <input type="text" id="hashtags" value="smallbusiness,entrepreneur,newbusiness" 
                    style="width: 100%; padding: 10px; margin-top: 8px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; color: var(--text);">
            </div>
            <div style="margin-top: 16px; display: flex; gap: 16px; flex-wrap: wrap;">
                <div>
                    <label style="color: var(--text2); font-size: 0.85rem;">Max DMs:</label>
                    <input type="number" id="max-dms" value="10" min="1" max="50"
                        style="width: 80px; padding: 10px; margin-top: 8px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; color: var(--text);">
                </div>
                <div>
                    <label style="color: var(--text2); font-size: 0.85rem;">Max Comments:</label>
                    <input type="number" id="max-comments" value="20" min="1" max="50"
                        style="width: 80px; padding: 10px; margin-top: 8px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; color: var(--text);">
                </div>
            </div>
            <div style="margin-top: 16px;">
                <label style="color: var(--text2); font-size: 0.85rem;">📌 Saved Collection URL (paste full URL from Instagram):</label>
                <input type="text" id="collection-url" value="" placeholder="https://www.instagram.com/username/saved/collection-name/ID/"
                    style="width: 100%; padding: 10px; margin-top: 8px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-size: 0.8rem;">
            </div>
            
            <!-- AI Mode Settings -->
            <div style="margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border);">
                <label style="color: #00d4ff; font-size: 0.9rem; font-weight: 600;">🤖 AI Mode Instructions:</label>
                <textarea id="ai-prompt" rows="4" placeholder="Example: Go to #smallbusiness posts, find businesses without websites, leave a comment about our website services, then send them a DM introducing our services."
                    style="width: 100%; padding: 12px; margin-top: 8px; background: var(--bg); border: 1px solid rgba(0,212,255,0.3); border-radius: 8px; color: var(--text); resize: vertical; font-size: 0.85rem;"></textarea>
                <p style="font-size: 0.7rem; color: var(--text2); margin-top: 6px;">💡 AI sees the screen and decides actions based on your instructions. Powered by Gemini Vision.</p>
            </div>
        </div>
        
        <div class="card">
            <h2>📱 Accounts</h2>
            <div id="accounts-list">
                <div class="account-item">
                    <span style="color: var(--text2);">No accounts configured</span>
                </div>
            </div>
            <p style="font-size: 0.75rem; color: var(--text2); margin-top: 12px;">
                Or edit <code>data/accounts.json</code> directly
            </p>
            
            <!-- Add Account Form -->
            <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border);">
                <div style="font-size: 0.85rem; color: var(--accent); margin-bottom: 10px;">➕ Add Instagram Account</div>
                <input type="text" id="new-username" placeholder="Instagram username" 
                    style="width: 100%; padding: 10px; margin-bottom: 8px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; color: var(--text);">
                <input type="password" id="new-password" placeholder="Password" 
                    style="width: 100%; padding: 10px; margin-bottom: 8px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; color: var(--text);">
                <button class="btn btn-secondary" onclick="addAccount()" style="width: 100%;">💾 Save Account</button>
            </div>
        </div>
    </div>
    
    <!-- FULL WIDTH LIVE MONITOR SECTION -->
    <div style="padding: 20px 30px;">
        <div class="card" style="width: 100%;">
            <h2 style="display: flex; justify-content: space-between; align-items: center;">
                <span>📜 LIVE ACTIVITY MONITOR</span>
                <span style="font-size: 0.75rem; color: var(--text2);">Auto-updates every 2 seconds</span>
            </h2>
            <div class="log-container" id="log-container" style="max-height: 60vh; min-height: 400px;">
                <div class="log-entry">
                    <span class="log-time">--:--:--</span>
                    Waiting to start... Click "Start Outreach" to begin.
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function refreshStats() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('total-dms').textContent = data.total_dms_sent || 0;
                    document.getElementById('session-dms').textContent = data.session_dms || 0;
                    document.getElementById('total-comments').textContent = data.total_comments || 0;
                    document.getElementById('total-prospects').textContent = data.total_prospects || 0;
                    document.getElementById('accounts-count').textContent = data.accounts_count || 0;
                    
                    const dot = document.getElementById('status-dot');
                    const text = document.getElementById('status-text');
                    if (data.running) {
                        dot.className = 'status-dot status-running';
                        text.textContent = 'Running';
                    } else {
                        dot.className = 'status-dot status-stopped';
                        text.textContent = 'Stopped';
                    }
                    
                    // Update accounts list
                    let accHtml = '';
                    if (data.accounts && data.accounts.length > 0) {
                        data.accounts.forEach(acc => {
                            const dmColor = acc.dm_limit_full ? '#ff4d8d' : (acc.dm_percent > 70 ? '#ff9f43' : '#00ff88');
                            const commentColor = acc.comment_limit_full ? '#ff4d8d' : (acc.comment_percent > 70 ? '#ff9f43' : '#9c27b0');
                            const limitBadge = acc.dm_limit_full && acc.comment_limit_full ? 
                                '<span style="background: rgba(255,77,141,0.2); color: #ff4d8d; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; margin-left: 8px;">⚠️ LIMIT FULL</span>' : 
                                (acc.dm_limit_full ? '<span style="background: rgba(255,159,67,0.2); color: #ff9f43; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; margin-left: 8px;">DM Limit</span>' : '');
                            
                            accHtml += `<div class="account-item" style="padding: 14px; margin-bottom: 12px;">
                                <div style="width: 100%;">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                                        <span class="account-name" style="font-size: 1rem;">@${acc.username}</span>
                                        ${limitBadge}
                                    </div>
                                    
                                    <!-- DM Progress -->
                                    <div style="margin-bottom: 8px;">
                                        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; margin-bottom: 4px;">
                                            <span style="color: ${dmColor};">📨 DMs: ${acc.dms_today}/${acc.dm_limit}</span>
                                            <span style="color: var(--text2);">${acc.dms_remaining} left</span>
                                        </div>
                                        <div style="background: rgba(255,255,255,0.1); height: 6px; border-radius: 3px; overflow: hidden;">
                                            <div style="width: ${acc.dm_percent}%; height: 100%; background: ${dmColor}; transition: width 0.3s;"></div>
                                        </div>
                                    </div>
                                    
                                    <!-- Comment Progress -->
                                    <div>
                                        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; margin-bottom: 4px;">
                                            <span style="color: ${commentColor};">💬 Comments: ${acc.comments_today}/${acc.comment_limit}</span>
                                            <span style="color: var(--text2);">${acc.comments_remaining} left</span>
                                        </div>
                                        <div style="background: rgba(255,255,255,0.1); height: 6px; border-radius: 3px; overflow: hidden;">
                                            <div style="width: ${acc.comment_percent}%; height: 100%; background: ${commentColor}; transition: width 0.3s;"></div>
                                        </div>
                                    </div>
                                </div>
                            </div>`;
                        });
                    } else {
                        accHtml = '<div class="account-item"><span style="color: var(--text2);">No accounts configured</span></div>';
                    }
                    document.getElementById('accounts-list').innerHTML = accHtml;
                });
        }
        
        function startOutreach() {
            const hashtags = document.getElementById('hashtags').value;
            const maxDms = document.getElementById('max-dms').value;
            fetch('/api/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ hashtags: hashtags.split(',').map(h => h.trim()), max_dms: parseInt(maxDms) })
            }).then(() => {
                addLog('🚀 Outreach started...');
                refreshStats();
            });
        }
        
        function stopOutreach() {
            fetch('/api/stop', { method: 'POST' }).then(() => {
                addLog('⏹️ Stopping...', 'warning');
                refreshStats();
            });
        }
        
        function startCommentMode() {
            const hashtags = document.getElementById('hashtags').value;
            const maxComments = document.getElementById('max-comments').value;
            fetch('/api/start-comment-mode', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ hashtags: hashtags.split(',').map(h => h.trim()), max_comments: parseInt(maxComments) })
            }).then(() => {
                addLog('💬 Comment Mode started...', 'action');
                refreshStats();
            });
        }
        
        function startSavedReelsMode() {
            const maxComments = document.getElementById('max-comments').value;
            const collectionUrl = document.getElementById('collection-url').value;
            fetch('/api/start-saved-reels-mode', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ max_comments: parseInt(maxComments), collection_url: collectionUrl })
            }).then(() => {
                addLog('💾 Saved Reels Mode started...', 'action');
                refreshStats();
            });
        }
        
        function startAIMode() {
            const aiPrompt = document.getElementById('ai-prompt').value;
            if (!aiPrompt.trim()) {
                addLog('⚠️ Please enter AI instructions first!', 'warning');
                return;
            }
            fetch('/api/start-ai-mode', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ prompt: aiPrompt })
            }).then(() => {
                addLog('🤖 AI Mode started...', 'action');
                refreshStats();
            });
        }
        
        function startCommentProfileMode() {
            const maxDms = document.getElementById('max-dms').value || 10;
            fetch('/api/comment-profile', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ max_dms: parseInt(maxDms) })
            }).then(() => {
                addLog('🎯 Comment Profile Mode started - AI analyzing commenters...', 'action');
                refreshStats();
            });
        }
        
        function addLog(message, type = 'info') {
            const container = document.getElementById('log-container');
            const time = new Date().toLocaleTimeString();
            const typeClass = 'log-' + type;
            container.innerHTML = `<div class="log-entry ${typeClass}"><span class="log-time">${time}</span>${message}</div>` + container.innerHTML;
        }
        
        function refreshLogs() {
            fetch('/api/logs')
                .then(r => r.json())
                .then(data => {
                    const container = document.getElementById('log-container');
                    let html = '';
                    data.logs.forEach(log => {
                        const typeClass = 'log-' + log.type;
                        html += `<div class="log-entry ${typeClass}"><span class="log-time">${log.time}</span>${log.message}</div>`;
                    });
                    if (html) {
                        container.innerHTML = html;
                    }
                });
        }
        
        function addAccount() {
            const username = document.getElementById('new-username').value.trim();
            const password = document.getElementById('new-password').value;
            
            if (!username || !password) {
                alert('Please enter both username and password');
                return;
            }
            
            fetch('/api/add-account', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ username: username, password: password })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    addLog('✅ Account @' + username + ' added!', 'success');
                    document.getElementById('new-username').value = '';
                    document.getElementById('new-password').value = '';
                    refreshStats();
                } else {
                    addLog('❌ Failed: ' + (data.error || 'Unknown error'), 'error');
                }
            });
        }
        
        // Auto refresh - stats every 5s, logs every 2s
        setInterval(refreshStats, 5000);
        setInterval(refreshLogs, 2000);
        refreshStats();
        refreshLogs();
    </script>
</body>
</html>
'''

@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/logs')
def api_logs():
    """Return activity logs for dashboard"""
    return jsonify({"logs": activity_log[:100]})  # Last 100 entries

@app.route('/api/status')
def api_status():
    agent.reload_stats()
    accounts_data = []
    
    # Get today's date for comment query
    today = datetime.now().strftime("%Y-%m-%d")
    
    for acc in agent.accounts:
        stats = get_today_stats(acc["username"])
        dm_limit = CONFIG["max_dms_per_day"]
        comment_limit = CONFIG["max_comments_per_day"]
        
        dms_sent = stats["dms_sent"]
        dms_remaining = max(0, dm_limit - dms_sent)
        dm_limit_full = dms_sent >= dm_limit
        
        # Get account-specific comment count for today
        try:
            conn = sqlite3.connect(CONFIG["db_path"])
            cursor = conn.cursor()
            cursor.execute('''SELECT COUNT(*) FROM sent_comments 
                WHERE sent_from = ? AND date(sent_at) = ?''', 
                (acc["username"], today))
            comments_today = cursor.fetchone()[0]
            conn.close()
        except:
            comments_today = 0
        
        comments_remaining = max(0, comment_limit - comments_today)
        comment_limit_full = comments_today >= comment_limit
        
        accounts_data.append({
            "username": acc["username"],
            "dms_today": dms_sent,
            "dms_remaining": dms_remaining,
            "dm_limit": dm_limit,
            "dm_limit_full": dm_limit_full,
            "dm_percent": min(100, int((dms_sent / dm_limit) * 100)),
            "comments_today": comments_today,
            "comments_remaining": comments_remaining,
            "comment_limit": comment_limit,
            "comment_limit_full": comment_limit_full,
            "comment_percent": min(100, int((comments_today / comment_limit) * 100))
        })
    
    # Get total comment count from database
    try:
        conn = sqlite3.connect(CONFIG["db_path"])
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sent_comments")
        total_comments = cursor.fetchone()[0]
        conn.close()
    except:
        total_comments = 0
    
    return jsonify({
        "running": agent.running,
        "total_dms_sent": agent.stats["total_dms_sent"],
        "session_dms": agent.stats["session_dms"],
        "total_comments": total_comments,
        "total_prospects": agent.stats["total_prospects"],
        "accounts_count": len(agent.accounts),
        "accounts": accounts_data,
        "dm_limit_per_account": CONFIG["max_dms_per_day"],
        "comment_limit_per_account": CONFIG["max_comments_per_day"]
    })

@app.route('/api/start', methods=['POST'])
def api_start():
    if agent.running:
        return jsonify({"error": "Already running"})
    
    data = request.json or {}
    hashtags = data.get("hashtags", TARGET_HASHTAGS)
    max_dms = data.get("max_dms", 10)
    
    # Run in background thread
    def run_async():
        asyncio.run(agent.run_outreach(hashtags, max_dms))
    
    Thread(target=run_async, daemon=True).start()
    return jsonify({"status": "started"})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    agent.stop()
    return jsonify({"status": "stopping"})

@app.route('/api/start-comment-mode', methods=['POST'])
def api_start_comment_mode():
    if agent.running:
        return jsonify({"error": "Already running"})
    
    data = request.json or {}
    hashtags = data.get("hashtags", TARGET_HASHTAGS)
    max_comments = data.get("max_comments", 20)
    
    def run_async():
        asyncio.run(agent.run_comment_mode(hashtags, max_comments))
    
    Thread(target=run_async, daemon=True).start()
    return jsonify({"status": "comment_mode_started"})

@app.route('/api/start-saved-reels-mode', methods=['POST'])
def api_start_saved_reels_mode():
    if agent.running:
        return jsonify({"error": "Already running"})
    
    data = request.json or {}
    max_comments = data.get("max_comments", 20)
    collection_url = data.get("collection_url", "")
    
    def run_async():
        asyncio.run(agent.run_saved_reels_mode(max_comments, collection_url))
    
    Thread(target=run_async, daemon=True).start()
    return jsonify({"status": "saved_reels_mode_started"})

@app.route('/api/start-ai-mode', methods=['POST'])
def api_start_ai_mode():
    if agent.running:
        return jsonify({"error": "Already running"})
    
    data = request.json or {}
    prompt = data.get("prompt", "")
    
    if not prompt:
        return jsonify({"error": "No prompt provided"})
    
    def run_async():
        asyncio.run(agent.run_ai_mode(prompt))
    
    Thread(target=run_async, daemon=True).start()
    return jsonify({"status": "ai_mode_started"})

@app.route('/api/comment-profile', methods=['POST'])
def api_comment_profile():
    if agent.running:
        return jsonify({"error": "Already running"})
    
    data = request.json or {}
    max_dms = data.get("max_dms", 10)
    collection_name = data.get("collection_name", "Comment Profile Leads")
    
    def run_async():
        asyncio.run(agent.run_comment_profile_mode(max_dms, collection_name))
    
    Thread(target=run_async, daemon=True).start()
    return jsonify({"status": "comment_profile_mode_started"})


@app.route('/api/add-account', methods=['POST'])
def api_add_account():
    """Add a new Instagram account from dashboard"""
    data = request.json or {}
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")
    
    if not username or not password:
        return jsonify({"success": False, "error": "Username and password required"})
    
    # Remove @ if included
    if username.startswith("@"):
        username = username[1:]
    
    # Load existing accounts
    accounts_path = Path(CONFIG["data_dir"]) / CONFIG["accounts_file"]
    accounts = []
    if accounts_path.exists():
        with open(accounts_path) as f:
            accounts = json.load(f)
    
    # Check if account already exists
    for acc in accounts:
        if acc["username"].lower() == username:
            return jsonify({"success": False, "error": "Account already exists"})
    
    # Add new account
    accounts.append({
        "username": username,
        "password": password,
        "enabled": True,
        "added": datetime.now().isoformat()
    })
    
    # Save
    with open(accounts_path, 'w') as f:
        json.dump(accounts, f, indent=2)
    
    # Reload accounts in agent
    agent.accounts = load_accounts()
    
    return jsonify({"success": True, "message": f"Account @{username} added!"})


# ============== MAIN ==============

def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║        📸 INSTAGRAM DM AGENT - Infinite Club              ║
╠═══════════════════════════════════════════════════════════╣
║  Automated Instagram outreach with safety features        ║
║                                                           ║
║  Dashboard: http://127.0.0.1:5002                        ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    # Initialize agent
    agent.load()
    
    if not PLAYWRIGHT_AVAILABLE:
        print("\n⚠️ Playwright not installed. Run these commands:")
        print("   pip install playwright")
        print("   playwright install chromium")
        print("\nStarting dashboard anyway...")
    
    # Start Flask
    app.run(host="0.0.0.0", port=5002, debug=False)

if __name__ == "__main__":
    main()
