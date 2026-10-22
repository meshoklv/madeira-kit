# DS3: не инвалидировать трансляции, если anti-tamper пишет те же байты

Дата: 20.10.2026. Исходники: `<build-tree>/src` @ fdfc9a2 (ветка `ci-build`), FEX f59cab9
(`<build-tree>/fex-src`, только чтение). На устройстве не проверялось.
Пометки: **[факт]** — прочитано в коде/логе; **[версия]** — не измерено.

## 0. Итог

- Инвалидация живёт **в FEX (xtajit64.dll)**, а не в Wine. Эту DLL CI **не собирает** — она лежит
  в репо готовым бинарём. [факт]
- Поэтому сделан патч в том, что CI собирает: **Wine, SIGBUS-обработчик** (`libntdll_unix.a`).
  Он ловит ту же запись **раньше FEX**, декодирует store, сравнивает байты с памятью:
  считает «same/changed/undecoded» всегда, а при `MADEIRA_SMC_SAME_SKIP=1` пропускает
  одинаковую запись (PC += 4) — FEX её не видит и страницу не чистит.
- Ветка `exp/smc-same-bytes` в `<build-tree>/src`, коммит `b8a21b3`, **не запушено**,
  не компилировалось (нет iOS SDK на этой машине).
- «Правильный» вариант — тот же приём внутри FEX (§4), но он требует пересборки xtajit64.dll.

## 1. Где обрабатывается запись в код [факт]

Путь одной записи anti-tamper в `.text` (0x140000000…):

1. Хост-страница R(X) (FEX держит её «в ловушке»: `ProtectRWXIntervalsInternal` →
   `NtProtectVirtualMemory(PAGE_EXECUTE_READ)`).
2. Store из JIT-кода → Mach-исключение → обработчик не берёт → SIGBUS → `bus_handler`
   (`build/ntdll-unix/signal_arm64_ios.c`, блок `[bus-data-av]`, ~стр. 13087) → AV c0000005 гостю.
   Там же на каждую запись — `ios_dump_guest_callers("smc-write")` и снимок ml1001.
3. PE-диспетчер → FEX `ResetToConsistentStateImpl` (`Source/Windows/ARM64EC/Module.cpp:1277`) →
   `InvalidationTracker::HandleRWXAccessViolation` (`Source/Windows/Common/InvalidationTracker.cpp:512`):
   под `CodeInvalidationMutex` — **инвалидация 4-КБ страницы во всех буферах и кэшах потоков**,
   затем `NtProtectVirtualMemory(PAGE_EXECUTE_READWRITE)`.
4. Возврат **без сдвига PC** → store выполняется повторно и ложится уже сам (или через ветки
   ml1018/fast-path на iOS). Следующие записи в страницу бесплатны, пока блок с неё не
   перекомпилируется (`ReprotectRWXIntervals` → снова RX).

**Старые и новые байты.** На шаге 2–3 запись ещё **не легла**: в памяти старые байты, новые —
в регистрах (Rt/Rt2) по декоду инструкции на PC. Т.е. сравнить можно **до** записи, без теневой
копии и без single-step. [факт по коду]

`"smc-write"`/`"wr-strip"` в Wine — только диагностика и починка снятой ОС защиты; решений об
инвалидации Wine не принимает. [факт]

## 2. Какой бинарь и собирает ли его CI [факт]

| Код | Бинарь | CI |
|---|---|---|
| `HandleRWXAccessViolation`, `ResetToConsistentStateImpl` | `libarm64ecfex.dll` → `app/Madeira/arm64ec-windows/xtajit64.dll` (PE, `build/fex-arm64ec/build.sh`, llvm-mingw, arm64ec) | **нет** — DLL закоммичена (последняя — 45afc53 «DLL farm», в ней `[build-id] xtajit64 rev=ml908 compiled Oct 14 2026`); CI только проверяет её наличие |
| FEXCore iOS static (`FEX/build-ios`) | линкуется в само приложение | да, но **это другая копия FEXCore** — xtajit64 несёт свою статически (комментарий в Module.cpp) |
| `bus_handler` | `libntdll_unix.a` | **да** (`build/ntdll-unix/build.sh`) |

