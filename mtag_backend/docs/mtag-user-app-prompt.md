# One-Shot Build Prompt — M-Tag User App (Flutter, Claymorphic)

> Paste everything below the line into a fresh Opus 5 / Claude Code session that has
> the `mtag_backend` repo available. It is self-contained.

---

You are building a **new production Flutter application** from scratch: the **M-Tag User App** —
the consumer-facing mobile app for the M-Tag electronic toll collection system on the Malir
Expressway (Shahra-e-Bhutto), Karachi. The Django REST backend already exists and is in this
repo at `mtag_backend/`. **Read the backend source before writing client code** — the contract
below is accurate as of today, but verify anything you depend on.

Build it in a new sibling directory: `mtag_user_app/`.

---

## 1. What the app is for

A tag holder (a normal motorist, not an operator) installs this app to:

1. **Check balance** on every M-Tag they own.
2. **Top up** that balance — JazzCash, Easypaisa, card, or "pay cash at a booth" instructions.
3. See **how many tags** they hold and each tag's status/expiry.
4. See **which vehicles** are registered against those tags.
5. See **tag information** — serial, TID, status, expiry, last scan, linked vehicle.
6. See **trip history** (entry plaza → exit plaza, fare charged) and **transaction history**.
7. Look up **fares** between plazas for their vehicle category.

This is a **read-mostly wallet app**. It must never expose operator or admin capability:
no tag issuance, no booth assignment, no vehicle registration, no fare editing, no gate control.

---

## 2. Domain model (from the backend — do not re-invent it)

The ownership chain is the single most important thing to internalise:

```
User (phone is the username; also has cnic, full_name, user_role, status)
  └── has many Vehicle           (Vehicle.owner → User, PROTECT)
        ├── has ONE Tag          (Tag.vehicle, OneToOne, nullable)
        └── has ONE Account      (Account.vehicle, OneToOne)  ← the wallet
              └── has many Transaction
              └── has many TopupRequest
```

Consequences you must respect in the UI:

- **The wallet belongs to the vehicle, not to the user.** A user with three vehicles has
  three separate balances. There is no single "user balance" — any "total balance" you show
  is a client-side sum you computed, and you must label it as such (e.g. "Total across 3 tags").
- **One tag per vehicle.** "Total tags" == count of the user's vehicles that have a tag row.
  A vehicle can exist with no tag (tag reissue in progress).
- Money is `DecimalField` server-side and arrives as a **JSON string** (`"1250.00"`). Never
  parse it into `double` for arithmetic you display — use `Decimal` (package `decimal`) or
  integer paisa. Format for display with `intl` as `Rs. 1,250`.

### Enums (mirror these exactly; render the labels, not the raw values)

`VehicleType` — this is the **fare class**, from the official toll notification:

| value | label |
|---|---|
| `car` | Car / Jeep / Taxi / Pickup |
| `wagon` | Wagon / Hiace |
| `coach` | Coach / Coaster / Mini Bus |
| `large_bus` | Large Bus |
| `truck_2axle` | 2 Axle Truck |
| `truck_3axle` | 3 Axle Truck |
| `truck_4axle` | 4 or More Axle Truck |
| `motorcycle` | Motorcycle — **not permitted on the expressway** |

`TagStatus`: `active`, `expired`, `suspended`, `deactivated`
`VehicleStatus`: `active`, `inactive`, `suspended`
`TransactionType`: `toll_deduction`, `topup`, `refund`, `transfer_out`, `transfer_in`
`TransactionStatus`: `success`, `failed`, `pending`
`TransactionSource`: `online_exit`, `offline_exit_sync`, `topup_jazzcash`, `topup_cash`, `refund`
`TopupStatus`: `pending`, `success`, `failed`
`TollTrip.status`: read `apps/tolls/models.py` for the current choices (`active` / `completed` /
others) — do not guess.

### Business rules the app must surface

- **Entry requires balance ≥ Rs. 50.** Below that the barrier will not open. Show a hard
  warning state under Rs. 50 and a soft "top up soon" state under Rs. 200.
- **Minimum top-up is Rs. 100** (enforced server-side in `InitiateTopupSerializer` and
  `JazzCashService.initiate_topup`). Enforce it client-side too so the user isn't bounced.
