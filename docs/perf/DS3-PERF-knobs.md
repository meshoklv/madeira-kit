# DS3: рычаги FPS без пересборки (madeira.cfg / конфиг игры)

Дата: 20.10.2026. Исходники: `<build-tree>/src` @ 6cc0bdb (FEX f59cab9, DXMT 40f96a2).
Куда писать: Game details › Advanced › **This game's config** (синтаксис madeira.cfg; ключ
игры побеждает глобальный, `env.*` экспортируются после глобальных, `dxmt =` дописывается).
Помечено: **[факт]** — из исходников/лога, **[версия]** — моё предположение, не мерил.

## Что показал лог DS3 (`logs/ds3/DarkSoulsIII.exe-2026-10-20_13-21-45.txt`) [факт]

- Упор в **главный поток 00a8**: медиана 244 мс CPU на 325 мс окна (~75 % ядра, p90 90 %);
  остальные потоки игры — единицы мс (`[xp-t]`).
- Главный поток шлёт в wineserver **~21 700 запросов/с** (медиана `[srv-req]`): `select`
  12 200/с, `release_mutex` 6 600/с, `release_semaphore` 1 800/с, `event_op` 600/с
  (номера → имена по `wine/include/wine/server_protocol.h`). Fastsync (движок по умолчанию)
  мьютексы не обрабатывает — каждый такой вызов идёт круговым рейсом через сервер.
  Именно этот случай описан в шапке `build/madsync/madsync.c` («~18 000 запросов/с … это и
  есть время кадра»).
- **Перегрев**: `[thermal]` nominal→fair (33 FPS) → serious (53 FPS, 13:23:51); после этого
  частота P-ядер в `[xp]` падает с 2.8–3.4 ГГц до 1.5–1.9 ГГц.
- **SMC (anti-tamper)**: ~36 000 перехватов за ~10 мин (≈60/с) — не узкое место. Не трогать.
- BC-текстуры не декодируются на CPU (`[bc-stream] decoded total=0`) — `mipClampBC` для FPS бесполезен.
- Включены выборщики, останавливающие потоки (`[thread-sample]` 1 946 строк), DXMT пишет
  ~87 000 строк лога за 10 мин (`[mem-census]`, `[bc-stream]`).
- QoS: все гостевые потоки уже `USER_INTERACTIVE` (`ios_eco_apply_self`, wine/dlls/ntdll/unix/sync.c:2205);
  `[thread-prio] … kept at pthread QoS`. ECO выключен.

## Таблица рычагов (сверху — пробовать первым)

| # | Строка | По умолчанию | Что делает / ожидание для DS3 | Риск | Источник |
|---|---|---|---|---|---|
| 1 | `inproc-sync = 1` | не задан → fastsync | **Madsync**: события, семафоры, **мьютексы** и ожидания живут в процессе, без запросов к wineserver. Бьёт ровно в 21 700 запросов/с главного потока. [версия] крупнейший выигрыш | Wine `services.exe` не отвечал по RPC под madsync — Dock сам выключает его для запуска с установщиками (`MADEIRA_MADSYNC_SESSION=0`). Проверить строку `[madsync]` в логе; если ключ игры не подхватился — поставить в общий madeira.cfg | build/madsync/madsync.c:1-19; ConfigCatalog:418; Library.swift:3714 |
| 2 | `env.MADEIRA_SRV_DIRECT = 2` | 0 | Простые запросы (события/семафоры/мьютексы/хэндлы; при `2` ещё `select` и таймеры) выполняются на вызывающем потоке под замком сервера — без переключения потоков. Альтернатива/дополнение к №1, если madsync ломает игру | Новый путь, пока проверен только на HZD-меню; `1` — осторожнее, чем `2` | ConfigCatalog:514; gen-config-catalog.py |
| 3 | FPS limit **30** (Game details, `fpsMode` 3) или `env.MADEIRA_FPS_CAP = 30` | 60 | Заставки/меню шли 53–60 FPS и прогревали чип до «serious» → троттлинг P-ядер вдвое. Кэп 30 сохраняет тепловой бюджет для геймплея (5–13 FPS ниже кэпа не трогает) | Нет (только визуальная плавность заставок) | server_ios.c:1971-2035; LIBRARY.md:142 |
| 4 | `env.MADEIRA_LEAN_DIAG = 1` | 0 | Выключает выборщики, которые 4 раза в 20 с **останавливают все потоки** (`[thread-sample]`, `[rip-profile]`, `[cpu-split]`), обходы памяти реже | Меньше диагностики для разборов падений | ConfigCatalog / gen-config-catalog.py (LEAN_DIAG); server_ios.c:5723 |
| 5 | `env.MADEIRA_ECO_NATIVE = 1` | 0 | Служебные потоки (прогрев JIT-пула, «лекарь» указателей) уходят на E-ядра, освобождая P-ядра | Нет: кадр их не ждёт | thread_ios.c:1250-1270 |
| 6 | `env.MADEIRA_FASTSYNC_SEM = 1` (= «Fast semaphore waits») | 0 | Семафоры через ячейки fastsync (1 800/с). Нужен только если остаёмся на fastsync (без №1). GTA V Enhanced так и стоит | Низкий | sync.c:1183; GameRecommendations.swift:305,330 |
| 7 | `env.DXMT_LOG_LEVEL = none`, `env.WINEDEBUG = err+all,err-virtual,fixme-all` | info / err+all,err-virtual,fixme-d3dcompiler | Меньше записи лога (~145 строк/с от DXMT). [версия] выигрыш малый | Теряются ошибки DXMT/Wine для разборов | dxmt/src/util/log/log.cpp:115-133; WineProcessBridge.m:949 |
| 8 | Разрешение ниже (`1280x720` или 480p + **MetalFX 1.5×**: `metalfx-upscale = 1.5`) | экран при 1280×720 пикселей | Игра в CPU, но GPU греет тот же чип: меньше пикселей → меньше тепла → P-ядра дольше на высокой частоте. [версия] | Мыло картинки | ContentView.swift:2863-2873; LIBRARY.md:136 |
| 9 | Настройки в самой игре: тени/эффекты/дальность — Low | — | Меньше вызовов отрисовки (~700/кадр) → меньше работы главного потока и DXMT. [версия] самый дешёвый рычаг вне Madeira | Картинка | — |
| 10 | `env.DXMT_WAIT_ON_ADDRESS = 1` | вкл. только в 32-бит | Ожидания DXMT через WaitOnAddress вместо std::atomic (который на PE может скатиться в сон-лестницу) | Экспериментально для 64-бит | dxmt/src/util/util_futex.cpp:71-78 |
| 11 | `cpu-count = 4` / CPU cores reported = 4 | устройство (6) | Меньше рабочих потоков движка на 2 P + 4 E. Упор в один поток → [версия] эффект слабый | Может замедлить загрузки | wine/dlls/ntdll/unix/system.c:1658-1670 |
| 12 | Frame generation (`MADEIRA_FRAMEGEN=1`) | выкл | MetalFX рисует промежуточный кадр: на экране ×2, игра не быстрее | Артефакты на HUD/краях, +½ кадра задержки, +нагрев GPU; кэпы FPS не действуют | winemetal_unix.c:3181-3209 |
| 13 | `env.FEX_EXTENDEDVOLATILEMETADATA = <dll>` | пусто | Снимает эмуляцию порядка памяти (TSO) в указанном модуле. Безопасно только для однопоточных библиотек (Oodle `oo2core_*`, Bink) — имя DLL сверить в папке игры | Если указать модуль с общей памятью между потоками — гонки, порча данных | FEX Config.json.in (ExtendedVolatileMetadata) |
| 14 | `env.FEX_TSOENABLED = 0` | 1 | Убирает барьеры на каждом обращении к памяти — самый большой «сырой» выигрыш FEX. [версия] +20–50 % | **«Highly likely to break any multithreaded application»** (описание FEX). DS3 многопоточный: зависания, порча сейва. Только с бэкапом сейва | FEX Config.json.in (TSOEnabled); TSOHandlerConfig.h:63 |

