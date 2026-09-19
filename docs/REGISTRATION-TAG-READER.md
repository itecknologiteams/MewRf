# Registration desk: USB tag reader

The operator adds the customer's details, then has to issue a tag — but the
serial printed on a tag is small and the operator is holding an unmarked one.
Placing it on the desk reader identifies it and fills the serial in.

Portal page: **M-Tag Registration** → step 2 → *Scan the tag*.

Just want the commands? See [READER-QUICKSTART.md](READER-QUICKSTART.md).

---

## How it fits together

The reader is USB on the operator's PC. The backend is on master. Nothing on the
desk holds an API credential:

```
 REGISTRATION PC                          MASTER  192.168.78.200
 ───────────────                          ──────────────────────
   [tag on reader]
         │ USB HID
         ▼
   tag_reader_agent.py --serve
         │ publishes the TID on
         │ http://127.0.0.1:8765/tag
         ▼
   browser  ◄──────── portal served from  :8081
         │ polls loopback every 0.8s
         │
         └─ GET /vehicles/tags/scan-lookup/?tid=…  ──────►  backend
              (the operator's own logged-in session)          │
                                                              ▼
                            available / already issued / not in inventory
```

The page is served from master but the fetch to the agent stays on the
operator's own machine, so the reader never has to be reachable from the
network and the desk holds no credentials.

The agent never talks to master. It only says "a tag was just read, here is its
TID"; the browser — already authenticated — does the lookup. So a registration
desk needs no API password, and a read never leaves the machine except as the
operator's own request.

The page tracks a sequence number, so a read left over from the previous
customer cannot auto-fill the next form.

---

## Installing on a registration desk

Build the bundle on a dev machine and copy one file across — the desk needs
neither the backend nor the repo:

```bash
cd mtag_backend && ./tools/make_reader_bundle.sh
# -> mtag-tag-reader.zip      (Windows)
# -> mtag-tag-reader.tar.gz   (Linux)
```

### Windows

Unzip, then **double-click `install.bat`**. It checks Python, installs
`pyserial` + `hidapi` (removing the conflicting `hid` package first) and lists
what is plugged in. There is no permission step: Windows gives the logged-in
user access to HID and COM devices, so no udev rule and no group membership.

Then **double-click `start-reader.bat`** whenever the desk is in use.

If Python is missing, install it from python.org and tick *"Add python.exe to
PATH"* during setup, or `install.bat` cannot find it.

### Linux

```bash
tar -xzf mtag-tag-reader.tar.gz && cd mtag-tag-reader && ./install.sh
python3 tools/tag_reader_agent.py --serve
```

---

## Setup detail (Linux)

### 1. The reader

A HopeLand UHF desktop reader (USB `2121:8633`). It is a composite device
exposing **both** a CDC serial port (`/dev/ttyACM0`) and a HID interface. The
serial port is silent — the protocol runs over HID, which is what the vendored
`com.rfid` SDK uses.

```bash
sudo cp mtag_backend/deploy/99-hopeland-uhf-reader.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
# unplug and replug the reader
```

Without the rule `/dev/hidraw*` is root-only and every open fails with a bare
`open failed`.

### 2. Python dependencies

```bash
pip install pyserial hidapi
```

**Not `hid`.** The SDK calls `hid.device()`, which is cython-hidapi, published as
`hidapi`. The similarly named `hid` package has a different API *and* ships a
`hid/` package directory that shadows hidapi's module, so with both installed
every reader fails with `module 'hid' has no attribute 'device'`.

### 3. Run the agent

```bash
cd mtag_backend
python tools/tag_reader_agent.py --serve
```

Leave it running while the desk is in use. It prints each read:

```
Publishing reads on http://127.0.0.1:8765/tag
Connected over USB:ID 2121:8633
Reader SN: …
Extended TID read enabled
TAG  tid=E280110520008081E83C0B67  epc=…  (published)
```

The registration page shows **Reader connected** (green dot) when it can see the
agent, and **Reader not detected** otherwise — in which case typing or pasting a
TID still works exactly as before.

---

## Diagnosing a reader

```bash
python tools/tag_reader_agent.py --list     # what is plugged in
python tools/tag_reader_agent.py            # read tags, print to console
python tools/tag_reader_agent.py --raw      # raw serial bytes (see note)
```

`--raw` reads the CDC serial port directly. On this model that port never
speaks, so silence there is expected and not a fault — it is only useful for a
different reader that does stream over serial.

| Symptom | Cause |
|---|---|
| `open failed` (Windows) | another program holds the reader — close any HopeLand demo tool, replug it |
| `open failed` (Linux) | udev rule not installed, or reader not replugged after it |
| `module 'hid' has no attribute 'device'` | wrong package — `pip uninstall hid && pip install hidapi` |
| `Reader not detected` in the page | agent not running, or not on this PC |
| Reads appear in the agent but not the page | the page is open on a different machine from the agent |

---

## Notes

- The agent binds to `127.0.0.1` only, so it is not reachable from the network.
- The portal is served from `http://192.168.78.200:8081`, a private address, and
  the agent is on loopback. Chrome treats that as a **private network request**
  and sends a preflight carrying `Access-Control-Request-Private-Network`. The
  agent answers with matching CORS plus `Access-Control-Allow-Private-Network:
  true`, which is what allows the fetch. Verified against that exact origin.
- If a browser ever does block it, the symptom is **Reader not detected** with a
  CORS/private-network error in the console. Manual TID entry keeps working, and
  the fix is to open the portal from the registration PC itself.
- If the portal is ever served over **HTTPS**, a plain-HTTP fetch to the agent
  may be blocked as mixed content. Chrome treats `http://127.0.0.1` as
  trustworthy so it generally still works, but verify it when TLS is switched on.
- Override the agent address with `VITE_READER_AGENT_URL` if 8765 is taken
  (`python tools/tag_reader_agent.py --serve 9000`).
