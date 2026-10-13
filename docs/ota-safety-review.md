# GeekMagic SmallTV-PRO: stock-to-custom OTA and feature-preservation review

**Reviewed:** 13 October 2026. **Verdict: do not flash the unmodified `giovi321/smalltv-mod` if preserving the existing stock apps is a requirement.** It is an independent replacement firmware, not an extension of the vendor app registry.[37]
 Stock weather, the Picture album interface, AIDA64 Monitor, and touch/menu behavior are not preserved by this implementation (`community/README.md:18–22`; `community/src/main.cpp:43–62`).[37][45]

**OTA transport is plausible, not certified safe for this exact unit.** The correct Pro target exists.[38]
But the claim that its partition table was verified from `/space.json` does not establish the actual OTA-slot offsets or sizes.[39]
Shared-filesystem auto-format, missing Wi-Fi migration, unknown stock bootloader rollback configuration, and pre-5.1 bootloader compatibility must be resolved before a preservation-oriented installation.[43][26][28]

## 1. Scope and evidence boundaries

- Local source snapshot: `/opt/data/smalltv-pro-recon/community`, commit `23890065eb1f85dfa3cdc20e46bab044d98e8834`, declaring firmware `2.16.0` in `src/config.h:14–15`.[41]
- Vendor snapshot: `/opt/data/smalltv-pro-recon/vendor`, commit `44c8030ce065071470035e75a59acbcc1cce8e0f`. A tracked-file inventory found no C/C++ implementation source; its public deliverables are firmware binaries and manuals. The vendor README describes uploading a model-specific `.bin` (`Readme.md:32–38`).[51]
- **Parent-provided live observations, not re-probed by this reviewer:** `/v.json` returned `{m: GeekMagic SmallTV-PRO, v: V3.3.65EN}`; `/space.json` returned total `3866624`, free `1396236`; the saved stock `/update` page is a multipart firmware-upload form. The parent reports 12 `/.sys` files plus 11 `/image` files backed up under `device-backup` (23 files). **That is a settings/assets backup, not a flash dump.** Those private backups and the protected configuration file were not opened here.
- This review made no device requests, writes, firmware builds, flashes, code edits, repository changes, or credential accesses. It inspected public code/manuals and the public matching-version vendor binary. Source repository working trees were clean before and after inspection. Scratch evidence is under `/opt/data/cache/scratch/smalltv-ota-evidence/`.

### Matching-version vendor binary: independently checked

The file inspected was `vendor/firmware/PRO_V3.3.65EN/FW_SmallTV-PRO_V3.3.65EN.bin`, not a newer release. Its release history dates V3.3.65 to **8 May 2025** (`update history.txt:1–2`). The following are local byte measurements of that public artifact, not measurements of the installed flash.[53][55]

| Check | Result |
|---|---|
| File size | `2106432` bytes |
| SHA-256 | `1aa9a0408e8a3bee568a45376eb2583fe35ba4daafc14880a8cf1531540066be` |
| MD5 | `ce66c79ffcb733e66b520498ca50f2e7`, matching the adjacent vendor `md5sum.txt:1` |
| First 24 bytes | `e905023f00320840ee0000000000000000ffff0000000001` |
| Header interpretation | ESP32 chip ID `0`, five segments, DIO, declared 8 MB flash, 80 MHz flash clock |
| Image integrity | Segment XOR checksum and appended SHA-256 both verified |
| App descriptor | `idf_ver = v4.4.6-dirty`; project `arduino-lib-builder` |
| Image type | An application image, not an 8 MB flash backup or a merged bootloader/partition-table image |

The header/descriptor interpretation follows Espressif `esp_app_format.h:15–21,31–63,70–109,118–129`. The declared flash size is **not** a JEDEC measurement of the device.[36]
 An app's IDF descriptor is **not** proof of the installed bootloader's version.[36][28]
 Reproducible measurements are saved in `stock-image-audit.json` in the scratch evidence directory.[36][55]

