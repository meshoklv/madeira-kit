# DS3: краш в `dxmt::DynamicBuffer::allocate` → `Allocation::incRef` — разбор

Run: `logs/ds3/DarkSoulsIII.exe-2026-10-20_18-45-14.txt`, строки 38532–38640.
Патч: `upstream/ds3-dynbuf.patch` (Wine `dlls/ntdll/unix/sync.c`, `git apply --check` проходит).

## Итог

DXMT не виноват. **Мьютекс `DynamicBuffer::mutex_` насильно отпустил «сборщик осиротевших
локов» Madeira (`ios_orphan_check`, режим по умолчанию), пока его законный владелец (поток 0148)
ещё был внутри `allocate()`.** Два ждавших потока (00a0, 0144) вошли в критическую секцию
одновременно с владельцем, очередь (deque) повредилась, и `fifo.front().allocation` прочитался как мусор.

## Доказательства (ПРОВЕРЕНО по логу и дизассемблеру)

1. Дизассемблер `build-ds3fix/src/d3d11/d3d11.dll`, `DynamicBuffer::allocate` (0x180115ca0):
   - `this` в x19; `AcquireSRWLockExclusive(this+0x48)` (= `mutex_`).
   - 0x115ce4..0x115cf8: `x20 = &map[start>>8][start&0xff]` (front entry), `x25 = [x20]` = `entry.allocation`.
   - 0x115d04: `bl Allocation::incRef` (копия `auto entry = fifo.front()`); incRef = `ldaxr [x0+8]`.
   - Значит разыменован **`entry.allocation` из головы fifo**, не `this`.
2. Регистры краша у 00a0 и 0144 **одинаковые**: x19=0x705ecb8810 (один и тот же DynamicBuffer),
   x20=0x707bab5a10 (одна и та же запись), x0=0x11451833. Два потока в одной точке одного
   объекта под «эксклюзивным» локом — невозможно, если лок работает.
3. Адрес лока: x19+0x48 = **0x705ecb8858**. Строки 38534–38538, за мгновение до краша:
   ```
   [lock-orphan] SRW 0x705ecb8858 word=00010007 waiters=3 no-live-stamp strike=1/3
   [lock-orphan] ... strike=2/3
   [lock-orphan] ... strike=3/3
   [lock-reap] SRW 0x705ecb8858 dead_teb=0xdead released exclusive (word 00010007 -> 00000006)
   0148:err:sync:RtlReleaseSRWLockExclusive Lock 000000705ECB8858 is not owned exclusive!
   ```
   Последняя строка — владелец 0148 был жив и сам отпустил лок, который уже отобрали.
4. Почему «три страйка» за один проход: в `ios_orphan_check` при неустановленном
   `MADEIRA_LOCK_ORPHAN` (mode 0) цикл идёт по **каждому ждущему потоку**, а дедуп «один страйк
   на лок за цикл» включён только в режиме `stamped`. 3 ждущих = 3 страйка = немедленный reap.
   Тот же дефект уже описан в `ConfigCatalog.generated.swift:487` (HZD, build 479); RDR2/HZD и
   др. получают `env.MADEIRA_LOCK_ORPHAN = stamped` в `GameRecommendations.swift`, у DS3 записи нет.
   В логе DS3 строки `[lock-orphan] madeira-bcd MADEIRA_LOCK_ORPHAN=` нет → режим 0.
5. Раньше в том же прогоне (стр. 29797–29850) то же самое с другим DynamicBuffer
   (лок 0x705ecbd578): reap → SEGV у 0150/0144 → два «not owned exclusive». Повторяемо.

## Ответы на вопросы задачи

- Все мутации `fifo` (`allocate`, `updateImmediateName`, `recycle`) — под `mutex_`. Без лока только
  `nextSuballocation`/`immediateName` (поле `name_`), их зовёт только immediate-контекст — по
  правилам D3D11 однопоточно. Не причина.
- Удаление DynamicBuffer во время `allocate`: в момент краша `this` валиден (лок по this+0x48
  совпал с отобранным, мьютекс живой). Не причина.
- Многопоточность легитимна: `d3d11_context_def.cpp:125` (deferred-контекст) зовёт
  `dynamic->allocate()` из своего потока; на стыке 3+ потоков (00a0, 0144, 014c, 0148) лок
  бывает с 3 ждущими — ровно условие reap.
- Refcount `Rc`/`Allocation` атомарный (`ldaxr/stxr`). FEX TSO не при чём (нативный ARM64EC).
- `0x11451833` — **не усечённый указатель**: это содержимое переиспользованной/перезаписанной
  памяти блока deque после гонки (адрес не принадлежит ни одному view Wine, стр. 38604–38605).
  Узких полей/кастов в пути нет. [версия: что именно лежало в блоке — не проверял]

## Исправление

- **Без пересборки (сразу):** в конфиг игры DS3 добавить `env.MADEIRA_LOCK_ORPHAN = stamped`
  (или `= 0`). Проверка: в логе появится `[lock-orphan] madeira-bcd MADEIRA_LOCK_ORPHAN=stamped`,
  и не будет строк `[lock-reap] SRW` для локов DXMT.
- **В Wine (патч):** режим по умолчанию → `stamped`, старый — по `MADEIRA_LOCK_ORPHAN=legacy`.
  В `stamped` освобождаются только локи, которые хоть раз штамповал живой поток (FEX code-buffer),
  и один страйк на лок за цикл — DXMT-мьютексы туда не попадают.
- Желательно (не в патче): завести DS3 в `GameRecommendations.swift` с этим ключом.

Уверенность: высокая (адрес лока, одинаковые регистры двух потоков, «not owned exclusive»
от владельца и повтор на стр. 29797). Не проверено: прогон с ключом.