Сборка xtajit64 на этом Linux — **реально, но не сделано** [версия по трудоёмкости]:
- тулчейн есть: `<build-tree>/pe-build/toolchains/llvm-mingw-20260421-ucrt-ubuntu-22.04-x86_64`
  (та же дата, что macOS-вариант в `build.sh`);
- в `fex-src` **пустые сабмодули** (vixl, fmt, rpmalloc, range-v3, unordered_dense, xxhash,
  zydis, jemalloc_glibc, tracy…) — нужен `git submodule update --init --depth 1` (без
  `fex-*-tests-bins`);
- cmake с флагами из `build/fex-arm64ec/build.sh`, `-DCMAKE_TOOLCHAIN_FILE=Data/CMake/toolchain_mingw.cmake`,
  путь к linux-тулчейну вместо macos; цель `arm64ecfex`; ~600 TU, при `-j4` ≈ 15–30 мин,
  1–2 ГБ ОЗУ (свободно сейчас ~1.4 ГБ, доступно ~9 ГБ — запускать осознанно);
- риск: бинарь с Linux-хоста ≠ бинарь фермы (другая сборка libc++/флаги) — сравнить размер и
  `[build-id]`, первый прогон — игра, которая уже работает (DSR), потом DS3.

## 3. Варианты и выбор

| Вариант | Где | Корректность | Цена |
|---|---|---|---|
| **A. Ранний отсев в Wine** (сделан) | `bus_handler`, CI | байты те же → трансляции верны по построению; **отклонение от Windows**: запись тех же байт в страницу, которую гость сам держит RX, не даёт AV (Wine не отличает ловушку FEX от защиты гостя) | ~1 syscall (чтение инструкции) + memcmp; при пропуске экономит SEH, мьютексы FEX, инвалидацию, 2× NtProtect и ~4.5 перекомпиляции |
| **B. Ранний отсев в FEX** (рекомендую как цель) | `ResetToConsistentStateImpl`, xtajit64 | тот же, но **только для страниц из `RWXIntervals`** — т.е. только ловушки FEX, гость семантику не теряет | как A + SEH-круг; нужна пересборка DLL |
| C. Теневая копия страницы + сравнение после записи | FEX | ломается на последовательностях «записал другое → вернул как было», копии 4 КБ на страницу | выше A/B, выигрыша нет: старые байты и так доступны до записи |
| D. Ленивая проверка (страница «грязная», при следующем входе в блок сверить хеш его гостевых байт; старый код из буфера не выкидывать) | FEXCore (LookupCache, буферы) | лучший охват (ловит и «расшифровал → исполнил → зашифровал»), но: связанные блоки, мульти-страничные блоки, жизнь старого кода в буфере при сбросе, страница без ловушки | сотни строк в FEXCore, высокий риск |

**Общий риск A/B — частота ловушек.** Сейчас после первой ловушки страница открыта до
перекомпиляции, остальные записи бесплатны. После пропуска страница **остаётся в ловушке** →
каждая следующая одинаковая запись снова ловится (~30–80 мкс [версия]). Выигрыш, пока на одну
сэкономленную серию из ~4.5 компиляций (~500 мкс [оценка из DS3-SMC.md]) приходится меньше ~6–15
дополнительных ловушек. Счётчики ниже это покажут: если `totals` в режиме SKIP вырастут в
разы против measure-only — выключить.

**Рекомендация:** 1) прогон DS3 с этим билдом **без** env — только счётчики (ответ на главный
вопрос «одинаковы ли записи в геймплее»); 2) если `same` ≳ 90 % — прогон с
`env.MADEIRA_SMC_SAME_SKIP = 1`, сравнить FPS, `[smc] ml1055` и компиляции/с; 3) если
выигрыш есть — перенести в FEX как вариант B (без отклонения от Windows) и собрать xtajit64.
D — только если B мало (т.е. записи всё-таки меняют байты).