## 2. Exact board configuration in smalltv-mod

Use **`smalltv_esp32_8mb`**, not the ESP8266 loader, ESP32-C2 target, or ordinary NM-TV-154 ESP32 target. Its build flags select both `SMALLTV_ESP32` and `SMALLTV_ESP32_PRO`; `config.h:59–67` selects the Pro pin header before the generic ESP32 header. The platform is pinned to `55.03.311`; that platform's `platform.json:32–42` selects Arduino core **3.3.11** (`community/platformio.ini:221–263`).[38][41][58]

| Function | SmallTV-PRO setting | Code evidence |
|---|---|---|
| TFT SPI clock | GPIO **18** | `src/board_esp32_pro.h:14` |
| TFT MOSI | GPIO **23** | `src/board_esp32_pro.h:15` |
| TFT data/command | GPIO **2** | `src/board_esp32_pro.h:16` |
| TFT reset | GPIO **4** | `src/board_esp32_pro.h:17` |
| TFT chip select | **No GPIO**; tied to ground, `TFT_CS=-1` | `src/board_esp32_pro.h:18` |
| Backlight | GPIO **25**, **active-low** PWM | `src/board_esp32_pro.h:19,24–25`; `src/Gfx.cpp:112–116` |
| Touch | GPIO **32**, T9, according to the board comment; **no implemented button handling** | `src/board_esp32_pro.h:10–11` |
| Ambient-light support | `HAS_LDR=0`; auto-brightness code compiled out | `src/board_esp32_pro.h:27–29`; `src/main.cpp:118–136` |
| Display | 240×240 ST7789-family IPS, SPI mode **3** | `src/config.h:69–70`; `src/Gfx.cpp:19–25,82–101` |

These are exact **source settings**, not a physical measurement of this board revision.[40][42]
Independent Pro implementations corroborate clock/MOSI/DC/reset/backlight: jo-m's Kconfig defaults at lines `3–6,22–35,41–59`, its LCD driver at `lcd.c:80–98`, and clowrey's configuration at `small-tv-pro-lvgl.yaml:49–52,67–70,125–137`.[19][18][21]
GPIO32 wiring remains attributed to smalltv-mod's comment rather than independently measured here.[40]

The custom flashing guide documents a six-pad Pro UART header: pad **1** (square) GND, **2** TX, **3** RX, **4** 3V3, **5** GPIO0, **6** RST (`flashing.md:141–150`). It describes a 3.3 V adapter and power-on GPIO0 download-mode selection. This is a documented recovery pinout, not a verified identification of the pads on the user's particular board; no connection or reset was attempted.[49]

Do not borrow the NM-TV-154 mapping. The audited GeekTV fork's ordinary ESP32 header uses clock **14**, MOSI **13**, CS **15**, backlight **19**, no reset GPIO, and a switched power pin **21** (`board_esp32.h:11–21`). A chip-compatible but board-incompatible app can therefore boot with an unusable display; matching “ESP32” alone is insufficient.[33]

## 3. Partition offsets: what is and is not verified

The following is **the custom repository's proposed layout**, exactly as written at `community/partitions/smalltv_8mb_ota.csv:8–12`. It is **not an independently verified dump of this device's table**.[39]

| Label | Type/subtype | Proposed offset | Proposed size | Exclusive end |
|---|---|---|---|---|
| `nvs` | data / nvs | `0x9000` | `0x5000` | `0xE000` |
| `otadata` | data / ota | `0xE000` | `0x2000` | `0x10000` |
| `app0` | app / ota_0 | `0x10000` | `0x220000` | `0x230000` |
| `app1` | app / ota_1 | `0x230000` | `0x220000` | `0x450000` |
| `spiffs` | data / spiffs | `0x450000` | `0x3B0000` | `0x800000` |

