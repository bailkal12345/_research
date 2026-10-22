# A5. BP machine and tracer

Image: `ShooterGameServer.exe` v361.7 (ARK: Survival Evolved), Win64 x64, image base `0x140000000`.
All RVAs were obtained from `v361.sqlite` (`fn`/`sym`); all field offsets and global
addresses — from Ghidra disassembly (`/v361_ShooterGameServer.exe`), every claim is
annotated with an address.

---

## 1. Symbol table

| Symbol | RVA | VA | size |
|---|---|---|---|
| `UObject::ProcessInternal` | `0x01FC0270` | `0x141FC0270` | 344 |
| `UObject::ProcessContextOpcode` | `0x01FC1FA0` | `0x141FC1FA0` | 184 |
| `UObject::CallFunction` | `0x01FBFEF0` | `0x141FBFEF0` | 889 |
| `UObject::ProcessEvent` | `0x01FC0DB0` | `0x141FC0DB0` | 664 |
| `UFunction::Invoke` | `0x01F867C0` | `0x141F867C0` | 792 |
| `UFunction::Bind` | `0x01F86D30` | `0x141F86D30` | 160 |
| `UFunction::GetReturnProperty` | `0x01F86CB0` | `0x141F86CB0` | 119 |
| `FFrame::FFrame` (ctor) | `0x01FA57E0` | `0x141FA57E0` | 382 |
| `FFrame::~FFrame` | `0x01FA56A0` | `0x141FA56A0` | 266 |
| `FFrame::ReadVariableSize` | `0x01FA5960` | `0x141FA5960` | 416 |
| `UObject::SkipFunction` | `0x01FBFD10` | `0x141FBFD10` | 480 |
| `UObjectBaseUtility::GetInterfaceAddress` | `0x01FCDAE0` | `0x141FCDAE0` | 259 |
| `UObject::ExecuteUbergraph` | `0x001C0ED0` | `0x141C0ED0` | 63 |
| `UObjectBaseUtility::GetName` | `0x001F0FE0` | `0x141F0FE0` | 45 |
| `FName::GetNames` | `0x01F427D0` | `0x141F427D0` | 107 |
| `FName::ToString` (wrapper) | `0x01F432B0` | `0x141F432B0` | 58 |
| `FName::ToString` (real) | `0x01F432F0` | `0x141F432F0` | 130 |
| `FName::AppendString` | `0x01F43380` | `0x141F43380` | 197 |

**Globals (data):**

| Name | RVA | VA | Purpose (proof) |
|---|---|---|---|
| `GNatives` | `0x0491C6B0` | `0x14491C6B0` | opcode dispatcher table, `MOV [RDI+RAX*8]` — `0x141FC0309/033C`, `0x141FC00BE/0108` |
| `GNativeDuplicate` | `0x0491C89C` | `0x14491C89C` | duplicate-opcode flag — `0x141FA013A` |
| `GScriptStack` | `0x04937F00` | `0x144937F00` | BP stack: `+0x0` allocator, `+0x8` ArrayNum, `+0xC` ArrayMax, stride `0x10` — `0x141FA58A8..0x141FA5922` |
| `GPrevScriptStack` | `0x04937F10` | `0x144937F10` | previous stack — `0x141FA58AA/0x141FA58C8` |
| `GFullStackTrace` | `0x04909C17` | `0x144909C17` | stack-trace byte flag — `0x141FA5869` |
| `NamePoolData` | `0x0498A1C8` | `0x14498A1C8` | FNameEntry pool, blocks of `0x800` slots — `0x141F427D4/0x141F42812` |

**xrefs to `UFunction::Invoke` (RVA `0x01F867C0`) — 3 calls total:**

- `0x141FBFFA2` — from `UObject::CallFunction`
- `0x141FC0FA7` — from `UObject::ProcessEvent`
- `0x141F869EB` — recursion "BreakHitResult_OLD" inside `Invoke` itself

**xrefs to `UObject::ProcessInternal` (RVA `0x01FC0270`):**

- `0x141FC01F4` `UNCONDITIONAL_CALL` — from `UObject::CallFunction`
- `0x141F86D7A`, `0x141F86D81` `DATA` — from `UFunction::Bind` (`MOV [R9+0xA8], RAX`, `RAX=0x141FC0270`)
- `0x144A7F044` `DATA` — vtable/table

Conclusion: `ProcessInternal` has **no caller call site in code** — it is invoked
**indirectly via `UFunction::Func`**, so the call point cannot be patched, only a detour
of the function body. `Invoke` does have call sites (3).

---

## 2. The set of `UObject::exec*`

- **68** distinct PDB symbols named `UObject::exec*`.
- They lie in **one continuous block `0x01FC1050` … `0x01FC36B6`** (61 unique addresses,
  **8776 bytes** total).
- **5 debug opcodes collapse onto a single 3-byte stub `0x001BCBB0`**:
  `execBreakpoint`, `execNothing`, `execNothingOp4a`, `execTracepoint`,
  `execWireTracepoint` (aliases in the PDB).
