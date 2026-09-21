# Race DX v1.05 timing, HUD, and refactor notes

This file records the constraints and failure modes discovered while adding fractional timing, elapsed TIME, lap results, checkpoint timing, sound changes, and later gameplay polish to Race DX.

Its purpose is not to document every experimental pass. It is to preserve the information needed to modify or refactor the current implementation without rediscovering the same problems.

The old pass patches should be considered historical development artifacts once the current source has been rebuilt and verified.

## Current behavior to preserve

A new game begins with 65.0 seconds of LEFT.

Each completed road awards another 60 whole seconds. The award does not reset or round the fractional timer phase. If a player finishes at 184.9 elapsed with 0.1 remaining, the next road therefore begins with 60.1 remaining.

TIME is cumulative elapsed race time. LEFT is the remaining awarded time. During active racing both displays derive their tenth from the same timer phase.

The central timing invariant is:

```
TIME + LEFT = total awarded race budget
```

Thus the initial budget is 65.0. After one checkpoint it is 125.0, then 185.0, 245.0, and so on.

At an exact timeout, TIME must equal that budget exactly. A timeout with a total budget of 185.0 can produce 185.0, but never 184.0 or 185.1.

Completed lap time is stored independently from both live display fields. During the between-road pause the completed `NN.N` lap result is copied into the LEFT numeric cells while cumulative TIME remains frozen and valid. Normal active-race HUD drawing reclaims the LEFT cells when the next road begins.

Speed and steering state reset at every road transition. Race DX currently uses stage-style roads rather than OutRun-style speed carryover.

Maximum speed is exactly 235 MPH.

## The original timer is part of the game architecture

`R6.0` is the original timer phase and remains the authoritative fractional timing source.

It is not a normal linear `0..59` frame counter. The original update routine performs an extra increment when its low nibble is zero, so the raw sequence skips:

```
01  11  21  31
```

Code which assumes that raw `R6.0` is a normal binary frame count will be wrong.

The current implementation converts the low six bits of the phase to tenths with `phaseTenthTable`. This is deliberately cheap enough to use in the HUD path.

Earlier experiments converted phase to a true linear frame number and even implemented exact centiseconds. Those calculations were valid, but doing the necessary arithmetic and BCD updates during active raster work proved too expensive.

Internal precision and displayed precision therefore intentionally differ. The timer retains finer phase information while the normal live HUD displays tenths.

Do not replace the existing timer merely to make its representation cleaner unless the entire raster schedule is reconsidered.

## Centiseconds were abandoned because of execution cost, not accuracy

An early elapsed-time implementation displayed `SSS.CC`.

Because the game clock is 60 Hz, exact centiseconds can be generated with a repeating `+1,+2,+2` pattern, equivalent to:

```
floor(frame_count * 100 / 60)
```

That scheme has no mathematical drift and lands exactly on `.00` every 60 frames.

The problem was execution cost.

Maintaining and formatting an independent multi-digit centisecond clock during racing consumed enough instructions to upset Race's beam-raced display schedule. Visible symptoms included road corruption, random pixels, malformed HUD digits, finish-line glitches, and turn-dependent instability.

Tenths were chosen because they preserve useful timing precision without requiring that work on every active frame.

If centiseconds are revisited later, they should be calculated outside the raster-sensitive path or reconstructed for a results screen after the road has stopped.

## Raster time is a hard resource

Race effectively has no conventional framebuffer. Video generation, game logic, road construction, and display timing are interleaved around exact CPU timing.

Adding a small amount of apparently harmless code to the wrong path can damage the picture.

Observed failures during development included broken road-dot lines, isolated garbage pixels, horizontal lines above or below scenery, HUD corruption, flicker when racing began, glitches while turning, and particularly frequent failures while the start/finish line was visible.

These were execution-budget failures, not ordinary graphics-data bugs.

New work was therefore moved away from road-draw, horizon-shift, turn, finish-line, and road-start frames wherever possible.

Elapsed bookkeeping belongs on known light frames. Result formatting belongs after a road has stopped. The countdown should not repeatedly redraw frozen result data.

When something can safely wait for the next ordinary HUD frame, let it wait.

A later refactor should first establish an instruction-budget map before moving or combining code.

