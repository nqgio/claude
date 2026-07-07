"""
setup_server.py

Idempotently scaffolds a Discord server (roles, categories, channels,
permission overwrites, and seed messages) from SERVER_CONFIG below.

Usage:
    python setup_server.py

Requires DISCORD_TOKEN and GUILD_ID in a .env file (see .env.example).
"""

import json
import logging
import os
import sys

import discord
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID_RAW = os.getenv("GUILD_ID")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("setup_server")

# ---------------------------------------------------------------------------
# SERVER_CONFIG
# ---------------------------------------------------------------------------

SERVER_CONFIG = {
    "roles": [
        {"name": "Admin", "color": 0xE74C3C, "hoist": True, "mentionable": False},
        {"name": "Mod", "color": 0xE67E22, "hoist": True, "mentionable": False},
        {"name": "Mentorship", "color": 0xF1C40F, "hoist": True, "mentionable": True},
        {"name": "Trader", "color": 0x2ECC71, "hoist": True, "mentionable": True},
        {"name": "Member", "color": 0x95A5A6, "hoist": False, "mentionable": False},
    ],
    "categories": [
        {
            "name": "\U0001F4CB START HERE",
            "locked_to": None,
            "channels": [
                {
                    "name": "welcome",
                    "type": "text",
                    "post_only": True,
                    "seed": [
                        "**Welcome.** This is where I trade the NQ live and teach the exact "
                        "system I run on funded accounts — no fluff, no hype, no fake Lambos.\n\n"
                        "• New here? Read #rules and #disclaimer.\n"
                        "• Want the full system + live trades? → #join-the-system\n"
                        "• Watch #results-proof for real, dated fills."
                    ],
                },
                {
                    "name": "rules",
                    "type": "text",
                    "post_only": True,
                    "seed": [
                        "**Server Rules**\n"
                        "1. Be respectful. No spam, no self-promo, no DMing members to sell.\n"
                        "2. This is an education community, not financial advice. You trade your own account.\n"
                        "3. No begging for signals in free channels.\n"
                        "4. No sharing paid content outside the server — it gets you removed and refund-blocked.\n"
                        "5. Post losses too. We learn from real trading, not a highlight reel."
                    ],
                },
                {
                    "name": "disclaimer",
                    "type": "text",
                    "post_only": True,
                    "pin_first": True,
                    "seed": [
                        "**Not financial advice.** Everything shared here is for educational purposes "
                        "only. I am not a licensed financial advisor or registered commodity trading "
                        "advisor. Trading futures involves substantial risk of loss and is not suitable "
                        "for everyone. Past performance does not guarantee future results. Anything I "
                        "share is my own trading and my own opinion — you are solely responsible for "
                        "your own trades and risk. Never trade money you can't afford to lose."
                    ],
                },
                {"name": "announcements", "type": "text", "post_only": True, "seed": []},
                {
                    "name": "join-the-system",
                    "type": "text",
                    "post_only": True,
                    "seed": [
                        "**Get the full system + live community** \U0001F447\n"
                        "The complete 8-module NQ course + 30 days inside the live community "
                        "(daily bias, watchlist, live trades) included.\n\n"
                        "\U0001F449 [PASTE YOUR WHOP CHECKOUT LINK HERE]\n\n"
                        "*Educational only. Not financial advice. Trading futures carries substantial risk.*"
                    ],
                },
            ],
        },
        {
            "name": "\U0001F4AC COMMUNITY",
            "locked_to": None,
            "channels": [
                {"name": "general", "type": "text"},
                {"name": "introduce-yourself", "type": "text"},
                {"name": "results-proof", "type": "text", "post_only": True, "seed": []},
                {"name": "member-wins", "type": "text"},
            ],
        },
        {
            "name": "\U0001F393 COURSE & CONTENT",
            "locked_to": "Trader",
            "channels": [
                {
                    "name": "course-hub",
                    "type": "text",
                    "post_only": True,
                    "seed": [
                        "**The System — start here.** Work top to bottom; each module builds on the last.\n"
                        "1. Foundations → 2. Bias & Liquidity → 3. Reversal Confirmation → "
                        "4. Fib Framework → 5. Entries → 6. Risk & Exits → 7. Funded Execution → "
                        "8. Discipline\n\n"
                        "\U0001F449 Open the full course: [PASTE WHOP COURSE LINK]\n"
                        "Questions on any lesson go in #course-questions."
                    ],
                },
                {"name": "course-questions", "type": "text"},
            ],
        },
        {
            "name": "\U0001F534 LIVE TRADING",
            "locked_to": "Trader",
            "channels": [
                {"name": "daily-bias", "type": "text", "post_only": True, "seed": []},
                {"name": "watchlist", "type": "text", "post_only": True, "seed": []},
                {"name": "live-trades", "type": "text", "post_only": True, "seed": []},
                {"name": "trade-recaps", "type": "text"},
                {"name": "members-chat", "type": "text"},
            ],
        },
        {
            "name": "\U0001F48E MENTORSHIP",
            "locked_to": "Mentorship",
            "channels": [
                {"name": "mentorship-lounge", "type": "text"},
                {"name": "trade-reviews", "type": "text"},
            ],
        },
        {
            "name": "\U0001F50A VOICE",
            "locked_to": None,
            "channels": [
                {"name": "Live Session", "type": "voice", "locked_to": "Trader"},
                {"name": "Community Hangout", "type": "voice"},
            ],
        },
    ],
}

