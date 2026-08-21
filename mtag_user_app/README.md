# M-Tag User App

The consumer wallet for the M-Tag electronic toll collection system on the Malir
Expressway (Shahra-e-Bhutto), Karachi. A tag holder uses it to check their balance, top
up, and review their tags, vehicles, trips and transactions.

It is **read-mostly**, and it holds no operator or admin capability: no tag issuance, no
booth assignment, no vehicle registration, no fare editing, no gate control. Every
operator endpoint (`/tolls/admin/*`, `/vehicles/inventory/*`, `/vehicles/tags/*`,
`/accounts/admin/*`, `/accounts/operator/*`, `/accounts/topup/*`, `/accounts/transfer/`)
is absent from the codebase, not merely unreachable from the UI.

Backend: `../mtag_backend` (Django REST Framework).

---

## Quick start

```bash
flutter pub get
dart run build_runner build --delete-conflicting-outputs   # drift + freezed
flutter gen-l10n                                            # English + Urdu

# Android emulator against a local runserver
flutter run --flavor dev \
  --dart-define=MTAG_FLAVOR=dev \
  --dart-define=MTAG_API_BASE=http://10.0.2.2:8000
```

```bash
flutter analyze      # must be clean
flutter test         # 272 tests
```

---

## The one thing to understand first: the wallet belongs to the vehicle

```
User (phone is the username)
  └── has many Vehicle
        ├── has ONE Tag      (nullable — a reissue in progress has none)
        └── has ONE Account  ← the wallet
              ├── has many Transaction
              └── has many TopupRequest
```

`Account` is a `OneToOneField` on `Vehicle`. So a holder with three vehicles has **three
independent balances**, and cannot spend one at another's plaza. There is no such thing as
a user balance.

The dashboard's hero figure is therefore a **client-side sum**, and the UI says so
("Total across 3 tags", with an explanation beneath it and the per-tag reality one swipe
below). If any balance could not be read, the total is marked *partial* rather than
presented as a total — too high is the direction that tells someone they can enter a plaza
when they cannot.

Money is a `DecimalField` server-side and arrives as a **JSON string** (`"1250.00"`). It is
a `Decimal` for its whole life in this app; `double` never touches it. That is not
fastidiousness — the app sums balances, previews `balance + amount`, and compares against
a Rs. 50 threshold that decides whether a barrier opens.

---

## Flavours and dart-defines