## Some instruction counts and addresses are intentionally awkward

Several modifications were implemented as fixed-size hooks which branch into unused ROM gaps.

This was done to avoid moving established beam-raced code or changing the instruction footprint of sensitive routines.

Do not assume that a short branch followed by padding `NOP`s is pointless. Do not remove padding merely because the resulting program still assembles.

Likewise, an apparently unused ROM gap may now contain an out-of-line helper.

Historically important fixed labels include:

```
drawRoad                 $01F9
displayRefresh           $0300
checkGlobalState         $0361
finishLapCapture         $0453
calcRoadOrShiftHorizon   $0500
incStores                $05D9
selectGlobalState        $0600
initTopInfo              $0645
startRace                $065C
finishRoad               $06B5
btmLightTop              $06CC
```

The graphics also have address significance:

```
btmCarCenter             $0C42
btmCarLeft               $0C4C
btmCarRight              $0C56
btmCar                   $0C5F
btmTopText               $0C72
```

These addresses should be treated as constraints until a deliberate relocation test proves otherwise.

## Graphics addresses also affect Studio III colour

There is an additional reason not to casually relocate graphics.

On the CDP1864 path, Race's colour follows the address being fetched by DMA. The colour index depends on address bits rather than simply on the logical screen row.

Moving graphic data can therefore alter its colour even when the pixel data and display code are otherwise unchanged.

The main README contains the full colour-layout explanation, including why colour groups 2, 3, and 4 intentionally share the same value.

A source cleanup which relocates `$0Cxx` graphics must therefore be treated as both a raster change and a colour change.

## Low RAM is not general-purpose scratch space

One failed results-HUD design copied the `SPEED LEFT TIME` header from ROM into low RAM so its text could later be modified.

That produced major road and HUD corruption.

`RAM+$00..$27` is the live road-curve work area.

It is overwritten while the road is generated and must not contain persistent HUD state while racing.

The stable design returned `displayRefresh` to the ROM copy of `btmTopText`.

This is an important architectural boundary:

```
road workspace != persistent HUD storage
```

Do not reintroduce a writable copy of the header in this region.

## Authoritative state and display state must remain separate

Several difficult regressions came from using visible HUD cells as the only storage for timing information.

That is unsafe because those cells are also reused for temporary results.

The current design separates the layers.

Hidden elapsed BCD state is authoritative for whole TIME seconds.

Hidden LEFT BCD state is authoritative for remaining whole seconds.

`R6.0` supplies the shared fractional phase.

Completed lap digits have dedicated storage.

Visible LEFT and TIME cells are presentation only.

This separation is what makes it safe to temporarily put a lap result in LEFT without destroying the remaining-time state needed for the next road.

Any future best-lap, high-score, results, or record system should follow the same rule.

Never make a temporary display field the sole authoritative copy of game state.

## LEFT and TIME must describe the same instant

There were several versions in which LEFT was mathematically correct and TIME was mathematically correct, but each represented a slightly different instant.

Those versions still failed.

The fields need to be synchronized to the same phase before formatting.

Testing should therefore use the combined invariant rather than validating each number independently:

```
TIME + LEFT = awarded budget
```

Check it just before a road finish, immediately after the finish, after the +60 award, at the start of the next road, and at timeout.

That single test exposes both fractional-phase and whole-second accounting errors.

## Whole elapsed seconds advance when LEFT consumes a second

TIME is no longer a separately ticking deferred clock.

Whenever the hidden LEFT countdown consumes a whole second during active racing, the hidden elapsed BCD counter receives exactly one whole second.

This greatly reduced active HUD work compared with repeatedly calculating:

```
TIME = budget - LEFT
```

The earlier subtraction design was logically attractive because the invariant was automatic, but the BCD subtraction was too expensive on some racing frames.

The hidden elapsed counter gives the same result with much less live work.

## Finish-line handling occurs one refresh later than the visible finish

This was one of the least obvious timing traps.

`drawRoad` raises state 12 when the finish is detected.

`finishRoad` is not dispatched until the following refresh.

By then `R6.0` has already advanced by one encoded timer tick even though the road has visually ended.

The finish-phase capture therefore has to undo that extra timer advancement before storing the canonical finish phase.

