"""
Central configuration for the trading-community Discord server.

Everything about the server's structure lives here so you can tweak names,
colours, roles, and channels without touching the build logic in
``setup_server.py``.

Hierarchy note: ROLES are listed from HIGHEST authority to LOWEST. The setup
script reproduces this exact order in the server's role list.
"""

# ---------------------------------------------------------------------------
# Tier role names — referenced by the bot at runtime, so keep them in sync
# with the ROLES list below.
# ---------------------------------------------------------------------------
ROLE_UNVERIFIED = "Unverified"
ROLE_MEMBER = "Member"            # free, verified access
ROLE_PREMIUM = "Premium"          # entry paid tier
ROLE_ELITE = "Elite"              # top paid tier
ROLE_LIFETIME = "Lifetime VIP"    # one-time / lifetime paid

# Self-assignable notification roles (the runtime bot posts a reaction menu).
NOTIFY_ROLES = [
    ("Crypto Pings", "🪙"),
    ("Forex Pings", "💱"),
    ("Stocks Pings", "📈"),
    ("Options Pings", "🎯"),
    ("News Pings", "📰"),
    ("Events Pings", "📅"),
]

# ---------------------------------------------------------------------------
# ROLES
# color: hex int.  hoist: show separately in member list.  perms: discord
# permission flag names (see discord.Permissions). Empty = no extra perms.
# ---------------------------------------------------------------------------
ROLES = [
    # ---- Staff -----------------------------------------------------------
    {"name": "Owner",         "color": 0xE74C3C, "hoist": True,  "mentionable": True,
     "perms": ["administrator"]},
    {"name": "Admin",         "color": 0xC0392B, "hoist": True,  "mentionable": True,
     "perms": ["administrator"]},
    {"name": "Moderator",     "color": 0x3498DB, "hoist": True,  "mentionable": True,
     "perms": ["kick_members", "ban_members", "manage_messages", "manage_nicknames",
               "moderate_members", "mute_members", "deafen_members", "move_members",
               "manage_threads", "view_audit_log"]},
    {"name": "Support",       "color": 0x1ABC9C, "hoist": True,  "mentionable": True,
     "perms": ["manage_messages", "manage_threads"]},

    # ---- Content team ----------------------------------------------------
    {"name": "Head Analyst",  "color": 0xF1C40F, "hoist": True,  "mentionable": True,
     "perms": ["mention_everyone", "manage_messages"]},
    {"name": "Analyst",       "color": 0xF39C12, "hoist": True,  "mentionable": True,
     "perms": ["mention_everyone"]},

    # ---- Bots ------------------------------------------------------------
    {"name": "Bot",           "color": 0x95A5A6, "hoist": False, "mentionable": False,
     "perms": []},

    # ---- Paid membership tiers (hoisted, top of member list) -------------
    {"name": ROLE_LIFETIME,   "color": 0x9B59B6, "hoist": True,  "mentionable": False,
     "perms": []},
    {"name": ROLE_ELITE,      "color": 0xE67E22, "hoist": True,  "mentionable": False,
     "perms": []},
    {"name": ROLE_PREMIUM,    "color": 0x2ECC71, "hoist": True,  "mentionable": False,
     "perms": []},

    # ---- Cosmetic / recognition -----------------------------------------
    {"name": "Server Booster", "color": 0xF47FFF, "hoist": True, "mentionable": False,
     "perms": []},
    {"name": "Trader of the Month", "color": 0xFFD700, "hoist": True, "mentionable": True,
     "perms": []},
    {"name": "OG Member",     "color": 0x00B5AD, "hoist": False, "mentionable": False,
     "perms": []},

    # ---- Notification (self-assignable) ---------------------------------
    *[{"name": n, "color": 0x607D8B, "hoist": False, "mentionable": False, "perms": []}
      for n, _emoji in NOTIFY_ROLES],

    # ---- Free / base membership -----------------------------------------
    {"name": ROLE_MEMBER,     "color": 0xBDC3C7, "hoist": False, "mentionable": False,
     "perms": []},
    {"name": ROLE_UNVERIFIED, "color": 0x7F8C8D, "hoist": False, "mentionable": False,
     "perms": []},
]

# Convenience groupings used to build channel permissions.
STAFF_ROLES = ["Owner", "Admin", "Moderator", "Support"]
ANALYST_ROLES = ["Head Analyst", "Analyst"]
PAID_ROLES = [ROLE_PREMIUM, ROLE_ELITE, ROLE_LIFETIME]
ELITE_ROLES = [ROLE_ELITE, ROLE_LIFETIME]

