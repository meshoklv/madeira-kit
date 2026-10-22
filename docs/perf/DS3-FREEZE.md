# DS3: permanent freeze after killing an enemy (20.10.2026)

Logs: `logs/ds3/DarkSoulsIII.exe-2026-10-20_15-21-05.txt` (the 15:21 run: FPS_CAP=30, ECO_NATIVE, LEAN_DIAG, DXMT_LOG_LEVEL=none)
and `logs/ds3/DarkSoulsIII.exe-2026-10-20_13-21-45.txt` (the 13:21 run, default settings). Line numbers below are 0-based indices into those files.
Labels: **[V]** = verified from a log or the source. **[H]** = hypothesis, not proven.

## Verdict

This is a **GPU-side stall, not a CPU deadlock or busy loop**. At one moment the GPU stops completing our command buffers.
Every CPU thread then parks behind it, in this order:

1. Metal's own submission thread is stuck inside the kernel in `IOGPUCommandQueueSubmitCommandBuffers`, with `run=4` (uninterruptible).
2. `dxmt-finish-thr` sits in `MTLCommandBuffer waitUntilCompleted`.
3. `dxmt-encode-thr` sits in `nextDrawable` (all drawables are held by unfinished command buffers).
4. The game's main thread is parked in WaitOnAddress, waiting on DXMT.

About 10 s later the iOS GPU watchdog runs a recovery that discards our buffers as **innocent victims**. The hang then comes back about every 10 s, so the game never recovers.
The command buffer that *caused* the hang is never reported. All 33 errors are victims, so the guilty buffer is outside DXMT's main queue, which is the only queue whose status DXMT checks.

## 1. When frames stop and what each thread does

### The 15:21 run (main thread = tid 00ac)
- **[V]** The main thread is about 250% CPU in every `[xp-t]` sample up to `15:22:07.379` (l.25289: `00ac 229/45`). At `15:22:07.674` it drops to 105 (l.25696), and from `15:22:07.998` on it does not appear at all. One short blip comes at 15:22:17.414 (l.25870).
- **[V]** Last present count: `15:22:07.910 detach-wait: presents=1069` (l.25697). The previous sample was presents=569 at 15:21:37.792.
- **[V]** After that: `nextDrawable #1070 BLOCKED 1003ms` (l.25719) and `#1072 BLOCKED 1001ms` (l.26854). The log ends at 15:22:18.38, about 10.7 s after the stall.
- **[V]** There are no `[gpu-perf]` or `Device error` lines in this run. `DXMT_LOG_LEVEL=none` mutes all DXMT `ERR()` output (`dxmt/src/util/log/log.cpp:123`), so this run could not have shown the GPU error.
- **[V]** The final `[thread-stacks]` dump (l.26297) shows:
  - port 0x5403: `IOConnectCallMethod ← IOGPUCommandQueueSubmitCommandBuffers ← Metal`, `run=4`.
  - `dxmt-finish-thr`: `Metal ← _MTLCommandBuffer_waitUntilCompleted`.
  - `dxmt-encode-thr`: `QuartzCore ← -[MadeiraWindowMetalLayer nextDrawable] ← _MetalLayer_nextDrawable`.
  - main thread `wtid=00ac`: `NtWaitForAlertByThreadId` (WaitOnAddress/futex), game return address `0x14192cfba`.
  - wineserver: idle in `semaphore_timedwait`.
- **[V]** In the earlier dumps (l.17480, 20547, 23648) the finish thread is idle in `NtWaitForAlertByThreadId`, and no Metal thread is inside the kernel submit call. The pattern appears only after the stall.
- **[V]** The `[srv-stuck]` list contains only ordinary idle waits on worker events. No wineserver lock is involved.

### The 13:21 run (main thread = tid 00a8)
- **[V]** The main thread is busy until `13:30:10.096` (l.179376: `00a8:133/140`). At `13:30:10.380` it drops to `2/63` (l.179382) and then disappears from the samples.
- **[V]** The last `[gpu-perf]` line is l.178800: 12.0 fps, GPU 17% busy, 515 draws/frame, **28 tessellated draws/frame**.
- **[V]** The dumps at l.179444 (13:30:13, before any error), 180649, 181922 and 183055 show the same stacks as the 15:21 run: the submit call stuck with `run=4`, the finish thread in `waitUntilCompleted`, and 00a8 in `NtWaitForAlertByThreadId` at the same `0x14192cfba`.
- **[V]** The last `[alert-ring]` entry (l.184301) contains `0138->00a8`, meaning dxmt-finish-thr woke the main thread. So the main thread is waiting on something the finish thread signals: frame-latency, the chunk ring, or the cpu_coherent fence.

## 2. The "GPU error at 13:30:19" claim

- **[V]** An error does exist, but the earlier description of it is wrong. The quoted line is l.180355:
  `Device error at frame 21935: Error Domain=MTLCommandBufferErrorDomain Code=1 "Discarded (victim of GPU error/recovery) (00000005:kIOGPUCommandBufferCallbackErrorInnocentVictim)" ... {Error Domain=IOGPUCommandQueueErrorDomain Code=5}`
