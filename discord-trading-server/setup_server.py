"""
Build the trading-community Discord server from ``config.py``.

Run this ONCE against a fresh (or near-fresh) server. It will:
  * create every role in the configured hierarchy,
  * create every category and channel,
  * apply per-category / per-channel view & send permissions,
  * lock the @everyone baseline so new joiners only see #verify.

Usage:
    python setup_server.py            # build everything
    python setup_server.py --wipe     # delete bot-created roles/channels first

The bot account must have the **Administrator** permission and its role must be
near the top of the role list (above the roles it creates). See README.md.
"""

import argparse
import asyncio
import os

import discord
from dotenv import load_dotenv

import config

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

intents = discord.Intents.default()
client = discord.Client(intents=intents)


def make_permissions(flag_names):
    """Turn a list of permission flag names into a discord.Permissions."""
    perms = discord.Permissions.none()
    if flag_names:
        perms.update(**{name: True for name in flag_names})
    return perms


async def build_roles(guild):
    """Create any missing roles, then order them per config.ROLES."""
    existing = {r.name: r for r in guild.roles}
    created = {}

    # Create from lowest priority to highest so newly created roles stack up
    # nicely; final ordering is enforced afterwards anyway.
    for spec in reversed(config.ROLES):
        if spec["name"] in existing:
            role = existing[spec["name"]]
            print(f"  • role exists: {spec['name']}")
        else:
            role = await guild.create_role(
                name=spec["name"],
                colour=discord.Colour(spec["color"]),
                hoist=spec["hoist"],
                mentionable=spec["mentionable"],
                permissions=make_permissions(spec["perms"]),
                reason="Trading server setup",
            )
            print(f"  ✓ created role: {spec['name']}")
        created[spec["name"]] = role

    # Enforce hierarchy. Position 1 sits just above @everyone; the highest
    # configured role gets the largest position. We keep the bot's own top
    # role untouched (it must remain above what it manages).
    bot_top = guild.me.top_role.position
    ordered = list(config.ROLES)  # highest -> lowest
    positions = {}
    pos = 1
    for spec in reversed(ordered):  # assign lowest first
        role = created[spec["name"]]
        if role >= guild.me.top_role:
            continue  # never move a role at/above the bot's top role
        positions[role] = pos
        pos += 1
        if pos >= bot_top:  # don't collide with the bot's role
            break
    try:
        await guild.edit_role_positions(positions=positions,
                                        reason="Trading server hierarchy")
        print("  ✓ role hierarchy ordered")
    except discord.HTTPException as exc:
        print(f"  ! could not reorder roles automatically ({exc}); "
              "drag them in Server Settings if needed.")
    return created


def resolve(role_names, roles):
    """Map a list of role names to role objects, skipping unknown ones."""
    out = []
    for name in role_names or []:
        if name in roles:
            out.append(roles[name])
    return out


def category_overwrites(everyone, view_names, roles):
    """Permission overwrites for a category based on who may view it."""
    ov = {}
    staff = resolve(config.STAFF_ROLES, roles)

    if view_names is None:
        # Public category — everyone can view.
        ov[everyone] = discord.PermissionOverwrite(view_channel=True)
    else:
        # Private — hide from everyone, reveal to listed + staff roles.
        ov[everyone] = discord.PermissionOverwrite(view_channel=False)
        for role in resolve(view_names, roles):
            ov[role] = discord.PermissionOverwrite(view_channel=True)

    # Staff always sees everything.
    for role in staff:
        ov[role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True,
            manage_messages=True, manage_threads=True,
        )
    return ov


def channel_overwrites(everyone, ch, cat_view, roles):
    """
    Per-channel overwrites layered on top of the category. Handles:
      * narrower `view` than the category,
      * read-only feeds via `send`.
    """
    ov = {}
    staff = resolve(config.STAFF_ROLES, roles)
    view_names = ch.get("view", cat_view)
    send_names = ch.get("send")  # None => anyone who can view may send

    # Visibility
    if view_names is None:
        ov[everyone] = discord.PermissionOverwrite(view_channel=True)
    else:
        ov[everyone] = discord.PermissionOverwrite(view_channel=False)
        for role in resolve(view_names, roles):
            ov[role] = discord.PermissionOverwrite(view_channel=True)

    # Read-only handling: deny send to the viewing audience, then re-grant to
    # the explicit `send` list.
    if send_names is not None:
        audience = view_names if view_names is not None else None
        if audience is None:
            base = ov.get(everyone, discord.PermissionOverwrite())
            base.update(view_channel=True, send_messages=False,
                        add_reactions=True, send_messages_in_threads=False)
            ov[everyone] = base
        else:
            for role in resolve(audience, roles):
                base = ov.get(role, discord.PermissionOverwrite())
                base.update(view_channel=True, send_messages=False)
                ov[role] = base
        for role in resolve(send_names, roles):
            base = ov.get(role, discord.PermissionOverwrite())
            base.update(view_channel=True, send_messages=True)
            ov[role] = base

    # Staff always full access.
    for role in staff:
        ov[role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True,
            manage_messages=True, manage_threads=True,
        )
    return ov