Because the raw phase encoding skips the nibble values described earlier, this correction is not always a simple subtraction of one.

Raw phase values ending in `2` require subtracting two; the others require subtracting one.

This seemingly strange special case is intentional. Removing it shifts some recorded lap and remaining-time values by a fraction.

## Fractional phase must survive the between-road countdown

The light countdown between roads continues to use the same timer machinery.

Without explicit preservation, it destroys the fractional remainder that existed when the road ended.

The stable sequence is:

At the finish, capture the corrected road-finish phase.

Mark that captured phase valid.

Allow the between-road countdown to proceed without treating its phase as race time.

On the final countdown transition, restore the saved race phase.

Clear the valid flag.

Capture the new road's LEFT whole-second state and tenth as the lap-start reference.

The +60 checkpoint award modifies only whole LEFT seconds. It does not modify fractional phase.

This is why a road ending with `0.1` LEFT can begin the next road with `60.1`.

## Finish-line boundary normalization changes both clocks

The final major timing bug was caused by correcting only half of the state.

Certain captured finish phases cross a whole-second boundary during normalization.

The normalization correctly removed one second from hidden LEFT, but an early implementation failed to credit that second to hidden TIME.

The result was a persistent accounting error:

```
TIME + LEFT = budget - 1.0
```

This later surfaced as a GAME OVER result of `184.0` when the true awarded budget was `185.0`.

An attempted fix in the GAME OVER code did not solve it because GAME OVER was merely where the bad state became visible.

The correct fix is in the boundary-normalization path itself.

Whenever finish normalization consumes one whole second from LEFT, it must immediately add one whole second to hidden elapsed TIME before the lap result is calculated.

This is implemented by the `finishNormalizeElapsed` path.

Do not move this correction to the terminal display code.

## Fix state where it becomes wrong, not where it becomes visible

The 184.0 timeout bug is worth retaining as a general debugging lesson.

A bad display at GAME OVER does not imply that GAME OVER formatting is broken.

In this case, changing the terminal formatter could make the displayed result look correct while leaving the underlying elapsed state wrong.

That would later break lap calculations, checkpoints, or any future record system.

When an invariant fails, trace the first state transition where it becomes false.

Correct that transition.

Only then inspect presentation code.

## Lap timing uses saved road-start and finish state

At the beginning of each road the code snapshots the current hidden LEFT seconds and its displayed tenth.

At the finish it obtains the corrected finish phase and current hidden LEFT seconds.

Lap whole seconds are the difference between the saved road-start seconds and the finish seconds.

Lap tenths are the difference between finish and start tenths, with a one-second borrow when the tenth subtraction is negative.

The final decimal lap digits are placed in dedicated `mLap*` storage before being copied to the HUD.

This avoids using the live TIME cells as temporary arithmetic storage.

Future best-lap logic can operate directly on this dedicated result rather than scraping digits back from the screen.

## Complicated R1/R2 result overlays were abandoned

Several versions attempted to display results such as:

```
R1 61.8
R2 60.9
```

These looked simple but crossed the packed LEFT/TIME display-cell boundary and repeatedly produced corruption or awkward aliasing.

Other versions temporarily placed the lap result directly in TIME. That made the display simpler but destroyed or obscured cumulative TIME.

The stable design uses dedicated lap storage and writes the simple `NN.N` result into the LEFT numeric field only after the road has finished.

TIME remains cumulative and frozen during the pause.

The road-number infrastructure was retained through some passes, but the current simple lap presentation no longer needs the R1/R2 overlay.

Do not restore the packed overlay without first redesigning the result display as a separate screen or properly allocated field.

## Do not redraw frozen values throughout the countdown

During the between-road pause, TIME and the lap result already contain the values the player needs to read.

Repeatedly rebuilding those values during every countdown frame created both raster load and opportunities for corruption.

The stable rule is to write the result once and leave it alone.

The active racing HUD naturally takes ownership of the fields again after the next race begins.

## Do not update the HUD on the final light-clear/start frame

One persistent visible flash occurred because timing capture and HUD synchronization were performed on the same transition that cleared the starting lights and entered active racing.

That frame is already sensitive.

The final solution makes the transition capture-only.

The code records the new road's timing baseline and then waits for vertical synchronization.

