# Diagnostic: Running the Massage-Booking Site on Render's Free Tier

**Date:** 2026-07-19
**Question:** Is the Render free plan (512 MB RAM, 0.1 CPU, $0/month) viable for this
Django site at ~10–20 visitors/day with one frequently-logged-in admin — without paying
anything?

## Verdict

**Yes — the free plan is viable for this traffic level, at a total cost of $0/month**,
*provided* the four structural gaps below are closed with external free services and the
listed code/config fixes are applied. None of the gaps can be solved on Render's free
instance alone; all four have solid free solutions.

| Gap on Render free | Consequence if ignored | Free solution (decided) |
|---|---|---|
| No persistent disk | Every deploy/restart deletes `media/` (gallery, masseur photos, logo) | **Cloudinary** free plan (25 credits/mo) |
| Free Postgres expires after 30 days | Database deleted (14-day grace period), all reservations lost | **Neon** free plan (0.5 GB, no expiry) |
| Instance spins down after 15 min idle | Next visitor waits 30–60 s; looks broken | **24/7 external ping** + `/healthz` |
| Nothing serves static files with `DEBUG=False` | Site loads with no CSS/JS/images | **WhiteNoise** (in-process, free) |

The traffic math is comfortable: 20 visitors/day ≈ a few hundred requests/day. Even at
0.1 CPU (~10× slower than one full core), a warm Django page render taking 100–300 ms of
CPU still responds in 1–3 s worst case, and pages are rarely requested concurrently at
this volume. The real risks are not capacity — they are the free-tier resource quotas and
the unthrottled endpoints, both covered below.

---

## 1. Free-quota budget (the numbers)

### Render free web service
- 512 MB RAM, 0.1 CPU, spins down after **15 min** without inbound traffic.
- **750 instance-hours/month** per workspace. A 24/7-pinged single service uses
  ~730 h/month — it fits, but only if this is the **only** free web service in the
  workspace. A second free service pinged 24/7 would exceed the quota and both would
  suspend until the next month.
- 100 GB/month outbound bandwidth — far above what this site can generate, especially
  once images are served by Cloudinary's CDN instead of the dyno.
- 500 build minutes/month — a `pip install` build is ~2–4 min; dozens of deploys fit.
- No SSH, no one-off jobs: `migrate` must run in the build/start command, and
  `createsuperuser` / `populate_db` must be handled via a one-time start-command hack or
  a data migration.

### Neon free Postgres
- 0.5 GB storage per project — this schema (users, reservations, comments, image
  *metadata*) will use a few MB; years of headroom.
- **100 compute-unit-hours/month.** Compute suspends after 5 min idle and suspended time
  is free. This is the one quota that interacts badly with a 24/7 keep-alive — see §3.
- First query after suspend has ~1 s wake-up latency. Acceptable.
- Requires TLS: the `DATABASE_URL` must carry `?sslmode=require`.

### Cloudinary free
- **25 credits/month**, where 1 credit = 1 GB storage **or** 1 GB bandwidth **or** 1 000
  transformations, pooled. A gallery of a few hundred photos ≈ 1–2 GB storage
  (1–2 credits) plus modest bandwidth at 20 visitors/day. Comfortable margin.
- Overage does not bill — it **suspends the account**, so image delivery would stop. At
  this traffic that requires either a viral event or hotlink abuse; acceptable risk.

### Uptime monitoring
- **UptimeRobot free (as originally chosen): caution.** Since December 2024 its ToS
  restrict the free plan to *personal, non-commercial* use. A massage studio's booking
  site is commercial use — the account could be suspended, silently killing both the
  keep-alive and the down-alerts.
- **Recommended compliant alternatives (both free, both email on failure):**
  - **cron-job.org** — free scheduled HTTP calls down to 1-min intervals, sends failure
    and recovery e-mails. Use as the 5-min keep-alive + alerting.
  - **Better Stack free plan** — 10 monitors at 3-min interval with e-mail alerts, as a
    more polished monitoring UI.
- Alerts go to **yaneyanev2807@gmail.com** (configured in the monitor, not in code).

**Bottom line: $0/month total across Render + Neon + Cloudinary + cron-job.org.**

---

## 2. Gunicorn configuration for 512 MB / 0.1 CPU

Gunicorn is currently **not in `requirements.txt`** — it must be added (pinned).

Recommended start command:

```bash
python manage.py migrate --noinput && \
gunicorn massageProject.wsgi:application \
  --bind 0.0.0.0:$PORT \
  --workers 1 \
  --worker-class gthread \
  --threads 4 \
  --preload \
  --max-requests 500 --max-requests-jitter 100 \
  --timeout 120 \
  --worker-tmp-dir /dev/shm \
  --access-logfile - --error-logfile -
```

