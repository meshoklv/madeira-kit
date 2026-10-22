# DS3: краш в GPUInterfaceTexture (0x14176d65b) — разбор

Run: `logs/ds3/DarkSoulsIII.exe-2026-10-20_10-57-25.txt`, строки 17094–17128
(`AV WRITE of 0`, rip=0x14176D65B, host fp(=RBP)=0xffffffff).

## Что за функция [rax+0x50] — ПРОВЕРЕНО (дизассемблер + RTTI, exe на диске)

Vtable `PPFX::IGPUTexture` @ 0x142b67338 (COL 0x143e9eec0, `.?AVIGPUTexture@PPFX@@`;
рядом `IGPUBaseTexture` @0x142b67288, `IGPUCubeTexture` @0x142b673f8).
Указатель на 0x14176d5c0 в .rdata ровно один — слот 7 этой vtable.

| слот | адрес | что делает |
|---|---|---|
| 7 (+0x38) | 0x14176d5c0 | функция краша: `n = this->vf10(); arr = alloc(n*8+8); for i<n: arr[i] = makeMipView(i)` |
| 8 (+0x40) | 0x14176d690 | парная: освобождение того же массива |
| 9 (+0x48) | 0x14176d940 | «инициализировать текстуру из готового SRV» |
| **10 (+0x50)** | **0x14176d430** | **`mov eax,[rcx+0xe4]; ret`** — геттер числа мипов |

Поле `this+0xe4` = число мип-уровней (деструктор 0x14176d830 крутит по нему цикл
`max(1,w>>i)*max(1,h>>i)*bpp` — освобождение памяти по мипам).

Кто пишет `+0xe4` (байтовый поиск по .text): конструкторы — 0; per-mip
обёртка 0x14176c0f0 — аргумент; и **0x14176d940 (слот 9)**:

```
view->GetDesc(&d)                      ; ID3D11View vtbl+0x40
require d.ViewDimension in {4 (TEX2D), 6 (TEX2DMS)}
0x14176b970(this+0x38, view)           ; view->GetResource + GetDesc -> копия
   └ 0x14176aef0: switch(ViewDimension) case TEX2D: out+0x28 = desc+8, out+0x2c = desc+0xc
this+0xe4 = this+0x94                  ; = SRV_DESC.Texture2D.MipLevels
call [vtbl+0x38]                       ; -> 0x14176d5c0 (функция краша)
```

Раскладка в aef0 (у TEX1DARRAY копируются 4 поля +8/+c/+10/+14) = это
`D3D11_SHADER_RESOURCE_VIEW_DESC`, а не RTV. Итого:
**vf10 возвращает `ID3D11ShaderResourceView::GetDesc().Texture2D.MipLevels`.**
anti-tamper-шифрования в этих функциях нет — код читается нормально.

## Почему 0xFFFFFFFF под DXMT — ПРОВЕРЕНО по исходникам, сам вызов игры НЕ трассирован

- D3D11: `MipLevels = (UINT)-1` в SRV-дескрипторе = «все мипы начиная с MostDetailedMip».
  Wine d3d11 (`dlls/d3d11/view.c: normalize_srv_desc`) подставляет
  `miplevel_count - MostDetailedMip` в сохранённый desc, и `GetDesc` отдаёт уже
  разрешённое число. На Windows игра работает → нативный D3D11 тоже отдаёт число
  (вывод по поведению, доку MS не цитирую).
- DXMT: `ExtractEntireResourceViewDescription(res, pDesc, &finalDesc)`
  (`src/d3d11/d3d11_resource.hpp`) при непустом pDesc просто копирует его.
  `d3d11_texture_device.cpp: CreateShaderResourceView` нормализует только
  **копию** `physDesc` (InitializeAndNormalizeViewDescriptor берёт её по ссылке),
  а в `TextureSRV` кладёт `finalDesc` с -1 → `GetDesc` возвращает 0xFFFFFFFF.
  То же в `d3d11_texture_dynamic.cpp`. (В `d3d11_texture_linear.cpp` finalDesc
  нормализуется — там бага нет.)
- В игре: 0xFFFFFFFF*8+8 = 32 ГБ → аллокатор вернул NULL → запись `[rsi+rcx]` по 0.

Версия (не проверено): тот же -1 портит учёт мипов в
`dxmt_resource_binding.cpp: ResourceSubset` (`end_mip_ = UINT8(begin + MipLevels)`)
при MostDetailedMip>0.

## Фикс

`upstream/ds3-mipcount.patch` (против `<build-tree>/src/dxmt`, `git apply --check` — OK;
НЕ собиралось). В `ExtractEntireResourceViewDescription` (ветка с pDesc) для SRV
разрешать `MipLevels == ~0u` → `res.MipLevels - MostDetailedMip` для всех
текстурных измерений, как Wine. `res.MipLevels` к этому моменту уже разрешён
(0 → полная цепочка) в CreateMTLTextureDescriptor. Путь с mip_bias_ (ml675)
даёт ту же физическую цифру, что и раньше (count−drop = physMips−most).

Уверенность: высокая (~85%) что причина именно эта — цепочка слот10 → +0xe4 →
SRV.MipLevels доказана дизассемблером, а -1 ровно то значение, которое DXMT
оставляет в GetDesc. Не доказано: что игра действительно передала -1 (нет
d3d11-трассы). Проверка после сборки: краш на 0x14176d65b уходит; для
уверенности — ERR-лог в TextureSRV при MipLevels==~0u до фикса.