**Evidence gap:** CSV comments at lines `2–4` identify `/space.json` and an unlinked `GeekTV-Pro/partitions.csv` as their basis. The parent's `3866624` total equals `0x3B0000`, but a filesystem capacity counter cannot establish `app0/app1` offsets, two equal slots, NVS/otadata positions, or partition-table contents. The app-only vendor binary cannot supply the installed table either. A public GitHub search did not identify the named `GeekTV-Pro` repository; do not treat that comment as independently corroborated hardware evidence.[39][27]

### Actual app-OTA constraints

1. **The existing flash table controls runtime writes.** Arduino 3.3.11 selects the next OTA partition using `esp_ota_get_next_update_partition(NULL)` and refuses a missing/running target (`Updater.cpp:235–240`); `Esp.cpp:271–277` returns that partition's actual size. Changing a project CSV does not rewrite the live table through an app-only upload.[5]
 An app using runtime partition lookup need not intrinsically hard-code these CSV offsets, but any raw-address write or filesystem image must match the actual table.[5][7]
2. **Use the plain Pro app image:** `smalltv-mod-firmware-esp32-pro.bin`, corresponding to `.pio/build/smalltv_esp32_8mb/firmware.bin`. A `.factory.bin` is a different, merged artifact; it is not an OTA payload.[37]
 The current guide explicitly retains stock bootloader/table for app OTA (`flashing.md:129–137`).[37][49]
3. **App size is bounded by the receiving slot, not available filesystem space or the whole-flash size.** `board_upload.maximum_size=8388608` (`platformio.ini:226–232`) is not permission to put an 8 MB app in an OTA slot.[38][5]
4. **For the proposed `0x220000` slot only:** slot size would be `2228224` bytes. smalltv-mod's manual upload handler applies `(getFreeSketchSpace()-0x1000)&0xFFFFF000`, so its effective manual limit would be `0x21F000 = 2224128` bytes (`WebPortal.cpp:460–465`). The matching vendor app is smaller by `121792` bytes than that proposed slot, or `117696` bytes than that manual limit. **This does not measure the stock uploader's actual limit or any custom build's final size.**[46][7]
5. **Stock bootloader compatibility is a separate gate.** Espressif supports older bootloaders booting newer-IDF apps, but explicitly warns that a pre-5.1 bootloader cannot load an app using `CONFIG_ESP_SYSTEM_ESP32_SRAM1_REGION_AS_IRAM`. Confirm that setting is disabled in the actual candidate's SDK configuration if the retained bootloader is pre-5.1, and verify image flash settings/chip revision requirements. Neither the installed bootloader nor a candidate build/configuration was inspected here (`bootloader` documentation, “Before ESP-IDF V5.1” and “SPI Flash Configuration”).[28]

**Required evidence before approving an OTA:** actual partition-table metadata (normally at `0x8000`, but verify the bootloader configuration), current running/next app slot and sizes, retained bootloader/security configuration, and the exact candidate image's size/header/configuration. A metadata-only UART read or a trusted existing runtime diagnostic can establish the table; no such read or firmware installation was attempted in this review. Filesystem free space is not a substitute.[27][5][28]

## 4. Filesystem preservation and Wi-Fi migration

### Critical: mount failure is treated as permission to erase

`src/Settings.cpp:456–460` first calls `LittleFS.begin()`, then explicitly calls `LittleFS.format()` on failure. `main.cpp:186–195` runs this before networking, and ignores the return values of settings initialization/loading. Thus a layout/format mismatch or corruption can erase stock settings/assets rather than safely stopping.[43][45]

The partition's label/subtype `spiffs` does **not** prove its on-disk format is SPIFFS.[17]
 Arduino LittleFS defaults to the **label** `spiffs` (`LittleFS.h:29`).[17]
 The matching V3.3.65 vendor app contains `LittleFS`, `esp_littlefs`, and `lfs.c` implementation markers, which strongly suggests LittleFS is linked into stock; that is not an on-device mount/format/configuration test. Even a correct label and likely common format do not justify erasing a failed mount.[43]
