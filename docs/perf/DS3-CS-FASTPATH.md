# DS3: быстрый путь CriticalSection без перехода x64→ARM64EC — проект правки

Дата: 20.10.2026. Статус: **реализовано и собрано (ntdll-csx64.dll), на устройстве не проверено.** Реализация — §7.
Пометки: **[факт]** — прочитано в исходнике/бинаре или посчитано из лога; **[версия]** — вывод без замера.

Исходники: Wine — `<build-tree>/src/wine` (подмодуль 9129e968), FEX — `<build-tree>/fex-src`
(тот же коммит f59cab95, что закреплён в `src` как подмодуль `FEX`), бинари — `src/app/Madeira/arm64ec-windows/`.
Бинари разобраны Python (`pefile` + `capstone`), см. §1.

## 1. Как x64-вызов EnterCriticalSection доходит до нативного кода [факт]

1. **Связывание импорта.** В `kernel32.dll` и `kernelbase.dll` `EnterCriticalSection`/`LeaveCriticalSection`/
   `TryEnterCriticalSection` — **экспорт-форвардеры строкой** (`NTDLL.RtlEnterCriticalSection`), своего кода нет.
   Загрузчик (`wine/dlls/ntdll/loader.c` ~1465) для **x64-импортёра** намеренно отдаёт адрес x64-заглушки
   экспорта из `.hexpthk`, для ARM64EC-импортёра — нативный адрес по таблице перенаправлений.
   Итог: IAT игры → `ntdll+0x91120` (Enter), `+0x91ce0` (Leave), `+0x92740` (TryEnter).
2. **x64-заглушка (FFS, «fast-forward sequence»)**, сгенерирована lld для каждого ARM64EC-экспорта,
   14 байт + `cc cc` в 16-байтовой ячейке:
   `48 8b c4  48 89 58 20  55  5d  e9 rel32` = `mov rax,rsp; mov [rax+20h],rbx; push rbp; pop rbp; jmp <EC>`.
   Цели: Enter → `ntdll+0x6784c`, Leave → `+0x67dcc`, TryEnter → `+0x67d10` (сходится с `[xp-api-top]`).
   У всех трёх есть запись в RedirectionMetadata (Source = адрес заглушки → EC-функция).
3. **FEX** транслирует заглушку как обычный x64-блок; `jmp` уходит в цикл диспетчера
   (`FEXCore/.../Dispatcher.cpp`, LoopTop): чтение RIP, проверка `EcCodeBitMap` (бит=1) → `br Pointers.ExitFunctionEC`
   = `ExitFunctionECJit` (`Source/Windows/ARM64EC/Module.S`):
   счётчик переходов, `InSimulation=0`, проверка `SuspendDoorbell`, перевод PE-адреса в адрес JIT-пула
   (таблица псевдонимов iOS, подсказка последнего попадания), чтение смещения entry thunk из `[target-4]`, `pop lr`, `br thunk`.
4. **Entry thunk** (`ntdll+0x7df98`, общий для сигнатуры `i8`): `stp` q6–q15 (160 байт, x64 XMM6–15 —
   неизменяемые), `stp x29,x30`, `blr` функция, `ldp` всё обратно, `br __os_arm64x_dispatch_ret`.
5. **Сама функция** (Wine `sync.c` RtlEnterCriticalSection): кадр 0x90 с сохранением 8 регистров даже на быстром пути,
   атомика `ldaxr/stlxr` + `dmb ish` (ntdll собран под ARMv8.0, без LSE).
6. **Возврат**: `RetToEntryThunk` → `enter_jit`: TEB через TPIDRRO_EL0, `InSimulation=1`, **`dmb ish`**
   (рукопожатие с чистильщиком пула ml460), `ldar` ворот, `br DispatcherLoopTopEnterEC`: загрузка STATE,
   две записи RIP, смена стека, `FillSpecialRegs`, проба L1, `ret` в JIT-код вызывающего.

**Стоимость одного вызова** — ~80–100 инструкций обвязки, из них 2 полных барьера (`dmb ish` в `enter_jit` и в атомике),
20 обращений к памяти на сохранение/восстановление q6–q15, 2 выхода из JIT-кода в диспетчер.
Оценка из лога: в меню главный поток делал **21 млн QPC/с при ~93 % ядра на 2.8–3.5 ГГц** → ≤ 44 нс ≈ **≤ 135 тактов
на вызов** вместе с телом QPC и циклом игры. Значит переход туда-обратно ≈ **90–110 тактов** [версия, оценка сверху].

