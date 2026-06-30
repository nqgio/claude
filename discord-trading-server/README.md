# 📈 Trading Community Discord — Server-as-Code

A complete, ready-to-deploy Discord server for a trading community, built
programmatically. One script builds every **role**, **category**, **channel**,
and **permission**; a runtime bot handles **verification**, **self-assignable
notification roles**, and **free vs. paid access** (with optional Stripe
integration).

You can't literally "download" a Discord server, so this is the next best
thing: code that constructs the entire server in your own guild and a bot that
runs it day-to-day.

---

## What you get

### Roles (highest → lowest)
**Staff:** Owner · Admin · Moderator · Support
**Content team:** Head Analyst · Analyst
**Bots:** Bot
**Paid tiers:** 💜 Lifetime VIP · 🧡 Elite · 💚 Premium
**Recognition:** Server Booster · Trader of the Month · OG Member
**Notification pings (self-assign):** Crypto · Forex · Stocks · Options · News · Events
**Base:** Member (free, verified) · Unverified (new joiners)

### Channels (by category)
- **👋 START HERE** — welcome, rules, verify, announcements, faq, how-to-upgrade, self-roles
- **💬 COMMUNITY** — general-chat, introductions, wins-and-losses, charts-and-ideas, off-topic, memes, bot-commands
- **🆓 FREE ZONE** — free-signals, market-news, daily-watchlist, education-basics
- **💎 PREMIUM** *(paid)* — premium-signals, crypto/forex/stocks-options, scalp & swing setups, premium-chat, trade-journal (forum)
- **🏆 ELITE** *(top paid)* — elite-lounge, analyst-desk, portfolio-reviews, live-trading
- **🎓 EDUCATION** *(paid)* — trading-courses, strategy-library, risk-management, q&a-with-analysts
- **🔊 VOICE** — general/trading/premium/elite voice, live analysis stream, AFK
- **🛠️ STAFF** *(private)* — staff-chat, analyst-room, mod-log, support-tickets, payment-log, staff voice

Permissions are wired so the public sees only **#verify** until they verify;
free members get the community + free zone; paid tiers unlock premium/elite;
signal channels are read-only feeds (only analysts/staff post).

---

## Setup

### 1. Create the bot application
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) → **New Application**.
2. **Bot** tab → **Reset Token** → copy it.
3. Under **Privileged Gateway Intents**, enable **Server Members Intent**.
4. **OAuth2 → URL Generator**: scopes `bot` + `applications.commands`;
   bot permission **Administrator**. Open the generated URL and invite the bot
   to your server.
5. In **Server Settings → Roles**, drag the bot's role **near the top** (it must
   sit above every role it creates).

### 2. Configure
```bash
cd discord-trading-server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit .env: DISCORD_TOKEN, GUILD_ID
```
Get `GUILD_ID`: Discord → Settings → Advanced → enable **Developer Mode**,
then right-click your server icon → **Copy Server ID**.

### 3. Build the server
```bash
python setup_server.py
# Re-running is safe (idempotent). To tear down config-managed items first:
python setup_server.py --wipe
```

### 4. Run the bot
```bash
python bot.py
```
Then, in any channel, as an admin run:
- `/post_verify` — posts the verify message in **#verify**
- `/post_selfroles` — posts the notification-role menu in **#self-roles**

Finally paste the starter copy from [`content/channel_messages.md`](content/channel_messages.md)
into the matching channels.

---

## Managing access

### Free access
New members get **Unverified** automatically and only see **#verify**. Reacting
✅ there swaps them to **Member** — the free tier.

### Paid access
Admin slash commands (require **Manage Server**):
```
/grant  @user Premium 30     # Premium for 30 days
/grant  @user Elite          # Elite, no expiry (manual)
/grant  @user "Lifetime VIP" # lifetime
/revoke @user                # remove all paid tiers
/whois  @user                # show tier + expiry
```
Subscriptions are tracked in `data/subscriptions.json`. A background task runs
every 6 hours and auto-removes expired tiers, logging to **#payment-log**.

### Automated payments (optional)
`webhook_stripe.py` is a reference Flask endpoint that converts Stripe checkout
events into tier grants:
1. Map your real Stripe Price IDs in `PRICE_TIERS`.
2. Pass the buyer's Discord ID as `client_reference_id` in Checkout.
3. Deploy the endpoint and register it as a Stripe webhook for
   `checkout.session.completed` and `customer.subscription.deleted`.

It writes the same `subscriptions.json` the bot reads. (Works the same way for
Whop, Gumroad, etc. — just adapt the webhook handler.)

---

## Customizing
Everything structural lives in **`config.py`** — edit role names, colours,
channel lists, and who-can-see-what, then re-run `setup_server.py`. The build
logic in `setup_server.py` and the runtime logic in `bot.py` read from it, so
you rarely need to touch them.

## Files
| File | Purpose |
|------|---------|
| `config.py` | All roles, categories, channels & permission rules |
| `setup_server.py` | Builds the server from config (idempotent; `--wipe` option) |
| `bot.py` | Runtime: verify, self-roles, premium grant/revoke/expiry |
| `webhook_stripe.py` | Optional Stripe → tier-grant webhook |
| `content/channel_messages.md` | Copy-paste welcome/rules/faq/upgrade text |

---

## ⚠️ Disclaimer
Trading involves risk. Signals and content shared via a server built with this
template are educational, not financial advice. Make sure your server complies
with Discord's Terms of Service and your local regulations (especially around
paid financial communities).
