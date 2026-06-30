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


# ---------------------------------------------------------------------------
# Verification UI — a persistent button gate (survives bot restarts).
# ---------------------------------------------------------------------------
class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # persistent

    @discord.ui.button(label="✅ Verify & Enter", style=discord.ButtonStyle.success,
                       custom_id="bullpen_verify")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild, member = interaction.guild, interaction.user
        member_role = discord.utils.get(guild.roles, name=config.ROLE_MEMBER)
        unverified = discord.utils.get(guild.roles, name=config.ROLE_UNVERIFIED)
        if member_role and member_role not in member.roles:
            await member.add_roles(member_role, reason="Verified via button")
        if unverified and unverified in member.roles:
            await member.remove_roles(unverified, reason="Verified via button")
        await interaction.response.send_message(
            f"✅ You're verified — welcome to **{config.SERVER_NAME}**!\n"
            f"Grab your notification pings in **#self-roles**, and check "
            f"**#how-to-upgrade** for full Premium access via Whop. 💎",
            ephemeral=True)


def upgrade_view():
    """Link buttons to the Whop storefront (used in verify / upgrade posts)."""
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(
        label="💎 Get Premium on Whop", style=discord.ButtonStyle.link,
        url=config.WHOP_STORE_URL))
    return view


class TradingBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.subs = load_subs()

    async def setup_hook(self):
        self.add_view(VerifyView())  # register persistent view
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        self.sync_subscriptions.start()

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

    # ----- background reconcile ------------------------------------------
    @tasks.loop(minutes=2)
    async def sync_subscriptions(self):
        """
        Reconcile Discord roles with the subscription store every couple of
        minutes. This is what makes the Whop / Stripe webhooks effective: they
        write data/subscriptions.json, and this loop applies the changes —
        granting roles for new memberships, fixing tier changes, and removing
        roles for expired or cancelled (Whop "invalid") memberships.
        """
        await self.wait_until_ready()
        self.subs = load_subs()  # pick up webhook-written changes
        now = datetime.now(timezone.utc)

        for guild in self.guilds:
            gid = str(guild.id)
            paid = {t: self.role(guild, t) for t in config.PAID_ROLES}
            member_role = self.role(guild, config.ROLE_MEMBER)

            # Build desired tier per user, dropping expired entries.
            desired = {}
            changed = False
            for uid, info in list(self.subs.get(gid, {}).items()):
                exp = info.get("expires")
                if exp and datetime.fromisoformat(exp) <= now:
                    self.subs[gid].pop(uid, None)
                    changed = True
                    continue
                desired[uid] = info["tier"]
            if changed:
                save_subs(self.subs)

            for member in guild.members:
                if member.bot:
                    continue
                want = desired.get(str(member.id))
                has = [t for t in config.PAID_ROLES if paid[t] and paid[t] in member.roles]

                if want:
                    for t in has:                      # strip wrong tiers
                        if t != want:
                            await member.remove_roles(paid[t], reason="Tier change")
                    if want not in has and paid.get(want):
                        await member.add_roles(paid[want], reason="Membership active")
                        if member_role and member_role not in member.roles:
                            await member.add_roles(member_role, reason="Base access")
                        await self.log_payment(guild, f"✅ **{member}** → **{want}** (synced).")
                elif has:                              # no active membership
                    for t in has:
                        await member.remove_roles(paid[t], reason="No active membership")
                    await self.log_payment(
                        guild, f"🚫 **{member}** lost {', '.join(has)} (membership ended).")


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
            f"👋 Welcome to **{config.SERVER_NAME}**, {member.mention}! "
            f"Head to **#verify** to unlock the server, then check "
            f"**#how-to-upgrade** for full Premium access via Whop.")


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
        title=f"✅ Verify to enter {config.SERVER_NAME}",
        description=(
            "Click **Verify & Enter** below to confirm you've read the **#rules** "
            "and unlock the community (free access).\n\n"
            "**Want full signals, live trading & the analyst desk?**\n"
            "Premium access is sold and verified through **Whop** — tap "
            "*Get Premium on Whop*. Your role is assigned automatically after "
            "purchase.\n\n"
            "_By verifying you agree these signals are **educational, not financial "
            "advice**. Trade at your own risk._"),
        colour=config.BRAND_COLOR)
    embed.set_footer(text=config.SERVER_TAGLINE)

    view = VerifyView()
    view.add_item(discord.ui.Button(
        label="💎 Get Premium on Whop", style=discord.ButtonStyle.link,
        url=config.WHOP_STORE_URL))
    await ch.send(embed=embed, view=view)
    await interaction.response.send_message("Posted verify section.", ephemeral=True)


@bot.tree.command(description="Post the Whop upgrade card in #how-to-upgrade.")
@admin_only()
async def post_upgrade(interaction: discord.Interaction):
    ch = discord.utils.get(interaction.guild.text_channels, name="how-to-upgrade")
    if not ch:
        await interaction.response.send_message(
            "No #how-to-upgrade channel found.", ephemeral=True)
        return
    embed = discord.Embed(
        title="💎 Unlock Premium Access",
        description=(
            "All paid access runs through **Whop** — secure checkout, instant "
            "Discord role, manage or cancel anytime.\n\n"
            f"**💚 {config.ROLE_PREMIUM}** — full signals (crypto · forex · "
            "stocks/options), premium chat, education & trade journal.\n"
            f"**🧡 {config.ROLE_ELITE}** — everything in Premium **plus** live "
            "trading, the analyst desk & 1:1 portfolio reviews.\n"
            f"**💜 {config.ROLE_LIFETIME}** — Elite access, forever. One payment.\n\n"
            "Tap the button to choose your plan. Access is granted automatically "
            "after checkout — issues? Open a ticket in **#support-tickets**."),
        colour=config.BRAND_COLOR)
    embed.set_footer(text=f"{config.SERVER_NAME} • {config.SERVER_TAGLINE}")
    await ch.send(embed=embed, view=upgrade_view())
    await interaction.response.send_message("Posted upgrade card.", ephemeral=True)


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
@post_upgrade.error
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