## 2. Что уже есть и чего нет [факт]

- **Ни в Wine, ни в Madeira, ни в Windows** нет x64-реализации CS: Windows ARM64EC тоже гонит x64-вызов через FFS → EC,
  только переход дешевле. Hybrid/FFS-экспорты Wine **использует** (их генерирует lld), но это лишь точка перехвата.
- Быстрый путь QPC (ml1117, `wine/dlls/ntdll/time.c`) — **EC-сторона**: читает `cntvct` вместо системного вызова,
  **переход x64→EC не убирает** (поэтому в меню 21 млн переходов/с).
- Рычаги FEX (`MADEIRA_FEX_EC_EXIT_LEAN`, `EC_RET`, `EC_RET_DIRECT`, `EC_BITMAP_CACHE`) уже включены и удешевляют
  обвязку, но не отменяют её. `[ec-hook]` (`build/ntdll-unix/virtual_ios.c`, `MADEIRA_EC_HOOK_TRACE`) — только отчёт о
  чужих правках `.hexpthk`; полезен для проверки нашей.
- В истории `<build-tree>/src` (50 коммитов) коммитов про переходы/QPC/fast path нет.

## 3. Варианты

| Вариант | Суть | Выигрыш | Риск/объём |
|---|---|---|---|
| **A. x64-заглушка CS (рекомендую)** | Перезаписать 3 FFS в `.hexpthk` ntdll на `jmp [rip]` → наш x64-код: незанятая/рекурсивная CS прямо в JIT, только конкуренция уходит в EC | убирает ~100 тактов на ~3.3 млн вызовов/с | ~150 строк в одном файле Wine, FEX не трогаем |
| A′. То же через подмену IAT x64-импортёров в загрузчике | Не трогает код ntdll | то же, но мимо `GetProcAddress` | правка в связывании импортов, хуже покрытие |
| B. FEX: распознать адрес FFS и встроить CS как IR-операцию | «thunk в JIT» | чуть больше, чем A | глубокая правка FEXCore, на каждое обновление FEX |
| C. Удешевить любой переход | убрать `dmb ish`+`ldar` на возврате (`enter_jit`), собрать ntdll с LSE (`-march=armv8.1-a`), не сохранять q6–q15 для листовых функций | −10…25 тактов на **все** 3.75 млн переходов/с | C1 трогает гонку с чистильщиком (ml460); C3 нарушает ABI x64 |

A даёт главный эффект и при этом **x64-семантика та же, что у Wine** — код CS остаётся одним протоколом над одной памятью.
C1/C2 — хороший второй шаг (поможет TlsGetValue, d3d11, QPC).

## 4. Рекомендуемая правка (вариант A)

### 4.1 Файлы

- **новый** `wine/dlls/ntdll/cs_x64_fastpath.c` (только `__arm64ec__`, подключается `#include` из `sync.c` — по образцу
  `arm64ec_x64_export_iat.c`, чтобы не трогать `Makefile.in`);
- `wine/dlls/ntdll/loader.c`, `load_arm64ec_module()`: вызов `madeira_cs_x64_install()` сразу после
  `arm64ec_process_init(...)` вернулся успешно (FEX загружен, x64-код игры ещё не исполнялся);
- `wine/dlls/ntdll/ntdll_misc.h`: прототип;
- `app/Madeira/ConfigCatalog*.swift`: переключатель `env.MADEIRA_CS_X64` (категория «Производительность»).

### 4.2 x64-код (собран вручную, проверен дизассемблером capstone)

Раскладка CS x64: `DebugInfo +0`, `LockCount +8` (Wine: −1 = свободна, +1 за владельца и каждого ждущего),
`RecursionCount +0xC`, `OwningThread +0x10` (= `ULongToHandle(tid)`, нули сверху), `LockSemaphore +0x18`, `SpinCount +0x20`.
TID = `gs:[0x48]` (`TEB->ClientId.UniqueThread`, тот же адрес читает EC-код `ldr w8,[x18,#0x48]`).