# ---------------------------------------------------------------------------
# Run-time bookkeeping
# ---------------------------------------------------------------------------

stats = {
    "roles_created": 0,
    "roles_reused": 0,
    "categories_created": 0,
    "categories_reused": 0,
    "channels_created": 0,
    "channels_reused": 0,
    "messages_seeded": 0,
    "messages_skipped": 0,
    "pins_added": 0,
    "pins_skipped": 0,
}

server_map = {"roles": {}, "categories": {}, "channels": {}}


# ---------------------------------------------------------------------------
# Role helpers
# ---------------------------------------------------------------------------

async def get_or_create_role(guild: discord.Guild, role_cfg: dict) -> discord.Role:
    existing = discord.utils.get(guild.roles, name=role_cfg["name"])
    if existing:
        stats["roles_reused"] += 1
        needs_update = (
            existing.color.value != role_cfg["color"]
            or existing.hoist != role_cfg["hoist"]
            or existing.mentionable != role_cfg["mentionable"]
        )
        if needs_update:
            await existing.edit(
                color=discord.Color(role_cfg["color"]),
                hoist=role_cfg["hoist"],
                mentionable=role_cfg["mentionable"],
                reason="Sync role settings from SERVER_CONFIG",
            )
            log.info("Updated role settings: %s", role_cfg["name"])
        else:
            log.info("Role exists, reusing: %s", role_cfg["name"])
        return existing

    role = await guild.create_role(
        name=role_cfg["name"],
        color=discord.Color(role_cfg["color"]),
        hoist=role_cfg["hoist"],
        mentionable=role_cfg["mentionable"],
        reason="Server scaffold setup",
    )
    log.info("Created role: %s", role_cfg["name"])
    stats["roles_created"] += 1
    return role


async def reorder_roles(guild: discord.Guild, ordered_roles: list) -> None:
    """Place roles just below the bot's own top role, preserving config order
    (first entry = highest)."""
    bot_member = guild.me
    if bot_member is None or bot_member.top_role is None:
        log.warning("Could not determine bot's top role; skipping role reorder")
        return

    top_position = bot_member.top_role.position
    positions = {}
    position = top_position - 1
    for role in ordered_roles:
        if position < 1:
            log.warning(
                "Ran out of room below the bot's role to place '%s'; move the "
                "bot's role higher in Server Settings > Roles",
                role.name,
            )
            break
        positions[role] = position
        position -= 1

    if not positions:
        return

    try:
        await guild.edit_role_positions(positions=positions, reason="Sync role hierarchy")
        log.info("Reordered roles to match configured hierarchy")
    except discord.HTTPException as exc:
        log.warning("Could not reorder roles (%s). Is the bot's role above them?", exc)


