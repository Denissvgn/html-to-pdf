"""Browser cookie extraction utilities, supporting Firefox (Native, Snap, Flatpak)."""

import os
import shutil
import sqlite3
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional


def find_firefox_profiles() -> List[Path]:
    """Find available Firefox profile directories across Snap, Native, and Flatpak installs."""
    home = Path.home()
    candidate_bases = [
        home / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
        home / ".mozilla" / "firefox",
        home / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",
    ]
    
    profiles = []
    for base in candidate_bases:
        if not base.is_dir():
            continue
        for item in base.iterdir():
            if item.is_dir() and (item / "cookies.sqlite").is_file():
                profiles.append(item)
    
    # Sort profiles by most recently modified cookies.sqlite
    profiles.sort(
        key=lambda p: (p / "cookies.sqlite").stat().st_mtime if (p / "cookies.sqlite").exists() else 0,
        reverse=True,
    )
    return profiles


def extract_firefox_cookies(url_or_domain: Optional[str] = None, profile_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Extract cookies from Firefox cookies.sqlite database for a specific URL/domain or all domains.
    Handles active Firefox locks by copying database files safely.
    Converts timestamps to seconds for Playwright.
    """
    profiles = [profile_dir] if profile_dir else find_firefox_profiles()
    if not profiles:
        return []

    target_profile = profiles[0]
    db_file = target_profile / "cookies.sqlite"
    wal_file = target_profile / "cookies.sqlite-wal"

    if not db_file.exists():
        return []

    # Copy to temporary location to avoid locks
    temp_dir = tempfile.mkdtemp(prefix="ff_cookies_")
    temp_db = os.path.join(temp_dir, "cookies.sqlite")
    temp_wal = os.path.join(temp_dir, "cookies.sqlite-wal")

    try:
        shutil.copy2(db_file, temp_db)
        if wal_file.exists():
            try:
                shutil.copy2(wal_file, temp_wal)
            except Exception:
                pass

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        domain_filter = None
        if url_or_domain:
            if "://" in url_or_domain:
                parsed = urllib.parse.urlparse(url_or_domain)
                hostname = parsed.hostname or ""
            else:
                hostname = url_or_domain
            # Extract root domain (e.g., example.com from app.example.com)
            parts = hostname.split(".")
            if len(parts) >= 2:
                domain_filter = "%" + ".".join(parts[-2:]) + "%"
            else:
                domain_filter = f"%{hostname}%"

        if domain_filter:
            cursor.execute(
                "SELECT host, name, value, path, isSecure, expiry FROM moz_cookies WHERE host LIKE ?",
                (domain_filter,)
            )
        else:
            cursor.execute("SELECT host, name, value, path, isSecure, expiry FROM moz_cookies")

        rows = cursor.fetchall()
        conn.close()

        playwright_cookies = []
        now = time.time()
        for host, name, value, path, is_secure, expiry in rows:
            cookie_dict = {
                "name": name,
                "value": value,
                "domain": host,
                "path": path or "/",
                "secure": bool(is_secure),
            }
            if expiry and expiry > 0:
                exp = float(expiry)
                # Firefox often stores expiry in milliseconds or microseconds
                if exp > 1e11:
                    exp = exp / 1000.0
                if exp > now:  # Only add non-expired cookies
                    cookie_dict["expires"] = exp
            playwright_cookies.append(cookie_dict)

        return playwright_cookies
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def extract_firefox_localstorage(url_or_domain: str, profile_dir: Optional[Path] = None) -> Dict[str, str]:
    """
    Extract localStorage items from Firefox storage/default for a specific URL or domain.
    Handles Snap, Native, and Flatpak installs, and gracefully copies files to avoid SQLite locks.
    """
    profiles = [profile_dir] if profile_dir else find_firefox_profiles()
    if not profiles:
        return {}

    target_profile = profiles[0]
    storage_base = target_profile / "storage" / "default"
    if not storage_base.is_dir():
        return {}

    if "://" in url_or_domain:
        parsed = urllib.parse.urlparse(url_or_domain)
        hostname = (parsed.hostname or "").lower()
    else:
        hostname = url_or_domain.lower()

    if not hostname:
        return {}

    parts = hostname.split(".")
    root_domain = ".".join(parts[-2:]) if len(parts) >= 2 else hostname

    matched_dirs = []
    for d in storage_base.iterdir():
        if not d.is_dir():
            continue
        d_name = d.name.lower()
        if hostname in d_name:
            matched_dirs.append((2, d))
        elif root_domain in d_name:
            matched_dirs.append((1, d))

    matched_dirs.sort(key=lambda x: x[0])

    results: Dict[str, str] = {}
    for _, d in matched_dirs:
        data_db = d / "ls" / "data.sqlite"
        if not data_db.is_file():
            continue

        temp_dir = tempfile.mkdtemp(prefix="ff_ls_")
        try:
            temp_db = Path(temp_dir) / "data.sqlite"
            shutil.copy2(data_db, temp_db)
            wal = data_db.with_name("data.sqlite-wal")
            if wal.is_file():
                try:
                    shutil.copy2(wal, Path(temp_dir) / "data.sqlite-wal")
                except Exception:
                    pass

            conn = sqlite3.connect(temp_db)
            conn.text_factory = bytes
            cursor = conn.cursor()
            for row in cursor.execute("SELECT key, value, conversion_type, compression_type FROM data"):
                k_b, val_b, conv_type, comp_type = row
                k = k_b.decode("utf-8", errors="ignore")
                if comp_type == 0:
                    if conv_type == 1:
                        val = val_b.decode("latin1", errors="ignore")
                    elif conv_type == 2:
                        val = val_b.decode("utf-16le", errors="ignore")
                    else:
                        val = val_b.decode("utf-8", errors="ignore")
                    results[k] = val
            conn.close()
        except Exception:
            pass
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return results