[17][55][43]

A successful default Arduino mount is also not read-only: `LittleFS.cpp:63–70` sets `read_only=false` and `grow_on_mount=true`.[9]
 Its `format()` delegates to formatting that selected filesystem partition (`LittleFS.cpp:98–110`).[9]
 For stock-preserving work, require **no format-on-failure, no automatic growth, and an explicitly read-only first inspection**; use an isolated configuration namespace/storage strategy rather than modifying stock data accidentally. This is a proposed safety requirement, not an implemented change.[9][43]

### No automatic stock Wi-Fi migration

smalltv-mod reads **`/config.json`**, not stock **`/.sys/config.json`** (`Settings.cpp:6,463–474`).[43]
 Its parser expects `wifi:[{ssid,pass}]` or its own legacy `staSsid/staPass` schema (`Settings.cpp:549–583`); “legacy migration” in this code refers to smalltv-mod releases, not GeekMagic settings.[43]

Defaults set `wifiCount=0` (`Settings.cpp:422–429`).[43]
 `Net.cpp:33–40` sets `WiFi.persistent(false)` and immediately opens AP mode when no custom networks are saved.[44]
 Therefore surviving vendor Wi-Fi data in NVS does not make this code autojoin stock Wi-Fi.[44]
 Expected first-install behavior is an open **`SmallTV-Setup`** AP at **`192.168.4.1`**, followed by deliberate user Wi-Fi setup (`config.h:349–350`; `Net.cpp:14–27`). This can make the existing LAN address disappear without the firmware being bricked.[44]
[43][44][41]

Also inspect **framework-level NVS behavior**, not only sketch writes. Arduino `esp32-hal-misc.c:331–337` erases the NVS partition if initialization reports `ESP_ERR_NVS_NO_FREE_PAGES` or `ESP_ERR_NVS_NEW_VERSION_FOUND`.[16]
 This is conditional, not an assertion that this unit will trigger it.[16]
 `WiFi.persistent(false)` selects RAM Wi-Fi storage (`WiFiGeneric.cpp:299–300`); it does not prevent the earlier core-level NVS erase.[16][11]
[16][11]

**Acceptable migration choices require explicit consent:** either manual reconfiguration through the custom AP, or a separately reviewed importer that reads the correct stock schema without erasing the filesystem and keeps secrets out of logs/build artifacts. No importer exists in this snapshot, and no credentials were read to assess it.[43][44]

## 5. Rollback and recovery: four different mechanisms

| Mechanism | Finding |
|---|---|
| Interrupted-download safety | Arduino writes the inactive app partition and withholds its initial bootable bytes until completion (`Updater.cpp:640–652,728–740`). Espressif's app OTA design protects the current app against interrupted download/selection. This is not assurance that the new firmware boots correctly or preserves shared data. |
| Automatic failed-boot rollback | Requires appropriate **installed bootloader** support/configuration and OTA state transitions. Two app slots alone do not prove this. Stock bootloader configuration remains unknown. |
| Manual return to previous slot | Arduino supplies `canRollBack()` / `rollBack()` (`Updater.cpp:138–151`), but this project exposes no corresponding route or action in `WebPortal.cpp:494–520`. The next OTA into the other slot can overwrite the retained stock app. |
| Recovery UI / safe mode | On panic/watchdog resets, custom code suppresses feature rendering and keeps its own web UI reachable when startup reaches it (`main.cpp:174–188,222–238,260–263`). It does not select the old stock app and cannot cover faults before the server starts. |

Evidence for the table: Arduino updater implementation and Espressif “App Rollback.”[5][26]
Custom recovery and route coverage are grounded in the project's startup/route code.[45][46]