- A tag is only usable when `is_valid` — assigned to a vehicle **and** `status == active`
  **and** `expiry_date >= today`. The backend exposes `is_valid` as a read-only field; show it
  as the authoritative badge rather than recomputing it.
- Fares are **directional**: A→B and B→A are separate rows in `fare_matrix`. Never assume symmetry.
- Booths can operate **offline** and sync every 30s, so a toll deduction can appear in history
  minutes after the trip. Never present transaction history as real-time; timestamp everything
  and add a "synced from booth" note for `offline_exit_sync`.

---

## 3. API contract

**Base URL:** `{{BASE}}/api/v1/` — inject via `--dart-define=MTAG_API_BASE=...`. Never hardcode.
Ship three flavours: `dev` (`http://10.0.2.2:8000`), `lan` (`http://192.168.78.200:8000`),
`prod` (HTTPS host, TBD — read it from the define).

### Response envelope — every endpoint

```json
{ "success": true,  "message": "Success", "data": <object|array|null> }
{ "success": false, "message": "Registration failed", "errors": { "phone": ["..."] } }
```

Paginated endpoints add a sibling `meta`:

```json
{ "success": true, "message": "Success", "data": [...],
  "meta": { "count": 137, "next": "…?page=2", "previous": null,
            "total_pages": 7, "current_page": 1 } }
```

Write **one** `ApiEnvelope<T>` unwrapper and one `PagedEnvelope<T>`. Every failure path must be
able to surface `message` plus field-level `errors` — the login screen in particular needs
`errors` mapped onto form fields.

Query params for pagination: `?page=`, `?page_size=` (default 20, max 100).

### 3.1 Auth — **read this carefully, it is counter-intuitive**

`POST /auth/login/` with `{"phone": "...", "password": "..."}` returns

```json
{ "success": true, "message": "Login successful",
  "data": { "user_id": 12, "uuid": "...", "full_name": "...", "phone": "...", "role": "user" } }
```

**The JWTs are NOT in the body.** `LoginView` pops `access` and `refresh` out of `data` and
sets them as `httpOnly` cookies (`access_token`, `refresh_token`) via `Set-Cookie`.
`POST /auth/token/refresh/` likewise reads the refresh token **only** from the cookie, never
from the body.

Therefore the Flutter client **must be cookie-based**:

- `dio` + `dio_cookie_manager` + `cookie_jar` with a **`PersistCookieJar`** backed by
  `path_provider` (encrypted via `flutter_secure_storage` for the storage key).
- `CORS_ALLOW_CREDENTIALS` is already `True`; native apps ignore `SameSite`, so `Lax` is fine.
- `secure` on the cookie follows `SESSION_COOKIE_SECURE`, which is `False` on the LAN profile
  — so plain-HTTP LAN builds work. Add `usesCleartextTraffic` only to the `dev`/`lan` Android
  flavours, never to `prod`.
- Access token lives **6 hours**, refresh **7 days**, and `ROTATE_REFRESH_TOKENS` +
  `BLACKLIST_AFTER_ROTATION` are on. So: a single-flight refresh interceptor that on `401`
  calls `/auth/token/refresh/` **once**, queues concurrent failures behind it, replays them on
  success, and on failure clears the jar and routes to login. Because refresh tokens rotate,
  two parallel refreshes will blacklist each other — the single-flight lock is mandatory, not
  an optimisation.
- `CookieJWTAuthentication` deliberately treats a bad **cookie** as anonymous (not an error),
  so a stale jar yields `401` from the permission layer, not a crash. Handle `401` uniformly.