Three flavours, and they are real Gradle product flavours rather than build-type overrides
— see [§ Cleartext](#cleartext-and-why-it-is-a-flavour-not-a-build-type).

| | `dev` | `lan` | `prod` |
|---|---|---|---|
| Host | `http://10.0.2.2:8000` | `http://192.168.78.200:8000` | HTTPS, supplied |
| Cleartext HTTP | yes | yes | **never** |
| Certificate pinning | no | no | **explicit** (pins, or `MTAG_CERT_PINS=none`) |
| Launcher label | M-Tag dev | M-Tag LAN | M-Tag |
| App id | `com.mtag.userapp.dev` | `com.mtag.userapp.lan` | `com.mtag.userapp` |

```bash
# dev
flutter run --flavor dev \
  --dart-define=MTAG_FLAVOR=dev \
  --dart-define=MTAG_API_BASE=http://10.0.2.2:8000

# lan — release, because that is what operators test with on the toll LAN
flutter build apk --release --flavor lan \
  --dart-define=MTAG_FLAVOR=lan \
  --dart-define=MTAG_API_BASE=http://192.168.78.200:8000

# prod
flutter build appbundle --release --flavor prod \
  --dart-define=MTAG_FLAVOR=prod \
  --dart-define=MTAG_API_BASE=https://api.example.com \
  --dart-define=MTAG_CERT_PINS=sha256/AAA…=,sha256/BBB…= \
  --dart-define=MTAG_SUPPORT_PHONE=+922134400000 \
  --dart-define=MTAG_SUPPORT_PHONE_DISPLAY="021 3440 0000"
```

### All defines

| Define | Default | Notes |
|---|---|---|
| `MTAG_API_BASE` | dev/lan have one; **prod throws without it** | Scheme + host, no `/api/v1/` |
| `MTAG_FLAVOR` | `dev` | `dev` \| `lan` \| `prod` |
| `MTAG_CERT_PINS` | empty | Comma-separated `sha256/…=`. **prod throws if empty.** |
| `MTAG_SUPPORT_PHONE` | `+922134400000` | Dialled. This IS the account-recovery flow. |
| `MTAG_SUPPORT_PHONE_DISPLAY` | `021 3440 0000` | Shown |
| `MTAG_JAZZCASH_CHECKOUT_URL` | empty | See [§ stubbed](#what-is-stubbed) |
| `MTAG_JAZZCASH_RETURN_URL` | empty | Must match the server's `JAZZCASH_RETURN_URL` |
| `MTAG_JAZZCASH_APP_SCHEME` | `jazzcash://` | Deep link for the aggregator flow |
| `MTAG_ENABLE_REGISTRATION` | `false` | Keep off — see [§ stubbed](#what-is-stubbed) |
| `MTAG_ENABLE_EASYPAISA` | `false` | No backend exists |
| `MTAG_ENABLE_CARD` | `false` | No backend exists |

A missing `MTAG_API_BASE` or `MTAG_CERT_PINS` on **prod throws at launch**. That is
deliberate: a release build that quietly points at `10.0.2.2`, or quietly ships unpinned,
looks fine in CI and fails in a user's hand. Failing on the first frame means QA catches it.

---

## Auth is cookie-based, and it has to be

`LoginView` pops `access` and `refresh` out of the response body and sets them as
`httpOnly` cookies. `TokenRefreshCookieView` reads the refresh token **only** from
`request.COOKIES` — never from the body. So **there is no token for the client to hold**:
possession of the two cookies is the entire session.

- `dio` + `dio_cookie_manager` + a `PersistCookieJar` on disk (`core/network/cookie_store.dart`).
  An in-memory jar would look correct in every test and log the user out on every cold start.
- Access token 6 hours, refresh 7 days, with `ROTATE_REFRESH_TOKENS` **and**
  `BLACKLIST_AFTER_ROTATION` on.

That last point is why `core/network/refresh_interceptor.dart` takes a **single-flight
lock**, and why it is mandatory rather than an optimisation. Every successful refresh
issues a new refresh token and blacklists the old one, so two concurrent refreshes mean
the second presents an already-retired token — and depending on ordering it can blacklist
the one the first just issued. The user is signed out despite a valid 7-day session.

It is not a rare race: the dashboard fans out several requests on a cold start, and after
six hours idle they all 401 at once. `test/core/refresh_interceptor_test.dart` fires eight
concurrent 401s and asserts exactly **one** refresh.

`CookieJWTAuthentication` treats an unusable cookie as anonymous rather than as an error,
so a stale jar produces a 401 from the permission layer. `GET /auth/me/` is the only
reliable session probe, and the splash screen uses it.

A **network** failure on that probe does **not** sign anyone out — the splash holds an
error state with a Retry. Logging out every user who opens the app in a basement, when
their session is good for a week, would be a bug.

---

## What is stubbed

Four things. Each is stubbed because the backend cannot support it yet, and each says so on
screen rather than presenting a button that does nothing.

### 1. App-initiated JazzCash checkout (`MTAG_JAZZCASH_CHECKOUT_URL`)

`POST /payments/topup/` creates a `pending` `TopupRequest` and returns `pp_*` fields. It is
not enough to take a payment:

- **no gateway checkout URL** in the response — there is nowhere to send the customer;
- `pp_Password` is a merchant credential and is **stripped server-side** before the
  response leaves (part of this app's Phase 0 changes), so the payload is not a complete
  JazzCash Hosted Checkout form either;
- `JAZZCASH_VERIFY_HASH` is `False` with the hashing formula unconfirmed.

**To finish it:** build the redirect **server-side** — an endpoint that composes the full
form (including `pp_Password`, which must never leave the server) and 302s to JazzCash.
Then set `MTAG_JAZZCASH_CHECKOUT_URL` and `MTAG_JAZZCASH_RETURN_URL`, and
`JazzCashCheckoutGateway` flips from `notConfigured` to `available` with no other change.

No in-app WebView is bundled, and that follows from the above rather than being an
omission: because the client can never hold `pp_Password`, a client-side POST of the
payload cannot work, so shipping `flutter_inappwebview` (several MB plus a WebView attack
surface) for a flow that cannot run would be dead weight. When the server endpoint exists,
open it in a WebView or the system browser, watch for the return URL, and use that **only**
as a signal to start polling. The seam is `JazzCashCheckoutGateway.isReturnUrl`.

Until then the app shows the pending top-up with a clear "waiting for payment
confirmation" state and the aggregator instructions, which work.

### 2. Easypaisa and card payments

**No backend of any kind** — no endpoint, no service, no model field. The gateway seam
(`features/topup/domain/payment_gateway.dart`) and the UI exist so wiring one up later is a
single class. Both render as *Coming soon* with a working alternative.

Deliberately not done: inventing an endpoint, or shipping a button that silently fails.
A user who taps a dead Pay button assumes their money went somewhere.

### 3. Phone-OTP login and password reset

There is no reset endpoint and no OTP endpoint. `POST /auth/register/` has no phone
verification at all — so `MTAG_ENABLE_REGISTRATION` is **off**, and the backend now refuses
anonymous registration outright (operators registering a holder at a booth are unaffected;
see `USER_SELF_REGISTRATION_ENABLED`).

The app's recovery path is therefore a **support phone number**, stated plainly on the
login screen and on the blocked-account dead end. When an OTP endpoint exists, replace
`_showForgotPassword` in `login_screen.dart`.

### 4. iOS screenshot blocking

`ScreenSecurity` raises Android's `FLAG_SECURE` on the tag-detail and top-up screens, which
blocks screenshots, screen recording **and** the recents-list thumbnail. iOS has no
equivalent — the OS permits screenshots unconditionally — so the calls are no-ops there.
The nearest iOS mitigation is hiding content on backgrounding, which is not implemented.

---

## Degrading against an older backend

Everything in Phase 0 sits behind a capability probe (`core/data/capabilities.dart`), probed
by use rather than by a preflight call, and only a **404** counts as "absent" (a timeout or
a 500 must not permanently downgrade the app).

| Missing | Fallback | Cost |
|---|---|---|
| `GET /vehicles/my/` | `/auth/me/` + per-vehicle fetches from cached ids | **Degraded.** `GET /vehicles/` is `IsOperator`, so a consumer has no listing at all. A fresh install against an old backend shows an empty state that says so. |
| `GET /accounts/my/summary/` | Aggregate client-side | Round trips only. The month-to-date figure becomes a lower bound and is labelled "at least". |
| `tid` on the tag serializer | Hide the JazzCash block entirely | The aggregator instructions cannot be followed without a TID, and a blank field under "type this into JazzCash" is worse than no field. |
| `source` on transactions | No "synced from booth" note | History looks late rather than explained. |

---

## Backend changes this app required (Phase 0)

Applied in `../mtag_backend`, with tests. Five of these are security fixes rather than
features.

1. **`GET /api/v1/vehicles/my/`** — the app's bootstrap call. `GET /vehicles/` is
   `IsOperator`, so before this a tag holder had no way to enumerate their own vehicles.
2. **Ownership scoping — IDOR fixes.** `AccountDetailView`, `TransactionListView`,
   `TripHistoryView`, `VehicleDetailView`, `VehicleByPlateView` and `TopupHistoryView` were
   all bare `IsAuthenticated` with no owner check: **any authenticated user could read any
   other user's balance, transactions, trips and payment history by incrementing an id.**
   Now scoped, returning **404** (not 403) so ids cannot be enumerated. Operators and
   admins keep their existing access.
3. **`PATCH /auth/me/` privilege escalation.** `UserDetailSerializer` marked only
   `id`/`uuid`/`created_at` read-only, and `MeView.patch` handed it `request.data`
   directly — so `PATCH /auth/me/ {"user_role": "admin"}` promoted any tag holder to admin,
   unlocking every `/admin/*` endpoint. `status` let a blocked account unblock itself, and
   `phone` is the `USERNAME_FIELD`. Now restricted to `full_name` and `cnic`.
4. **`pp_Password` leaked to the client.** `initiate_topup` put
   `settings.JAZZCASH_PASSWORD` into the payload returned to the app — so anyone who
   installed it could read the merchant password out of a response body. Stripped.
5. **`InitiateTopupView` accepted any `account_id`**, letting one holder open a pending
   top-up against another's wallet. Now ownership-checked.
6. **`tid` / `epc` exposed** on `TagSerializer` (read-only). `tid` is what the JazzCash
   aggregator flow keys on.
7. **`source` exposed** on `TransactionSerializer`, for the "synced from booth" note.
8. **Anonymous `/auth/register/` gated** behind `USER_SELF_REGISTRATION_ENABLED` (off).
9. **`GET /api/v1/accounts/my/summary/`** — the dashboard in one call instead of 1 + 2N.
10. **`GET /api/v1/tolls/trips/my/`** — every trip across all of the holder's vehicles, in
    one ordered page. `trips/<vehicle_id>/` is per vehicle, so an account-wide list
    previously meant fetching `/vehicles/my/` and then one request per vehicle — and then
    merging N independently paginated streams, which cannot be done correctly: page 1 of two
    vehicles is not the first page of their union, so the merged order is wrong exactly
    where it matters. Ordered `-entry_time, -id`; the id tiebreak stops two trips sharing an
    instant from swapping between pages and duplicating or hiding a row. `?status=` filters
    server-side and **refuses** an unknown value rather than silently returning everything.
11. **Phone OTP is also pushed** to devices already registered to the account, alongside the
    SMS — see [§ OTP over push](#otp-over-push-and-the-takeover-it-must-not-permit) for why
    it can never be the only channel.

```bash
cd ../mtag_backend
python manage.py test           # 148 tests
```

---

## Architecture

```
lib/
  core/
    cache/        drift — one stamped key/value table (§ Offline)
    data/         repositories, capability probe, Cached<T>
    env/          dart-define reading
    errors/       AppFailure — one closed set, no DioException escapes
    models/       freezed DTOs, hand-written fromApi (§ Models)
    network/      dio, envelope, single-flight refresh, redaction, pinning
    router/       go_router with a redirect auth guard
    security/     FLAG_SECURE channel
    settings/     theme + locale
    storage/      flutter_secure_storage
    utils/        Money (Decimal), AppDates (PKT), labels
  design_system/  tokens · clay/ primitives · theme  (§ Design system)
  features/       auth · dashboard · tags · vehicles · topup · transactions ·
                  trips · fares · profile · shell · shared
  l10n/           app_en.arb, app_ur.arb
```

### Deviations from the brief, and why

**Riverpod providers are hand-written, not `@riverpod`.** Not a preference — an unsolvable
version conflict at the time of writing: `riverpod_generator` 4.x requires `analyzer ^13`
while `json_serializable` 6.x and `freezed` 3.x are pinned to analyzer 8–11. pub cannot
satisfy both, so the choice was codegen for **models** or for **providers**. Models win:
~20 DTOs whose `fromJson`/`==`/`copyWith` is pure boilerplate, and a hand-written `==` that
misses a field is a silently stale widget. Provider bodies port to `@riverpod` unchanged
when the constraints converge.

**Models use freezed with a hand-written `fromApi`, and the json_serializable *builder* is
absent.** A generated parser keys on Dart field names (`fullName`) rather than the API's
(`full_name`) and would silently produce empty models; expressing the real shape through
annotations is longer than the code. Every field here needs custom handling anyway — enums
fall back to `unknown` rather than throwing on a value a future deployment adds, money is a
`Decimal` parsed from a string, timestamps normalise to UTC. `fromApi` also names the thing
accurately: it reads one specific server's shape, verified against that serializer.

**Two palette values differ from the brief**, because the brief also requires WCAG AA and
these did not clear it:
- light `textMuted` `#7C88A8` measured **3.13:1** on `#EEF1F8`; it is `#5F6B8A` at 4.68:1.
- the four semantic colours measure 1.9–3.5:1 on the light surface. They are kept as
  **fills** (with white on top) and as icons and large figures, where AA Large's 3:1
  applies; each gained an `…OnSurface` sibling clearing 4.5:1 for small coloured text.

The dark palette measured clean as specified and is unchanged. Every value is annotated
with its measured ratio in `design_system/tokens/clay_palette.dart`.

---

## Design system

Claymorphism: soft inflated shapes, generously rounded, low contrast, **borderless**.

Two rules the whole system rests on:

1. **No `Border`, no `Divider`, no `OutlineInputBorder`.** Separation is depth alone.
   Material's `DividerTheme` is set transparent wholesale, because a stray hairline from a
   Material default is easier to prove absent than to chase.
2. **Colour never carries meaning alone.** Every status colour is paired with a label or an
   icon — clay's low contrast makes hue a weak channel even for people with full colour
   vision, and some users cannot read it at all.

Flutter has **no inset `BoxShadow`**, so `ClaySurface`'s `pressed` state is painted
properly: clip to the rounded rect, then stroke the same rect twice with a blur, offset
outward each way, so the blurred tail lands as a soft band on the interior edge. A gradient
overlay reads flat because it has no blur falloff, which is the entire cue the eye uses for
depth. The pressed fill also goes slightly darker — a carved surface catches less light,
and without that the groove reads as a bright vignette rather than a dent.

Scales: depth `10` hero / `6` card / `4` control / `2` nested; radius `36` / `28` / `22` /
`999`; spacing 4·8·12·16·24·32 with a 20 gutter and 16 card gap.

Balance figures are 40sp w700 with `FontFeature.tabularFigures()`, so a refresh does not
make the number twitch.

`Nunito` and `NotoSansArabic` are **bundled assets**, not `google_fonts`: these users are on
patchy mobile data or a LAN with no internet, and a runtime fetch means the app renders in
Roboto. Noto is not optional — Nunito has no Arabic glyphs, so without it every Urdu string
would be tofu on a device with no Arabic font. Naskh rather than Nastaliq deliberately:
Nastaliq needs roughly 2× the line height and would break every card.

**Golden tests** cover every `ClaySurface` variant in both themes
(`test/design_system/goldens/`). Clay regressions are invisible in code review and obvious
on screen — a wrong shadow offset or a lost inset painter breaks no assertion and no test.
The image is the assertion.

```bash
flutter test --update-goldens    # after an intentional visual change
```

---

## The top-up flow

The most important thing about this screen is that **only one of the five methods works end
to end today, and it is the one this app is not part of.**

**Flow A — aggregator, and the primary path.** The customer opens the *JazzCash* app,
chooses M-Tag, and enters their **TID**. JazzCash calls
`POST /payments/jazzcash/inquiry/` (the server returns their name, plate and balance as a
check), they pay, and JazzCash calls `POST /payments/jazzcash/payment/`, which credits the
account idempotently on `jazzcash_txn_id`. Both are gateway→server webhooks; **the app
never calls them.**

So the app cannot initiate that payment, cannot set the amount, and gets no callback. It is
therefore implemented as what it is: numbered instructions, a big monospaced copyable TID, a
deep link into JazzCash, and then polling `/payments/history/{account_id}/` to reflect the
credit when it lands.

**Flow B** is [stubbed](#what-is-stubbed).

Rules the flow obeys, in order of importance:

- **A balance is only ever displayed from a server read.** Nothing is credited locally, ever.
  "Balance after top-up" is explicitly a preview; the real balance is re-read from
  `/accounts/vehicle/{id}/` after confirmation, never computed as `old + amount` — the
  gateway may settle a different figure, and a toll can be deducted mid-flight.
- **Only the server leaving `pending` counts as payment.** Not a WebView redirect, not a
  gateway success page, not the user saying they paid.
- **Timing out is not failing.** Polling backs off 2s→30s and gives up after ~3 minutes into
  a "we'll update your balance automatically — you do not need to pay again" state. Showing
  a failure there is what produces duplicate payments.
- **Pending top-ups are shown prominently.** Both working paths leave them, and a user who
  cannot see theirs pays twice.
- **One idempotency key per intent.** `/payments/topup/` creates a row on every call and the
  server does not deduplicate, so a Retry tap reuses the key rather than minting a new one
  and orphaning a second pending row.

---

## Offline

`drift`, one table: `key`, `payload`, `storedAt`. A key/value store rather than a relational
mirror, because the cache exists so the app opens with real content on a dead connection,
not so it can query offline.

`storedAt` is **not optional**. Every cache-served balance is displayed with its age, because
a balance is a number the user decides whether to enter a plaza on, and a two-hour-old one
shown without its age is indistinguishable from a current one. `Cached<T>` carries the
provenance so a widget cannot accidentally omit the ribbon.

The network is tried **first** every time — this is not a cache-first store. A `401` is
never answered with cached content (the user is on their way to the login screen, and on a
shared handset that would be a small leak). Logout wipes the cache.

---

## Security

- **Redaction.** Nothing is logged in release at all — not redacted, absent. `kDebugMode`
  gates the whole interceptor, because "we redact carefully" is one missed field away from a
  wallet balance in a crash report. In debug, cookies, passwords, `pp_*` (matched by
  prefix), TIDs, CNICs and balances are replaced before the line is written.
- **Certificate pinning** on prod only (`core/network/tls_pinning.dart`). Not applied to
  dev/lan, which are plain HTTP by design.
- **`FLAG_SECURE`** on the tag-detail and top-up screens. Android only — see
  [§ stubbed](#what-is-stubbed).
- **Biometric app lock**, optional and off by default. It is a **local gate, not
  authentication**: the session is in httpOnly cookies and this does not touch them.
  Offered as convenience-grade privacy, never described as security. The biometric is
  verified *before* the setting is persisted, so a device with nothing enrolled cannot lock
  someone out of their own wallet.
- **`flutter_secure_storage`** for the cookie-jar marker and the remembered phone.
  `SharedPreferences` holds theme and locale only.
- **R8 with obfuscation** on release, and source-file/line attributes are deliberately not
  kept: a readable trace from an app that handles balances and TIDs is a map of the data
  layer. Deobfuscate with the build's `mapping.txt`.

### Certificate pinning

The pins are SHA-256 of the whole DER **certificate**, because that is what Dart's
`X509Certificate` exposes (`cert.der`); extracting the SPKI needs an ASN.1 walk this app
does not carry.

The consequence has to be planned for: **a certificate pin breaks on every renewal**, even
one that reuses the key. So supply at least two pins, and ship the next certificate's pin
**before** the current one is replaced.

#### Let's Encrypt hosts cannot be pinned this way

`api.maliroperations.com` uses Let's Encrypt, and that makes the scheme above unusable:
certbot reissues the leaf roughly every 60 days with a new serial, so its digest changes at
each renewal, and the replacement's pin **cannot be computed in advance** — the certificate
does not exist until it is issued. A pinned build would therefore fail closed at the first
renewal, on every installed device, with no update able to land in time.

Pinning the *CA* instead of the leaf would survive renewals, but Dart's `HttpClient` exposes
only the peer certificate, not the issuer chain, so it is not reachable from this interceptor.

So prod builds against a Let's Encrypt host opt out **explicitly**:

```bash
--dart-define=MTAG_CERT_PINS=none
```

An *absent* `MTAG_CERT_PINS` still throws at launch. Only the literal `none` (or `off` /
`disabled`) is accepted, so a build that simply forgot the flag is still caught in QA and can
never be mistaken for a pinned one. Transport security then rests on the platform trust
store, HSTS, and the flavour's cleartext ban — the configuration Let's Encrypt itself
recommends over pinning.

```bash
openssl s_client -connect api.example.com:443 -servername api.example.com </dev/null 2>/dev/null \
  | openssl x509 -outform DER \
  | openssl dgst -sha256 -binary \
  | openssl base64
# -> prefix with "sha256/" to get the MTAG_CERT_PINS value
```

This is verified by `computePin` in `test/core/tls_pinning_test.dart`, so the recipe and the
comparison cannot drift.

### Release signing

```bash
export MTAG_KEYSTORE_PATH=/secure/mtag-release.jks
export MTAG_KEYSTORE_PASSWORD=…
export MTAG_KEY_ALIAS=mtag
export MTAG_KEY_PASSWORD=…
flutter build appbundle --release --flavor prod --dart-define=…
```

Without those, `release` falls back to debug keys so a release build stays testable. A store
upload with debug keys is rejected, which is the desired failure — silently shipping
debug-signed would be worse.

### Cleartext, and why it is a flavour not a build type

`config.settings.lan` sets `SESSION_COOKIE_SECURE = False` because the toll LAN is
HTTP-only. Operators test that LAN with **release** builds. Putting `usesCleartextTraffic`
in the debug source set only would leave a release LAN build unable to hold its session
cookie — login returns 200, the cookie is discarded, the next request is anonymous, and the
UI reports "invalid phone number or password". (This exact failure already happened
server-side once; see the comment in `apps/users/views.py:_set_auth_cookies`.)

So `src/dev/` and `src/lan/` carry the flag and `src/prod/` cannot: there is no manifest
there that permits it.

---

## Localisation

English and Urdu, every string in ARB. `l10n.yaml` writes
`l10n_untranslated.json`, so a key present in `app_en.arb` and missing from `app_ur.arb`
is visible rather than shipping an English string inside an Urdu build.

RTL specifics that are easy to get wrong and are handled explicitly:

- **Codes stay LTR**: plate numbers, tag serials, TIDs, plaza display ids and every money
  figure are forced `TextDirection.ltr`. An unconstrained `Text` reverses the visual order
  of `KDE1836` in an RTL layout, making it unreadable.
- Directional icons (back, chevrons) flip on `Directionality`.
- `AlignmentDirectional` and `EdgeInsetsDirectional` throughout.
- The Urdu option in Profile is labelled **اردو** — someone looking for it cannot
  necessarily read "Urdu".

Text scale is honoured but **capped at 1.4×**. The hero is a 40sp balance in a fixed-height
clay card; at the 2.0× some Android settings allow, that figure overflows its card and takes
the low-balance warning beside it off screen — worse for the user the setting exists to help.

---

## Testing

```bash
flutter test                    # 272
flutter test --update-goldens   # after an intentional visual change
```

| File | Covers |
|---|---|
| `core/api_envelope_test.dart` | envelope + pagination, `non_field_errors`, HTML-instead-of-JSON |
| `core/money_test.dart` | Decimal parsing, exact sums, the Rs. 50/100 boundaries |
| `core/refresh_interceptor_test.dart` | **eight concurrent 401s → one refresh**, no loops, login excluded |
| `core/fare_lookup_test.dart` | the join key, directional fares, no reverse fallback |
| `core/tls_pinning_test.dart` | pin encoding, non-prod is unpinned, defaults are off |
| `features/login_screen_test.dart` | phone display vs wire form, mid-number caret |
| `features/topup_flow_test.dart` | `pp_Password` never reaches the app, gateway availability, **timeout and dropped-poll branches** |
| `features/topup_widget_test.dart` | minimum enforcement, waiting/timed-out/confirmed states |
| `core/app_dates_test.dart` | PKT day boundaries, bare `DateField` parsing, Urdu 24-hour |
| `core/api_contract_test.dart` | **parsers against real captured server responses** |
| `design_system/clay_golden_test.dart` | every surface variant, both themes |
| `design_system/rtl_golden_test.dart` | Urdu layout, with plates and money still LTR |

Goldens load the bundled fonts **and** the SDK's Material icon font, so the images verify
real layout rather than a grid of Ahem boxes.

### Contract tests against real server output

`test/fixtures/*.json` are **not hand-written**. They are captured by driving the actual
Django views through DRF against a real database:

```bash
cd ../mtag_backend
DB_NAME=mtag_fixtures python manage.py migrate
DB_NAME=mtag_fixtures python manage.py dump_api_fixtures
```

The command runs inside a transaction it rolls back, so it leaves no rows behind.

That distinction is the point. A hand-written fixture only proves the parser matches the
fixture; a captured one proves it matches the **server**. If a serializer gains, loses or
renames a field, regenerating makes `api_contract_test.dart` fail — which is exactly when a
hand-written parser would otherwise start silently returning nulls.

The fixtures deliberately include the awkward states: a vehicle with no tag, a
blocked-level (Rs. 42) balance, an offline-synced toll, a transaction with a null `source`,
an active trip with null exit fields, and asymmetric fares.

Two real bugs were caught this way and by the Urdu goldens:

- `Tag.expiry_date` is a `DateField`, so it arrives as a bare `2099-12-31`.
  `DateTime.parse` reads that as **local** midnight, and `.toUtc()` then shifted it by the
  device's offset — putting the expiry a day early for every user east of Greenwich and a
  day late for everyone west. "Expires in N days" was off by one. Now parsed as UTC midnight.
- CLDR's `ur` data abbreviates the day period to a bare Latin `a`/`p`, so
  `DateFormat('h:mm a', 'ur')` rendered 20:30 as **"8:30 p"** — which an Urdu reader cannot
  tell from morning. Urdu now uses a 24-hour clock, which also matches the `%H:%M:%S` on the
  booths' printed receipts.

---

## Push notifications

Money alerts are pushed by the SERVER: a `post_save` signal on `Transaction` and
`TopupRequest` fires `send_to_user` on commit, so every path that moves money notifies —
including the ones added later. The app only registers a device token and reacts to what
arrives; it never composes a notification from a local guess, and it never applies the
amount from a notification to a balance. Balance stays server truth.

### The app builds and runs without Firebase

`android/app/build.gradle.kts` applies the `google-services` plugin **only if a config file
is present**, and `Firebase.initializeApp()` is wrapped everywhere it is called. That is
deliberate: the plugin *fails the build* when it cannot find `google-services.json`, so
applying it unconditionally would make the app unbuildable until someone set up a Firebase
project, and an unguarded `initializeApp` in `main()` would produce an app that installs
cleanly and shows a black screen.

With no config, push reports `PushAvailability.notConfigured` and everything else works.
`BuildConfig.FIREBASE_CONFIGURED` records which build you have, so the UI can distinguish
"this build has no Firebase" from "the user declined permission" — two states with different
fixes that a single boolean would conflate.

### Finishing the setup

1. Create a Firebase project, then add an **Android app for each flavour's package name** —
   the plugin rejects a config whose client list does not contain the package being built
   (`No matching client found for package name`):

   | flavour | applicationId |
   |---|---|
   | dev  | `com.mtag.userapp.dev` |
   | lan  | `com.mtag.userapp.lan` |
   | prod | `com.mtag.userapp` |

2. Download `google-services.json` and drop it at `android/app/google-services.json`. One
   file covering all three package names is simplest; per-flavour files under
   `android/app/src/<flavour>/google-services.json` also work.

3. On the server, point Django at a service account for the **same** project:

   ```bash
   FCM_PROJECT_ID=your-project-id
   FCM_CREDENTIALS_FILE=/secure/mtag-fcm-service-account.json
   ```

   A path, never the key itself. The legacy server-key API was shut down in June 2024, so
   HTTP v1 plus a service account is the only option.

4. Confirm with `GET /api/v1/notifications/status/` — `push_available` must be `true`.
   Until it is, a perfectly valid device token receives nothing, which is why the app checks
   both halves before telling anyone that alerts are on.

Rebuild after adding the file; Gradle prints which branch it took.

### What happens on each app state

| app state | who renders it | what the app does |
|---|---|---|
| foreground | the app | refetches wallet, activity and trips, then shows an in-app banner |
| background | the system tray | tapping it deep-links via the payload's `route` |
| terminated | the system tray | `getInitialMessage()` is pulled on launch and routed |

A foreground push deliberately does **not** raise a system notification. The tray is for
things the user is not looking at; an app in front of the user should update itself and say
so in place. The refresh is the important half — without it the notification says
"Toll paid · Rs. 120" while the dashboard behind it still shows the old balance.

### Sign-out releases the token first

`SessionController.signOut()` awaits the unregister **before** clearing cookies.
`/notifications/devices/unregister/` is `IsAuthenticated` and scopes its delete to
`request.user`, so unregistering after the session is gone returns 401 and leaves the row
behind — and because FCM hands the same token to whoever installs next on a handset, the
previous owner would keep receiving the new owner's balance notifications. That is a privacy
leak, not a missing feature, which is why it is the one step in an otherwise optimistic
sign-out that is waited on.

### OTP over push, and the takeover it must not permit

The server pushes the verification code **in addition to** the SMS, and only ever to devices
already registered to that account. It is not a replacement, and the reason is a one-step
account takeover rather than a matter of taste.

An OTP proves the requester holds the phone NUMBER. SMS establishes that because delivery is
bound to the SIM. Push delivery is bound to holding an app install — which the requester
obviously has. So if the code went to whichever device asked for it:

1. an attacker installs the app and obtains a token,
2. requests a code for a victim's number — the number is all that is needed,
3. receives the code on their own device,
4. verifies, takes the set-password token, sets a new password,
5. and owns the victim's wallet.

So the app has **no way to request push delivery and no way to name a destination**. The
server derives it from `DeviceToken` rows, which can only be created by an authenticated
request. `apps/users/tests_otp.py::OtpPushDeliveryTest` asserts this directly, including that
a token supplied in the request body is ignored.

Practical consequence: a fresh install — which is the enrolment case — has no registered
device, so it gets an SMS. A returning holder still signed in on their phone gets the code
instantly and free. `OTP_PUSH_SUPPRESSES_SMS` can skip the SMS fee once a push has
demonstrably landed; it is off by default, because a bound device may be one the holder no
longer carries and this system has no password reset.

## Deep links

```
mtag://tag/{serial}          # keyed by SERIAL — it is printed on the physical tag
mtag://topup?account={id}
```

---

## Known limitations

- **Activity across multiple vehicles is merged client-side.** The server paginates per
  account (`/accounts/{id}/transactions/`) with no all-accounts endpoint, so for a
  multi-vehicle holder "All" fetches page N of each and merges: ordering is exact only
  within the pages fetched. Picking one vehicle gives exact pagination, and that is the
  default for a single-vehicle holder. The alternative — forcing a vehicle choice before any
  history is visible — is worse.
- **PKT is a fixed UTC+05:00** (`core/utils/app_dates.dart`) rather than the tz database.
  Exact today; Pakistan has observed no DST since 2009. If DST returns, that file is the only
  thing to change.
- **The APK is ~62MB** because `sqlite3_flutter_libs` bundles native libraries for every
  ABI. Use `--split-per-abi`, or an app bundle for the Play Store, which splits
  automatically.
- **The month-to-date toll figure is a lower bound** when `/accounts/my/summary/` is absent,
  and is labelled "at least" rather than presented as exact.