Rationale, setting by setting:

- **`--workers 1`.** The usual `2×CPU+1` formula assumes whole cores; at 0.1 CPU extra
  worker processes only multiply memory (~120–180 MB RSS each for this app) while
  time-slicing the same CPU sliver. One worker keeps total RSS ≈ 150–200 MB, leaving
  ~300 MB headroom for Pillow image operations and OS overhead inside the 512 MB cap.
  **Critically, a single process also makes the existing rate limiting correct**: the
  project has no `CACHES` setting, so `django-ratelimit` and the comment throttle use
  per-process `LocMemCache`. With one worker that cache is effectively global; with
  multiple workers every limit would silently become N× looser.
- **`--worker-class gthread --threads 4`.** The request mix is I/O-bound at the tail:
  Neon queries over TLS to another host, Cloudinary uploads, Turnstile verification
  calls, Gmail API sends. Threads let one slow external call (or one visitor on a cold
  Neon wake) not block the health-check ping — which matters, because a blocked ping
  looks like downtime to the monitor. Threads share the worker's memory; 4 costs almost
  nothing.
- **`--preload`.** Loads Django once in the master; recycled workers fork instead of
  re-importing the app, which on 0.1 CPU saves a multi-second respawn stall.
- **`--max-requests 500 --max-requests-jitter 100`.** Recycles the worker periodically
  so any slow memory growth (Pillow, template caches) can never creep toward the 512 MB
  OOM kill. At this traffic that is roughly one recycle every 1–2 days.
- **`--timeout 120`.** Generous on purpose: at 0.1 CPU a worker that is merely slow
  (cold Neon wake + big admin page) must not be shot by the heartbeat and dropped as a
  502. Slow-request DoS is not a concern here — Render's proxy terminates clients and
  buffers requests, so slowloris-style attacks don't reach gunicorn.
- **`--worker-tmp-dir /dev/shm`.** Standard on Render: the heartbeat file lives in RAM
  instead of the container's slower disk layer, avoiding spurious worker timeouts.
- **`migrate` in the start command** because the free tier has no SSH/one-off jobs. It
  runs on every deploy/restart; with no pending migrations it takes ~1–2 s against Neon.

Build command:

```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py compilemessages
```

---

## 3. Keep-alive + health check design (and the Neon quota trap)

The naive design — one monitor hitting a DB-checking `/healthz` every 5 minutes —
**would keep Neon's compute awake 24/7 ≈ 180 CU-hours/month, exceeding the 100 CU-hour
free quota** before any real traffic. Likewise, hitting the homepage would run the full
ORM stack per ping. The fix is to split shallow and deep checks:

1. **`/healthz` (shallow)** — returns `200 ok` from Django *without touching the
   database*. Proves the instance is up, the port answers, and Django routes requests.
   - Monitor: cron-job.org, **every 5 min, 24/7** → keeps Render awake, never wakes Neon.
2. **`/healthz?db=1` (deep)** — additionally runs `SELECT 1` on the default connection
   and returns 500 with a short reason if it fails. Proves the database is reachable.
   - Monitor: second cron-job.org job, **every 30–60 min** → Neon wakes for ~5 min per
     check ≈ 6–12 CU-hours/month. Combined with real traffic (20 visits/day ≈ 15
     CU-hours/month), total stays well under 100.
3. Both monitors e-mail **yaneyanev2807@gmail.com** on failure and recovery. Deep-check
   failures catch a dead/misconfigured database within an hour; for a booking site with
   20 visitors/day that detection latency is proportionate.

Two settings interact with this design:

- **`CONN_MAX_AGE` must stay 0 (Django's default — do not set it).** A persistent
  connection would hold Neon awake between requests and drain the CU-hour quota. Fresh
  connections cost ~50–100 ms against Neon; irrelevant at this volume.
- The shallow `/healthz` must be exempt from `SECURE_SSL_REDIRECT` complications — see
  the `SECURE_PROXY_SSL_HEADER` fix in §5, which resolves this globally.

---

## 4. Spam / take-down surface audit

Context for severity: with 0.1 CPU, *any* determined attacker can saturate the CPU with
plain page requests — no application setting prevents that. The goals here are
(a) stop the *cheap* abuse that actually happens to small sites (bot spam, e-mail-send
abuse, form flooding), and (b) make sure abuse can't cost money or data. For volumetric
protection, the single best free move is **putting Cloudflare's free plan in front of
the site** (the project already uses Cloudflare Turnstile, so an account exists): it
gives DDoS filtering, caching of static assets, and hides the Render origin URL.

### What is already good ✅

| Area | State |
|---|---|
| Auth modal endpoints (`check-email`, `send-code`, `verify-code`, `register`, `login-password`) | `django-ratelimit` per-IP **and** per-e-mail limits (3–10/min), `request.limited` handled with proper 429 JSON |
| E-mail-sending signup path | Cloudflare **Turnstile** verified server-side on `send-code` and `register` |
| Comment content | Length-capped (2 000 chars), login required, `is_reviewed=False` moderation gate, bleach sanitisation of admin rich text |
| Security headers | HSTS, secure cookies, nosniff, `X_FRAME_OPTIONS=DENY` under `DEBUG=False` |
| Rosetta | Mounted only in `DEBUG`, staff-only access function |
| Signup via allauth | Closed by `ClosedSignupAccountAdapter`; Google flow forces the complete-profile form |

### Findings to fix 🔴 (ordered by severity)

1. **`BrandedPasswordResetView` has no rate limit and no Turnstile** —
   `accounts/urls.py` → `password-reset/`. It is an *unauthenticated endpoint that sends
   e-mail*. A bot can flood arbitrary inboxes from your Gmail identity (reputation
   damage, Gmail API quota burn) while each request costs your 0.1 CPU a full
   render+send. **Fix:** apply the same `@ratelimit(key='ip', rate='3/h')` +
   `key='post:email', rate='3/h'` pattern used by `send_code`, and verify a Turnstile
   token in `form_valid`.
2. **`check_availability` (`/check-availability/`) is public with no rate limit** —
   `main_app/views.py:21`. Each call is several ORM queries plus slot generation. It's
   the cheapest way for a bot to keep the CPU busy and (with the keep-alive) the
   instance awake against Neon's quota. **Fix:** `@ratelimit(key='ip', rate='30/m',
   block=True)` — generous for the booking UI's real usage, hostile to loops.
3. **Comment throttle trusts client-supplied `X-Forwarded-For`** —
   `main_app/views.py:272` takes the *first* entry of XFF, which the client sets freely,
   so the 1/min limit is bypassable by rotating a fake header. Severity is softened by
   `@login_required`, but a spam account then floods the moderation queue. **Fix:**
   replace the hand-rolled limiter with `@ratelimit(key='user', rate='1/m',
   block=True)` (keys on the authenticated user; no header trust), or key on
   `REMOTE_ADDR`/Render's rightmost-proxy semantics.
4. **`send-code` costs a Turnstile HTTP verification before its cheap checks** — the
   order is fine, but note every hit also makes an outbound HTTPS call to Cloudflare on
   your CPU. The existing 5/min IP limit runs *before* the view body (good). No change
   needed beyond keeping the decorator order.
5. **Admin at a well-known path with a single powerful account** — `/{lang}/admin/` is
   guessable; login attempts hit Django auth at full price. With one admin user, the
   cheapest hardening is: strong unique password (already implied), and optionally
   renaming the path (`path('sitemanage/', admin.site.urls)`). Low priority — Django's
   admin login is not rate-limited by default, so if left at `/admin/`, add a
   `ratelimit` on the admin login or rely on Cloudflare's bot fight mode.
6. **User-enumeration by design** — `check-email` returns `exists: true/false` and is
   rate-limited (8/min per e-mail, 10/min per IP). This is a deliberate UX trade-off in
   the modal flow; the limits make bulk enumeration slow. Accepted risk, documented.
7. **Request body size** — Django's defaults (`DATA_UPLOAD_MAX_MEMORY_SIZE` = 2.5 MB)
   already cap anonymous POST bodies; image uploads happen only through the
   staff-only admin. No change needed; do **not** raise these defaults.

### Explicitly out of scope for the free plan
Volumetric DDoS resistance. 0.1 CPU cannot absorb one; Cloudflare-in-front is the only
free mitigation, and even then a targeted attack means downtime, not data loss. For a
10–20-visitor/day local business this is an acceptable and normal posture.

---

## 5. Deployment blockers found in the codebase (must fix before first deploy)

These are not part of the hardening scope but the diagnostic would be dishonest without
them — the site **will not come up correctly** on Render today:

1. **`gunicorn` is not in `requirements.txt`.** Render's suggested start command will
   fail at boot.
2. **No `STATIC_ROOT` and no WhiteNoise.** `STATICFILES_DIRS` points at the *source*
   `staticfiles/` directory, `STATIC_ROOT` is undefined → `collectstatic` fails, and
   with `DEBUG=False` nothing serves static files at all (no CSS/JS). Fix: add
   `STATIC_ROOT = BASE_DIR / 'static_collected'`, add `whitenoise` with
   `CompressedManifestStaticFilesStorage`, insert its middleware right after
   `SecurityMiddleware`.
3. **`SECURE_SSL_REDIRECT = True` without `SECURE_PROXY_SSL_HEADER`.** Render
   terminates TLS at its proxy and forwards plain HTTP with `X-Forwarded-Proto: https`.
   Without `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')`, Django sees
   every request as insecure → **infinite redirect loop on every page**.