- **63** of them are actually registered in `GNatives` as bytecode opcodes (see §4).
- **4** have code but no slot in `GNatives`: `execUndefined` (`0x01FC1050` — table
  filler), `execObjectToBool` (`0x01FC3480`), `execInterfaceToBool` (`0x01FC34D0`),
  `execObjectToInterface` (`0x01FC3520`) — the static names of the last three are
  `...CastTemp`/`...Registar`, not `...BytecodeTemp` (the bytecode compiler does not
  produce them).
- Separately: `UObject::ExecuteUbergraph` (`0x001C0ED0`, 63 B) — not an opcode but a
  tunnel-UFunction.

Full list (RVA, size):

```
0x01FC1050  29  execUndefined            0x01FC2860 609 execStringLocConst
0x01FC1070  53  execLocalVariable        0x01FC2AD0 602 execTextConst
0x01FC10B0  55  execInstanceVariable     0x01FC2D30  20 execObjectConst
0x01FC10F0  73  execLocalOutVariable     0x01FC2D50  90 execInstanceDelegate
0x01FC1140  72  execInterfaceContext     0x01FC2DB0 188 execBindDelegate
0x01FC1190 219  execEndOfScript          0x01FC2E70  53 execNameConst
0x01FC1270   5  execEndFunctionParms     0x01FC2EB0  15 execByteConst
0x01FC1280  29  execJump                 0x01FC2EC0  45 execRotationConst / execVectorConst
0x01FC12A0  76  execComputedJump         0x01FC2EF0 129 execTransformConst
0x01FC12F0  98  execJumpIfNot            0x01FC2F80 201 execStructConst
0x01FC1360 247  execAssert               0x01FC3050 458 execSetArray
0x01FC1460 132  execPushExecutionFlow    0x01FC3220   8 execIntZero
0x01FC14F0 114  execPopExecutionFlow     0x01FC3230   8 execIntOne
0x01FC1570 165  execPopExecutionFlowIfNot 0x01FC3240  5 execTrue
0x01FC1620 485  execLet                  0x01FC3250   5 execFalse
0x01FC1810 604  execLetObj               0x01FC3260   8 execNoObject
0x01FC1A70 604  execLetWeakObjPtr        0x01FC3270  15 execIntConstByte
0x01FC1CD0 325  execLetBool              0x01FC3280 244 execDynamicCast
0x01FC1E20 169  execLetDelegate          0x01FC3380 208 execMetaCast
0x01FC1ED0 164  execLetMulticastDelegate 0x01FC3450  31 execPrimitiveCast
0x01FC1F80   4  execSelf                 0x01FC3470  11 execInterfaceCast
0x01FC1F90   5  execContext / execContext_FailSilent
0x01FC2060 497  execStructMemberContext  0x01FC3480  71 execObjectToBool     (no slot)
0x01FC2260 110  execVirtualFunction      0x01FC34D0  72 execInterfaceToBool  (no slot)
0x01FC22D0  21  execFinalFunction        0x01FC3520 200 execObjectToInterface(no slot)
0x01FC24C0   8  execCallMulticastDelegate
0x01FC24D0 140  execAddMulticastDelegate  0x01FC2640  19 execIntConst / execSkipOffsetConst
0x01FC2560 140  execRemoveMulticastDelegate
0x01FC25F0  78  execClearMulticastDelegate
0x01FC2660  23  execFloatConst
0x01FC2680  23  execDoubleConst
0x01FC26A0 213  execStringConst
0x01FC2780 217  execUnicodeStringConst
0x01FC35F0 198  execInterfaceToInterface
```

---

## 3. Layout of the interpreter frame

### 3.1 `FFrame` — confirmed by the `FFrame::FFrame` constructor (`0x141FA57E0`)

Canonical call from `UObject::CallFunction` (`0x141FC0029`):
`FFrame::FFrame(this=&stack, Owner=this, Function=UFunction*, Locals=buf,
PreviousFrame=param_1, PropertyChainForCompiledIn=*(UFunction+0x38))`.

| Offset | Field | How obtained |
|---|---|---|
| `+0x00` | `void** vftable` = `0x144073EB0` | `MOV [RCX],RAX` — `0x141FA5815` |
| `+0x08` | `uint16` = `0x100` | `MOV word [RCX+8],0x100` — `0x141FA5808` |
| `+0x10` | **`UFunction* Node`** | `MOV [RCX+0x10],R8` — `0x141FA5818` |
| `+0x18` | **`UObject* Object`** | `MOV [RCX+0x18],RDX` — `0x141FA581C` |
| `+0x20` | **`uint8* Code`** (PC in bytecode) | `MOV [RCX+0x20],RAX`, where `RAX=[R8+0x48]` — `0x141FA5820/24` |
| `+0x28` | **`uint8* Locals`** | `MOV [RCX+0x28],R9` — `0x141FA5828` |
| `+0x30` | `UProperty* MostRecentProperty` | `MOV [RCX+0x30],0` — `0x141FA582E`; write `0x141FC107E` |
| `+0x38` | `uint8* MostRecentPropertyAddress` | `MOV [RCX+0x38],0` — `0x141FA5832`; write `0x141FC108E` |
| `+0x60` | inline-heap allocator `TArray FlowStack` | `ADD RCX,0x60; CALL 0x1401BF260` — `0x141FA5836/3A` |
| `+0x68` / `+0x6C` | `FlowStack.ArrayNum`=0 / `ArrayMax`=8 | `0x141FA583F/42` |
| `+0x70` | `FFrame* PreviousFrame` | `MOV [RBX+0x70],RAX` — `0x141FA584E` |
| `+0x78` | `FOutParmRec* OutParms` | `MOV [RBX+0x78],0` — `0x141FA5852` |
| `+0x80` | `UField* PropertyChainForCompiledIn` | `MOV [RBX+0x80],RAX` — `0x141FA585B` |
| `+0x88` | **`UFunction* CurrentNativeFunction`** | `MOV [RBX+0x88],0` — `0x141FA5862`; write of `this` in `UFunction::Invoke` — `0x141F86AA0` |

