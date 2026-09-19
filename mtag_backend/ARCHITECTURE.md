# m-tag Toll System — Complete Architecture

## Network Layout

```
┌─────────────────────────────────────────────────────────┐
│                    MALIR EXPRESSWAY                      │
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │ Plaza A  │    │ Plaza B  │    │ Plaza C  │          │
│  │  Gate PC │    │  Gate PC │    │  Gate PC │          │
│  └──────────┘    └──────────┘    └──────────┘          │
│       │               │               │                  │
│       └───────────────┴───────────────┘                  │
│                       │                                  │
│               LAN (192.168.x.x)                         │
│                       │                                  │
│              ┌────────────────┐                          │
│              │  Master Server │                          │
│              │ 192.168.78.200 │                          │
│              └────────────────┘                          │
└─────────────────────────────────────────────────────────┘
```

---

## Har Gate PC ke Andar

```
┌─────────────────────────────────────────────┐
│              Gate PC                         │
│                                              │
│  ┌─────────────────────────────────────┐    │
│  │         Django Server               │    │
│  │         (Gunicorn)                  │    │
│  │                                     │    │
│  │  ┌────────────┐                     │    │
│  │  │ REST API   │   (no sync agent)   │    │
│  │  │ Entry/Exit │                     │    │
│  │  └────────────┘                     │    │
│  │                                     │    │
│  │  ┌─────────────────────────────┐    │    │
│  │  │     ANPR Gate Controller    │    │    │
│  │  │  WebSocket Client           │    │    │
│  │  └─────────────────────────────┘    │    │
│  └─────────────────────────────────────┘    │
│                    │                         │
│         no local database — every            │
│         query goes to MASTER below           │
│                                              │
│  ┌─────────────────────────────────────┐    │
│  │    quick-toll-system (Node.js)      │    │
│  │    LPR Camera → WebSocket :3003     │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Camera  │  │ Barrier  │  │ Display  │  │
│  │  (LPR)   │  │ (Serial) │  │ (HTTP)   │  │
│  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────┘
```

---

## Vehicle Ka Safar — Entry to Exit

```
ENTRY (Plaza A)
──────────────────────────────────────────────
Camera → plate detect
    ↓
quick-toll-system broadcast (ws://localhost:3003)
    ↓
AnprGateController.on_plate()
    ↓
Plate normalize (KDE-1836 → KDE1836)
    ↓
Vehicle + Tag lookup (master DB)
    ↓
Tag status check (ACTIVE?)
    ↓
EntryService.process_entry()
    ↓
Balance check (≥ Rs.50?)
    ↓
TollTrip CREATE → master DB
    ↓
Barrier OPEN + Display show balance


EXIT (Plaza B)
──────────────────────────────────────────────
Camera → plate detect
    ↓
AnprGateController.on_plate()
    ↓
ExitService.process_exit()
    ↓
_find_active_trip()
  └─ Master DB (booth ka apna DB nahi hai — 'default' hi master hai)
    ↓
TollRate lookup (A → B ka rate)
    ↓
Balance deduct → master DB
TollTrip UPDATE (status=completed) → master DB
Transaction CREATE → master DB
    ↓
Barrier OPEN + Display show fare

Sab kuch ek hi transaction mein master pe commit hota hai.
Koi sync step nahi — entry Plaza A pe hote hi Plaza B ko turant dikh jati hai.
```

---

## Sync Agent — removed

Pehle har booth 30 second ke cycle par master se pull aur master ko push karta
tha (`apps/tolls/sync/`, PM2 app `mtag-sync`). Woh poora package delete kar diya
gaya hai.

Wajah simple hai: `booth_bootstrap.sh` ab booth par koi local Postgres install
nahi karta aur `DB_*` seedha master pe point karta hai. Matlab sync ke dono
end ek hi server the — har pass master ki rows ko master pe hi wapas likhta,
watermarks aage barhata jinka koi matlab nahi tha, aur 12 tables par `setval`
dobara chalata. Ab jo gate likhta hai woh pehle se hi master par hota hai.

Jo cheezein is ke saath khatam ho gayin: sync lag, watermark drift, aur do
databases ke beech divergence. Jo cheez add hui: master ki availability ab har
lane ki availability hai.

---

## Master Server