Endpoints:

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/login/` | throttled **10/minute** (`AnonRateThrottle` scope `login`). Show a real cooldown message on `429`, don't retry blindly. |
| POST | `/auth/logout/` | blacklists the refresh token, clears cookies. Call it, then clear the local jar regardless of outcome. |
| GET | `/auth/me/` | current user. Use as the session-validity probe on cold start. |
| PATCH | `/auth/me/` | profile update (`full_name`, `cnic`) |
| POST | `/auth/change-password/` | `{old_password, new_password}`, min 8 chars |
| POST | `/auth/register/` | `AllowAny`, `{full_name, phone, cnic?, password?}` — **see §7, gate this behind a flag** |

Global throttle: `user` 2000/hour, `anon` 200/hour. Treat `429` as a first-class state with
`Retry-After` respected.

### 3.2 Balance, transactions, top-ups

| Method | Path | Returns |
|---|---|---|
| GET | `/accounts/vehicle/{vehicle_id}/` | `{id, plate_number, vehicle_type, balance, balance_updated_at, created_at}` — `id` here is the **account id** you need everywhere else |
| GET | `/accounts/{account_id}/transactions/` | paginated `{id, transaction_type, amount, balance_before, balance_after, status, tag_serial, reference_id, processed_at}`; filter `?type=toll_deduction` |
| POST | `/payments/topup/` | `{account_id, amount}` (amount ≥ 100) → `{topup_id, jazzcash_payload:{pp_TxnRefNo, pp_Amount, pp_TxnCurrency, pp_MerchantID, pp_ReturnURL, topup_id, pp_SecureHash}}` |
| GET | `/payments/history/{account_id}/` | `[{id, amount, status, jazzcash_txn_id, requested_at, completed_at}]` — poll this to resolve a pending top-up |

`/payments/jazzcash/callback/`, `/jazzcash/inquiry/`, `/jazzcash/payment/` are **gateway→server**
webhooks. The app must never call them.

### 3.3 Vehicles and tags

| Method | Path | Perm | Notes |
|---|---|---|---|
| GET | `/vehicles/` | **`IsOperator`** | ⚠️ a normal user gets 403. See §7. |
| GET | `/vehicles/{id}/` | `IsAuthenticated` | `{id, plate_number, vehicle_type, status, registered_at, owner_id, owner_phone, owner_name, tag:{id, tag_serial, issued_at, expiry_date, status, last_scanned_at, is_valid}}` |
| GET | `/vehicles/plate/{plate}/` | `IsAuthenticated` | plate is normalised server-side (`KDE-1836` → `KDE1836`) |

Note `TagSerializer` currently exposes **no `tid` and no `epc`** — see §7, the app needs `tid`.

### 3.4 Trips and fares

| Method | Path | Notes |
|---|---|---|
| GET | `/tolls/trips/{vehicle_id}/` | paginated `{id, plate_number, entry_plaza_name, exit_plaza_name, entry_time, exit_time, charge_amount, balance_before, balance_after, status, duration_minutes}` |
| GET | `/tolls/plazas/` | `{id, plaza_id, name, latitude, longitude, is_active, lanes:[…]}` |
| GET | `/tolls/rates/` | full fare matrix: `{from_plaza, from_plaza_name, from_plaza_display_id, to_plaza, to_plaza_name, to_plaza_display_id, category, category_name, category_code, fare}` |
| GET | `/tolls/vehicle-categories/` | `{id, category_index, code, name, description, is_active}` |

`plaza_id` is the operator-facing number (1, 2, 101–107) and `display_id` is it zero-padded
(`001`). These are **not** the row `id`. `FareSerializer.category` is the integer
`category_index`, and `category_code` maps onto `Vehicle.vehicle_type` — that is your join key
for "what will this trip cost *my* car".

Everything under `/tolls/admin/*`, `/vehicles/inventory/*`, `/vehicles/tags/*`,
`/accounts/admin/*`, `/accounts/operator/*`, `/accounts/topup/*` and `/accounts/transfer/` is
operator/admin surface. **Do not implement any of it.**

---

## 4. Claymorphic design system

Claymorphism, done properly: soft inflated 3D shapes that look like pressed modelling clay.
Puffy, generously rounded, low-contrast, **borderless**. Two outer shadows per surface — a
light one up-left and a dark one down-right — plus an *inner* highlight/shadow pair for
pressed and inset states.

**Build the design system first, as a package-private library, before any screen.** Everything
else composes from it.

### 4.1 Tokens

```
LIGHT                                DARK
clayBase       #E9EDF5               #1B1F2A     page background
claySurface    #EEF1F8               #222735     card fill (a hair lighter than base)
clayHighlight  #FFFFFF @ 0.85        #343B4E @ 0.90   up-left shadow
clayShadow     #B8C0D4 @ 0.55        #0D1018 @ 0.75   down-right shadow
primary        #2E7DF6               #5B9DFF
primarySoft    #DCE8FF               #24344F
success        #3BC98C               #46D69A
warning        #F5A524               #FFBB4D
danger         #F0526B               #FF6B80
textPrimary    #2B3550               #ECEFF7
textMuted      #7C88A8               #98A3BE
```

Both themes are first-class. Follow the system by default with a manual override in Profile.

### 4.2 The `ClaySurface` primitive

Flutter has **no inset `BoxShadow`**, so build this yourself — do not reach for an
abandoned pub package.

```dart
enum ClayDepthStyle { raised, pressed, flat }

class ClaySurface extends StatelessWidget {
  final Widget? child;
  final double depth;        // shadow offset in logical px
  final double radius;
  final Color? color;
  final ClayDepthStyle style;
  final EdgeInsets padding;
  // ...
}
```

- **raised**: two outer `BoxShadow`s —
  `BoxShadow(color: clayShadow, offset: Offset(d, d), blurRadius: d * 2, spreadRadius: 1)` and
  `BoxShadow(color: clayHighlight, offset: Offset(-d, -d), blurRadius: d * 2, spreadRadius: 1)`.
- **pressed / inset**: a `CustomPainter` that clips to the rounded rect and strokes two blurred
  `RRect`s just outside the clip (`MaskFilter.blur(BlurStyle.normal, d)`), dark from the
  top-left and light from the bottom-right — the inverse of raised. A gradient overlay alone is
  not good enough; it reads flat.
- **flat**: fill only, for nested content inside an already-raised card.

Depth scale: `d = 10` hero balance card · `6` standard card · `4` buttons, chips, list tiles ·
`2` nested/flat.
Radius scale: `36` hero · `28` card · `22` button / list tile · `999` pill.

Then build on top: `ClayCard`, `ClayButton` (primary / tonal / ghost, with a press animation
that interpolates **raised → pressed** over ~120 ms — this is the signature interaction of the
whole app, get it right), `ClayIconButton`, `ClayTextField` (always `pressed`, so inputs read as
carved *into* the surface), `ClayPill` / `ClayStatusBadge`, `ClayProgressRing`, `ClayBottomNav`
(4 items, raised bar, pressed active item), `ClaySheet`, `ClaySkeleton` (a shimmering `flat`
block — never a spinner on a full-page load), `ClayEmptyState`, `ClaySnack`.

### 4.3 Rules

- **Never** use `Border`, `Divider`, or `OutlineInputBorder`. Separation comes from depth alone.
- Spacing scale 4 / 8 / 12 / 16 / 24 / 32. Card padding 20, screen gutter 20, card gap 16.
- Bundle a rounded typeface as an **asset** — Nunito or Poppins. Do not use `google_fonts`
  (it fetches at runtime; these users are on patchy mobile data and sometimes a LAN with no
  internet). Weights 400 / 600 / 700 only.
- Balance figures are the loudest thing on screen: 40sp / w700, tabular figures
  (`fontFeatures: [FontFeature.tabularFigures()]`) so digits don't jitter on refresh.
- Colour never carries meaning alone — every status colour is paired with a label or icon
  (colour-blind users, and clay's low contrast makes hue alone weak).
- Verify contrast: clay is inherently low-contrast, so **text and icons must still hit WCAG AA
  (4.5:1)** against `claySurface` in both themes. Depth may be subtle; text may not.
- Respect `MediaQuery.disableAnimations` / reduce-motion: drop the shimmer and press animations,
  keep the depth.
- These shadow stacks are not free. Do not put a `ClaySurface` inside a per-item builder more
  than ~2 levels deep, and profile a 200-row transaction list on a low-end device.

---

## 5. Screens

1. **Splash / session gate** — probe `GET /auth/me/`; route to Home or Login. Clay logo, no spinner.
2. **Login** — phone + password. Phone input formatted for Pakistan (`03XX XXX XXXX`), sent to
   the server in the exact stored format. Map `errors` onto fields. Handle `429` with a live
   cooldown. Handle "Account is blocked. Contact support." as its own dead-end state with a
   support phone number.
3. **Home / Dashboard**
   - Hero clay card: **total balance across all tags**, explicitly labelled as a sum, with the
     tag count beneath it and a big **Top Up** button.
   - Three stat tiles: Tags · Vehicles · This month's tolls.
   - A **low-balance banner** whenever any tag is under Rs. 200, and an urgent variant under
     Rs. 50 naming the affected plate ("KDE1836 cannot enter — Rs. 50 minimum").
   - Horizontally scrolling tag cards, one per tag: plate, balance, status badge.
   - Recent activity: last 5 transactions merged across all accounts, newest first.
   - Pull-to-refresh on the whole screen.
4. **My Tags** — list of every tag. Per row: tag serial, linked plate, status badge, expiry
   (with an "expires in N days" warning under 30 days), balance. Vehicles with no tag appear as
   an explicit "No tag fitted" row, not silently dropped.
5. **Tag detail** — tag serial, **TID** (monospace, tap-to-copy — the user needs it for a
   JazzCash top-up), status, issued, expiry, last scanned; the linked vehicle; the account
   balance; that account's transactions; a Top Up CTA.
6. **Vehicles** and **vehicle detail** — plate, fare-class label, status, registered date, its
   tag, its balance, its trips.
7. **Top Up** (the highest-value flow — see §6).
8. **Transactions** — paginated infinite scroll, grouped by day with sticky clay day headers.
   Filter chips: All · Tolls · Top-ups · Refunds (maps to `?type=`). Each row shows type icon,
   amount signed and coloured (deduction `danger`, credit `success`), plaza/tag context,
   `balance_after`, and a "synced from booth" note when `source == offline_exit_sync`.
9. **Trips** — entry plaza → exit plaza, entry/exit times, `duration_minutes`, fare charged.
   An `active` trip (entered, not yet exited) renders as a distinct live card.
10. **Fares** — pick from-plaza and to-plaza, auto-select the user's own vehicle category,
    show the fare. Make direction explicit with a swap button, since A→B ≠ B→A.
11. **Profile** — name, phone, CNIC, change password, theme, language, logout (confirm first),
    app version, support contact.

Bottom nav: **Home · Tags · Activity · Profile**. Top Up is a prominent CTA on Home and Tag
detail, not a nav item.

Every list needs all four states designed: loading (clay skeletons) · empty (illustrated
`ClayEmptyState` with a useful next action) · error (message + Retry) · offline (cached data
plus a "showing saved data from {time}" ribbon).

---

## 6. The top-up flow — read this before implementing it

The backend's payment integration is **partially built**, and the app must be honest about that
rather than faking a completed checkout. Two distinct flows exist:

**Flow A — aggregator, JazzCash-initiated (this one actually works end to end).**
The customer opens the *JazzCash* app, chooses M-Tag, and enters their **TID**. JazzCash calls
`POST /payments/jazzcash/inquiry/` (server returns the consumer's name, plate, current balance),
the customer pays, then JazzCash calls `POST /payments/jazzcash/payment/`, which credits the
account idempotently on `jazzcash_txn_id`. **Our app is not in this loop at all.**

So: implement a first-class **"Top up from the JazzCash app"** path — show the TID big,
copyable, with numbered instructions and a deep link to JazzCash if installed. Then poll
`/payments/history/{account_id}/` and `/accounts/vehicle/{id}/` to reflect the credit when it
lands. This is the path most likely to be used on day one; treat it as primary, not a fallback.

**Flow B — app-initiated (incomplete server-side).**
`POST /payments/topup/` creates a `pending` `TopupRequest` and returns a `jazzcash_payload` of
`pp_*` fields. **It contains no gateway checkout URL**, and `JAZZCASH_VERIFY_HASH` is off with
the hashing formula still unconfirmed. So:

- Define a `PaymentGateway` interface with implementations `JazzCashGateway`, `EasypaisaGateway`,
  `CardGateway`, `CashAtBoothGateway`.
- `JazzCashGateway` posts the returned `jazzcash_payload` to a checkout URL read from remote
  config / dart-define. **If that URL is not configured, do not pretend.** Show the pending
  top-up with a clear "waiting for payment confirmation" state and the Flow A instructions.
- Complete the redirect leg in an in-app `flutter_inappwebview`, intercept the return URL
  (`{JAZZCASH_RETURN_URL}?topup_id=…`), then **confirm against the server** by polling
  `/payments/history/{account_id}/` until that `topup_id` leaves `pending` (backoff 2s → 30s,
  give up after ~3 min into a "we'll update your balance automatically" state). Never treat the
  WebView redirect itself as proof of payment.
- **Easypaisa has no backend implementation whatsoever.** Build the UI and the gateway seam, and
  render the Easypaisa option as *coming soon* / retailer-instructions. Do not ship a button that
  silently does nothing, and do not invent an endpoint.
- `CashAtBoothGateway` is pure information: nearest plazas, what to bring (tag/TID), the fact
  that the operator issues a printed receipt.
- Amount step: presets 500 / 1000 / 2000 / 5000 plus custom, **min Rs. 100** enforced client-side
  with the server's exact wording on rejection. Show "balance after top-up" live.
- Generate an idempotency key per attempt and never re-POST `/payments/topup/` on retry of the
  same intent — you'll orphan `pending` rows.

Every top-up screen ends by reconciling against the **server's** balance, never a locally
optimistic one. Money must only ever be displayed from a server read.

---

## 7. Backend gaps — Phase 0, do this first

The backend has **no user-scoped surface**. Implement these small Django changes in
`mtag_backend/` before the Flutter work, keeping the existing envelope helpers
(`utils.response.success_response` / `error_response`) and style. Add tests alongside the
existing ones.

**Blocking (the app cannot be built correctly without these):**

1. **`GET /api/v1/vehicles/my/`** — `IsAuthenticated`, returns `request.user.vehicles` with
   `select_related('tag', 'account')`, each entry carrying the vehicle, its tag, its
   `account_id` and `balance`. Today `GET /vehicles/` is `IsOperator`, so a consumer gets 403
   and has no way to enumerate what they own. This one endpoint should be the app's primary
   bootstrap call.

2. **Ownership checks — these are IDOR holes today, not just missing features.**
   `AccountDetailView` (`accounts/views.py:255`), `TransactionListView` (`:266`),
   `TripHistoryView` (`tolls/views.py:56`), `VehicleDetailView` and `VehicleByPlateView` are all
   bare `IsAuthenticated` with no owner check — **any authenticated user can read any other
   user's balance, transactions and trips by incrementing an id.** Add: if
   `user_role == 'user'`, restrict to objects the user owns and return 404 (not 403) otherwise;
   operators and admins keep today's access. Use the existing `IsOwnerOrAdmin` pattern in
   `apps/users/permissions.py`.

3. **Expose `tid` (and `epc`) on the user-facing tag serializer.** `TagSerializer` omits both,
   yet `tid` is the exact identifier the JazzCash aggregator flow keys on — without it the app
   cannot tell a customer how to top up. Add them read-only.

**Strongly recommended:**

4. **Phone-OTP login / password reset.** There is no reset flow at all, and `POST /auth/register/`
   is `AllowAny` with no verification — self-signup would let anyone create `user` rows against
   arbitrary phone numbers. Real accounts are created at a booth. So: **hide the register screen
   behind a disabled-by-default flag**, and ship a "first-time login / forgot password" flow
   backed by an OTP endpoint. Until that endpoint exists, the app's recovery path is a support
   phone number, stated plainly.

5. **A `GET /api/v1/accounts/my/summary/` aggregate** — total balance, tag count, vehicle count,
   month-to-date tolls, and the N most recent transactions across all of the user's accounts.
   Without it the dashboard needs 1 + 2N round trips on every cold start, which is poor on
   mobile data. Not blocking; the client can fan out in parallel meanwhile.

**Degrade gracefully:** put every one of these behind a capability probe in the Flutter data
layer. If `/vehicles/my/` 404s, fall back to `/auth/me/` plus per-vehicle fetches; if the
summary endpoint is absent, aggregate client-side; if `tid` is missing, hide the JazzCash
instruction block rather than showing an empty field. The app must run against today's backend,
just with fewer features.

---

## 8. Technical requirements

- **Flutter 3.x / Dart 3**, null-safe, `flutter_lints` + `very_good_analysis`, zero analyzer
  warnings.
- **State:** `flutter_riverpod` (code-gen `@riverpod`). No singletons, no `GetX`, no
  `setState` for anything crossing a widget boundary.
- **Routing:** `go_router` with a redirect-based auth guard and deep links
  (`mtag://tag/{serial}`, `mtag://topup?account=`).
- **Network:** `dio` + `dio_cookie_manager` + `cookie_jar` (`PersistCookieJar`) + a single-flight
  refresh interceptor + a logging interceptor that **redacts cookies, passwords and `pp_*`
  fields**. Timeouts 15 s. Retry only idempotent GETs, never a POST that moves money.
- **Models:** `freezed` + `json_serializable`. One model per API shape, hand-verified against
  the serializers in this repo. Money as `Decimal`, dates as `DateTime` parsed as UTC and
  rendered in `Asia/Karachi`.
- **Local cache:** `drift` or `hive` — cache accounts, vehicles, tags, and the first page of
  transactions/trips so the app opens with real content offline. Stamp every cache write and
  show its age. **Never** cache-serve a balance without visibly stating how old it is.
- **Secrets/session:** `flutter_secure_storage` for the cookie-jar key and any remembered phone.
  Nothing sensitive in `SharedPreferences`.
- **Localisation:** `flutter_localizations` + ARB, **English and Urdu** (RTL verified — this
  user base is Karachi motorists; the backend's own docs are in Roman Urdu). Every string
  localised from the start; no hardcoded copy.
- **Errors:** one `AppFailure` union (network / timeout / unauthorised / forbidden / notFound /
  throttled / validation / server / unknown) mapped from the envelope, each with a localised
  user-facing message. Never surface a raw Dio exception.
- **Security:** certificate pinning on the `prod` flavour, `flutter_secure_screen`-style
  screenshot blocking on the top-up screens, no logging of balances or TIDs in release,
  optional biometric app-lock (`local_auth`).
- **Testing:** unit tests for the envelope parser, the money formatter, the refresh
  single-flight, and the fare-lookup join; widget tests for the top-up flow including the
  pending/timeout branches; **golden tests for every `ClaySurface` variant in both themes**
  (clay regressions are invisible in code review and obvious on screen); a mock Dio adapter with
  fixtures captured from `mtag_postman_collection.json`.
- **CI:** `flutter analyze` + `flutter test` + build both APK and IPA.

Structure feature-first:

```
lib/
  core/           di, router, env, network (dio, interceptors, envelope), errors, storage, utils
  design_system/  tokens, clay/ (ClaySurface + primitives), theme, typography, goldens
  features/
    auth/  dashboard/  tags/  vehicles/  topup/  transactions/  trips/  fares/  profile/
      data/ (dto, remote, local, repository_impl)
      domain/ (entity, repository)
      presentation/ (controller, screen, widgets)
  l10n/
```

---

## 9. Definition of done

- Runs against a live backend on all three flavours; every screen in §5 built with real data.
- Phase 0 backend changes implemented, tested, and the client degrading correctly without them.
- Cookie session survives an app restart; a 6-hour-expired access token refreshes silently,
  exactly once, under concurrent requests.
- No operator/admin endpoint reachable from any code path.
- Golden tests green for the clay system in light and dark; AA contrast verified.
- Urdu RTL layout correct on every screen.
- Zero analyzer warnings; all tests pass.
- `README.md` documenting setup, the dart-defines, flavours, and — explicitly — **what is
  stubbed** (Easypaisa, app-initiated JazzCash checkout URL, OTP) and what is required to finish
  each one.

## 10. Do not

- Do not invent endpoints, fields, or response shapes. If something is missing, say so and stub
  it behind a flag, exactly as §7 does.
- Do not fake a successful payment, and do not credit a balance client-side under any
  circumstance. Balance is server truth, always.
- Do not use `double` for money.
- Do not ship placeholder/lorem data on any path reachable in a release build.
- Do not hardcode a base URL, merchant id, salt, or plaza list.
- Do not add borders or dividers — this is a claymorphic app; depth is the only separator.
- Do not implement operator features "just in case".

---

Start by reading `mtag_backend/apps/*/models.py`, `serializers.py`, `urls.py` and
`config/settings/base.py`, then confirm the §3 contract and the §7 gap list against what you
find. Report any discrepancy **before** writing client code. Then build in this order:
**Phase 0 backend patch → design system + goldens → core/network + auth → dashboard →
tags/vehicles → top-up → transactions/trips → fares/profile → l10n → hardening.**