The first normal racing HUD path updates the visible timer afterward.

A one-frame-delayed HUD refresh is preferable to corrupting the race-start raster.

## Stage transitions reset speed and steering

An intermediate build accidentally allowed speed from one road to carry into the next.

That subtly changed gameplay difficulty.

The intended current model is stage-style racing.

At a road transition, steering state, speed state, the speed update counter, and displayed speed digits are reset.

This behavior is implemented out of line so that the established `$0600` state block does not move.

If continuous speed carryover is ever desired, it should be treated as a deliberate gameplay mode and retuned accordingly rather than arising as a side effect of timing work.

## The 235 MPH maximum is a split-digit limit

The speed representation is not a single MPH integer.

`MAX_SPEED = 23` represents the high two displayed decimal digits. The ones digit is stored separately.

Simply changing `MAX_SPEED` to 24 would not create a 235 MPH limit. It would effectively permit the next 10-MPH band and alter gameplay more than intended.

The current exact cap uses:

```
MAX_SPEED = 23
MAX_SPEED_ONES = 5
```

`speedCap235` checks both pieces and permits acceleration through 231, 232, 233, 234, and 235, but blocks another increment at 235.

The helper lives in the final bytes below `$0100`, and the original active `incSpeed` slot remains fixed-size.

This preserves the established raster-sensitive code layout while producing a true 235 MPH ceiling rather than approximating it as 230 or 240.

The road-motion cadence still primarily follows the existing coarse speed representation, so this is intentionally only a very small difficulty reduction.

## Sound work also has raster scheduling constraints

The countdown uses short B4 beeps, with a higher B5 final beep.

The final countdown beep is intentionally longer than the preceding beeps.

The roadside effect is a short periodic low-tone pulse rather than a sustained tone.

Roadside sound bookkeeping was deliberately moved away from road-draw frames. It runs on the non-road-draw input path so that sound handling does not consume the margin needed for turns and finish-line rendering.

If audio behavior is expanded later, do not put additional envelope, divider, or cadence work into the heavy road path without measurement.

## The known initial-load raster glitch predates this work

There is a known startup condition in which the initial title/display can load into a bad raster state until CLEAR is pressed.

This existed independently of the later results/timing changes.

Once the machine has been reset, the race has otherwise been stable.

Do not automatically treat that initial-load artifact as evidence that a timing refactor has broken active racing.

Conversely, random road pixels, broken horizon lines, or start/finish corruption during play are not the same known startup issue.

## Studio II / Studio III testing and PAL scope

The gameplay/timing work was tested through the Studio II and Studio III NTSC paths during development.

PAL timing was not part of this single-binary work.

A future PAL adaptation should not assume that raster margins, countdown timing, beep pitch, or the exact frame/tenth relationship can simply be copied unchanged.

## Current ROM gaps are not necessarily free

The current source intentionally places helpers into holes in the original address map.

Examples include fractional-phase support in the `$04xx` area, the exact speed-cap helper below `$0100`, checkpoint/timer helpers near the `$0CA0` region, the phase-to-tenth table at `$0EC0`, and lap arithmetic near the end of ROM.

Before reclaiming an apparently unused range, consult the assembled listing.

A cleaner logical layout is desirable, but relocation should happen only after the sensitive address and cycle requirements are understood.

## Likely cleanup candidates in the current source

Some remnants appear to survive from abandoned display experiments and should be reviewed during the eventual deslop pass rather than assumed necessary.

`mElapsedFrac` is defined but no longer referenced by the current implementation.

`mTopText` remains defined at `RAM+0`, but the active display uses the immutable ROM `btmTopText`; putting persistent HUD content at that RAM address was specifically proven unsafe.

`gameLabel` is present in ROM but is not referenced by the current code.

The road-number state remains from the R1/R2 result-display experiments. The current lap display does not visibly use that road number, although the lap arithmetic still passes it through a register in places.

`initTopInfoRest` is currently only a label left by earlier layout work.

These are candidates for careful cleanup, not immediate deletion. Reassemble and compare addresses after each removal.

## Historical passes that should not define current behavior

The development patches are useful as archaeology but several describe designs which were later deliberately replaced.

The live-centisecond patch documents an exact but overly expensive timing scheme.