4. **Media URLs are only served when `DEBUG=True`** (`urls.py` static() block) — already
   known (former bug B14); resolved by the Cloudinary decision, since `MEDIA_URL` will
   point at Cloudinary's CDN.
5. **Both `psycopg2` and `psycopg2-binary` are pinned.** The source `psycopg2` needs
   libpq build headers at build time and wastes build minutes; keep only
   `psycopg2-binary`.
6. **`TIME_ZONE = 'UTC'` with a 2-hour booking lead-time rule.** Not a Render issue, but
   worth noting: `timezone.localtime()` in `check_availability` resolves to UTC, so the
   lead-time and "today's slots" logic shifts by 2–3 h relative to Bulgarian local time.
   Consider `TIME_ZONE = 'Europe/Sofia'` (with `USE_TZ = True` unchanged) as part of the
   deploy config review.
7. **Secrets via environment.** `.env` is read if present, but on Render all of
   `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `DATABASE_URL` (Neon, with
   `sslmode=require`), `CSRF_TRUSTED_ORIGINS` (needed for the `onrender.com` /custom
   domain), Turnstile keys, Gmail API keys, Google OAuth keys, and Cloudinary keys must
   be set in the dashboard. `ALLOWED_HOSTS` must include the `onrender.com` hostname
   (and the custom domain if added).

---

## 6. When the free plan stops being the right answer

Upgrade to **Starter ($7/mo, 0.5 CPU, no spin-down)** only if one of these actually
happens — none is expected at the stated traffic:

- Cold-start complaints persist despite the keep-alive (e.g., free-hours exhaustion from
  a second service, or Render throttling pinged free instances).
- Real traffic grows past ~a few hundred visitors/day and pages feel slow while warm
  (0.1 CPU saturation).
- The monthly Neon CU-hours or Cloudinary credits are exceeded in practice (check both
  dashboards after the first month).
- The business starts depending on the site enough that "best-effort free tier" is no
  longer an acceptable SLA for taking paid bookings.

## 7. Implementation checklist (for the follow-up task)

1. Add `gunicorn` + `whitenoise` + `dj-database-url`-compatible Neon URL; remove
   source `psycopg2`.
2. `STATIC_ROOT`, WhiteNoise storage + middleware.
3. `SECURE_PROXY_SSL_HEADER`, `CSRF_TRUSTED_ORIGINS`, `ALLOWED_HOSTS` from env.
4. `render.yaml` (or dashboard config) with the build/start commands from §2.
5. `/healthz` view (shallow + `?db=1` deep variant).
6. Rate limits: password reset (+ Turnstile), `check_availability`, comment throttle
   keyed on user.
7. Cloudinary: `django-cloudinary-storage`, `DEFAULT_FILE_STORAGE`, env keys.
8. Create Neon project (Frankfurt), Cloudinary account, cron-job.org monitors
   (5-min shallow 24/7, 60-min deep, e-mail alerts to yaneyanev2807@gmail.com).
9. Optional: Cloudflare free plan in front; `Europe/Sofia` time zone review.

## Sources

- [Render — Deploy for Free (free tier limits, spin-down, instance hours)](https://render.com/docs/free)
- [Render — Pricing](https://render.com/pricing)
- [Neon — Plans (free plan CU-hours, storage, scale-to-zero)](https://neon.com/docs/introduction/plans)
- [Neon — Free plan limits FAQ](https://neon.com/faqs/free-plan-limits-and-quotas)
- [Cloudinary — Pricing and credit model](https://cloudinary.com/pricing)
- [Cloudinary — How credits work](https://cloudinary.com/documentation/developer_onboarding_faq_credits)
- [UptimeRobot — Pricing (free plan, non-commercial restriction)](https://uptimerobot.com/pricing/)
- [UptimeRobot free plan limits in 2026 (commercial-use ban analysis)](https://stillup.org/blog/uptimerobot-free-plan-limits)
