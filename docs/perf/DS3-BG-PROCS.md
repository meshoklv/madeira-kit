# DS3: фоновые процессы Steam и их цена (20.10.2026)

Источник: логи `logs/ds3/DarkSoulsIII.exe-2026-10-20_21-35-10.txt` (333 с игры) и
`..._20-52-57.txt` (127 с), исходники `<build-tree>/src` (`build/ntdll-unix/server_ios.c`,
`process_ios.c`, `loader_ios.c`, `docs/MADEIRA_DOCK.md`). Пометки: **[факт]** — посчитано
по логу/коду, **[версия]** — не проверено.

## 1. Что реально запущено

Вопрос исходил из того, что рядом с игрой работает настоящий Steam (steam.exe +
steamwebhelper). **Это не так [факт].** Madeira Dock — свой headless `dockhost.exe`,
который грузит `steamclient64.dll` внутрь себя; ни steam.exe, ни Chromium-хелпера,
ни steamservice, ни gameoverlayui в сессии нет (в логе 0 упоминаний `steam.exe`,
`steamwebhelper`; `steamservice.dll` не загрузился — c000007b).

| Процесс | PEB | Как появился | Потоки |
|---|---|---|---|
| explorer.exe (рабочий стол) | 0x71ffff0000 | первый процесс сессии | 002c, 003c… (wine_*) |
| dockhost.exe + steamclient64 | 0x10b600000 | `[phase] spawn` t+3.1 c | 0040–00a8: IPC:CSteamEngine, SteamEngineWatchdog, CJobMgr, CHTTP*, CNet Encrypt, SocketThread, CSteamController… |
| conhost.exe --headless | 0x10b6f0000 | t+3.2 c (консоль dockhost) | — |
| DarkSoulsIII.exe | 0x10b5f4000 | t+15.7 c, запускает Valve's LaunchApp | 00ac и все потоки выше |

Отклонено гейтом `[proc-gate]` (уже по умолчанию): `steamerrorreporter64.exe` ×2,
`vulkandriverquery64.exe`, `vulkandriverquery.exe`.

Как привязывать потоки к процессам: `[thr-create] creator_peb=…` + `[thr-name] tid=…`;
win-tid выдаются по порядку, всё до 00ac (главный поток игры, `signal_start_thread …
peb=0x10b5f4000`) принадлежит explorer/dockhost/conhost. Формат `[xp-t]`:
`<роль><tid>:Pмс/Eмс:ГГцP/ГГцE:Минстр` за сэмпл ~320 мс, показываются только 14 самых
занятых потоков ≥2 мс (покрытие ~83 % CPU процесса). `m<число>` — нативные потоки
хоста (Madeira/wineserver, к Windows-процессам не относятся).

## 2. Сколько едят не-игровые процессы [факт]

Игра, весь процесс (`[xp]`): **P ≈ 1 608 мс/с, E ≈ 814 мс/с** (из 2 000 и 4 000
возможных: P-ядра заняты на ~80 %, E — на ~20 %).

- **dockhost/explorer/conhost (потоки < 00ac): 0,03 мс/с** в 21-35 и 0,02 мс/с в 20-52.
  За 333 с игры поток Steam попал в топ-14 `[xp-t]` три раза. В `[thread-sample]`
  (замер раз в 20 с) все ~25 потоков Steam — `cpu=0%`. Верхняя граница для потока,
  ни разу не попавшего в топ: < 6 мс/с.
- `[srv-stuck]` по Steam IPC — это ожидания, а не CPU (см. DS3-PERF-next.md).
- **gameoverlayrenderer64.dll**: загружен в игру (`Load module … 71EF1F0000`, 1,7 МБ,
  x64 без копии в пул, TLS-слот 7). Собственных потоков нет; из 3 170 адресов в
  `[rip-profile]`/`[thread-sample]` в его диапазон не попал ни один; в `[xp-api-top]`
  его нет. Значит, хук Present стоит в пределах шума замера (< ~0,1 %) [факт по
  сэмплам; точную цену за кадр не мерили].

Куда уходит CPU на самом деле — игра: 00ac (главный, ~670 мс/с), GXWorker:1–5
(~115 мс/с каждый), 012c (~92), dxmt-encode-thr (~77), GXRenderThread (~72),
FD4JobWorker:1 (~66), плюс нативные потоки хоста m839482 (~144), m838320 (~102),
wine-x18-exc (~42). Что такое m839482/m838320 — **[версия]** wineserver-поток и
поток Metal/UI; имена у них пустые.

## 3. Существующие ручки

- **`env.MADEIRA_BG_QOS_PROCS`** (по умолчанию `SocialClubHelper.exe;Launcher.exe;
  RockstarService.exe;dockhost.exe`): **в DS3 не работает [факт]**. Включается только
  когда `[xp]` видит поток с ролью P, а роль регистрирует только madeira-d3d12;
  DS3 идёт через DXMT (D3D11) — строк `[bg-qos]` и `ml1128 role` в обоих логах 0.
  Да и переносить нечего: dockhost простаивает.
- **`env.MADEIRA_SPAWN_BLOCK`**: в игре больше ничего не запускается — блокировать
  нечего. dockhost блокировать нельзя (он и есть Steam-клиент: без него нет входа,
  лицензии и `steam_api` игры). conhost — консоль dockhost; CPU 0, блокировка —
  риск поломать старт ради копий DLL в JIT-пуле.
- **Опции Steam (-no-browser, -cef-disable-gpu, -noverifyfiles)**: неприменимы —
  steam.exe не запускается, Dock передаёт только launch option по умолчанию (свои
  аргументы не поддерживаются, MADEIRA_DOCK.md).
- **Оверлей Steam**: отдельной ручки в Madeira/Dock нет (поиск по исходникам: 0).
  Работает общий механизм Wine: `env.WINEDLLOVERRIDES = <имя>=` → загрузчик возвращает
  STATUS_DLL_NOT_FOUND (`loader_ios.c` ~1785; так уже делают `video64=` в
  GameRecommendations). Путь через `localconfig.vdf` `OverlayAppEnable "0"` —
  **[версия]**, не проверено, что steamclient в Dock его читает.

## 4. Что пробовать (по одному за прогон)

**Прогон 1 — убрать оверлей** (строка в конфиг DS3; если там уже есть
`WINEDLLOVERRIDES`, дописать через `;`):

```
env.WINEDLLOVERRIDES = gameoverlayrenderer64=
```

Ожидание: CPU — 0–1 % (в пределах шума), минус 1,7 МБ образа и его трансляции; хук на
Present уходит. Риск низкий: игра с выключенным оверлеем — штатный режим Steam,
авторизация идёт в dockhost и не зависит от этой DLL. Проверка: в логе нет
`Load module gameoverlayrenderer64.dll`, игра стартует, FRAME_STATS не хуже.
Откат: убрать строку.

**Не делать:** `MADEIRA_BG_QOS_PROCS` (не срабатывает в DS3), блокировку dockhost/
conhost, ключи steam.exe — эффекта ноль или сломается вход.

**Вывод:** фоновый Steam в DS3 почти ничего не стоит (< 0,1 % CPU); FPS упирается в
сам процесс игры на двух P-ядрах. Искать выигрыш надо там (GXWorker/главный поток,
перенос части работы на простаивающие E-ядра), а не в Steam.