```c
/* Enter: rcx = crit. 68 bytes; last 8 = EC RtlEnterCriticalSection */
static const BYTE cs_enter_x64[] = {
 0x65,0x8b,0x14,0x25,0x48,0,0,0,      /* mov edx, gs:[48h]            */
 0xb8,0xff,0xff,0xff,0xff,            /* mov eax, -1                  */
 0x45,0x31,0xc0,                      /* xor r8d, r8d                 */
 0xf0,0x44,0x0f,0xb1,0x41,0x08,       /* lock cmpxchg [rcx+8], r8d    */
 0x75,0x0e,                           /* jne recur                    */
 0x48,0x89,0x51,0x10,                 /* mov [rcx+10h], rdx           */
 0xc7,0x41,0x0c,1,0,0,0,              /* mov dword [rcx+0Ch], 1       */
 0x31,0xc0, 0xc3,                     /* xor eax,eax; ret             */
 0x48,0x39,0x51,0x10,                 /* recur: cmp [rcx+10h], rdx    */
 0x75,0x0a,                           /* jne slow                     */
 0xf0,0xff,0x41,0x08,                 /* lock inc dword [rcx+8]       */
 0xff,0x41,0x0c,                      /* inc dword [rcx+0Ch]          */
 0x31,0xc0, 0xc3,                     /* xor eax,eax; ret             */
 0xff,0x25,0,0,0,0, /* +8 */          /* slow: jmp [rip] -> EC Enter  */
};
/* Leave: 74 bytes; [+0x34] = EC RtlpUnWaitCriticalSection (wake), [+0x42] = EC RtlLeaveCriticalSection */
static const BYTE cs_leave_x64[] = {
 0x8b,0x41,0x0c,                      /* mov eax, [rcx+0Ch]           */
 0x83,0xf8,0x01,                      /* cmp eax, 1                   */
 0x7c,0x34,                           /* jl slow   (<=0: Wine ERR)    */
 0x75,0x18,                           /* jne recur (>1)               */
 0x48,0xc7,0x41,0x10,0,0,0,0,         /* mov qword [rcx+10h], 0       */
 0xc7,0x41,0x0c,0,0,0,0,              /* mov dword [rcx+0Ch], 0       */
 0xf0,0xff,0x49,0x08,                 /* lock dec dword [rcx+8]       */
 0x79,0x0f,                           /* jns wake (>=0: waiters)      */
 0x31,0xc0, 0xc3,
 0xff,0xc8,                           /* recur: dec eax               */
 0x89,0x41,0x0c,                      /* mov [rcx+0Ch], eax           */
 0xf0,0xff,0x49,0x08,                 /* lock dec dword [rcx+8]       */
 0x31,0xc0, 0xc3,
 0xff,0x25,0,0,0,0, /* +8 */          /* wake: jmp [rip] -> EC UnWait */
 0xff,0x25,0,0,0,0, /* +8 */          /* slow: jmp [rip] -> EC Leave  */
};
/* TryEnter: 63 bytes, no EC fallback at all (same logic as Wine's RtlTryEnterCriticalSection) */
static const BYTE cs_tryenter_x64[] = {
 0x65,0x8b,0x14,0x25,0x48,0,0,0, 0xb8,0xff,0xff,0xff,0xff, 0x45,0x31,0xc0,
 0xf0,0x44,0x0f,0xb1,0x41,0x08, 0x75,0x11,
 0x48,0x89,0x51,0x10, 0xc7,0x41,0x0c,1,0,0,0, 0xb8,1,0,0,0, 0xc3,
 0x48,0x39,0x51,0x10, 0x75,0x0d, 0xf0,0xff,0x41,0x08, 0xff,0x41,0x0c, 0xb8,1,0,0,0, 0xc3,
 0x31,0xc0, 0xc3,
};
```

Слабые места разобраны: рекурсия проверяется **после** неудачного `cmpxchg` по `OwningThread` — ровно как в
`RtlTryEnterCriticalSection` Wine (чужой поток не может оставить там наш TID: Leave обнуляет владельца до `lock dec`).
Leave повторяет Wine: `--RecursionCount`; если стало 0 — `OwningThread=0`, `lock dec LockCount`, при результате ≥ 0 —
будить. Порядок «обнулить владельца → атомарно отпустить» сохраняется (x64 TSO, FEX переводит `lock` в `casal/ldaddal`).