### Не трогать / не работает
- `env.FEX_SMCCHECKS` — оставить `mtrack`; `none` сломает anti-tamper (он пишет в код), а SMC и так ≈60/с. `env.MADEIRA_FEX_SMC_FASTPATH` уже вкл.
- `env.FEX_VECTORTSOENABLED = 0`, `MEMCPYSETTSOENABLED = 0` — **уже 0** в этой сборке (лог: `TSO config tso=true halfbar=true vector=false memcpyset=false`); строка из RDR2 ничего не даст.
- `env.MADEIRA_WIN_THREAD_PRIORITY = 1`, `env.MADEIRA_DXMT_SCHED_FIFO = 1`, `eco = 1` — **понижают** потоки (уводят на E-ядра). Закрепить поток за P-ядром нечем: в iOS нет привязки к ядрам, `USER_INTERACTIVE` — потолок для приложения (util_madeira_compat.h:105-125).
- `env.MADEIRA_FEX_CALLRET_ELIDE / EC_RET / EC_RET_DIRECT / EC_EXIT_LEAN / EC_BITMAP_CACHE` — уже вкл. по умолчанию.
- `pool` — только глобальный; в логе 896 МБ, нехватки нет. `env.FEX_MULTIBLOCK = 0` — короче компиляция, медленнее код.
- `d3d11.commitBeforePresent` — 1 (лучший вариант) уже по умолчанию. `quiet-log`, `draw-dedup`, `encode-batch` — только D3D12.

## Наборы для прогона (каждый — отдельный запуск, одна и та же сцена, `[xp]` + оверлей FPS)

**A — безопасный** (ожидание: меньше перегрева, чуть больше FPS):
```
env.MADEIRA_FPS_CAP = 30
env.MADEIRA_LEAN_DIAG = 1
env.MADEIRA_ECO_NATIVE = 1
env.DXMT_LOG_LEVEL = none
env.WINEDEBUG = err+all,err-virtual,fixme-all
```

**B — средний** (A + убрать круговые рейсы в сервер; главная ставка):
```
inproc-sync = 1
env.MADEIRA_FPS_CAP = 30
env.MADEIRA_LEAN_DIAG = 1
env.MADEIRA_ECO_NATIVE = 1
env.DXMT_LOG_LEVEL = none
```
Если madsync ломает запуск/Steam — вместо `inproc-sync = 1`:
```
env.MADEIRA_FASTSYNC_SEM = 1
env.MADEIRA_SRV_DIRECT = 2
```
Проверка: в `[srv-req]` должно стать на порядок меньше `select`/`release_mutex`.

**C — агрессивный** (B + снятие TSO; только с бэкапом сейва, ловить зависания/артефакты):
```
inproc-sync = 1
env.MADEIRA_FPS_CAP = 30
env.MADEIRA_LEAN_DIAG = 1
env.MADEIRA_ECO_NATIVE = 1
env.DXMT_WAIT_ON_ADDRESS = 1
cpu-count = 4
env.FEX_TSOENABLED = 0
```
Если C падает/виснет — вернуть `FEX_TSOENABLED`, оставить остальное.