async def build_channels(guild, roles):
    everyone = guild.default_role
    existing_cats = {c.name: c for c in guild.categories}
    existing_chans = {c.name: c for c in guild.channels}

    for cat in config.CATEGORIES:
        cat_view = cat.get("view")  # None = public
        ov = category_overwrites(everyone, cat_view, roles)

        category = existing_cats.get(cat["name"])
        if category is None:
            category = await guild.create_category(
                cat["name"], overwrites=ov, reason="Trading server setup")
            print(f"  ✓ category: {cat['name']}")
        else:
            await category.edit(overwrites=ov)
            print(f"  • category exists: {cat['name']}")

        for ch in cat["channels"]:
            ctype = ch.get("type", "text")
            cov = channel_overwrites(everyone, ch, cat_view, roles)

            if ch["name"] in existing_chans:
                print(f"      • channel exists: {ch['name']}")
                continue

            common = dict(category=category, overwrites=cov,
                          reason="Trading server setup")
            if ch.get("slowmode"):
                common["slowmode_delay"] = ch["slowmode"]

            if ctype == "voice":
                await guild.create_voice_channel(ch["name"], **common)
            elif ctype == "forum":
                await guild.create_forum(
                    ch["name"], topic=ch.get("topic"), **common)
            elif ctype == "announcement":
                await guild.create_text_channel(
                    ch["name"], topic=ch.get("topic"), news=True, **common)
            else:
                await guild.create_text_channel(
                    ch["name"], topic=ch.get("topic"), **common)
            print(f"      ✓ channel: {ch['name']} ({ctype})")


async def wipe(guild):
    """Remove bot-managed categories, their channels, and configured roles."""
    cfg_cats = {c["name"] for c in config.CATEGORIES}
    for category in list(guild.categories):
        if category.name in cfg_cats:
            for ch in category.channels:
                await ch.delete(reason="Trading server wipe")
            await category.delete(reason="Trading server wipe")
            print(f"  ✗ removed category: {category.name}")

    cfg_roles = {r["name"] for r in config.ROLES}
    for role in list(guild.roles):
        if role.name in cfg_roles and role < guild.me.top_role and not role.managed:
            try:
                await role.delete(reason="Trading server wipe")
                print(f"  ✗ removed role: {role.name}")
            except discord.HTTPException:
                pass


@client.event
async def on_ready():
    print(f"Logged in as {client.user} ({client.user.id})")
    guild = client.get_guild(GUILD_ID) if GUILD_ID else None
    if guild is None and client.guilds:
        guild = client.guilds[0]
    if guild is None:
        print("ERROR: bot is not in any guild / GUILD_ID not found. "
              "Invite the bot first (see README).")
        await client.close()
        return

    print(f"Target server: {guild.name} ({guild.id})\n")

    if client._wipe:  # noqa: SLF001 (set on the client below)
        print("Wiping existing config-managed roles & channels...")
        await wipe(guild)
        print()

    print("Building roles...")
    roles = await build_roles(guild)
    print("\nBuilding categories & channels...")
    await build_channels(guild, roles)

    print("\n✅ Done. Run bot.py for verification, self-roles, and premium "
          "management.")
    await client.close()


def main():
    parser = argparse.ArgumentParser(description="Build the trading Discord server.")
    parser.add_argument("--wipe", action="store_true",
                        help="Delete config-managed roles/channels before building.")
    args = parser.parse_args()

    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN missing. Copy .env.example to .env and fill it in.")

    client._wipe = args.wipe  # stash for on_ready
    client.run(TOKEN)


if __name__ == "__main__":
    main()