### 4.3 Установка (набросок)

```c
void madeira_cs_x64_install(void)
{
    static const struct { const char *name; const BYTE *code; SIZE_T len; } fn[3] = { ... };
    void *ffs[3], *ec[3], *unwait_ec; BYTE *page = NULL; SIZE_T size = 0x1000;
    if (env MADEIRA_CS_X64 == "0") { ERR("[cs-x64] off\n"); return; }
    for i: ffs[i] = RtlFindExportedRoutineByName( ntdll, fn[i].name );       /* x64 FFS address */
           if (memcmp( ffs[i], ffs_prefix /*48 8b c4 48 89 58 20 55 5d e9*/, 10 )) -> log "already patched by someone", skip all;
           ec[i] = (BYTE *)ffs[i] + 14 + *(LONG *)((BYTE *)ffs[i] + 10);     /* same target callers used */
    unwait_ec = decode FFS of "RtlpUnWaitCriticalSection" the same way;
    NtAllocateVirtualMemory( GetCurrentProcess(), &page, 0, &size, MEM_RESERVE|MEM_COMMIT, PAGE_READWRITE );
    copy the three stubs at 64-byte-aligned offsets, fill the 8-byte jmp slots (ec[0], unwait_ec, ec[1]);
    NtProtectVirtualMemory( ..., page, PAGE_EXECUTE_READ ); NtFlushInstructionCache( GetCurrentProcess(), page, size );
    for i: /* 14 bytes over the FFS: jmp qword ptr [rip+0]; dq stub */
           NtProtectVirtualMemory( ffs[i], 16, PAGE_EXECUTE_READWRITE, &old );
           write  ff 25 00 00 00 00 <stub_i>;
           NtProtectVirtualMemory( ffs[i], 16, old, &old );   /* triggers the iOS .hexpthk -> pool sync */
           NtFlushInstructionCache( GetCurrentProcess(), ffs[i], 16 );   /* wrapped: FEX invalidates */
    ERR( "[cs-x64] v1 installed enter=%p leave=%p try=%p stub=%p\n", ... );
}
```

Почему так:
- **Перезапись FFS ловит всех x64-вызывающих**: IAT игры (через форвардеры kernel32/kernelbase), `GetProcAddress`,
  x64-DLL. Это ровно тот приём, ради которого FFS существует (x64-хуки), и Madeira его уже переносит (`[ec-hook]`).
- **ARM64EC-вызывающие не затронуты**: они связываются по RedirectionMetadata (Source = адрес заглушки, не байты) и
  зовут нативную функцию напрямую. EC-код, вызвавший заглушку по указателю, после правки попадёт в эмуляцию нашего
  x64-кода — корректно, лишь медленнее (`ExitToX64` FFS-bypass и `arm64x_check_call` FFS больше не узнают).
- Медленный путь — `jmp` (не `call`) на тот же EC-адрес, что и раньше: адрес возврата, `rcx`, стек — как у FFS,
  энтри-тханк и счётчики `[xp-api]` работают без изменений.

### 4.4 Ограничения корректности

- Кодировка LockCount — **Wine-овская** (−1/счётчик), не Vista+; заглушка обязана с ней совпадать, иначе смешение с EC-путём сломает замок.
  Если Wine когда-нибудь сменит протокол CS (ключевые события / `NtWaitForAlertByThreadId`) — менять заглушку вместе.
- Ожидание (`LockSemaphore` + `RtlWaitOnAddress`/семафор), `DebugInfo->ContentionCount`, тайм-ауты ml810,
  `[cs-raise]` — всё на медленном пути, не изменено. `ios_cs_note` и так выключен (ml1117).
- Теряется только диагностический счётчик `ios_xp_nt.cs_wakes` для x64-освобождений с будильником
  (будим напрямую `RtlpUnWaitCriticalSection`). Если нужен — экспортировать `-private` обёртку, считающую и зовущую UnWait.