`Locals` — **neither** a `TArray<uint8*>` **nor** a list of pointers: it is a
**flat `uint8*` buffer**, addressed by offsets from `UProperty`. There is no "Stride":

```asm
; UObject::execLocalVariable, 0x141FC1070
141fc1070  MOV  RAX,[RDX+0x20]        ; FFrame->Code
141fc1077  MOV  RCX,[RAX]             ; UProperty*  (8-byte literal in the code stream)
141fc107a  ADD  RAX,0x8
141fc107e  MOV  [RDX+0x30],RCX        ; FFrame->MostRecentProperty
141fc1082  MOV  [RDX+0x20],RAX        ; Code += 8
141fc1086  MOVSXD R8,dword ptr [RCX+0x4C]   ; UProperty::Offset_Internal (int32)
141fc108a  ADD  R8,[RDX+0x28]               ; Locals + Offset_Internal
141fc108e  MOV  [RDX+0x38],R8                ; MostRecentPropertyAddress
```

Outcome: **`Locals[Prop->Offset_Internal]`**, where `UProperty+0x4C = Offset_Internal (int32)`.

### 3.2 `UFunction` — confirmed by `UFunction::Bind` (`0x141F86D30`) and the `FFrame` ctor

| Offset | Field | Proof |
|---|---|---|
| `+0x18` | **`FName Name`** (`ComparisonIndex`@`+0x18`, `Number`@`+0x1C`) | `UObjectBaseUtility::GetName`: `MOV RAX,[RCX+0x18]` — `0x141F0FE0+6`; `UFunction::Invoke`: `MOV RAX,[RBP+0x18]; CMP EAX,NAME_BreakHitResult.ComparisonIndex; SHR RAX,0x20; CMP EAX,Number` — `0x141F86946..958`; the script stack writes `[RSI+0x18]` — `0x141FA58DA` |
| `+0x20` | `UObject* Outer` (for a UFunction — the owning `UClass`) | `UFunction::Invoke` walks it as a `UClass*` via `Super` (`+0x30`) looking for `UInterface::StaticClass` — `0x141F869F5..0x141F86A20` |
| `+0x38` | `UProperty* PropertyChainForCompiledIn` | `UObject::CallFunction`: `MOV RAX,[R14+0x38]`, passed as the 6th argument to `FFrame::FFrame` (`+0x80`) — `0x141FC000E/0012/0029` |
| `+0x40` | `int32 ParmsSize` | `MOVSXD RDX,dword [R9+0x40]`, then a `memset` of that size — `0x141FBFFBF/0011` |
| `+0x48` | **`uint8* Script` (pointer to bytecode)** | `FFrame::FFrame`: `MOV RAX,[R8+0x48]; MOV [RCX+0x20],RAX` — `0x141FA5820/24`; the same pair `(FName@+0x18, Script@+0x48)` is written to `GScriptStack` — `0x141FA58DA` (FName), the pair write `0x141FA58EB`+`0x141FA5922` |
| `+0x90` | `uint32 FunctionFlags` | `TEST dword [R9+0x90],0x400` (FUNC_Native) — `0x141FBFF36`, `0x141F86D6D`; `TEST [R14+0x90],0x400000` (FUNC_HasOutParms) — `0x141FC0036` |
| `+0xA8` | **`FNativeFuncPtr Func`** | `CALL qword ptr [RBP+0xA8]` — `0x141F86AB2`; `LEA RAX,[0x141FC0270]; MOV [R9+0xA8],RAX` — `0x141F86D7A/81` |

**Key fact (matters for the tracer):**

```asm
; UFunction::Bind, 0x141F86D6D
141f86d6d  TEST dword ptr [R9 + 0x90], 0x400      ; FunctionFlags & FUNC_Native
141f86d78  JNZ  0x141f86d89                        ; if native -> take from NativeFuncMap
141f86d7a  LEA  RAX,[0x141FC0270]                  ; &UObject::ProcessInternal
141f86d81  MOV  qword ptr [R9 + 0xA8],RAX         ; UFunction->Func = ProcessInternal
```

That is, **for any scripted (non-native) UFunction the field `Func` =
`&UObject::ProcessInternal`**.
`UFunction::Invoke` is exactly `Func(Obj, FFrame&, RESULT)` plus a small prologue
(BreakHitResult shims, an interface lookup, `GProgressBarAddQuanta`).

