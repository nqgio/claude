"""
Runtime bot for the trading community.

Responsibilities:
  * Verification: members react in #verify to swap Unverified -> Member (free).
  * Self-roles: members react in #self-roles to toggle notification pings.
  * Premium management: admin slash commands to grant/revoke paid tiers, with
    optional expiry. A background task removes expired subscriptions and logs
    to #payment-log.
  * Welcome: greets new members and assigns the Unverified role.

This is intentionally framework-light (discord.py 2.x). Payment processors
(Stripe / Whop / etc.) can call ``grant_tier`` via webhook_stripe.py.

Commands (admin only):
    /grant   user tier [days]   -> give a paid tier, optionally for N days
    /revoke  user               -> remove all paid tiers
    /whois   user               -> show a member's tier & expiry
    /post_verify                -> (re)post the verify message in #verify
    /post_selfroles             -> (re)post the self-roles menu in #self-roles
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

import config

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
SUBS_FILE = DATA_DIR / "subscriptions.json"

VERIFY_EMOJI = "✅"
TIER_CHOICES = [
    app_commands.Choice(name=config.ROLE_PREMIUM, value=config.ROLE_PREMIUM),
    app_commands.Choice(name=config.ROLE_ELITE, value=config.ROLE_ELITE),
    app_commands.Choice(name=config.ROLE_LIFETIME, value=config.ROLE_LIFETIME),
]

intents = discord.Intents.default()
intents.members = True            # required for joins & role management
intents.message_content = False   # we use reactions/slash, not message text


# ---------------------------------------------------------------------------
# Tiny JSON subscription store: {guild_id: {user_id: {"tier", "expires"}}}
# ---------------------------------------------------------------------------
def load_subs():
    if SUBS_FILE.exists():
        return json.loads(SUBS_FILE.read_text())
    return {}


def save_subs(subs):
    SUBS_FILE.write_text(json.dumps(subs, indent=2))


class TradingBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.subs = load_subs()

    async def setup_hook(self):
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        self.expiry_check.start()

    # ----- helpers --------------------------------------------------------
    def role(self, guild, name):
        return discord.utils.get(guild.roles, name=name)

    async def log_payment(self, guild, message):
        ch = discord.utils.get(guild.text_channels, name="payment-log")
        if ch:
            await ch.send(message)

    async def grant_tier(self, guild, member, tier, days=None):
        """Add a paid tier, removing other paid tiers first. days=None => no expiry."""
        for other in config.PAID_ROLES:
            r = self.role(guild, other)
            if r and r in member.roles and other != tier:
                await member.remove_roles(r, reason="Tier change")
        role = self.role(guild, tier)
        member_role = self.role(guild, config.ROLE_MEMBER)
        if role:
            await member.add_roles(role, reason="Paid tier granted")
        if member_role and member_role not in member.roles:
            await member.add_roles(member_role, reason="Base access")

        expires = None
        if days and tier != config.ROLE_LIFETIME:
            expires = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        self.subs.setdefault(str(guild.id), {})[str(member.id)] = {
            "tier": tier, "expires": expires,
        }
        save_subs(self.subs)
        until = f" until {expires[:10]}" if expires else " (no expiry)"
        await self.log_payment(
            guild, f"💳 **{member}** granted **{tier}**{until}.")

    async def revoke_tiers(self, guild, member, reason="Subscription ended"):
        removed = []
        for tier in config.PAID_ROLES:
            r = self.role(guild, tier)
            if r and r in member.roles:
                await member.remove_roles(r, reason=reason)
                removed.append(tier)
        self.subs.get(str(guild.id), {}).pop(str(member.id), None)
        save_subs(self.subs)
        if removed:
            await self.log_payment(
                guild, f"🚫 **{member}** lost {', '.join(removed)} ({reason}).")
        return removed

    # ----- background expiry ---------------------------------------------
    @tasks.loop(hours=6)
    async def expiry_check(self):
        await self.wait_until_ready()
        now = datetime.now(timezone.utc)
        for gid, members in list(self.subs.items()):
            guild = self.get_guild(int(gid))
            if not guild:
                continue
            for uid, info in list(members.items()):
                exp = info.get("expires")
                if not exp:
                    continue
                if datetime.fromisoformat(exp) <= now:
                    member = guild.get_member(int(uid))
                    if member:
                        await self.revoke_tiers(guild, member,
                                                reason="Subscription expired")


bot = TradingBot()


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    print("Bot is ready. Use /post_verify and /post_selfroles to set up menus.")


@bot.event
async def on_member_join(member):
    role = bot.role(member.guild, config.ROLE_UNVERIFIED)
    if role:
        await member.add_roles(role, reason="New member")
    welcome = discord.utils.get(member.guild.text_channels, name="welcome")
    if welcome:
        await welcome.send(
            f"👋 Welcome {member.mention}! Head to **#verify** to unlock the "
            f"server, then check **#how-to-upgrade** for Premium access.")


@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
    channel = guild.get_channel(payload.channel_id)
    if not channel:
        return

    # --- Verification ---
    if channel.name == "verify" and str(payload.emoji) == VERIFY_EMOJI:
        member_role = bot.role(guild, config.ROLE_MEMBER)
        unverified = bot.role(guild, config.ROLE_UNVERIFIED)
        if member_role:
            await member.add_roles(member_role, reason="Verified")
        if unverified and unverified in member.roles:
            await member.remove_roles(unverified, reason="Verified")
        return

    # --- Self notification roles ---
    if channel.name == "self-roles":
        for name, emoji in config.NOTIFY_ROLES:
            if str(payload.emoji) == emoji:
                r = bot.role(guild, name)
                if r:
                    await member.add_roles(r, reason="Self-role")
                break


@bot.event
async def on_raw_reaction_remove(payload):
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
    channel = guild.get_channel(payload.channel_id)
    if not channel or channel.name != "self-roles":
        return
    for name, emoji in config.NOTIFY_ROLES:
        if str(payload.emoji) == emoji:
            r = bot.role(guild, name)
            if r and r in member.roles:
                await member.remove_roles(r, reason="Self-role removed")
            break


# ---------------------------------------------------------------------------
# Slash commands (admin)
# ---------------------------------------------------------------------------
def admin_only():
    return app_commands.checks.has_permissions(manage_guild=True)


@bot.tree.command(description="Grant a paid tier to a member.")
@app_commands.describe(user="Member to upgrade", tier="Paid tier",
                       days="Optional: expire after N days (omit = no expiry)")
@app_commands.choices(tier=TIER_CHOICES)
@admin_only()
async def grant(interaction: discord.Interaction, user: discord.Member,
                tier: app_commands.Choice[str], days: int | None = None):
    await bot.grant_tier(interaction.guild, user, tier.value, days)
    suffix = f" for {days} days" if days else ""
    await interaction.response.send_message(
        f"✅ Granted **{tier.value}** to {user.mention}{suffix}.", ephemeral=True)


@bot.tree.command(description="Revoke all paid tiers from a member.")
@app_commands.describe(user="Member to downgrade")
@admin_only()
async def revoke(interaction: discord.Interaction, user: discord.Member):
    removed = await bot.revoke_tiers(interaction.guild, user, reason="Manual revoke")
    msg = (f"🚫 Removed {', '.join(removed)} from {user.mention}."
           if removed else f"{user.mention} had no paid tier.")
    await interaction.response.send_message(msg, ephemeral=True)


@bot.tree.command(description="Show a member's tier and expiry.")
@admin_only()
async def whois(interaction: discord.Interaction, user: discord.Member):
    info = bot.subs.get(str(interaction.guild.id), {}).get(str(user.id))
    if not info:
        await interaction.response.send_message(
            f"{user.mention} has no tracked subscription.", ephemeral=True)
        return
    exp = info.get("expires")
    when = f"expires {exp[:10]}" if exp else "no expiry"
    await interaction.response.send_message(
        f"{user.mention}: **{info['tier']}** ({when}).", ephemeral=True)


@bot.tree.command(description="Post the verification message in #verify.")
@admin_only()
async def post_verify(interaction: discord.Interaction):
    ch = discord.utils.get(interaction.guild.text_channels, name="verify")
    if not ch:
        await interaction.response.send_message("No #verify channel found.", ephemeral=True)
        return
    embed = discord.Embed(
        title="✅ Verify to unlock the server",
        description=(f"React with {VERIFY_EMOJI} below to confirm you've read the "
                     f"**#rules** and gain access to the community.\n\n"
                     f"By verifying you agree these signals are **educational, not "
                     f"financial advice**. Trade at your own risk."),
        colour=0x2ECC71)
    msg = await ch.send(embed=embed)
    await msg.add_reaction(VERIFY_EMOJI)
    await interaction.response.send_message("Posted verify message.", ephemeral=True)


@bot.tree.command(description="Post the self-roles menu in #self-roles.")
@admin_only()
async def post_selfroles(interaction: discord.Interaction):
    ch = discord.utils.get(interaction.guild.text_channels, name="self-roles")
    if not ch:
        await interaction.response.send_message("No #self-roles channel found.", ephemeral=True)
        return
    lines = "\n".join(f"{emoji} — **{name}**" for name, emoji in config.NOTIFY_ROLES)
    embed = discord.Embed(
        title="🔔 Choose your notification pings",
        description=f"React to toggle a role and get pinged for that category.\n\n{lines}",
        colour=0x607D8B)
    msg = await ch.send(embed=embed)
    for _name, emoji in config.NOTIFY_ROLES:
        await msg.add_reaction(emoji)
    await interaction.response.send_message("Posted self-roles menu.", ephemeral=True)


@grant.error
@revoke.error
@whois.error
@post_verify.error
@post_selfroles.error
async def on_app_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "You need the **Manage Server** permission to use this.", ephemeral=True)
    else:
        raise error


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN missing. Copy .env.example to .env and fill it in.")
    bot.run(TOKEN)