- SpinCount: заглушка делает одну попытку, при занятости уходит в EC, где Wine сам крутит спин — семантика та же.
- Невыровненная CS — как и раньше (FEX обработает `lock` по невыровненному адресу backpatch-ем; EC-путь падал бы так же).
- Кто-то уже пропатчил FFS (античит/оверлей) — проверка префикса, тогда не ставим ничего.
- Wow64 (i386) не затрагивается: только ARM64EC-процесс.
- **Риск, требующий проверки на устройстве**: что правка `.hexpthk` реально доходит до кода, который транслирует FEX
  (синхронизация PE→пул через `NtProtectVirtualMemory`). Проверка: `MADEIRA_EC_HOOK_TRACE=1` должен показать нашу правку,
  а `[xp-api]` — падение целей `ntdll+0x6784c/0x67dcc` в `[xp-api-top]` почти до нуля.

### 4.5 Переключатель

`MADEIRA_CS_X64` — `0` выключает (стоят оригинальные FFS, поведение как сейчас). В первой сборке — **по умолчанию выкл.,
`=1` в рекомендациях DS3**, после прогона — по умолчанию вкл., как остальные `madeira-bcd`-рычаги. Лог-строка `[cs-x64] v1 ...`.

### 4.6 Проверка

1. Тест `tests/` x64: 4 потока × 10 млн Enter/Leave с рекурсией до 3, TryEnter, общий счётчик под замком — итог точный;
   плюс CS, созданная в EC-коде (например, через `InitializeCriticalSection` и использование из d3d11), чтобы смешать оба пути.
2. Микро-замер: та же петля Enter/Leave на одном потоке — нс/пара до/после (`calltest-x64.exe`-подобный).
3. DS3: `[xp-api]` x64→EC/с (ожидание: 3.75 млн → ~0.5 млн), доля CS в `[rip-profile]`, FPS в той же сцене.

## 5. Ожидаемый выигрыш [версия]

- В геймплее ~3.28 млн вызовов CS/с (87.5 % от 3.75 млн) на главном потоке при 1.5–1.85 ГГц.
- Переход ≈ 90–110 тактов (из меню, §1) → **~300–360 млн тактов/с ≈ 18–22 % главного потока**.
  Профиль `[rip-profile]` даёт 24–53 % выборок на вызовах CS — сверху оценка выше.
- Новый путь ≈ 15–25 тактов (одна `casal`, два поиска L1 на call/ret).
- Если главный поток — предел: **+20…40 % FPS (≈ 11 → 13–15)**. Дальше упрёмся в компиляции JIT/anti-tamper и wineserver
  (`DS3-PERF-log.md` §6, пункты 2–3).

## 6. Дальше тем же приёмом

- `TlsGetValue` (kernelbase, 4.6 % переходов): x64-заглушка `idx<64 → gs:[1480h+idx*8]`, иначе
  `TlsExpansionSlots`, плюс `gs:[68h]=0` (LastError).
- `QueryPerformanceCounter` (21 млн/с в меню, греет чип): x64 через `rdtsc` (FEX отдаёт `cntvct`) с масштабом —
  только после сверки частоты, которую FEX возвращает для `rdtsc`.
- Вариант C1/C2 (дешевле любой переход) — отдельной правкой FEX/сборки.

## 7. Реализация (20.10.2026) — собрано на Linux-хосте, на устройстве не проверено

**Где.** Ветка `exp/cs-x64-fastpath` в `<build-tree>/src/wine` (поверх 9129e968, коммит 4ac095d1, автор: meshoklv),
патч — `upstream/wine-cs-x64-fastpath.patch`. Новый файл `dlls/ntdll/cs_x64_fastpath.c` подключается `#include` из
`loader.c` (рядом с `arm64ec_x64_export_iat.c`), вызов `madeira_x64_fastpath_install()` — последней строкой
`load_arm64ec_module()`, после `arm64ec_process_init`. `Makefile.in`, `ntdll_misc.h`, `.spec` не тронуты.

**Переключатели (по умолчанию ВЫКЛ):** `env.MADEIRA_CS_X64 = 1` в madeira.cfg — CS; `env.MADEIRA_TLS_X64 = 1` —
`TlsGetValue` (kernelbase). Читаются через helper `flag( L"...", false )` — формат, который ловит
`build/tools/gen-config-catalog.py` (после пина wine и перегенерации каталог покажет оба с дефолтом 0) [версия, генератор не запускал].
Лог: `[cs-x64] v1 installed enter=…->… leave=… try=… (ec … unwait …) stubs=…`, `[tls-x64] v1 installed … kernel32 thunk -> … (covered|NOT covered)`;
при отказе — `not installed` с причиной (не тот шаблон FFS = уже кто-то перехватил; форвардер; цель не в `.text`).