Other useful `UProperty` offsets (needed only for context):
`+0x30 ArrayDim`, `+0x34 ElementSize`, `+0x38 uint64 PropertyFlags`, `+0x4C
Offset_Internal`, `+0x60 Next` (from `0x141FC039C/03A4`, `0x141FC0386`, `0x141FC012C`,
the chain in `ProcessEvent`).

---

## 4. Opcode dispatcher

### 4.1 How the handler is selected

**Pointer table `GNatives[256]` (2048 bytes), index = opcode byte.** No `switch`/jumptable.

The loop of `UObject::ProcessInternal` (`0x141FC0320`–`0x141FC0369`), verbatim:

```asm
141fc0320  MOV  RAX,[RBX+0x20]          ; Code
141fc0324  LEA  R8,[RSP+0x30]           ; &scratchResult (64 bytes, local buffer)
141fc0329  MOV  RDX,RBX                 ; FFrame*
141fc032c  MOVZX ECX,byte ptr [RAX]     ; op = *Code
141fc032f  INC  RAX
141fc0332  MOV  [RBX+0x20],RAX          ; Code++
141fc0336  MOV  EAX,ECX
141fc0338  MOV  RCX,[RBX+0x18]          ; FFrame->Object  -> 1st argument
141fc033c  CALL qword ptr [RDI+RAX*0x8] ; RDI=0x14491C6B0  ->  GNatives[op]
141fc033f  MOV  RAX,[RBX+0x20]
141fc0343  CMP  byte ptr [RAX],0x4      ; op == 0x04 (EX_Return)?
141fc0346  JNZ  0x141fc0320
141fc0348  INC  qword ptr [RBX+0x20]     ; skip the 0x04 byte
141fc034c  MOV  RAX,[RBX+0x20]
141fc0350  MOV  RCX,[RBX+0x18]
141fc0354  MOVZX EDX,byte ptr [RAX]     ; the last opcode
141fc0357  INC  RAX
141fc035a  MOV  R8,RSI                  ; the REAL RESULT (param_2)
141fc035d  MOV  [RBX+0x20],RAX
141fc0361  MOV  EAX,EDX
141fc0363  MOV  RDX,RBX
141fc0366  CALL qword ptr [RDI+RAX*0x8] ; -> GNatives[op](Object, Frame, RESULT)
```

That is:
- **The 3rd argument** of each `exec*` is a pointer to a **64-byte local scratch**
  (`RSP+0x30`), zeroed at the start (the same stack as `local_68[64]` in the
  decompilation). This is where `exec*` writes the value for the subsequent consuming
  opcode (the UE4 "Property Copy" mechanism).
- **The transition to the next instruction** is done by **the dispatcher itself**:
  `Code` is incremented by 1 **before** the call (`INC RAX` at `0x141FC032F`). The opcode
  handler does NOT move the PC (except `execJump`/`execJumpIfNot`/`execComputedJump`/
  `execEndOfScript`, which set `FFrame->Code` themselves).
- Symbolic constants/pointers to `UProperty` lie **inline in the stream** and are consumed
  via `Code += 8` (`execLocalVariable`, `0x141FC107A`).
- `exec*` handlers often **tail-jump** (`JMP qword ptr [RAX+0x288]` — `0x141FC109D`),
  i.e. they do not bloat their frame.

The same dispatcher is duplicated in `UObject::CallFunction` (`LEA
R13,[0x14491C6B0]` — `0x141FC00BE`, `CALL qword ptr [R13+RAX*0x8]` — `0x141FC0108`);
there the terminator is **`0x16`** (`CMP byte [RAX],0x16`, `0x141FC00B5`), i.e.
`EX_EndFunctionParms`, after which out-parms are copied and `ProcessInternal` is called.

`UObject::ProcessContextOpcode` (`0x141FC1FA0`, 184 B) — **not an opcode**, but a helper:
called from `UObject::execContext` (`0x141FC1F90`, the only xref — a
`UNCONDITIONAL_JUMP`). It reads the opcode through `GNatives` (inside
`0x141FC1F9x`), then `ReadVariableSize` and sets `Code += uint32@Code` (`0x141FC205x`).

### 4.2 How `GNatives` is populated

By static initializers of the form
`dynamic initializer for 'UObjectexec<Name>BytecodeTemp'()` (63 of them, RVAs in the
range `0x000A0080`…`0x000A39C0`, size 126–130 B). Example:

```c
// dynamic initializer for 'UObjectexecLocalVariableBytecodeTemp', RVA 0x000A00D0 (127 B)
if (!g_guard) {                 // CMP byte [0x1448EA529],0
    for (i = 0x20; i; --i)      // MOV ECX,0x20
        for (j = 0; j < 8; ++j)  // 8 × MOV [RAX+k*8],RDX
            GNatives[i*8+j] = &UObject::execUndefined;   // filler
}
if (GNatives[0] != &execUndefined) GNativeDuplicate = 0;  // CMP [0x14491C6B0],RDX ; CMOVNE
GNatives[0] = &UObject::execLocalVariable;                // ← opcode binding
```

