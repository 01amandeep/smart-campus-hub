"""Auto-tagging of complaints.

Step 1 - rule based category detection (fast, free, deterministic).
Step 2 - priority from urgency keywords.
Step 3 - optional Amazon Comprehend sentiment: a strongly NEGATIVE
         complaint is escalated by one priority level.
If Comprehend is unavailable the function still works (graceful degradation).
"""
import re

CATEGORIES = {
    "Wi-Fi & Network": ["wifi", "wi-fi", "internet", "network", "router", "lan", "bandwidth", "slow net"],
    "Hostel": ["hostel", "warden", "dorm", "room", "bed", "mattress", "laundry"],
    "Lab & Equipment": ["lab", "computer", "system", "projector", "equipment", "printer", "software"],
    "Classroom & Infrastructure": ["classroom", "bench", "fan", "ac", "light", "board", "door", "window", "ceiling", "lift", "elevator"],
    "Canteen & Food": ["canteen", "food", "mess", "meal", "hygiene", "lunch", "breakfast", "dinner"],
    "Water & Sanitation": ["water", "toilet", "washroom", "restroom", "drinking", "leak", "drain", "cleaning", "garbage"],
    "Electricity": ["power", "electric", "current", "socket", "switch", "voltage", "short circuit", "power cut"],
    "Transport": ["bus", "transport", "route", "driver", "parking"],
    "Library": ["library", "book", "librarian", "reading room"],
    "Academics & Admin": ["exam", "timetable", "faculty", "attendance", "fee", "scholarship", "certificate", "marks"],
    "Safety & Security": ["harass", "ragging", "theft", "stolen", "security", "unsafe", "fight", "bully"],
}

HIGH_WORDS = ["fire", "shock", "short circuit", "harass", "ragging", "emergency", "danger", "injury",
              "injured", "unsafe", "no water", "sparking", "collapse", "snake", "theft", "stolen", "bully"]
LOW_WORDS = ["suggest", "suggestion", "request", "would be nice", "improve", "feedback", "kindly consider"]

LEVELS = ["LOW", "MEDIUM", "HIGH"]


def _has(text, word):
    """Whole-word match that tolerates simple suffixes (room -> rooms, harass -> harassment)."""
    return re.search(r"\b" + re.escape(word.strip()) + r"(s|es|ed|ing|ment)?\b", text) is not None


def _score(text, words):
    return sum(1 for w in words if _has(text, w))


def detect_category(text):
    text = text.lower()
    best, best_score = "Other", 0
    for cat, words in CATEGORIES.items():
        s = _score(text, words)
        if s > best_score:
            best, best_score = cat, s
    return best


def detect_priority(text):
    text = text.lower()
    if any(_has(text, w) for w in HIGH_WORDS):
        return "HIGH"
    if any(_has(text, w) for w in LOW_WORDS):
        return "LOW"
    return "MEDIUM"


def escalate(priority):
    return LEVELS[min(LEVELS.index(priority) + 1, len(LEVELS) - 1)]


def classify(text, comprehend=None):
    """Return dict(category, priority, sentiment)."""
    category = detect_category(text)
    priority = detect_priority(text)
    sentiment = "UNKNOWN"
    if comprehend is not None:
        try:
            res = comprehend.detect_sentiment(Text=text[:4500], LanguageCode="en")
            sentiment = res["Sentiment"]
            if sentiment == "NEGATIVE" and res["SentimentScore"]["Negative"] > 0.85:
                priority = escalate(priority)
        except Exception:  # noqa - never fail a complaint because AI tagging failed
            sentiment = "UNKNOWN"
    return {"category": category, "priority": priority, "sentiment": sentiment}
