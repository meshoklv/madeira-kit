# DS3: аппаратный TSO на iPhone — можно ли включить

Дата: 20.10.2026. Итог: **на iOS 27 без эксплойта ядра — нельзя.** Чип, скорее всего, умеет, но включить его может только ядро, и в публичном ядре iOS для сторонних приложений нет ни вызова, ни флага.

## 1. Есть ли бит TSO в A-серии

- Бит: `ACTLR_EL1_EnTSO (1ULL << 1)` в `osfmk/arm64/proc_reg.h` открытого xnu (xnu-12377.121.6, строка 3233). **Проверено фактом** (скачан файл с github apple-oss-distributions/xnu).
- **A12Z (t8020, iPad-чип)** — TSO есть: под него написана первая версия TSOEnabler (ветка `t8020`), DTK гонял Rosetta 2. Источник: README https://github.com/saagarjha/TSOEnabler.
- **A14 = те же ядра Firestorm/Icestorm, что в M1** — TSO есть (M1 подтверждён: Rosetta, Asahi, патчи Linux https://lkml.iu.edu/hypermail/linux/kernel/2404.1/04656.html).
- **A17 Pro / A18 / A19** — прямых доказательств не нашёл. M3/M4/M5 на тех же ядрах, Rosetta там работает → **[версия]: бит есть**. Проверить на iPhone без ядра нельзя: `ACTLR_EL1` из EL0 не читается.

## 2. Можно ли включить из приложения

- Бит пишется только на EL1. Ядро само выставляет его при возврате в пользовательский режим, если у потока стоит внутренний флаг TSO (код TSOEnabler ищет в ядре `ldr [thread,#off]; cbz; mrs actlr_el1; orr #0x2`, затем пишет байт в структуру потока **из кекста**).
- В открытом xnu код, который пишет `EnTSO`, **вырезан**; нет ни syscall, ни sysctl, ни `thread_set_state`-флейвора. Rosetta-путь (`CONFIG_ROSETTA`, `IMGPF_ROSETTA`, `sysctl.proc_translated`) в `config/MASTER.arm64.iPhoneOS` включён **только в DEV/DEBUG сборках ядра** (опция `rosetta` в `BSD_DEV`/`BSD_DEBUG`, в `BSD_RELEASE` её нет) — на розничном iOS его нет вообще. Проверено фактом.
- Отладчик (наш JIT через StikJIT) меняет только `arm_thread_state64` (x0–x28, fp, lr, sp, pc, cpsr) и отладочные регистры — `ACTLR` туда не входит. `get-task-allow` даёт только `task_for_pid`/отладку, не доступ к EL1.
- Hypervisor.framework (на macOS 14.4+ гость может писать TSOEN) на iPhone приложениям недоступен (частное право `com.apple.private.hypervisor`).
- Остаётся только эксплойт ядра (как TSOEnabler, но на iOS: KTRR/PPL/SPTM защищают код, но данные потока писать можно) — для iOS 27 на A17+ публичных нет. **Не реально.**

## 3. Что в Madeira

- `FEX/Source/Windows/Common/FEXUnixLib.cpp: TryEnableHardwareTSO()` под `FEX_IOS_HOST` всегда `return false` → игровой путь (xtajit64.dll) честно использует программный TSO. Правильно.
- `src/app/Madeira/FEXBridge.mm:474` вызывает `SetHardwareTSOSupport(true)` **без проверки железа** — это выключает эмуляцию TSO. Используется только в самотесте `fex_test_execute` (ContentView.swift:2351), не в играх. Безопасно, но вводит в заблуждение комментарием «Apple Silicon supports TSO».
- Обсуждений аппаратного TSO на iOS у UTM / iSH / Pojav / Winlator-форков не нашёл (UTM на iOS — TCG, аппаратный TSO его не касается).

## 4. Какой был бы выигрыш

- FEX: «эмуляция порядка памяти x86 — главный тормоз», до ~10× на отдельных участках даже с RCPC (FEX-2404/2306 релиз-ноты, https://fex-emu.com/FEX-2306/). Для целых игр — [версия] +20–50 % в CPU-узких местах (как в DS3-PERF-knobs.md, пункт 14).
- Что было бы нужно: включить бит на **всех** потоках гостя до первого их запуска (иначе гонки) и ответить `true` в `TryEnableHardwareTSO()`; `FEX_TSOENABLED` трогать не нужно — FEX сам выключит барьеры при `SetHardwareTSOSupport(true)`.

## Что реально осталось

Только программные рычаги: `FEX_TSOENABLED=0` (риск порчи данных) или снятие TSO по модулям (`FEX_EXTENDEDVOLATILEMETADATA`) — см. DS3-PERF-knobs.md.