# ---------------------------------------------------------------------------
# CHANNELS
#
# Each category has a list of channels. Per-channel keys:
#   name      : channel name (no leading #)
#   type      : "text" | "voice" | "forum" | "announcement"  (default "text")
#   topic     : channel topic / description
#   view      : list of role names that can SEE it.
#               None  -> visible to everyone (public).
#               []    -> visible to no one except staff (staff always added).
#   send      : list of role names that can SEND. None -> same as `view`
#               (everyone who can see can talk). Use to make read-only feeds.
#   slowmode  : seconds of slowmode (optional)
#
# Staff roles are ALWAYS granted full access to every channel automatically.
# ---------------------------------------------------------------------------
CATEGORIES = [
    {
        "name": "👋 START HERE",
        "channels": [
            {"name": "welcome",        "topic": "Welcome to the community! Start here.",
             "view": None, "send": STAFF_ROLES},
            {"name": "rules",          "topic": "Community rules & risk disclaimer. Read before participating.",
             "view": None, "send": STAFF_ROLES},
            {"name": "verify",         "topic": "React below to verify and unlock the server.",
             "view": [ROLE_UNVERIFIED], "send": STAFF_ROLES},
            {"name": "announcements",  "type": "announcement",
             "topic": "Official server announcements.",
             "view": None, "send": STAFF_ROLES + ["Head Analyst"]},
            {"name": "faq",            "topic": "Frequently asked questions.",
             "view": None, "send": STAFF_ROLES},
            {"name": "how-to-upgrade", "topic": "How to get Premium / Elite access and what you unlock.",
             "view": None, "send": STAFF_ROLES},
            {"name": "self-roles",     "topic": "Pick your signal notification pings here.",
             "view": None, "send": STAFF_ROLES},
        ],
    },
    {
        "name": "💬 COMMUNITY",
        "view": [ROLE_MEMBER] + PAID_ROLES,
        "channels": [
            {"name": "general-chat",     "topic": "Main community chat."},
            {"name": "introductions",    "topic": "Introduce yourself to the community."},
            {"name": "wins-and-losses",  "topic": "Share your trades — the good and the bad."},
            {"name": "charts-and-ideas", "topic": "Post charts and discuss setups."},
            {"name": "off-topic",        "topic": "Anything not trading-related."},
            {"name": "memes",            "topic": "Trading memes and fun."},
            {"name": "bot-commands",     "topic": "Use bot commands here.", "slowmode": 5},
        ],
    },
    {
        "name": "🆓 FREE ZONE",
        "view": [ROLE_MEMBER] + PAID_ROLES,
        "channels": [
            {"name": "free-signals",        "topic": "A taste of our signals — free tier.",
             "send": ANALYST_ROLES + STAFF_ROLES},
            {"name": "market-news",         "topic": "Market headlines and macro news.",
             "send": ANALYST_ROLES + STAFF_ROLES},
            {"name": "daily-watchlist",     "topic": "Free daily watchlist.",
             "send": ANALYST_ROLES + STAFF_ROLES},
            {"name": "education-basics",    "topic": "Free educational content for new traders.",
             "send": ANALYST_ROLES + STAFF_ROLES},
        ],
    },
    {
        "name": "💎 PREMIUM",
        "view": PAID_ROLES,
        "channels": [
            {"name": "premium-announcements", "topic": "Premium-only announcements.",
             "send": ANALYST_ROLES + STAFF_ROLES},
            {"name": "premium-signals",     "topic": "Full premium trade signals.",
             "send": ANALYST_ROLES + STAFF_ROLES},
            {"name": "crypto-signals",      "topic": "Crypto trade calls.",
             "send": ANALYST_ROLES + STAFF_ROLES},
            {"name": "forex-signals",       "topic": "Forex trade calls.",
             "send": ANALYST_ROLES + STAFF_ROLES},
            {"name": "stocks-and-options",  "topic": "Equities and options plays.",
             "send": ANALYST_ROLES + STAFF_ROLES},
            {"name": "scalp-setups",        "topic": "Short-term scalp setups.",
             "send": ANALYST_ROLES + STAFF_ROLES},
            {"name": "swing-setups",        "topic": "Multi-day swing setups.",
             "send": ANALYST_ROLES + STAFF_ROLES},
            {"name": "premium-chat",        "topic": "Premium members chat."},
            {"name": "trade-journal",       "type": "forum",
             "topic": "Log and track your trades (one thread per trade)."},
        ],
    },
    {
        "name": "🏆 ELITE",
        "view": ELITE_ROLES,
        "channels": [
            {"name": "elite-lounge",        "topic": "Elite & Lifetime members only."},
            {"name": "analyst-desk",        "topic": "Direct access to the analyst team.",
             "send": ELITE_ROLES + ANALYST_ROLES + STAFF_ROLES},
            {"name": "portfolio-reviews",   "topic": "1:1 portfolio reviews and feedback."},
            {"name": "live-trading",        "topic": "Live trading alerts and play-by-play.",
             "send": ANALYST_ROLES + STAFF_ROLES},
        ],
    },
    {
        "name": "🎓 EDUCATION",
        "view": PAID_ROLES,
        "channels": [
            {"name": "trading-courses",     "topic": "Structured course material.",
             "send": ANALYST_ROLES + STAFF_ROLES},
            {"name": "strategy-library",    "topic": "Documented strategies and playbooks.",
             "send": ANALYST_ROLES + STAFF_ROLES},
            {"name": "risk-management",     "topic": "Position sizing & risk control.",
             "send": ANALYST_ROLES + STAFF_ROLES},
            {"name": "qa-with-analysts",    "topic": "Ask the analysts your questions."},
        ],
    },
    {
        "name": "🔊 VOICE",
        "view": [ROLE_MEMBER] + PAID_ROLES,
        "channels": [
            {"name": "General Lounge",      "type": "voice"},
            {"name": "Trading Floor",       "type": "voice"},
            {"name": "Premium Voice",       "type": "voice", "view": PAID_ROLES},
            {"name": "Elite Voice",         "type": "voice", "view": ELITE_ROLES},
            {"name": "Live Analysis Stream","type": "voice", "view": PAID_ROLES,
             "send": ANALYST_ROLES + STAFF_ROLES},
            {"name": "AFK",                 "type": "voice"},
        ],
    },
    {
        "name": "🛠️ STAFF",
        "view": [],  # staff-only (staff auto-added)
        "channels": [
            {"name": "staff-chat",          "topic": "Private staff discussion."},
            {"name": "analyst-room",        "topic": "Analyst team coordination.",
             "view": ANALYST_ROLES},
            {"name": "mod-log",             "topic": "Automated moderation log."},
            {"name": "support-tickets",     "topic": "Member support tickets land here."},
            {"name": "payment-log",         "topic": "Premium grant / payment events log."},
            {"name": "Staff Voice",         "type": "voice"},
        ],
    },
]