Hence: **`GNatives` is exactly 256 slots (2048 bytes)**. The second static in each pair,
`...Registar`, calls
`UClass::AddNativeFunction(UObject::StaticClass, "execLocalVariable", &execLocalVariable)`
— registering the same name in `UClass::FuncMap`.

### 4.3 The recovered opcode map (read from PE bytecode, not invented)

| op | exec | op | exec | op | exec | op | exec |
|---|---|---|---|---|---|---|---|
| `0x00` | LocalVariable | `0x24` | ByteConst | `0x4C` | PushExecutionFlow | `0x5F` | LetObj |
| `0x01` | InstanceVariable | `0x25` | IntZero | `0x4D` | PopExecutionFlow | `0x60` | LetWeakObjPtr |
| `0x06` | Jump | `0x26` | IntOne | `0x4E` | ComputedJump | `0x61` | BindDelegate |
| `0x07` | JumpIfNot | `0x27` | True | `0x4F` | PopExecutionFlowIfNot | `0x62` | RemoveMulticastDelegate |
| `0x09` | Assert | `0x28` | False | `0x50` | Breakpoint* | `0x63` | CallMulticastDelegate |
| `0x0B` | Nothing* | `0x29` | TextConst | `0x51` | InterfaceContext | `0x64` | DoubleConst |
| `0x0F` | Let | `0x2A` | NoObject | `0x52` | InterfaceCast | `0x65` | StringLocConst |
| `0x13` | MetaCast | `0x2B` | TransformConst | `0x53` | EndOfScript | | |
| `0x14` | LetBool | `0x2C` | IntConstByte | `0x54` | InterfaceToInterface | | |
| `0x16` | EndFunctionParms | `0x2E` | DynamicCast | `0x5A` | WireTracepoint* | | |
| `0x17` | Self | `0x2F` | StructConst | `0x5B` | SkipOffsetConst | | |
| `0x19` | Context | `0x31` | SetArray | `0x5C` | AddMulticastDelegate | | |
| `0x1A` | Context_FailSilent | `0x34` | UnicodeStringConst | `0x5D` | ClearMulticastDelegate | | |
| `0x1B` | VirtualFunction | `0x38` | PrimitiveCast | `0x5E` | Tracepoint* | | |
| `0x1C` | FinalFunction | `0x42` | StructMemberContext | | | | |
| `0x1D` | IntConst | `0x43` | LetMulticastDelegate | | | | |
| `0x1E` | FloatConst | `0x44` | LetDelegate | | | | |
| `0x1F` | StringConst | `0x48` | LocalOutVariable | | | | |
| `0x20` | ObjectConst | `0x4A` | NothingOp4a* | | | | |
| `0x21` | NameConst | `0x4B` | InstanceDelegate | | | | |
| `0x22` | RotationConst | | | | | | |
| `0x23` | VectorConst | | | | | | |

`*` — all five debug opcodes point to the common stub `0x001BCBB0` (3 bytes).

Vacant slots (remain `execUndefined`): `0x02,0x03,0x04,0x05,0x08,0x0A,0x0C,0x0D,0x0E,0x10,0x11,0x12,0x15,0x18,
0x1E?no, 0x45,0x46,0x47,0x49,0x55..0x59,0x66..0xFF`.
**`0x04` is the terminator `EX_Return`**: its handler is never called
(`ProcessInternal` checks `*Code != 0x04` and exits; `CallFunction` uses `0x16`).

Consistency check: the recovered map **exactly matches** the canonical UE4
`EExprToken` (`EX_Let=0x0F`, `EX_LetBool=0x14`, `EX_DynamicCast=0x2E`,
`EX_EndFunctionParms=0x16`, `EX_Self=0x17`, `EX_Context=0x19`, `EX_EndOfScript=0x53`,
`EX_LetObj=0x5F`…). Separately noted: **not a single arithmetic opcode exists in this
build** — there are no `UObject::execAdd/Sub/Mul/...` symbols in the PDB, and the slots
`0x45,0x46,0x47,0x49` are not registered.

---

## 5. `UFunction::Invoke`

**Signature** (per disassembly, `0x141F867C0`):

```
void __fastcall UFunction::Invoke(
    UFunction* this,      // RCX
    UObject*    Obj,      // RDX
    FFrame&     Stack,    // R8  (pointer)
    void*       RESULT);  // R9
```

(this is the `UObject::ProcessDelegate`/`ProcessEvent`-compatible form of `FNativeFuncPtr`:
`void(UObject* Obj, FFrame& Stack, RESULT_DECL)`).

**Owner of a `UFunction`:** `UFunction` is an ordinary `UObject`
(`UFunction : UStruct : UField : UObject`). For a concrete UFunction the owner (`Outer`,
`+0x20`) is the **owning `UClass`** — walking its `Super` chain (`UClass+0x30`) looking
for `UInterface` — `0x141F869F5`…`0x141F86A20`. There is no global "invoke owner":
`Invoke` is a method of the `UFunction` itself, called on a concrete instance.

