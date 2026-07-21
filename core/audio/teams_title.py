"""Read Microsoft Teams window title via macOS Accessibility (System Events)."""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

TEAMS_PROCESS_NAMES = (
    "Microsoft Teams",
    "Microsoft Teams (work or school)",
    "MSTeams",
    "Teams",
)
TEAMS_SUFFIXES = (
    "Microsoft Teams",
    "Microsoft Teams (work or school)",
    "Teams",
)

# Navigation / shell window titles that are not real meeting names
GENERIC_TEAMS_UI_TITLES = frozenset(
    {
        "chat",
        "sohbet",
        "calendar",
        "takvim",
        "activity",
        "etkinlik",
        "arama",
        "calls",
        "call",
        "teams",
        "microsoft teams",
        "microsoft teams (work or school)",
        "msteams",
        "home",
        "ana sayfa",
        "files",
        "dosyalar",
        "apps",
        "uygulamalar",
        "meetings",
        "toplantılar",
        "toplantilar",
        "window",
        "untitled",
        "adsız",
        "adsiz",
    }
)


@dataclass
class TeamsTitleResult:
    raw_title: str
    title: str
    participants_hint: str | None
    source: str = "teams_window"


def is_generic_teams_title(title: str | None) -> bool:
    if not title:
        return True
    normalized = title.strip().lower()
    if not normalized:
        return True
    if normalized in GENERIC_TEAMS_UI_TITLES:
        return True
    # "Chat | Microsoft Teams" already stripped — also catch bare UI words
    if len(normalized) <= 2:
        return True
    return False


def parse_teams_window_title(raw: str) -> TeamsTitleResult | None:
    """Parse 'Haftalık Sync | Microsoft Teams' or 'Ahmet Yılmaz | Microsoft Teams'."""
    raw = raw.strip()
    if not raw:
        return None

    title_part = raw
    for suffix in TEAMS_SUFFIXES:
        for sep in (" | ", " - ", " — "):
            marker = f"{sep}{suffix}"
            if raw.endswith(marker):
                title_part = raw[: -len(marker)].strip()
                break
            if suffix.lower() in raw.lower() and "|" in raw:
                parts = [p.strip() for p in raw.split("|")]
                if parts and suffix.lower() not in parts[0].lower():
                    title_part = parts[0]
                    break

    if not title_part or title_part.lower() in {s.lower() for s in TEAMS_SUFFIXES}:
        return None
    if is_generic_teams_title(title_part):
        return None

    participants_hint = None
    if re.match(r"^[A-Za-zÀ-ÿĞğÜüŞşİıÖöÇç][\w\s.'-]{1,60}$", title_part) and " " not in title_part.strip():
        participants_hint = title_part
    elif "|" not in raw and len(title_part.split()) <= 4:
        participants_hint = title_part

    return TeamsTitleResult(
        raw_title=raw,
        title=title_part,
        participants_hint=participants_hint,
    )


def _read_via_osascript(process_name: str) -> str | None:
    # Do not set frontmost — steals focus and may switch to Chat/Calendar
    script = f'''
tell application "System Events"
    if not (exists process "{process_name}") then return ""
    tell process "{process_name}"
        if (count of windows) = 0 then return ""
        return name of front window
    end tell
end tell
'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            logger.debug("osascript failed for %s: %s", process_name, result.stderr.strip())
            return None
        title = result.stdout.strip()
        return title or None
    except Exception as e:
        logger.debug("Teams title read failed (%s): %s", process_name, e)
        return None


def read_teams_window_title() -> TeamsTitleResult | None:
    """Best-effort Teams window title; requires Accessibility permission."""
    for process_name in TEAMS_PROCESS_NAMES:
        raw = _read_via_osascript(process_name)
        if raw:
            parsed = parse_teams_window_title(raw)
            if parsed:
                logger.info("Teams window title: %s", parsed.title)
                return parsed
            logger.debug("Unparsed/generic Teams title: %s", raw)
    return None


def datetime_fallback_title(dt: datetime | None = None) -> TeamsTitleResult:
    dt = dt or datetime.now()
    label = f"Toplantı — {dt.strftime('%d.%m.%Y %H:%M')}"
    return TeamsTitleResult(
        raw_title=label,
        title=label,
        participants_hint=None,
        source="datetime",
    )


def check_accessibility_for_teams() -> dict:
    """Probe whether System Events can see Teams (Accessibility granted)."""
    raw = None
    for process_name in TEAMS_PROCESS_NAMES:
        raw = _read_via_osascript(process_name)
        if raw is not None:
            break
    if raw is None:
        return {
            "state": "denied",
            "message": "Erişilebilirlik izni gerekli — Teams pencere başlığı okunamıyor",
        }
    return {
        "state": "granted",
        "message": "Erişilebilirlik aktif" if raw else "Teams penceresi bulunamadı (uygulama kapalı olabilir)",
        "sample_title": raw or None,
    }
