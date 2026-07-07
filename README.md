# NQ Trading Discord Server Scaffold

`setup_server.py` builds out the full Discord server structure (roles,
categories, channels, permissions, and intro copy) for a paid NQ futures
trading community, defined entirely by the `SERVER_CONFIG` dict at the top
of the script. It's idempotent — re-running it reconciles the existing
server to match the config instead of creating duplicates.

## 1. Create the bot in the Discord Developer Portal

1. Go to https://discord.com/developers/applications → **New Application**.
   Name it whatever you like (e.g. "Server Setup Bot").
2. Open the **Bot** tab → **Reset Token** → copy the token. This goes in
   `.env` as `DISCORD_TOKEN`. Keep it secret — anyone with this token has
   full control of the bot.
3. You do **not** need to enable any Privileged Gateway Intents (Presence,
   Server Members, Message Content) — this script only creates roles/
   channels and sends messages, it doesn't read them.

## 2. Invite the bot to your server

1. Go to the **OAuth2 → URL Generator** tab.
2. Under **Scopes**, check `bot`.
3. Under **Bot Permissions**, check **Administrator** (simplest option for
   a one-time setup script), or if you'd rather grant the minimum, check:
   `Manage Roles`, `Manage Channels`, `Manage Messages`, `View Channels`,
   `Send Messages`, `Read Message History`, `Connect`.
4. Copy the generated URL, open it in your browser, and authorize the bot
   into your server.
5. **Move the bot's role up the hierarchy.** Discord adds the bot's role
   near the bottom of the role list by default. Go to
   **Server Settings → Roles** and drag the bot's role **above** where
   `Admin` should sit. The script can only manage roles/permissions below
   its own highest role — if you skip this step, role reordering and some
   permission edits will fail or be skipped (with a warning in the logs).

## 3. Get your Guild (server) ID

1. In Discord, go to **User Settings → Advanced** and enable **Developer
   Mode**.
2. Right-click your server's icon → **Copy Server ID**. This goes in
   `.env` as `GUILD_ID`.

## 4. Configure and run

```bash
cp .env.example .env
# edit .env and fill in DISCORD_TOKEN and GUILD_ID

pip install -r requirements.txt
python setup_server.py
```

The script will:

1. Create (or reuse) the `Admin`, `Mod`, `Mentorship`, `Trader`, and
   `Member` roles, in that hierarchy order, and try to position them
   directly below the bot's own role.
2. Create (or reuse) each category and its channels in order, applying
   the correct visibility and send-permission overwrites:
   - Public categories are visible to `@everyone`.
   - Locked categories (e.g. `Trader`-only) are hidden from `@everyone`
     and visible only to the named role. `Admin` and `Mod` always have
     full access regardless of locks.
   - `post_only` channels are read-only for everyone except `Admin`/`Mod`.
3. Seed intro channels (`welcome`, `rules`, `disclaimer`,
   `join-the-system`, `course-hub`) with their copy, and pin the first
   message in `disclaimer`. Channels that already contain messages are
   left alone on subsequent runs.
4. Write `server_map.json` with the created role/category/channel IDs
   (useful for the Whop role-gating step) and print a summary table of
   what was created vs. reused.

Re-run the script any time you change `SERVER_CONFIG` — it will create
anything new and update permissions/colors on anything that already
exists, without duplicating roles or channels.

## Notes

- The script exits after a single run; it isn't meant to run as a
  long-lived bot process.
- If `GUILD_ID` is wrong or the bot hasn't been invited to that server,
  the script logs an error and exits without making changes.
- Role colors/hoist/mentionable settings are kept in sync on existing
  roles too, so editing `SERVER_CONFIG` and re-running will update them.