**Do not claim that the sketch simply “has no rollback confirmation.”** Arduino 3.3.11 has its own hooks: `verifyOta()` defaults true, `verifyRollbackLater()` defaults false, and `initArduino()` conditionally confirms a pending image before the sketch's `setup()` (`esp32-hal-misc.c:261–287,314–328`; `cores/esp32/main.cpp:111–113`). The community source contains no override or post-startup health check.[45][46]
 If those core hooks are enabled and stock bootloader rollback is supported, they can cancel rollback before display/Wi-Fi/web health is demonstrated. If not enabled, that protection is not established either.[16][8][45]

The vendor's V3.2.21 history describes repeated incomplete boots causing **AP recovery** (`vendor/firmware/PRO_V3.3.65EN/update history.txt:137–139`); it does not establish old-image rollback. The custom “factory reset” only removes its own configuration, not the firmware (`Settings.cpp:487–489`; `reference/recovery.md:8–12`).[53][43][50]

**Correction to the custom project's documentation:** `flashing.md:137` says the stock image is not officially redistributed. The audited official vendor repository **does** provide the matching V3.3.65 app binary. That supplies a potential app-restore payload if a compatible updater remains reachable, but not the original bootloader/table/NVS/filesystem. A full flash backup has a different recovery scope; the parent's 23-file backup is not one. Returning to stock after erasing shared data would require data restoration too, and is not verified by possessing a vendor app binary.[49][51][55]

## 6. Additional concrete failure hazards in giovi321/smalltv-mod

- **No firmware authenticity assurance from its self-updater:** GitHub API and firmware download clients use `setInsecure()` (`OtaUpdate.cpp:49–50,132–140`). The sketch does not pin a trusted release digest/signature. SDK image-integrity checks are not publisher authentication.[36]
 Default web auth is off (`Settings.cpp:189–192`; `WebPortal.cpp:54–59`), including initially on the open setup AP.[47][43][46]
- **Manual upload success is not explicitly tracked:** completion tests only `!Update.hasError()` and schedules a reboot (`WebPortal.cpp:437–442`), not whether a firmware upload began and ended successfully. An empty POST can consequently be acknowledged without installing an image.[46]
 The core also has an allocation-failure return without setting an error (`Updater.cpp:290–295`).[5]
 These are static error-path findings, not device-tested failures.[46][5]
- **End-of-upload uses `Update.end(true)`:** there is no independent expected file length or board-model check in the sketch (`WebPortal.cpp:456–467`). The underlying updater still checks image validity when setting the boot partition (`Updater.cpp:715–740,766–829`); do not conclude that arbitrary truncated garbage will necessarily boot.[5]
 A valid image for the wrong classic-ESP32 board remains a different risk.[33]
[46][5][33]
- **The first custom boot is not storage-atomic:** app OTA's inactive-slot protection does not protect shared filesystem/NVS changes executed after boot. Retaining a stock app slot does not restore stock photos/settings after a format.[43][16][26]
- **Safe mode has limited reach:** filesystem and display initialization precede web startup; all compiled modes still run their `begin()` calls (`main.cpp:186–195,222–230`). A fault there can recur despite the safe-mode rendering guard.[45]
- **The ESP8266 loader is not a Pro rescue/partition-migration mechanism:** its build target and imports are explicitly ESP8266 (`platformio.ini:115–124`; `loader.cpp:15–18`). Never adapt its two-hop instructions to the classic ESP32 Pro by uploading that binary.[38][48]

## 7. Feature-preserving alternatives and their limits

### A. Keep stock firmware; use a supported external data/display path

**Monitor backend:** vendor instructions enable AIDA64 RemoteSensor LCD support on TCP port 80 and point the device at a host PC. The documented stock renderer displays CPU usage/temperature/frequency, RAM, and drive information (`How to use Monitor APP.pdf`, extracted lines `5,12–13`; `monitor_config_file_v1.3.rslcd:4–14`). The saved device page `monitor.html:46–51` only configures host IP and refresh interval.[56]
 A compatible external feed is a plausible stock-preserving option for that bounded data screen. **It is not evidence of an arbitrary drawing API, executable plugin loader, or a new menu-app registration hook.** Protocol/layout extension would require separate research.[56][57]