```
┌─────────────────────────────────────────────┐
│           Master (192.168.78.200)            │
│                                              │
│  ┌─────────────────────────────────────┐    │
│  │      Django Admin Portal            │    │
│  │                                     │    │
│  │  • Vehicles register                │    │
│  │  • Tags issue                       │    │
│  │  • Balance topup                    │    │
│  │  • Reports & stats                  │    │
│  │  • Plaza/Rate management            │    │
│  └─────────────────────────────────────┘    │
│                    │                         │
│  ┌─────────────────────────────────────┐    │
│  │      Master PostgreSQL              │    │
│  │                                     │    │
│  │  Single source of truth             │    │
│  │  All plazas ka data yahan           │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

---

## Master Down — kya hota hai

> **Yeh section pehle ulta likha tha.** Purana design mein booth ka apna local
> Postgres tha aur master down hone par bhi lane chalti rehti thi. Ab aisa
> **nahi** hai — booths online-only hain, unka koi apna database nahi.

```
Master DOWN
    ↓
Booth ka 'default' DB = master. Koi fallback nahi.
    ↓
Entry ❌  Exit ❌  Balance deduct ❌
Barrier nahi khulega — gate DB error log karega
    ↓
Master BACK UP
    ↓
Lane turant chalne lagti hai. Reconcile karne ko kuch nahi,
kyunki outage ke doran koi transaction hui hi nahi.
```

Yeh trade-off jaan boojh kar liya gaya hai: ek hi database hone ka matlab hai
koi replication lag nahi, koi divergence nahi, aur koi double-charge nahi — lekin
master ki availability ab har lane ki availability hai. Master aur booths ke
beech ka network us hisaab se treat karna chahiye.

---

## Cross-Plaza Exit — Timing

```
0s  — Vehicle enters Plaza A  → master pe commit
0s  — Plaza B ko wohi trip turant dikhti hai (same database)
      Vehicle exits B → success ✅

Max delay = 0 seconds
```

Pehle yahan 60 second tak ka sync lag hota tha (push 30s + pull 30s), jise
Malir Expressway ke 6-8 minute travel time se cover kiya jata tha. Online-only
ke baad woh window bilkul khatam hai — short hop ya U-turn par bhi koi race
nahi.

---

## Conflict Analysis

| Table | Conflict Risk | Reason |
|-------|--------------|--------|
| toll_trips | None | Entry/exit alag events, timestamp guard |
| accounts | None (practically) | 1 vehicle = 1 active trip at a time |
| transactions | None | Immutable, ON CONFLICT DO NOTHING |
| vehicles/tags | None | Sirf master se update hote hain |

---

## Key Numbers

| Cheez | Value |
|-------|-------|
| Primary DB per gate | Master PostgreSQL (no local DB) |
| Sync interval | — (no sync) |
| Cross-plaza trip max delay | 0 seconds |
| Master down tolerance | **None — lane stops** |
| Minimum balance for entry | Rs.50 |
| Plate cooldown (same plate) | 5 seconds |
| Barrier open duration | 2 seconds |

---

## Files — Kahan Kya Hai

| File | Kaam |
|------|------|
| `apps/tolls/services.py` | EntryService, ExitService |
| `apps/tolls/management/commands/run_anpr_gate.py` | ANPR WebSocket controller |
| `apps/tolls/management/commands/run_gate.py` | RFID gate controller |
| `apps/tolls/barrier.py` | Barrier backend — service or serial |
| `apps/tolls/apps.py` | Django startup — ANPR auto-start |

> The `apps/tolls/sync/` package (agent, pull, push, connections) has been
> removed. Booths are online-only and have no database of their own, so there is
> nothing to replicate. See the note under **Deployment** below.
| `config/settings/lan.py` | Production settings (LAN, no SSL) |
| `gunicorn.conf.py` | Gunicorn config (1 worker, 4 threads) |
| `mtag.service` | systemd service file |
| `anpr_config.ini` | Gate PC config (plaza, mode, IPs) |

---

## Environment — .env

```ini
DB_HOST=192.168.78.200         # MASTER — booth ka apna DB nahi hai
DB_FALLBACK_HOST=              # Koi fallback nahi
MASTER_DB_HOST=192.168.78.200  # Wohi server; 'master_pg' alias isi pe jata hai
```

---

## Production Start Command

```bash
# Development
python manage.py runserver

# Production
DJANGO_SETTINGS_MODULE=config.settings.lan \
  gunicorn -c gunicorn.conf.py config.wsgi:application

# systemd (auto-start on boot)
sudo systemctl start mtag
sudo systemctl enable mtag
```