Raster passes 2 and 3 document the migration toward tenths and light-frame timing work.

Results pass 4 introduced writable low-RAM header storage and budget-minus-LEFT formatting; both were later replaced.

Pass 5 records the discovery that low RAM collided with road construction.

Pass 6 moved to the independent hidden elapsed counter and restored stage-speed reset.

Passes 7 through 9 record unsuccessful attempts to squeeze richer lap displays into the existing packed fields.

Pass 10 established dedicated lap storage and the stable result-only HUD approach.

The final finish-normalization fix came afterward and is essential even though it is not represented by those older patch files.

This document should preserve those lessons; the patch sequence does not need to remain in the normal source directory merely to explain them.

## Repository-state warning before cleanup

At the time this note was consolidated, the checkout contained a newer `race_colour.asm` than its generated build artifacts.

The ASM includes the exact 235 MPH cap (`MAX_SPEED_ONES` / `speedCap235`) and the final `finishNormalizeElapsed` accounting fix.

The existing `race_colour.lst` does not contain those symbols.

Therefore the checked-in listing and the `.rom` / `.st2` produced alongside it should be treated as stale until the source is rebuilt.

Do not use the existing CRCs in `STATIC_VALIDATION.txt` as final release identities.

Rebuild first, then regenerate the listing, ROM, ST2, hashes, and any static-validation address report.

## Other documentation in the checkout is partially stale

`TEST_NOTES.txt` describes an earlier pass and should not be treated as the final timing design.

`STATIC_VALIDATION.txt` preserves useful historical fixed-address information, but its version label and CRCs predate the final source.

The current README still contains some pass-era descriptions of the elapsed-time and lap-display architecture. In particular, descriptions of TIME as budget-minus-LEFT and the old R1/R2 inter-road overlay should be updated to match the final hidden-elapsed and dedicated-lap implementation.

`README_pass3.md`, `race_colour_pass3.*`, `race_colour_pass5.asm`, `race_colour.old.asm`, the numbered development patches, and the root `patch_pass4*.py` scripts are development-history artifacts rather than parts of the current design.

The durable technical reasoning from them is now recorded here.

## Refactor strategy

Do not attempt a large aesthetic rewrite first.

Begin from a newly rebuilt, hardware-confirmed source and generated binary.

Record the sensitive code and graphics addresses from that exact build.

Remove genuinely dead definitions and abandoned result-display remnants one at a time.

After every layout-changing edit, compare the listing and verify that intentional fixed labels have either stayed fixed or were deliberately revalidated.

Keep authoritative timer state, temporary HUD state, road workspace, and raster-time execution separate.

Do not move arithmetic into road/horizon/finish paths merely because a refactor makes doing so convenient.

Only after the implementation is structurally clean should larger routine relocation or address compaction be attempted.

The goal of the refactor should be understandable code with explicitly understood timing constraints, not simply fewer branches or fewer bytes.

## Minimum regression checks after timing or HUD changes

At minimum, verify the following behavior on hardware or an equivalently timing-sensitive environment:

```
Initial LEFT is 65.0.

TIME and LEFT advance in opposite directions while preserving:
TIME + LEFT = awarded budget.

A road finished with a fractional remainder preserves that remainder
through the countdown and +60 award.

Lap NN.N is correct and does not overwrite cumulative TIME.

TIME and LEFT do not become garbled during the between-road pause.

No flash occurs as the next road starts.

Speed and steering reset for each road.

Speed reaches 235 but never 236.

Hard left and right turns do not corrupt the road.

The finish line can remain visible without raster corruption.

Timeout occurs at exactly 00.0 LEFT.

Terminal TIME equals the exact awarded budget:
65.0 / 125.0 / 185.0 / 245.0 / ...

A finish on a fractional whole-second boundary does not leave TIME
one second short.

Countdown and roadside sounds do not introduce visual instability.

The known initial-load/reset artifact is distinguished from new
in-race raster failures.
```

The timer invariant should be the first diagnostic whenever timing behavior changes.

## Core design rule

The work ultimately became stable when four things were kept distinct:

```
authoritative game state
fractional timer phase
visible HUD storage
raster-time execution
```

Most of the failed approaches accidentally coupled two of them.

Preserve those boundaries and future improvements should be substantially easier.