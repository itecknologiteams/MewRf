# M-Tag — Electronic Toll Collection System

Malir Expressway ke liye RFID-based toll collection system. Vehicle ek booth pe scan hoti hai, trip start hoti hai, exit pe sahi toll amount automatically deduct hota hai.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CENTRAL SERVER (192.168.78.200)             │
│                                                                 │
│   ┌──────────────────┐        ┌──────────────────────────────┐  │
│   │  Django Web API  │        │  PostgreSQL (tag_db)         │  │
│   │  port 8000       │◄──────►│                              │  │
│   │  (Admin Portal + │        │  tags, vehicles, accounts    │  │
│   │   REST API)      │        │  toll_trips, transactions    │  │
│   └──────────────────┘        │  plazas, toll_lanes          │  │
│                               │  toll_rates                  │  │
│                               └──────────────────────────────┘  │
└────────────────────────────────┬────────────────────────────────┘
                                 │ LAN (192.168.78.x)
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
┌─────────▼──────┐    ┌──────────▼─────┐    ┌──────────▼─────┐
│  Booth 2 PC    │    │  Booth 10 PC   │    │  Booth 5 PC    │
│  (Qayyumabad)  │    │  (Shahfaisal)  │    │  (Qayyumabad)  │
│                │    │                │    │                │
│  run_gate.py   │    │  run_gate.py   │    │  run_gate.py   │
│  + SQLite      │    │  + SQLite      │    │  + SQLite      │
│  (offline_     │    │  (offline_     │    │  (offline_     │
│   cache.db)    │    │   cache.db)    │    │   cache.db)    │
└────────┬───────┘    └────────┬───────┘    └────────┬───────┘
         │                     │                     │
    RFID Reader            RFID Reader           RFID Reader
    192.168.78.8           192.168.78.x          192.168.78.x
         │                     │                     │
    Barrier (Serial)      Barrier (Serial)      Barrier (Serial)
    COM1/COM2             COM1/COM2             COM1/COM2
```

---

## Database Tables (PostgreSQL)

| Table | Kya Store Hota Hai |
|---|---|
| `users` | Operators aur admins |
| `vehicles` | Registered vehicles (plate number, type) |
| `tags` | RFID tags — har tag ek vehicle se linked |
| `accounts` | Vehicle ka wallet (balance) |
| `transactions` | Har top-up aur toll deduction ka record |
| `plazas` | Toll plazas (Qayyumabad, Shahfaisal) |
| `toll_lanes` | Har plaza ki lanes (1-7 QYD, 1-7 SHF) |
| `toll_rates` | Entry plaza + Exit plaza + Vehicle type = Rate |
| `toll_trips` | Har trip ka record (entry se exit tak) |
| `pending_gate_opens` | Portal se manually barrier kholne ke commands |

---

## Entry Flow — Jab Vehicle Scan Ho

```
Vehicle RFID Tag
      │
      ▼
RFID Reader (192.168.78.8:9090)
      │  TCP connection
      ▼
run_gate.py → on_tag(epc, tid)
      │
      ├─ Cooldown check (5 seconds) — double scan rokta hai
      │
      ▼
EntryService.process_entry(tag_serial, plaza_id, lane_id)
      │
      ├─ Step 1: Tag DB mein hai?
      │          NO  → DENIED "Tag not found"
      │
      ├─ Step 2: Tag kisi vehicle se linked hai?
      │          NO  → DENIED "Tag not assigned to any vehicle"
      │
      ├─ Step 3: Tag active hai? Expiry nahi hua?
      │          NO  → DENIED "Tag is suspended/expired"
      │
      ├─ Step 4: Vehicle active hai?
      │          NO  → DENIED "Vehicle is inactive"
      │
      ├─ Step 5: Balance >= Rs.50 (minimum)?
      │          NO  → DENIED "Insufficient balance"
      │
      ├─ Step 6: Koi active trip already hai?
      │          YES → DENIED "Vehicle already has an active trip"
      │
      └─ Step 7: Sab theek → TollTrip create (status=ACTIVE)
                      │
                      ▼
               Serial port → 'o' → Barrier OPEN
               Display update → fare show
               2 seconds baad → 'f' → Barrier CLOSE
```

**Console output (success):**
```
>>> EPC: E28278... | TID: E28278... | 2026-05-06 10:00:00 | mode=ENTRY
[gate] ENTRY OK — vehicle: ABC-123 balance: Rs.500.00
```

---

## Exit Flow — Jab Vehicle Exit Kare

```
Vehicle RFID Tag (same tag)
      │
      ▼