**How to get the bytecode:** `UFunction+0x48`. It is not read directly in `Invoke` —
the frame already carries `Code` (`FFrame+0x20`). But the constructor `FFrame::FFrame`
does exactly `Code = Function->Script`
(`MOV RAX,[R8+0x48]; MOV [RCX+0x20],RAX` — `0x141FA5820/24`), and
`ProcessEvent`/`CallFunction` create a local `FFrame` from a `UFunction*` before the
call. In sum: `Function->Script == Frame->Code` for any properly constructed frame.

**A convenient point where both UFunction and frame are known:** the entry of `Invoke`
itself — `RCX = this (UFunction*)`, `R8 = FFrame*`. Even better — **`ProcessInternal`**:
`RDX = FFrame*`, and `FFrame->Node` (`+0x10`) is the same `UFunction`
(in `ProcessInternal` it is passed to `GetFunctionCallspace` and
`UFunction::GetReturnProperty` — `0x141FC02B7`, `0x141FC036B`). Additionally, `Invoke`
**does not** write `FFrame->Node` before the call to `Func`
(it was already set by the frame constructor), and `Invoke` **additionally**
saves/restores `FFrame->CurrentNativeFunction` (`+0x88`) — `0x141F86A8C`…`0x141F86AB9`.

**Profile:** `Invoke` = 1.89 %, `ProcessInternal` = 2.17 % of frame.
`ProcessInternal` > `Invoke` because into it come both the `Invoke → Func` path (for
scripted functions) and the **direct** path
`UObject::CallFunction → ProcessInternal` (`0x141FC01F4`), bypassing Invoke.

---

## 6. Tracer sketch

### 6.1 Hook point — choice

**I choose `UObject::ProcessInternal` (RVA `0x01FC0270`), the first 12 bytes.**

Justification:

| Criterion | `ProcessInternal` | `UFunction::Invoke` |
|---|---|---|
| Hit frequency | **once per entry into a scripted UFunction** (per BP function) | once per **any** UFunction call, including native implementations, which are invoked **from every bytecode instruction** |
| Coverage | a **superset**: both `Invoke→Func` and the direct `CallFunction→ProcessInternal` | does not see `CallFunction→ProcessInternal` (`0x141FC01F4`) |
| Input data | `RDX = FFrame*`; `FFrame->Node(+0x10)` = UFunction, `FFrame->Code(+0x20)` = bytecode, `FFrame->Object(+0x18)` = object | `RCX = UFunction`, `R8 = FFrame` (2 registers needed) |
| Added cost | lower by ~K times, where K is the average number of bytecode instructions per BP call | comparable to Invoke itself |
| Risk | a general detour (no call sites) | one can patch call sites (2) |

Key argument: **`Invoke` is semantically "per UFunction call", while `ProcessInternal`
is per BP function entry**. For tracing "which UFunctions are called" this is exactly the
needed granularity and the minimal frequency. Hooking into `GNatives`/each `exec*` is
impossible — that frequency is an order of magnitude higher.

A lower-risk alternative (fallback): a hook on `Invoke` by patching **two** call sites
(`0x141FBFFA2` from `CallFunction`, `0x141FC0FA7` from `ProcessEvent`) — but then the
direct path `CallFunction → ProcessInternal` is lost.

### 6.2 What we log

**Exactly one thing:** the full `UFunction` name + a call counter. No arguments, no
parameter values, no behavior change.

- Name: `UFunction+0x18` (`FName`: `ComparisonIndex` u32, `Number` u32).
- `FName → str` **is never done in the hot path**. The ring-buffer record carries
  `(timestamp u64, UFunction* u64, ComparisonIndex u32, Number u32)` = 24 bytes.
  String resolution happens at flush time via
  `NamePoolData` (`RVA 0x0498A1C8`) → `FNameEntry*` = `block[ComparisonIndex]`,
  the string at `entry+0x10` (ASCII) or UTF-16 if `*(BYTE*)entry & 1`
  (see `FName::ToString`, `0x141F4330F`–`0x141F43338`). The same path is used by
  `UObjectBaseUtility::GetName` (`MOV RAX,[RCX+0x18]` + `MOV [RSP+0x40],RAX`).
- "Full name" = the `Outer` chain: `UFunction->Outer` (`+0x20`) is a `UClass`; the class
  name + function name are concatenated at flush time. The class string is also taken
  from `+0x18` of that same `UClass`.
- **Cache key hash:** `(UFunction*, ComparisonIndex)` — a pair, so that address reuse
  after GC does not produce a false hit.

### 6.3 Buffering

**A fixed-size ring buffer in plugin memory:**

- Storage: a `static` array in the plugin's `.data`, the size fixed at link time
  (e.g. `1<<20` records × 24 bytes = 24 MB; for a 60-second window at ~50 k calls/s,
  `1<<18` = 6 MB is enough — the size is chosen empirically, see §6.5 on
  "calibration").
- **The write index is thread-local (`__declspec(thread)`), no atomics, no locks.**
  Ring overflow is recorded by a `dropped` flag (a counter of lost records) — silently
  losing is not allowed.