**Picture/image backend:** the vendor manual supports JPEG/GIF pictures up to 240×240 (`SmallTV Pro User manual V3.2.52EN.pdf`, extracted lines `54–60`). A separate primary implementation, `ssafayet/geekmagic-custom-apps`, pushes rendered JPEG dashboards through stock `/doUpload` and the Picture app rather than installing firmware. Its `stock-pro.ts:104–119` uses multipart field **`file`**, distinct from firmware upload. This leaves stock application code in place, but is an externally rendered screen, not an on-device custom firmware app.[29]
[63][29]

**Important limits:** that project's author reports physical verification on **V3.4.88EN**, not this unit's **V3.3.65EN** (`docs/DEVICES.md:9–14`). Its deterministic managed mode deletes other album pictures with consent and backup (`stock-pro.ts:26–31,84–101,180–190`; `DEVICES.md:84–99`). Do **not** describe installing/running managed takeover as automatically preserving the existing photo library. Preserve the parent's album, validate older-firmware behavior separately, and require explicit consent for any later uploads/deletions. Continuous JPEG replacement also warrants a flash-write rate budget.[30][29]

### B. Fork/reimplement features only after the user chooses replacement

smalltv-mod's registered modes are ticker, usage, radar, Home Assistant, and theme; notification handling is separate (`main.cpp:25–62`). Theme weather fields/animated sprites are not the original stock weather/Picture/Monitor apps.[37][45]
 Touch handling is expressly absent.[40]
 Porting equivalent screens is possible engineering work, not evidence that existing features survive an OTA.[45][37][40]

The audited **`bairachnyi/geektv`** snapshot (`dcc33efb8e141ed5561a1dc6e229d976dde24210`) implements clock/weather and JPEG/GIF gallery (`README.md:39–52`), but lists ESP8266, C2, and **NM-TV-154**, not SmallTV-PRO (`README.md:59–68`).[31]
Its generic ESP32 target uses the wrong pin header and a 4 MB table with `0x180000` app slots (`platformio.ini:137–150`; `board_esp32.h:11–21`; `smalltv_4mb_ota.csv:8–10`).[32][33][34]
It is a candidate for a **reviewed Pro port/reimplementation**, not a ready stock-preserving image to upload. It is also not the unidentified `GeekTV-Pro` citation in smalltv-mod's partition comment.[31][39]

### C. Dual boot or binary patch: research options, not completed preservation

**Dual boot:** keeping stock in one app slot while a carefully designed custom app runs in the other can retain a return path, if the actual table/bootloader support it and both apps leave shared stock storage intact. It would need an intentional selector, protected stock slot, isolated settings, and no normal self-update that overwrites that slot. Unmodified smalltv-mod does not implement this workflow; it is not “add a screen to the same stock menu.”[5][46][43]

**Binary patch:** the vendor publishes an app image but no audited source or plugin SDK. A version-specific patch preserving the rest of that application would require reverse-engineering the app/menu/render callbacks and updating image integrity data, while respecting any configured security checks. No injection point, patch, or safe install procedure was demonstrated in this read-only review. Editing web assets or adding JSON to `/.sys/app.json` is not by itself proof that the MCU can execute a new screen.[51][55][36]

## 8. Decision and acceptance gates

**For “extend the existing firmware without losing stock weather/photo apps”: keep stock and first choose between the bounded Monitor feed and a non-destructive Picture-backed external screen.** Both preserve firmware code; neither silently converts the device to a replacement firmware.[56][63][29]

**For native new on-device code:** ask the user to choose explicitly between a stock-specific binary-patch investigation, protected dual-boot design, and a replacement/Pro port with enumerated feature parity. The current unmodified smalltv-mod is **NO-GO for stock feature preservation**.[37][45]