run_gate.py → on_tag(epc, tid)
      │
      ▼
ExitService.process_exit(tag_serial, exit_plaza_id, lane_id)
      │
      ├─ Step 1: Tag DB mein hai?
      │
      ├─ Step 2: Is vehicle ki ACTIVE trip hai?
      │          NO  → DENIED "No active trip found"
      │
      ├─ Step 3: Rate lookup
      │          entry_plaza + exit_plaza + vehicle_type → TollRate table
      │          NOT FOUND → DENIED "Toll rate not configured"
      │
      ├─ Step 4: Balance >= charge?
      │          NO  → DENIED "Insufficient balance at exit"
      │
      ├─ Step 5: account.balance -= charge  (atomic DB transaction)
      │
      ├─ Step 6: TollTrip update
      │          exit_plaza, exit_time, charge_amount
      │          status = COMPLETED
      │
      └─ Step 7: Transaction record create
                 (toll_deduction, amount, balance_before, balance_after)
                      │
                      ▼
               Serial port → 'o' → Barrier OPEN
               Display → fare amount show
               2 seconds baad → 'f' → Barrier CLOSE
```

**Console output (success):**
```
>>> EPC: E28278... | TID: E28278... | 2026-05-06 10:30:00 | mode=EXIT
[gate] EXIT OK — vehicle: ABC-123 charge: Rs.150.00 balance: Rs.350.00
```

---

## Offline Mode — Jab DB Down Ho

Har booth PC pe `offline_cache.db` (SQLite) hoti hai. Har 60 second mein central DB se sync hoti hai.

```
Central DB DOWN ho gaya
         │
         ▼
EntryService → OperationalError (connection timeout)
         │
         ▼
offline_cache.py → process_entry_offline()
         │
         ├─ local tag_cache check karo
         ├─ balance check karo (cached value)
         └─ Barrier OPEN ✅
              │
              ▼
         active_trips (SQLite) mein save
         pending_transactions (SQLite) mein queue
```

### Exit During Offline — 3 Cases

**Case 1: Entry bhi offline tha (same PC)**
```
active_trips (SQLite) mein entry mili → normal exit → barrier open
```

**Case 2: Entry online tha, phir DB crash hua (most common)**
```
active_trips (SQLite) mein entry NAHI mili
tag_cache mein tag mila → vehicle valid → barrier open
Rs.50 flat charge (conservative) → queue mein save
DB wapas aane pe: correct rate calculate, proper deduction
```

**Case 3: Tag bilkul cache mein nahi**
```
DENIED — operator manually handle kare
```

### DB Wapas Aane Pe (Auto-Reconciliation)
```
Sync loop → pending_transactions flush kare
           → ExitService.process_exit() call
           → central DB mein trip mili
           → correct toll deduct
           → Transaction record create
```

---

## Portal-Triggered Barrier Open

Agar operator web portal se manually barrier kholna chahe:

```
Operator → Web Portal → "Open Gate" button
      │
      ▼
PendingGateOpen record DB mein create
      │
      ▼
run_gate.py (poll thread, har 1 second)
      │
      ▼
Record mila → executed_at set → Barrier OPEN
```

---

## Booth Console — `http://<booth-lan-ip>:8000/booth/`

Har booth apni **apni** diagnostics page serve karta hai. Lane pe khare ho kar
browser mein booth ka LAN IP kholo — koi SSH nahi, koi install nahi. Portal wale
hi credentials chalte hain (padhne ke liye operator, kuch badalne ke liye admin).

```
Laptop browser ──► http://192.168.1.61:8000/booth/
                        │
                        ├── mtag-web (gunicorn)  ── rfid_config.ini padhta/likhta
                        │                         ── reader / barrier / display probe
                        │                         ── booth_activity.db se history
                        │
                        └── mtag-gate (run_gate)  ── har read booth_activity.db mein likhta
```

### Kya dikhata hai