# ---------------------------------------------------------------------------
# Permission overwrite builder
# ---------------------------------------------------------------------------

def build_overwrites(guild: discord.Guild, roles: dict, category_cfg: dict, channel_cfg: dict | None = None):
    everyone = guild.default_role
    admin = roles["Admin"]
    mod = roles["Mod"]
    is_voice = channel_cfg is not None and channel_cfg.get("type") == "voice"

    if channel_cfg is not None and "locked_to" in channel_cfg:
        locked_to = channel_cfg["locked_to"]
    else:
        locked_to = category_cfg.get("locked_to")

    overwrites = {}

    if locked_to:
        locked_role = roles[locked_to]
        overwrites[everyone] = discord.PermissionOverwrite(view_channel=False)
        if is_voice:
            overwrites[locked_role] = discord.PermissionOverwrite(
                view_channel=True, connect=True, speak=True
            )
        else:
            overwrites[locked_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )
    else:
        overwrites[everyone] = discord.PermissionOverwrite(view_channel=True)

    # Admin/Mod always get full access, regardless of category/channel locks.
    if is_voice:
        overwrites[admin] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
        overwrites[mod] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
    else:
        overwrites[admin] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True, manage_messages=True
        )
        overwrites[mod] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True, manage_messages=True
        )

    post_only = channel_cfg is not None and channel_cfg.get("post_only", False)
    if post_only and not is_voice:
        if locked_to:
            locked_role = roles[locked_to]
            overwrites[locked_role].send_messages = False
        else:
            overwrites[everyone].send_messages = False

    return overwrites


# ---------------------------------------------------------------------------
# Category / channel helpers
# ---------------------------------------------------------------------------

async def get_or_create_category(guild: discord.Guild, roles: dict, cat_cfg: dict) -> discord.CategoryChannel:
    existing = discord.utils.get(guild.categories, name=cat_cfg["name"])
    overwrites = build_overwrites(guild, roles, cat_cfg, channel_cfg=None)

    if existing:
        stats["categories_reused"] += 1
        log.info("Category exists, reusing: %s", cat_cfg["name"])
        edited = await existing.edit(overwrites=overwrites, reason="Sync category overwrites")
        return edited or existing

    category = await guild.create_category(
        name=cat_cfg["name"], overwrites=overwrites, reason="Server scaffold setup"
    )
    log.info("Created category: %s", cat_cfg["name"])
    stats["categories_created"] += 1
    return category


async def get_or_create_channel(
    guild: discord.Guild,
    roles: dict,
    category: discord.CategoryChannel,
    cat_cfg: dict,
    chan_cfg: dict,
):
    chan_type = chan_cfg.get("type", "text")
    existing = discord.utils.get(category.channels, name=chan_cfg["name"])
    overwrites = build_overwrites(guild, roles, cat_cfg, chan_cfg)

    if existing:
        stats["channels_reused"] += 1
        log.info("Channel exists, reusing: #%s", chan_cfg["name"])
        edited = await existing.edit(overwrites=overwrites, reason="Sync channel overwrites")
        return edited or existing

    if chan_type == "voice":
        channel = await guild.create_voice_channel(
            name=chan_cfg["name"], category=category, overwrites=overwrites, reason="Server scaffold setup"
        )
    else:
        channel = await guild.create_text_channel(
            name=chan_cfg["name"], category=category, overwrites=overwrites, reason="Server scaffold setup"
        )
    log.info("Created channel: #%s", chan_cfg["name"])
    stats["channels_created"] += 1
    return channel