- **Call counters:** a separate table `slot → uint64`, accessed by slot index from the
  direct cache. The hot path only **reads** this table.
- **Flush to disk:** a separate plugin thread, every `N` seconds (an RCON command sets
  `N`, default 30 s). The thread works in Query mode: it stops/swaps the write pointer,
  serializes raw records `(ts, UFunction*, ComparisonIndex, Number)` + counter dumps,
  then resolves strings and writes a text report. Name resolution is **outside** the
  hot path.

### 6.4 Overhead estimate

Hot path (cache hit, tracer enabled) — an estimate by instruction count, not a
measurement:

```
mov  rax,[rdx+0x10]            ; FFrame->Node
test byte ptr [g_Enabled],0
jz   out
mov  rcx,gs:[g_TlsSlots]       ; per-thread counter base
mov  rdx,[rax+0x18]            ; FName.ComparisonIndex
mov  rsi,rcx; shr rsi,4
and  rsi,8191                  ; direct-mapped cache index (8192 slots)
mov  r8,[rsi*16+cache+0]       ; saved UFunction*
cmp  r8,rax
jne  miss
mov  r8,[rsi*16+cache+4]
cmp  r8,edx
jne  miss
inc  qword ptr [rsi*16+counters+8]
out:
ret
```

≈ **10–12 instructions, ~5–7 cycles** per hit + ~5–10 cycles of detour overhead
(JMP + Indirect Branch Target Buffer). **FName→string on this path — zero.**

The baseline for comparison: `UObject::ProcessInternal` — 344 bytes of code; per BP
function entry it executes a prologue+epilogue with `__security_check_cookie`
(~25–30 instructions) **plus** the dispatcher loop — at least one iteration
(~12 instructions) per bytecode instruction. A real BP function executes tens to hundreds
of bytecode instructions, i.e. `ProcessInternal` spends **hundreds of instructions** per
call, and a detour pays off once for the whole function.

Estimate as a percentage of frame:

- The hook adds to `ProcessInternal` (2.17 % of frame) a value of the order of
  **5–15 %** of its cost (a rough upper bound for very short BP functions; typical —
  3–8 %).
- In total **≈ +0.07…0.33 % of frame**, which is **3–14 % of the 1.1 % budget** and
  **≤ 0.17× of `Invoke` itself (1.89 %)**.
- The target criterion "<5 % of 22.8 % (i.e. <1.1 % of frame)" — **met with a ×3…×15
  margin**.

Caveat: this is a **calculated estimate, not a measurement**. I have no profiler/counter
for a precise figure offline. But it is a self-checking quantity: the first tracer run
with the ring enabled yields `N_PI` — the number of `ProcessInternal` calls per window;
then
`overhead % = N_PI × 12_cycles / (T_frame_sec × 3e9) × 100`, and an A/B run (off/on) per
the A5 protocol gives the actual delta. **Without that measurement, this figure must not
be written into RE2.md as measured.**

### 6.5 Kill switch

- RCON command: `bptrace 0|1` (default **0**), `bptrace flush` (force a flush),
  `bptrace reset` (reset counters), `bptrace stat` (dump counters without a reset).
- **By default the detour IS NOT INSTALLED AT ALL.** At load the plugin only registers
  the RCON command and the point `0x141FC0270`; the `E9` patch is applied by the command
  `bptrace 1` and removed back by `bptrace 0`. This gives **literally zero influence in
  production** (not "zero, conditionally the branch is not executed"): no modified bytes →
  no influence on the instruction cache, branch predictor, CET/ENDBR, and no code-change
  trigger.
- All state (ring, counters, TLS base) is allocated lazily, only at the first
  `bptrace 1`.
- The default value is off; enable on production servers only for a 30–60 s window.

### 6.6 Thread-safety requirements

BP is executed **not only on the game thread**: `UFunction::Invoke` is called from
TaskGraph workers (async physics, partial `UWorld` operations), and `FFrame`/
`ProcessInternal` are not serialized there.

Requirements:

1. **The hot path is read-only.** Nobody writes to the direct cache
   `UFunction* → slot` or the name tables after warm-up. No atomics are needed for reads
   (x64 gives atomic 8/16-byte reads).
2. **The slot index is a per-thread buffer.** `__declspec(thread) uint32 TlsSlotBase;`
   read once (`mov rcx, gs:[...]`), ~1 cycle on an L1 hit. The per-thread size is
   fixed (e.g. 4096 slots × 8 bytes = 32 KB), allocated in `DllMain(THREAD_ATTACH)`
   from VirtualAlloc (not from the heap, to avoid depending on engine state).
3. **The ring buffer is also per-thread.** One buffer per thread, no locks; the flush
   thread uses `InterlockedExchange` on the "end of window" pointer or simply reads
   a copy (writes go only forward, so tearing is impossible if one copies first and then
   marks).
4. **The cold path (cache miss) is under `SRWLOCK` in exclusive mode.** Misses decrease
   monotonically and are bounded by the number of distinct `UFunction`s (tens of
   thousands, all created at load). Fully excluded during warm-up at the first
   `bptrace 1` (a walk over all `UFunction`s).