| Tab | Kya |
|---|---|
| **Overview** | Reader, barrier, master DB, display, pm2 — sab ka live status |
| **Detections** | Har tag read, RSSI ke saath, threshold bands ke upar chart. Dots = raw read, line = wo median jis pe gate faisla karta hai |
| **Barrier** | Is gate ne jo commands bheje, aur portal ne jo maange. Do test buttons |
| **LPR Camera** | RTSP se ek frame (ffmpeg), plus stream ka codec/resolution |
| **Balance Validator** | TID / tag serial / plate → wahi verdict jo barrier pe milega. Kuch charge nahi hota |
| **Reader Config** | `rfid_config.ini` edit + validate + `pm2 restart mtag-gate` |
| **Gate Log** | `pm2 logs mtag-gate` ka tail |

### RSSI tuning — asal kaam

Detections tab isi liye banaya hai. Gaadi ko aate hue dekho, boom pe pahunchte
waqt dBm note karo, phir Reader Config mein band set karo:

```
rssi_detect    = -70   ← itna door se balance dikhana shuru
rssi_open_min  = -55   ← boom sirf is band ke andar khulta hai
rssi_open_max  = -45   ← itna qareeb = doosri lane / hath mein pakda tag
```

Likhne se **pehle** validate hota hai — wahi rules jo `run_gate` start pe lagata
hai. Ghalat ordering reject ho jati hai, warna PM2 crash-loop mein chala jata aur
lane band ho jati. Har write ke sath `rfid_config.ini.bak` chhoot jata hai.

### Do cheezein jo confuse karti hain

- **`antenna_power` gate apply nahi karta.** `run_gate` value parhta hai lekin
  reader ko bhejta nahi — `RW_RFIDAntPower` set karne se TID reads band ho jate
  the. Power reader ki apni utility se badlo; lane ki reach RSSI band se control
  karo. Console yeh field ke neeche warning mein likhta hai.
- **Plaza / lane / mode console se edit nahi hote.** Yeh decide karte hain kis
  plaza pe billing hogi — SSH ka kaam hai, browser ka nahi.

### Fleet-wide camera setup — `set_camera.sh`

`[camera]` ek hi baar sab booths pe daalne ke liye, `set_rssi.sh` wale andaz mein.
Booth list master ki DB se aati hai; har booth pe `.bak` chhoot jata hai.

```bash
./set_camera.sh --dry-run                       # dekho, kuch likha nahi jayega
./set_camera.sh                                 # blank [camera] sab booths pe
./set_camera.sh --url-map cameras.txt           # aur har booth ka apna URL
./set_camera.sh 192.168.78.19 --url 'rtsp://admin:Iteck%40123@192.168.78.21:554/profile1'
```

**Lane band nahi hoti.** `run_gate` `[camera]` parhta hi nahi, is liye yeh script
`mtag-gate` ko haath nahi lagati — sirf `mtag-web` restart hota hai taake console
nayi values uthaye. Barrier chalti rehti hai.

Idempotent hai: jo values booth pe pehle se hain wo rehti hain, comment block
refresh ho jata hai, aur doosri baar chalao to "unchanged" bolta hai.

Har lane ka apna camera hai, is liye ek fleet-wide URL nahi ho sakta. Ya to
`--url-map` do (`booth_ip  rtsp_url` lines — **git mein mat daalo**, password
hota hai; `.gitignore` mein `cameras.txt` already hai), ya blank chhod kar har
booth ka URL console ke **Reader Config** tab se set karo.

Password **percent-encode** karna hai: `Iteck@123` → `Iteck%40123`. Script do se
zyada `@` dekh kar mana kar deti hai, aur agar URL mein `%` hai lekin booth ka
`booth_probe.py` purana hai to `NEEDS CODE` bol kar skip kar deti hai.

### Activity file

`booth_activity.db` — booth pe local SQLite ring buffer (WAL). `mtag-gate` likhta
hai, `mtag-web` parhta hai. Capped hai (20k reads / 5k events / 5k barrier
commands), kabhi bhi delete kar sakte ho, gate dobara bana leta hai. Ismein koi
paisa/trip nahi — sab master pe hai.

---

## Balance Top-Up

### JazzCash (Online)
```
User → JazzCash payment → callback URL → account.balance += amount
```

### Cash at Booth (Operator)
```
Insufficient balance → LowBalanceAlert → Operator cash leta hai
Operator → Portal → Cash Top-up → account.balance += amount
```

---

## Malir Expressway — Booth Configuration