async def seed_channel(channel: discord.TextChannel, chan_cfg: dict) -> None:
    seeds = chan_cfg.get("seed") or []
    pin_first = chan_cfg.get("pin_first", False)

    if not seeds and not pin_first:
        return

    first_message = None

    if seeds:
        history = [msg async for msg in channel.history(limit=1)]
        if history:
            log.info("#%s already has messages, skipping seed", chan_cfg["name"])
            stats["messages_skipped"] += len(seeds)
        else:
            for i, content in enumerate(seeds):
                msg = await channel.send(content)
                if i == 0:
                    first_message = msg
                stats["messages_seeded"] += 1

    if pin_first:
        try:
            pins = await channel.pins()
        except discord.HTTPException:
            pins = []

        if pins:
            log.info("#%s already has a pinned message, skipping pin", chan_cfg["name"])
            stats["pins_skipped"] += 1
            return

        if first_message is None:
            async for msg in channel.history(limit=1, oldest_first=True):
                first_message = msg
                break

        if first_message:
            try:
                await first_message.pin(reason="Pin disclaimer per SERVER_CONFIG")
                stats["pins_added"] += 1
                log.info("Pinned first message in #%s", chan_cfg["name"])
            except discord.HTTPException as exc:
                log.warning("Could not pin message in #%s (%s)", chan_cfg["name"], exc)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def run_setup(guild: discord.Guild) -> None:
    roles = {}
    ordered_roles = []
    for role_cfg in SERVER_CONFIG["roles"]:
        role = await get_or_create_role(guild, role_cfg)
        roles[role_cfg["name"]] = role
        ordered_roles.append(role)
        server_map["roles"][role_cfg["name"]] = role.id

    await reorder_roles(guild, ordered_roles)

    for cat_cfg in SERVER_CONFIG["categories"]:
        category = await get_or_create_category(guild, roles, cat_cfg)
        server_map["categories"][cat_cfg["name"]] = category.id
        server_map["channels"].setdefault(cat_cfg["name"], {})

        for chan_cfg in cat_cfg["channels"]:
            channel = await get_or_create_channel(guild, roles, category, cat_cfg, chan_cfg)
            server_map["channels"][cat_cfg["name"]][chan_cfg["name"]] = channel.id

            if chan_cfg.get("type", "text") != "voice":
                await seed_channel(channel, chan_cfg)


def print_summary() -> None:
    print("\n" + "=" * 60)
    print("SERVER SCAFFOLD SUMMARY")
    print("=" * 60)
    print(f"{'Type':<12}{'Created':<10}{'Reused':<10}")
    print(f"{'Roles':<12}{stats['roles_created']:<10}{stats['roles_reused']:<10}")
    print(f"{'Categories':<12}{stats['categories_created']:<10}{stats['categories_reused']:<10}")
    print(f"{'Channels':<12}{stats['channels_created']:<10}{stats['channels_reused']:<10}")
    print()
    print(f"Messages seeded: {stats['messages_seeded']}  (skipped: {stats['messages_skipped']})")
    print(f"Pins added:      {stats['pins_added']}  (skipped: {stats['pins_skipped']})")
    print("=" * 60)


def write_server_map() -> None:
    with open("server_map.json", "w") as f:
        json.dump(server_map, f, indent=2)
    log.info("Wrote server_map.json")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class SetupClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())

    async def on_ready(self):
        log.info("Logged in as %s — starting scaffold", self.user)
        try:
            guild = self.get_guild(int(GUILD_ID_RAW))
            if guild is None:
                log.error(
                    "Guild %s not found in cache. Confirm GUILD_ID is correct and "
                    "that the bot has been invited to that server.",
                    GUILD_ID_RAW,
                )
                return
            await run_setup(guild)
        except Exception:
            log.exception("Setup failed")
        finally:
            print_summary()
            write_server_map()
            await self.close()


def main():
    if not DISCORD_TOKEN or not GUILD_ID_RAW:
        log.error("DISCORD_TOKEN and GUILD_ID must be set in .env (see .env.example)")
        sys.exit(1)

    try:
        int(GUILD_ID_RAW)
    except ValueError:
        log.error("GUILD_ID must be a numeric Discord guild ID")
        sys.exit(1)

    client = SetupClient()
    try:
        client.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        log.error("Login failed — check that DISCORD_TOKEN is correct")
        sys.exit(1)


if __name__ == "__main__":
    main()