5. **Counter merging at flush:** the dump thread does an `InterlockedExchange64` on
   each counter within its window, then adds into the global; dropping counters is
   unacceptable.
6. **TLS in the DLL:** use static TLS (`__declspec(thread)`), not manual `TlsAlloc` —
   a TLS index has a limit on the number of modules. In the "off" state TLS is not
   touched at all.
7. **Reentrancy:** the hook calls no UE API (neither `FName::ToString`, nor allocations,
   nor logs) — only its own arrays and `Interlocked*`. Otherwise there is a recursion
   risk (a call from a log destructor).
8. **No FP/SSE:** the hook does not touch XMM so as not to corrupt the SSE context
   (compile without SSE registers, do not apply `-Oi` to the hook).

### 6.7 Risk class

**Medium.**

Why not low: the entry point is the hottest function of the scripting core; an error
(a stack shift, clobbering of unsaved RBX/RSI/RDI, a wrong trampoline length) manifests
**immediately and on 100 % of calls**, not rarely. A 12-byte detour for a 344-byte
function is safe by length; `ProcessInternal` is not a hot-patch candidate and has no
`ENDBR64` in those 12 bytes
(verified: the first instructions are `PUSH RBX; PUSH RSI; PUSH RDI; SUB RSP,0x80`), so
with CET enabled this would require disabling it or using a shadow-stack-compatible
variant — **a separate item to check before deployment**.

Why not high:
- no behavior change, no arguments, no writes into game memory;
- by default **not installed at all**;
- rollback = restoring 12 bytes back from `E9`; the plugin state — only its own buffers.

Mitigations: build with a CET-compatible trampoline (or `mov r11,imm64; jmp r11` =
12 bytes, does not touch the stack), remove the ASLR dependency via RVA, run A/B on
Genesis with `bptrace 1` enabled for 30–60 s, compare `t/s` per the A5 protocol.

---

## 7. Explicitly NOT FOUND / not checked

1. **Not measured** — the real number of `ProcessInternal` / `Invoke` calls per second —
   offline, no bench. All overhead percentages in §6.4 are computation by instructions,
   not a measurement.
2. **Not checked** — the enablement/state of `GFullStackTrace` (`0x044909C17`) in a
   working server and the actual cost of enabling `GScriptStack` — not tried.
3. **Not determined** — the exact offsets `FFrame+0x00..0x0F`, `+0x40..0x5F`,
   `+0x90 and beyond`. Only the fields listed in §3.1 are known. The full size of
   `FFrame` is not confirmed (assumed `0x90`, but not measured).
4. **Not determined by name** — the offsets `UObject+0x00`, `+0x08`, `+0x10`, `+0x20` as
   typed fields. Indirectly by usage: `+0x08` — 32-bit flags (`ObjectFlags`, a test of
   bit 14 in `ProcessEvent` `0x141FC0Dxx`, bit 26 in `Invoke` `0x141F8697A`), `+0x10` —
   `UClass*` (`execDynamicCast` `0x141FC339x`, `Invoke` `0x141F8696B`), `+0x20` —
   `Outer`. `+0x18` = `FName Name` — **confirmed directly** (`0x141F0FE0`, `0x141F86946`).
5. **Not verified** — that `UFunction+0x20` is precisely `Outer` and not some other
   field: it follows from the Super-chain walk in `Invoke` and `Bind` (an inference, not
   a type from the PDB).
6. **Not verified** — the contents of `GNatives` in memory (offline): the map in §4.3 was
   recovered from static initializers in the PE, not read from runtime. The match with
   the UE4 `EExprToken` is a strong but indirect check.
7. **Not checked** — how many slots in `GNatives` are actually overlapped/used (i.e. how
   many opcodes occur in ARK Blueprint bytecode) — a runtime statistical dump is needed.
8. **Not checked** — behavior under CET/shadow stack (see §6.7).
9. **Not found** — any `UObject::exec*` for arithmetic (`execAdd`, `execSub`, `execMul`,
   `execDiv`, `execLess`, `execJumpIf`, `execSwitch`, `execClassContext`, `execSuper`,
   `execSeek`, `execPop`, `execDuplicate`, `execStringSwitch`, `execArrayIndex`,
   `execEmptyArray`). Absent both from the PDB and from `GNatives`. **Why is
   undetermined** (the bytecode compiler implementation of this UE version or a removal);
   the conclusion "arithmetic is not supported" must not be drawn.
10. **Not found** — the symbol of the function called by `UObjectBaseUtility::GetName`
    (`0x141F1004` + `disp32` → `RVA 0x03C632B0`; no entry in `fn`/`sym`) — probably an
    ICCU-generated helper. `FName::ToString` itself was found separately
    (`0x01F432B0`/`0x01F432F0`).
11. **Not verified** — whether `UObject::ProcessContextOpcode` is called from anywhere
    else besides `UObject::execContext` — only 2 xrefs (1 call + 1 data), and the data
    xref is unresolved.
12. `dump_index.json` for `UObject::ProcessContextOpcode` and `UObject::CallFunction`
    returns `None` (the index is incomplete); all information on them was obtained
    directly from Ghidra.