- **[V]** The order is the reverse of the earlier claim. Frames stopped first (13:30:10.1–10.4). The error came **9.5 s later** (13:30:19.818). The error is a consequence of the stall, not its cause.
- **[V]** The game never "recovered". The same victim error repeats for frames 21935…21944 at 13:30:19.8, 29.8, 40.0, 49.9, 13:31:18.1 and 30.1, about one GPU recovery every 10 s. Presents went 21872 (13:30:05) → 21942 (13:30:35) → 21945 (13:31:05). Then comes `[freeze] GAP #1 25.2s cause=unexplained-FREEZE` (l.184300).
- **[V]** Across all 11 DS3 logs: 66 InnocentVictim mentions (33 errors), all in the 13:21 run, and **zero** "Caused GPU Timeout/Hang" or "Ignored" errors.
- **[V]** How DXMT handles the error (`dxmt/src/dxmt/dxmt_command_queue.cpp:171-213`, `WaitForFinishThread`): it calls `waitUntilCompleted`. If the status is Error, it logs `Device error`, calls `MarkDeviceError()` (a sticky flag), and then still signals the frame-latency fence and `cpu_coherent`, and continues. So a failed buffer does not leave a fence unsignalled forever.
  - `HasDeviceError()` is read only by d3d9 (`d3d9_device.cpp:1604`). **D3D11 never returns DEVICE_REMOVED** and keeps submitting.
  - The only thing that never returns is `waitUntilCompleted` on a buffer the GPU neither runs nor errors. The watchdog unblocks it after about 10 s.
- **[V]** Only the main queue's buffers are checked. The `ResourceInitializer` upload queue (`dxmt_resource_initializer.cpp:54`, `flushInternal()` l.643) commits buffers whose status and error are never read. Main-queue buffers wait on its shared event (`dxmt_command_queue.cpp:141`, `encodeWaitForEvent`).
- **[H]** The guilty buffer is most likely an upload-queue buffer (texture/buffer initial-data blits or clears), or a main-queue buffer waiting on an upload event. Supporting detail: a new 32 MB init-upload heap was allocated at 13:30:05.218 (`init-upload live=32MB allocs=51`, l.178638) and released only at 13:30:19.818, the recovery moment (l.180367, `frees=50`). Release is lazy, so this is suggestive, not proof.

## 3. Why it happens on killing an enemy

- **[V]** There is no shader or pipeline-compile logging in DXMT, so a new pipeline right before the freeze cannot be confirmed or ruled out from these logs.
- **[V]** In the 13:21 run, right before the stall:
  - 9 new private textures were created between 13:30:05 and 13:30:08 (`tex-private allocs 5309→5318`).
  - Rarely-active game workers 01c4 and 021c woke up at 13:30:10.096 (`-021c:42/39 -01c4:20/23`, l.179376). They had been parked on the job counter `0x703b9630a8`.
  - That is new assets loading right at the kill.
- **[H]** Death effects (ash/dissolve particles, soul pickup) bring new textures, initial-data uploads and probably new shaders, and that work hangs the GPU or the upload path. Tessellation is also in use (28–56 tessellated draws/frame), which is a classic GPU-hang source in DXMT's emulation. Neither is proven.

## 4. Fix / workaround

No config option for GPU timeout or recovery exists for D3D11. `gpu-fault-info` / `gpu-fault-skip` in `ConfigCatalog.generated.swift` apply to Direct3D 12 only. The FPS cap does not matter: the freeze happened with both settings.

1. **The next run must be diagnosable (high confidence it is needed, low cost):**
   - Do not use `DXMT_LOG_LEVEL=none`. It hides `Device error` and `[gpu-perf]`.
   - In DXMT, after committing an upload buffer in `ResourceInitializer::flushInternal()`, check its status/error and log it (a completed handler, or a check in the next `flushToWait`).
   - Create main and upload buffers with `errorOptions = EncoderExecutionStatus` and label the encoders: port winemetal op 8/9 (already used by madeira_d3d12 `gpu-fault-info`) to `CommandQueue::CommitChunkInternal`.
   - This names the guilty buffer and encoder (draw/compute/blit) on the next kill.
2. **Watchdog in DXMT:** if `waitUntilCompleted` stays blocked for more than 3 s, log the stuck chunk's frame, encoder list and the pending upload seq vs `upload_queue_event_.signaledValue()`. That distinguishes a real GPU hang from an event wait that never resolves (`dxmt_command_queue.cpp:180`).
3. **Experiments to narrow it down [H]:**
   - Kill the same enemy with tessellation disabled (needs a DXMT switch; none exists today).
   - Kill it with the upload queue folded into the main queue (`flushToWait` → encode the init blits into the chunk's own buffer instead of a cross-queue event wait). If the freeze disappears, the cross-queue event or upload path is the cause.

Confidence:
- "A GPU stall/hang, not a CPU deadlock": **high** (identical stacks in two runs, and the error comes after the stall).
- "The guilty buffer is outside the checked main queue": **medium-high**.
- "The upload queue or tessellation is the culprit": **low** (a hypothesis only).