Any future custom OTA approval should require all of the following:

- Actual live app offsets/sizes, filesystem label/format, current slot, and bootloader/security compatibility established; `/space.json` alone rejected as partition-table proof.[27][5][28]
- Correct Pro plain app image, measured final size, compatible headers, and pre-5.1 SRAM1-IRAM setting checked where applicable.[38][5][28]
- Stock settings/assets preserved with no implicit format/growth, and core NVS erase conditions addressed rather than ignored.[43][9][16]
- A consented Wi-Fi migration/setup plan and nearby recovery access, without logging or embedding credentials.[43][44]
- Delayed health confirmation/explicit return-to-stock strategy, and protection against the next update destroying the stock slot.[16][5][46]
- Named feature acceptance tests: stock weather, JPEG/GIF album and existing files, stock Monitor, time/night brightness, touch short/double/long press, menu navigation, reboot, and recoverability. Native replacements must state what is reimplemented and what is lost.[63][56][45]

**Not accomplished or claimed:** a live partition-table verification, physical pin measurement, safe rollback test, stock Wi-Fi migration, custom binary build/size validation, stock-to-custom OTA acceptance test, binary patch, or preservation-oriented firmware implementation. No device state was changed by this reviewer.

## Sources

[5] https://raw.githubusercontent.com/espressif/arduino-esp32/3.3.11/libraries/Update/src/Updater.cpp
[7] https://raw.githubusercontent.com/espressif/arduino-esp32/3.3.11/cores/esp32/Esp.cpp
[8] https://raw.githubusercontent.com/espressif/arduino-esp32/3.3.11/cores/esp32/main.cpp
[9] https://raw.githubusercontent.com/espressif/arduino-esp32/3.3.11/libraries/LittleFS/src/LittleFS.cpp
[11] https://raw.githubusercontent.com/espressif/arduino-esp32/3.3.11/libraries/WiFi/src/WiFiGeneric.cpp
[16] https://raw.githubusercontent.com/espressif/arduino-esp32/3.3.11/cores/esp32/esp32-hal-misc.c
[17] https://raw.githubusercontent.com/espressif/arduino-esp32/3.3.11/libraries/LittleFS/src/LittleFS.h
[18] https://raw.githubusercontent.com/jo-m/smalltv-pro-esp-idf/d31bb8e8992286fb6012194ef146f7dd47e23274/components/display/lcd.c
[19] https://raw.githubusercontent.com/jo-m/smalltv-pro-esp-idf/d31bb8e8992286fb6012194ef146f7dd47e23274/components/display/Kconfig.projbuild
[21] https://raw.githubusercontent.com/clowrey/esphome-geekmagic-small-TV-pro/c9c58154a5017b6218dd0828f59c49cbdc5fce40/small-tv-pro-lvgl.yaml
[26] https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/system/ota.html
[27] https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-guides/partition-tables.html
[28] https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-guides/bootloader.html
[29] https://raw.githubusercontent.com/ssafayet/geekmagic-custom-apps/96c93fbd1017fe2c8762728bba6a1a11d74ee298/packages/device-core/src/adapters/stock-pro.ts
[30] https://raw.githubusercontent.com/ssafayet/geekmagic-custom-apps/96c93fbd1017fe2c8762728bba6a1a11d74ee298/docs/DEVICES.md
[31] https://raw.githubusercontent.com/bairachnyi/geektv/dcc33efb8e141ed5561a1dc6e229d976dde24210/README.md
[32] https://raw.githubusercontent.com/bairachnyi/geektv/dcc33efb8e141ed5561a1dc6e229d976dde24210/platformio.ini
[33] https://raw.githubusercontent.com/bairachnyi/geektv/dcc33efb8e141ed5561a1dc6e229d976dde24210/src/board_esp32.h
[34] https://raw.githubusercontent.com/bairachnyi/geektv/dcc33efb8e141ed5561a1dc6e229d976dde24210/partitions/smalltv_4mb_ota.csv
[36] https://raw.githubusercontent.com/espressif/esp-idf/v4.4.6/components/bootloader_support/include/esp_app_format.h
[37] https://github.com/giovi321/smalltv-mod/blob/23890065eb1f85dfa3cdc20e46bab044d98e8834/README.md
[38] https://github.com/giovi321/smalltv-mod/blob/23890065eb1f85dfa3cdc20e46bab044d98e8834/platformio.ini
[39] https://github.com/giovi321/smalltv-mod/blob/23890065eb1f85dfa3cdc20e46bab044d98e8834/partitions/smalltv_8mb_ota.csv
[40] https://github.com/giovi321/smalltv-mod/blob/23890065eb1f85dfa3cdc20e46bab044d98e8834/src/board_esp32_pro.h
[41] https://github.com/giovi321/smalltv-mod/blob/23890065eb1f85dfa3cdc20e46bab044d98e8834/src/config.h
[42] https://github.com/giovi321/smalltv-mod/blob/23890065eb1f85dfa3cdc20e46bab044d98e8834/src/Gfx.cpp
[43] https://github.com/giovi321/smalltv-mod/blob/23890065eb1f85dfa3cdc20e46bab044d98e8834/src/Settings.cpp
[44] https://github.com/giovi321/smalltv-mod/blob/23890065eb1f85dfa3cdc20e46bab044d98e8834/src/Net.cpp
[45] https://github.com/giovi321/smalltv-mod/blob/23890065eb1f85dfa3cdc20e46bab044d98e8834/src/main.cpp
[46] https://github.com/giovi321/smalltv-mod/blob/23890065eb1f85dfa3cdc20e46bab044d98e8834/src/WebPortal.cpp
[47] https://github.com/giovi321/smalltv-mod/blob/23890065eb1f85dfa3cdc20e46bab044d98e8834/src/OtaUpdate.cpp
[48] https://github.com/giovi321/smalltv-mod/blob/23890065eb1f85dfa3cdc20e46bab044d98e8834/src/loader.cpp
[49] https://github.com/giovi321/smalltv-mod/blob/23890065eb1f85dfa3cdc20e46bab044d98e8834/docs/src/content/docs/getting-started/flashing.md
[50] https://github.com/giovi321/smalltv-mod/blob/23890065eb1f85dfa3cdc20e46bab044d98e8834/docs/src/content/docs/reference/recovery.md
[51] https://github.com/GeekMagicClock/smalltv-pro/blob/44c8030ce065071470035e75a59acbcc1cce8e0f/Readme.md
[53] https://github.com/GeekMagicClock/smalltv-pro/blob/44c8030ce065071470035e75a59acbcc1cce8e0f/firmware/PRO_V3.3.65EN/update%20history.txt
[55] https://github.com/GeekMagicClock/smalltv-pro/blob/44c8030ce065071470035e75a59acbcc1cce8e0f/firmware/PRO_V3.3.65EN/FW_SmallTV-PRO_V3.3.65EN.bin
[56] https://github.com/GeekMagicClock/smalltv-pro/blob/44c8030ce065071470035e75a59acbcc1cce8e0f/user%20manual/How%20to%20use%20Monitor%20APP.pdf
[57] https://github.com/GeekMagicClock/smalltv-pro/blob/44c8030ce065071470035e75a59acbcc1cce8e0f/user%20manual/monitor_config_file_v1.3.rslcd
[58] https://raw.githubusercontent.com/pioarduino/platform-espressif32/55.03.311/platform.json
[63] https://github.com/GeekMagicClock/smalltv-pro/blob/44c8030ce065071470035e75a59acbcc1cce8e0f/user%20manual/SmallTV%20Pro%20User%20manual%20V3.2.52EN.pdf