**Отличия от наброска §4.3** [факт, код]:
- адрес FFS берётся прямо из таблицы экспорта (без форвардеров/редиректа), проверяется: в `.hexpthk`, 10 байт префикса lld,
  цель `jmp` — в `.text`. Медленный путь прыгает ровно туда, куда прыгала FFS;
- CS — всё или ничего (Enter, Leave, TryEnter, RtlpUnWait должны найтись все); порядок записи Leave → TryEnter → Enter;
- заглушки в одной странице `NtAllocateVirtualMemory` RW → `PAGE_EXECUTE_READ` + `NtFlushInstructionCache` (через FEX-обёртку);
  FFS: `NtProtectVirtualMemory` RWX → запись 14 байт `ff 25 00000000 <abs64>` → прежняя защита → `NtFlushInstructionCache`;
- `C_ASSERT` на смещения CS (8/0xC/0x10) и TEB (0x48 TID, 0x68 LastError, 0x1480 TlsSlots) и на длины заглушек;
- TlsGetValue: `gs:[68h]=0`; `idx<64` → `gs:[1480h+idx*8]`; иначе EC. kernel32!TlsGetValue — x64 `jmp [rip]` через свой IAT;
  покрыт, только если слот указывает на FFS kernelbase — это и пишет лог (не проверено, что так).
- Счётчик `ios_xp_nt.cs_wakes` для x64-освобождений не растёт (будим напрямую `RtlpUnWaitCriticalSection`).

**Проверки** [факт]:
- байты заглушек = листинг `clang -c` + `llvm-objdump` (все 4 найдены в собранной DLL байт-в-байт);
- нативный тест на x86_64 (`<build-tree>/wine-pe/test/cstest.c`: байты берутся из исходника, gs → фальшивый TEB, медленный путь —
  C-копия протокола Wine): 1/4/8 потоков × 2 млн Enter/Leave с рекурсией до 3 и TryEnter — счётчик точный, замок в конце
  свободен (`lock=-1 rec=0 owner=0`), при 8 потоках 2,55 млн уходов в медленный путь и 2,52 млн пробуждений — PASS.
  FEX и ARM64-атомику это не проверяет.

**Сборка ntdll на Linux** — `<build-tree>/wine-pe/build-ntdll.sh base|csx64` (рецепт `src/build/wine-pe/build-ntdll.sh`:
`--enable-archs=arm64ec --without-x --disable-tests --enable-winegstreamer`, llvm-mingw 20260421 ubuntu, strip, добивка до
SizeOfImage+0x50000). Хост-инструменты: make/bison/flex/m4 — deb'ы Ubuntu через `apt-get download` + `dpkg-deb -x` (без root),
хост-компилятор — `zig cc` из venv pe-build. Каталог сборки внутри снимка исходников и `../configure` — так строки `__FILE__`
совпадают с фермой. Результат [факт]: **`ntdll-base.dll` совпадает с фермовым `ntdll.dll` байт-в-байт, кроме метки времени
линковки (6 байт: заголовок + каталог экспорта)**; размер 1 572 864, секции, 1473 экспорта на тех же RVA, импорты — одинаковы.
PE-часть ntdll не менялась между пином фермы (f34c435b) и 9129e968 (разница только в `dlls/ntdll/unix/`).
`ntdll-csx64.dll`: тот же размер и раскладка секций, RVA CS-экспортов (FFS) прежние; код в `.text` сдвинулся (518 экспортов-
системных вызовов на других RVA) — нормально для пересборки, но адреса `ntdll+0x6784c` и т.п. из старых логов больше не верны.

**Риски / что смотреть на устройстве:** правка `.hexpthk` доходит ли до FEX (`MADEIRA_EC_HOOK_TRACE=1` → `[ec-hook]` на
адресах FFS; `[xp-api-top]` — цели Enter/Leave должны почти исчезнуть); античит/оверлей, проверяющий байты FFS ntdll;
EC-код, вызывающий CS через x64-адрес FFS, теперь эмулирует заглушку (корректно, медленнее). Деплой: положить
`ntdll-csx64.dll` вместо `app/Madeira/arm64ec-windows/ntdll.dll` (без `=1` ведёт себя как прежде, но это другой бинарь —
другие адреса кода).
