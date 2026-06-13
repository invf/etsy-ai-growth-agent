# Day 28 — Production Smoke Test Runbook

Goal: confirm the full value loop works end-to-end in production with a **real
Etsy store** and **live AI**, then invite beta users.

Prod URLs:
- Frontend (Vercel): https://etsy-ai-growth-agent.vercel.app
- Backend (Render): https://etsy-agent-backend.onrender.com

---

## 0. Prerequisites — API keys (the only real blockers)

### Etsy app → `ETSY_CLIENT_ID` + `ETSY_CLIENT_SECRET`
1. Go to https://www.etsy.com/developers/your-apps → **Create a New App**.
2. Fill name + description (e.g. "Etsy AI Growth Agent").
3. After creation Etsy shows:
   - **Keystring** → this is `ETSY_CLIENT_ID`
   - **Shared Secret** → this is `ETSY_CLIENT_SECRET`
4. In the app's OAuth settings, add this **Callback / Redirect URI** exactly:
   ```
   https://etsy-agent-backend.onrender.com/v1/stores/connect/callback
   ```
5. Scopes are requested at login time by the app — no config needed. The app
   requests: `listings_r listings_w shops_r shops_w transactions_r`.
6. A new app starts in limited/personal mode — enough to test with **your own
   shop**. Apply for commercial access later for higher rate limits.

### Anthropic → `ANTHROPIC_API_KEY`
1. https://console.anthropic.com → **Settings → API Keys → Create Key**.
2. Add billing / credits to the account (live calls cost money).
3. Models used: `claude-fable-5` (primary), `claude-haiku-4-5` (fast). Make sure
   the account has access to them.

### Where to paste (Render → Env Group `etsy-agent-secrets`)
- `ETSY_CLIENT_ID`, `ETSY_CLIENT_SECRET`, `ANTHROPIC_API_KEY`
- Confirm already set: `ETSY_REDIRECT_URI` =
  `https://etsy-agent-backend.onrender.com/v1/stores/connect/callback`
- Save → backend + worker redeploy.

---

## 1. Pre-flight checks
- [ ] `curl https://etsy-agent-backend.onrender.com/health` → `{"status":"ok"}`
- [ ] Frontend loads, can register/login.
- [ ] Render: backend + worker both **Live**; worker logs show `celery@... ready`.
- [ ] Sentry: both projects receiving the deploy (no startup errors).

## 2. Onboarding + connect store
- [ ] Register a fresh account → redirected into the onboarding wizard.
- [ ] Step "Connect Etsy store" → **Connect Etsy Store** → redirected to Etsy.
- [ ] Approve on Etsy → redirected back to `/dashboard/stores?connected=true`.
- [ ] Store card shows shop name + listing count.

## 3. Sync listings
- [ ] Click **Sync** on the store → status goes `syncing` → done.
- [ ] Worker logs show `sync_store_listings` running, no errors.
- [ ] Listings table populates with real listings.

## 4. SEO analysis (live AI — costs credits)
- [ ] Open a listing → **Analyze**.
- [ ] SSE stream shows progress → completes; SEO score + recommendations appear.
- [ ] Credits balance decremented on the dashboard.
- [ ] Worker logs show the Anthropic call succeeded (no 401/credit errors).

## 5. Apply optimization
- [ ] **Create optimizations** → pending rows appear.
- [ ] **Approve** one → **Apply** → status `applied`.
- [ ] Verify the change is reflected on the live Etsy listing (title/tags).

## 6. Daily agent (optional — scheduled 07:00 UTC)
- [ ] To test now without waiting: trigger `tasks.agent.run_daily_agent` for the
      store (Render Shell / one-off job) OR wait for the 07:00 UTC beat tick.
- [ ] Agent run completes; a daily-digest **notification** appears in the bell;
      digest email sent (if SendGrid key set); `store.health_score` updated.

## 7. Sentry verification
- [ ] Trigger a deliberate error (e.g. hit a non-existent protected route or a
      forced 500) → it appears in the Sentry **backend** project within ~1 min.
- [ ] Trigger a frontend error → appears in the Sentry **frontend** project.

## 8. Billing (optional, Paddle sandbox)
- [ ] Needs `PADDLE_*` keys + price IDs. On `/pricing`, complete a sandbox
      checkout → webhook allocates credits → `/billing/subscription` reflects it.

---

## 9. Invite beta users
- [ ] Share the Vercel URL with ~5 testers.
- [ ] Watch Sentry for errors + Render logs for failures during their sessions.
- [ ] Collect feedback on the onboarding → first-recommendation flow.

## Troubleshooting
- **OAuth redirect mismatch** → the Etsy callback URI must match
  `ETSY_REDIRECT_URI` byte-for-byte (https, no trailing slash).
- **AI 401 / invalid key** → check `ANTHROPIC_API_KEY` in the env group + model
  access. **Insufficient credits** → top up the Anthropic account.
- **First request slow (~50s)** → free backend cold start; not an error.
- **CORS error** → backend `FRONTEND_URL` must equal the Vercel domain.