## 4. Что сделано в ветке `exp/smc-same-bytes` (b8a21b3)

Файл `build/ntdll-unix/signal_arm64_ios.c`, +144 строки:
- `ios_smc_same_check()` (перед `bus_handler`): декодирует store **без writeback** —
  `STR* #uimm12`, `STUR*`, `STLUR*`, `STLR*/STLLR*`, `STR* [Xn, Rm{,ext}]`, `STP W/X` signed offset;
  собирает байты из регистров; требует, чтобы адрес ошибки лежал внутри доступа и доступ не
  пересекал 16-КБ страницу; `memcmp` с памятью → 1 same / 0 changed / -1 undecoded.
  SIMD, атомики, pre/post-index — не декодируются (идут старым путём).
- В `[bus-data-av]` сразу после первой строки лога: счётчики и пропуск.
  Пропуск только если `MADEIRA_SMC_SAME_SKIP=1`, байты те же и Wine считает страницу R|X без W
  (`ios_page_expected_prot`). Тогда `PC += 4`, `ios_fixup_x18_for_return`, возврат — AV не
  создаётся, ml1001/`ios_dump_guest_callers` тоже не зовутся.
- Выключатель: `MADEIRA_SMC_SAME_SKIP` не задан/`0` — **поведение прежнее**, только счётчики.

Строки в логе:
```
[smc-same] exp/smc-same-bytes v1 mode=measure only (MADEIRA_SMC_SAME_SKIP=(unset))
[smc-same] #N SAME|CHANGED|undecoded insn=… addr=… ea=… n=… pc=… [-> skipped]   (первые 24)
[smc-same] totals=… same=… changed=… undecoded=… skipped=… mode=…               (каждые 4096)
```
Если `undecoded` велико — посмотреть `insn` в первых 24 строках и добавить форму (вероятно
`STR Q`/`STUR Q` или `DMB`+`STR` с writeback).

Чтобы собрать: влить в `ci-build` (CI запускается пушем в `ci-build` или вручную
`workflow_dispatch`). Не пушил.

## 5. Набросок варианта B (FEX, Module.cpp) — не написан в коде

В `ResetToConsistentStateImpl`, iOS-ветка, **до** `HandleRWXAccessViolation`:
```cpp
// MADEIRA_FEX_SMC_SAME: "0" = off; default on; "count" = только счётчики
if (IosSmcSame && InvalidationTracker->IsTrappedRWX(FaultAddress) &&   // новый метод: shared_lock + RWXIntervals.Query
    CTX->IsAddressInCodeBuffer(Thread, NativeContext->Pc)) {
  int R = IosSmcSameCheck(*NativeContext, FaultAddress);              // декод как в Wine, регистры из NativeContext->X/Sp
  Count(R);
  if (R == 1 && IosSmcSame == Skip) { NativeContext->Pc += 4; return true; }
}
```
- Блокировки не нужны: ничего не пишем; гонка с другим потоком, который уже открыл страницу и
  записал новые байты, безопасна — сравниваем с текущей памятью, а его запись сама прошла
  через инвалидацию.
- Порядок памяти: пропущенный store не меняет значение, наблюдатель не может отличить —
  release-семантика не теряется по существу.
- Счётчики `[smc-same]` раз в 10 с через `LogMan::Msg::EFmt`, рядом с `[smc] ml1055`.
- Переключатель по образцу `MADEIRA_FEX_SMC_FASTPATH` (Module.cpp:1197).

## 6. Не проверено

- Компиляция патча (iOS SDK есть только в CI).
- Что AV для этих записей действительно проходит через `[bus-data-av]` на каждой записи, а не
  частично через Mach-эмуляцию (по DS3-SMC.md — да, 225–248 AV/с ≈ 200–250 SMC/с).
- Доля одинаковых записей в геймплее — главный неизвестный; ради него шаг 1 рекомендации.
- Изменится ли частота ловушек в режиме SKIP.
