# Tag reader — quick setup

USB tag reader on a registration PC. Full detail: [REGISTRATION-TAG-READER.md](REGISTRATION-TAG-READER.md)

---

## 1. Build the bundle (dev machine)

```bash
cd mtag_backend
./tools/make_reader_bundle.sh
```

Produces `mtag_backend/mtag-tag-reader.zip`

---

## 2. Copy to the registration PC

USB stick, or from the Windows PC:

```powershell
scp user@<dev-machine>:~/Github_backup/Github/MewRf/mtag_backend/mtag-tag-reader.zip .
```

---

## 3. Install — Windows

Unzip, then:

```
double-click  install.bat
```

Needs Python 3.8+ on PATH (python.org → tick "Add python.exe to PATH").

## 3. Install — Linux

```bash
tar -xzf mtag-tag-reader.tar.gz
cd mtag-tag-reader
./install.sh
# unplug and replug the reader
```

---

## 4. Run

Leave the window open while the desk is in use.

```
Windows:  double-click  start-reader.bat
Linux:    python3 tools/tag_reader_agent.py --serve
```

Expected:

```
Publishing reads on http://127.0.0.1:8765/tag
Connected over USB:ID 2121:8633
Extended TID read enabled
```

---

## 5. Use

On the **same PC**, open:

```
http://192.168.78.200:8081
```

M-Tag Registration → step 2 → green dot → place tag on reader.

---

## Fixes

| Problem | Command |
|---|---|
| What's plugged in? | `python tools/tag_reader_agent.py --list` |
| `module 'hid' has no attribute 'device'` | `pip uninstall -y hid && pip install hidapi` |
| `open failed` (Windows) | Close any HopeLand demo tool, replug reader |
| `open failed` (Linux) | Re-run `./install.sh`, replug reader |
| "Reader not detected" in page | Agent must run on the same PC as the browser |
| Port 8765 taken | `--serve 9000` + set `VITE_READER_AGENT_URL` |

---

## Notes

- Registration PC needs **only** this bundle — not the backend, not the repo.
- Agent holds no passwords; your browser does the lookup.
- No reader? Type/paste the TID into the same field — works identically.