### Qayyumabad Side (Entry)
| Booth | Config File | Lane |
|---|---|---|
| Booth 2 | `booth_configs/booth_2_qyd.ini` | Lane 1 |
| Booth 3 | `booth_configs/booth_3_qyd.ini` | Lane 2 |
| Booth 4 | `booth_configs/booth_4_qyd.ini` | Lane 3 |
| Booth 5 | `booth_configs/booth_5_qyd.ini` | Lane 4 |
| Booth 6 | `booth_configs/booth_6_qyd.ini` | Lane 5 |
| Booth 7 | `booth_configs/booth_7_qyd.ini` | Lane 6 |
| Booth 8 | `booth_configs/booth_8_qyd.ini` | Lane 7 |

### Shahfaisal Side (Entry)
| Booth | Config File | Lane |
|---|---|---|
| Booth 10 | `booth_configs/booth_10_shf.ini` | Lane 1 |
| Booth 11 | `booth_configs/booth_11_shf.ini` | Lane 2 |
| Booth 12 | `booth_configs/booth_12_shf.ini` | Lane 3 |
| Booth 13 | `booth_configs/booth_13_shf.ini` | Lane 4 |
| Booth 14 | `booth_configs/booth_14_shf.ini` | Lane 5 |
| Booth 15 | `booth_configs/booth_15_shf.ini` | Lane 6 |
| Booth 16 | `booth_configs/booth_16_shf.ini` | Lane 7 |

---

## Deployment — Booth PC Setup

### 1. Project Copy Karo
```
C:\mtag\
    manage.py
    booth_configs\
        booth_2_qyd.ini   ← sirf apne booth ki file
    offline_cache.db      ← auto-create hogi
    .env
```

### 2. `.env` File (Booth PC Pe)
```
DJANGO_SETTINGS_MODULE=config.settings.local
DB_HOST=192.168.78.200
DB_NAME=tag_db
DB_USER=postgres
DB_PASSWORD=superadmin123456
DB_PORT=5432
```

### 3. Gate Start Karo
```bat
cd C:\mtag
venv\Scripts\activate
python manage.py run_gate --config booth_configs\booth_2_qyd.ini
```

### 4. Auto-Start (Windows Task Scheduler)
- Trigger: System startup
- Action: `python manage.py run_gate --config booth_configs\booth_2_qyd.ini`
- Run whether user logged in or not: YES

---

## Central Server Setup

### Django Web Server
```bat
cd C:\mtag
venv\Scripts\activate
python manage.py runserver 0.0.0.0:8000
```

### Hourly Database Backup
`C:\backups\backup_tagdb.bat`:
```bat
@echo off
set PGPASSWORD=superadmin123456
set DT=%date:~6,4%-%date:~3,2%-%date:~0,2%_%time:~0,2%h
set DT=%DT: =0%
"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" -U postgres -d tag_db -f "C:\backups\tag_db_%DT%.sql"
forfiles /p "C:\backups" /m tag_db_*.sql /d -7 /c "cmd /c del @path" 2>nul
```
Task Scheduler mein hourly set karo.

### Restore After Crash
```bat
psql -U postgres -d tag_db -f C:\backups\tag_db_2026-05-06_14h.sql
```

---

## Key Files

| File | Kya Karta Hai |
|---|---|
| `apps/tolls/services.py` | Entry aur Exit logic |
| `apps/tolls/offline_cache.py` | DB down hone pe SQLite fallback |
| `apps/tolls/management/commands/run_gate.py` | RFID gate controller |
| `apps/tolls/booth_console.py` | Booth console ke API endpoints (`/booth/api/...`) |
| `apps/tolls/booth_probe.py` | `rfid_config.ini` parhna/likhna + hardware probes |
| `apps/tolls/booth_activity.py` | Local ring buffer — reads, decisions, barrier commands |
| `apps/tolls/templates/booth_console.html` | Console ka poora UI (ek file, koi build step nahi) |
| `apps/tolls/management/commands/run_all_gates.py` | Sab gates ek saath start |
| `apps/tolls/models.py` | Plaza, Lane, Rate, Trip, PendingGateOpen |
| `apps/vehicles/models.py` | Vehicle, Tag |
| `apps/accounts/models.py` | Account, Transaction |
| `booth_configs/` | Har booth ki alag config |
| `.env` | DB credentials aur settings |

---

## Uptime Strategy

| Layer | Solution | Downtime Prevent |
|---|---|---|
| DB unreachable | Offline SQLite cache | Booth chalta raha |
| DB crash | Hourly pg_dump backup | Max 1 hour data loss |
| Booth PC crash | Windows Task Scheduler auto-restart | 1-2 minute |
| Network down | Offline cache | Booth chalta raha |
