# A5. BP-машина и трассировщик

Образ: `ShooterGameServer.exe` v361.7 (ARK: Survival Evolved), Win64 x64, image base `0x140000000`.
Все RVA получены из `v361.sqlite` (`fn`/`sym`); все смещения полей и адреса глобалов — из дизассемблирования
Ghidra (`/v361_ShooterGameServer.exe`), каждый тезис помечен адресом.

---

## 1. Таблица символов

| Символ | RVA | VA | size |
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
| `FName::ToString` (обёртка) | `0x01F432B0` | `0x141F432B0` | 58 |
| `FName::ToString` (реальная) | `0x01F432F0` | `0x141F432F0` | 130 |
| `FName::AppendString` | `0x01F43380` | `0x141F43380` | 197 |

**Глобалы (данные):**

| Имя | RVA | VA | Назначение (доказательство) |
|---|---|---|---|
| `GNatives` | `0x0491C6B0` | `0x14491C6B0` | таблица диспетчера опкодов, `MOV [RDI+RAX*8]` — `0x141FC0309/033C`, `0x141FC00BE/0108` |
| `GNativeDuplicate` | `0x0491C89C` | `0x14491C89C` | флаг дубля опкода — `0x141FA013A` |
| `GScriptStack` | `0x04937F00` | `0x144937F00` | стек BP: `+0x0` allocator, `+0x8` ArrayNum, `+0xC` ArrayMax, stride `0x10` — `0x141FA58A8..0x141FA5922` |
| `GPrevScriptStack` | `0x04937F10` | `0x144937F10` | предыдущий стек — `0x141FA58AA/0x141FA58C8` |
| `GFullStackTrace` | `0x04909C17` | `0x144909C17` | byte-флаг трассировки стека — `0x141FA5869` |
| `NamePoolData` | `0x0498A1C8` | `0x14498A1C8` | пул FNameEntry, блок по `0x800` слотов — `0x141F427D4/0x141F42812` |

**xref на `UFunction::Invoke` (RVA `0x01F867C0`) — всего 3 вызова:**

- `0x141FBFFA2` — из `UObject::CallFunction`
- `0x141FC0FA7` — из `UObject::ProcessEvent`
- `0x141F869EB` — рекурсия «BreakHitResult_OLD» внутри самого `Invoke`

**xref на `UObject::ProcessInternal` (RVA `0x01FC0270`):**

- `0x141FC01F4` `UNCONDITIONAL_CALL` — из `UObject::CallFunction`
- `0x141F86D7A`, `0x141F86D81` `DATA` — из `UFunction::Bind` (`MOV [R9+0xA8], RAX`, `RAX=0x141FC0270`)
- `0x144A7F044` `DATA` — vtable/таблица

Вывод: у `ProcessInternal` **нет вызывающего call-site в коде** — он вызывается **косвенно через `UFunction::Func`**,
поэтому патчить точку вызова нельзя, только detour тела функции. У `Invoke` call-site'ы есть (3 шт.).

---

## 2. Набор `UObject::exec*`

- **68** различных символов PDB, именующихся `UObject::exec*`.
- Они лежат **одним непрерывным блоком `0x01FC1050` … `0x01FC36B6`** (61 уникальный адрес, суммарно **8776 байт**).
- **5 отладочных опкодов схлопываются на один 3-байтный стаб `0x001BCBB0`**:
  `execBreakpoint`, `execNothing`, `execNothingOp4a`, `execTracepoint`, `execWireTracepoint` (алиасы в PDB).
- **63** из них реально регистрируются в `GNatives` как байткод-опкоды (см. §4).
- **4** имеют код, но не имеют слота в `GNatives`: `execUndefined` (`0x01FC1050` — заполнитель таблицы),
  `execObjectToBool` (`0x01FC3480`), `execInterfaceToBool` (`0x01FC34D0`),
  `execObjectToInterface` (`0x01FC3520`) — у последних трёх статики называются
  `...CastTemp`/`...Registar`, а не `...BytecodeTemp` (компилятор байткода их не порождает).
- Отдельно: `UObject::ExecuteUbergraph` (`0x001C0ED0`, 63 б) — это не опкод, а туннель-UUFunction.

Полный список (RVA, размер):

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
0x01FC2060 497  execStructMemberContext  0x01FC3480  71 execObjectToBool     (нет слота)
0x01FC2260 110  execVirtualFunction      0x01FC34D0  72 execInterfaceToBool  (нет слота)
0x01FC22D0  21  execFinalFunction        0x01FC3520 200 execObjectToInterface(нет слота)
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

## 3. Раскладка кадра интерпретатора

### 3.1 `FFrame` — подтверждено конструктором `FFrame::FFrame` (`0x141FA57E0`)

Канонический вызов из `UObject::CallFunction` (`0x141FC0029`):
`FFrame::FFrame(this=&stack, Owner=this, Function=UFunction*, Locals=buf, PreviousFrame=param_1, PropertyChainForCompiledIn=*(UFunction+0x38))`.

| Offset | Поле | Как получено |
|---|---|---|
| `+0x00` | `void** vftable` = `0x144073EB0` | `MOV [RCX],RAX` — `0x141FA5815` |
| `+0x08` | `uint16` = `0x100` | `MOV word [RCX+8],0x100` — `0x141FA5808` |
| `+0x10` | **`UFunction* Node`** | `MOV [RCX+0x10],R8` — `0x141FA5818` |
| `+0x18` | **`UObject* Object`** | `MOV [RCX+0x18],RDX` — `0x141FA581C` |
| `+0x20` | **`uint8* Code`** (PC в байткоде) | `MOV [RCX+0x20],RAX`, где `RAX=[R8+0x48]` — `0x141FA5820/24` |
| `+0x28` | **`uint8* Locals`** | `MOV [RCX+0x28],R9` — `0x141FA5828` |
| `+0x30` | `UProperty* MostRecentProperty` | `MOV [RCX+0x30],0` — `0x141FA582E`; запись `0x141FC107E` |
| `+0x38` | `uint8* MostRecentPropertyAddress` | `MOV [RCX+0x38],0` — `0x141FA5832`; запись `0x141FC108E` |
| `+0x60` | inline-heap allocator `TArray FlowStack` | `ADD RCX,0x60; CALL 0x1401BF260` — `0x141FA5836/3A` |
| `+0x68` / `+0x6C` | `FlowStack.ArrayNum`=0 / `ArrayMax`=8 | `0x141FA583F/42` |
| `+0x70` | `FFrame* PreviousFrame` | `MOV [RBX+0x70],RAX` — `0x141FA584E` |
| `+0x78` | `FOutParmRec* OutParms` | `MOV [RBX+0x78],0` — `0x141FA5852` |
| `+0x80` | `UField* PropertyChainForCompiledIn` | `MOV [RBX+0x80],RAX` — `0x141FA585B` |
| `+0x88` | **`UFunction* CurrentNativeFunction`** | `MOV [RBX+0x88],0` — `0x141FA5862`; запись `this` в `UFunction::Invoke` — `0x141F86AA0` |

`Locals` — **не** `TArray<uint8*>` и **не** список указателей: это **плоский `uint8*`-буфер**,
адресуемый по смещениям из `UProperty`. Никакого «Stride» нет:

```asm
; UObject::execLocalVariable, 0x141FC1070
141fc1070  MOV  RAX,[RDX+0x20]        ; FFrame->Code
141fc1077  MOV  RCX,[RAX]             ; UProperty*  (8-байтовый литерал в потоке кода)
141fc107a  ADD  RAX,0x8
141fc107e  MOV  [RDX+0x30],RCX        ; FFrame->MostRecentProperty
141fc1082  MOV  [RDX+0x20],RAX        ; Code += 8
141fc1086  MOVSXD R8,dword ptr [RCX+0x4C]   ; UProperty::Offset_Internal (int32)
141fc108a  ADD  R8,[RDX+0x28]               ; Locals + Offset_Internal
141fc108e  MOV  [RDX+0x38],R8                ; MostRecentPropertyAddress
```
Итог: **`Locals[Prop->Offset_Internal]`**, где `UProperty+0x4C = Offset_Internal (int32)`.

### 3.2 `UFunction` — подтверждено `UFunction::Bind` (`0x141F86D30`) и ctor'ом `FFrame`

| Offset | Поле | Доказательство |
|---|---|---|
| `+0x18` | **`FName Name`** (`ComparisonIndex`@`+0x18`, `Number`@`+0x1C`) | `UObjectBaseUtility::GetName`: `MOV RAX,[RCX+0x18]` — `0x141F0FE0+6`; `UFunction::Invoke`: `MOV RAX,[RBP+0x18]; CMP EAX,NAME_BreakHitResult.ComparisonIndex; SHR RAX,0x20; CMP EAX,Number` — `0x141F86946..958`; скрипт-стек пишет `[RSI+0x18]` — `0x141FA58DA` |
| `+0x20` | `UObject* Outer` (для UFunction — владеющий `UClass`) | `UFunction::Invoke` обходит его как `UClass*` по `Super` (`+0x30`) в поисках `UInterface::StaticClass` — `0x141F869F5..0x141F86A20` |
| `+0x38` | `UProperty* PropertyChainForCompiledIn` | `UObject::CallFunction`: `MOV RAX,[R14+0x38]`, кладётся 6-м аргументом в `FFrame::FFrame` (`+0x80`) — `0x141FC000E/0012/0029` |
| `+0x40` | `int32 ParmsSize` | `MOVSXD RDX,dword [R9+0x40]`, далее `memset` этого размера — `0x141FBFFBF/0011` |
| `+0x48` | **`uint8* Script` (указатель на байткод)** | `FFrame::FFrame`: `MOV RAX,[R8+0x48]; MOV [RCX+0x20],RAX` — `0x141FA5820/24`; та же пара `(FName@+0x18, Script@+0x48)` кладётся в `GScriptStack` — `0x141FA58DA` (FName), запись пары `0x141FA58EB`+`0x141FA5922` |
| `+0x90` | `uint32 FunctionFlags` | `TEST dword [R9+0x90],0x400` (FUNC_Native) — `0x141FBFF36`, `0x141F86D6D`; `TEST [R14+0x90],0x400000` (FUNC_HasOutParms) — `0x141FC0036` |
| `+0xA8` | **`FNativeFuncPtr Func`** | `CALL qword ptr [RBP+0xA8]` — `0x141F86AB2`; `LEA RAX,[0x141FC0270]; MOV [R9+0xA8],RAX` — `0x141F86D7A/81` |

**Ключевой факт (важен для трассировщика):**

```asm
; UFunction::Bind, 0x141F86D6D
141f86d6d  TEST dword ptr [R9 + 0x90], 0x400      ; FunctionFlags & FUNC_Native
141f86d78  JNZ  0x141f86d89                        ; если native -> взять из NativeFuncMap
141f86d7a  LEA  RAX,[0x141FC0270]                  ; &UObject::ProcessInternal
141f86d81  MOV  qword ptr [R9 + 0xA8],RAX         ; UFunction->Func = ProcessInternal
```
То есть **для любой скриптовой (не-native) UFunction поле `Func` = `&UObject::ProcessInternal`**.
`UFunction::Invoke` — это ровно `Func(Obj, FFrame&, RESULT)` плюс мелкий prologue (BreakHitResult-шимп,
поиск интерфейса, `GProgressBarAddQuanta`).

Прочие полезные смещения `UProperty` (нужны только для контекста):
`+0x30 ArrayDim`, `+0x34 ElementSize`, `+0x38 uint64 PropertyFlags`, `+0x4C Offset_Internal`, `+0x60 Next`
(из `0x141FC039C/03A4`, `0x141FC0386`, `0x141FC012C`, цепочка в `ProcessEvent`).

---

## 4. Диспетчер опкодов

### 4.1 Как выбирается обработчик

**Таблица указателей `GNatives[256]` (2048 байт) по индексу = байт опкода.** Никакого `switch`/jumptable.

Цикл `UObject::ProcessInternal` (`0x141FC0320`–`0x141FC0369`), дословно:

```asm
141fc0320  MOV  RAX,[RBX+0x20]          ; Code
141fc0324  LEA  R8,[RSP+0x30]           ; &scratchResult (64 байта, локальный буфер)
141fc0329  MOV  RDX,RBX                 ; FFrame*
141fc032c  MOVZX ECX,byte ptr [RAX]     ; op = *Code
141fc032f  INC  RAX
141fc0332  MOV  [RBX+0x20],RAX          ; Code++
141fc0336  MOV  EAX,ECX
141fc0338  MOV  RCX,[RBX+0x18]          ; FFrame->Object  -> 1-й аргумент
141fc033c  CALL qword ptr [RDI+RAX*0x8] ; RDI=0x14491C6B0  ->  GNatives[op]
141fc033f  MOV  RAX,[RBX+0x20]
141fc0343  CMP  byte ptr [RAX],0x4      ; op == 0x04 (EX_Return)?
141fc0346  JNZ  0x141fc0320
141fc0348  INC  qword ptr [RBX+0x20]     ; пропустить байт 0x04
141fc034c  MOV  RAX,[RBX+0x20]
141fc0350  MOV  RCX,[RBX+0x18]
141fc0354  MOVZX EDX,byte ptr [RAX]     ; последний опкод
141fc0357  INC  RAX
141fc035a  MOV  R8,RSI                  ; РЕАЛЬНЫЙ RESULT (param_2)
141fc035d  MOV  [RBX+0x20],RAX
141fc0361  MOV  EAX,EDX
141fc0363  MOV  RDX,RBX
141fc0366  CALL qword ptr [RDI+RAX*0x8] ; -> GNatives[op](Object, Frame, RESULT)
```

То есть:
- **3-й аргумент** каждого `exec*` — указатель на **64-байтный локальный scratch** (`RSP+0x30`),
  обнуляемый в начале (тот же стек, что и `local_68[64]` в декомпиляции). Именно сюда `exec*`
  пишет значение для последующего consuming-опкода (механизм UE4 «Property Copy»).
- **Переход к следующей инструкции** делает **сам диспетчер**: `Code` увеличивается на 1 **до** вызова
  (`INC RAX` на `0x141FC032F`). Обработчик опкода НЕ двигает PC (кроме `execJump`/`execJumpIfNot`/
  `execComputedJump`/`execEndOfScript`, которые переставляют `FFrame->Code` сами).
- Символьные константы/указатели на `UProperty` лежат **инлайн в потоке** и потребляются
  `Code += 8` (`execLocalVariable`, `0x141FC107A`).
- `exec*` часто **делают tail-jump** (`JMP qword ptr [RAX+0x288]` — `0x141FC109D`), т.е. свой кадр
  не раздувают.

Тот же диспетчер продублирован в `UObject::CallFunction` (`LEA R13,[0x14491C6B0]` — `0x141FC00BE`,
`CALL qword ptr [R13+RAX*0x8]` — `0x141FC0108`), там терминатор — **`0x16`** (`CMP byte [RAX],0x16`,
`0x141FC00B5`), т.е. `EX_EndFunctionParms`, после чего копируются out-parms и вызывается `ProcessInternal`.

`UObject::ProcessContextOpcode` (`0x141FC1FA0`, 184 б) — **не опкод**, а помощник:
вызывается из `UObject::execContext` (`0x141FC1F90`, единственный xref — `UNCONDITIONAL_JUMP`).
Читает опкод через `GNatives` (`0x141FC1F9x`区内), затем `ReadVariableSize` и переставляет
`Code += uint32@Code` (`0x141FC205x`).

### 4.2 Как `GNatives` заполняется

Статическими инициализаторами вида
`dynamic initializer for 'UObjectexec<Name>BytecodeTemp'()` (63 штуки, RVA в диапазоне
`0x000A0080`…`0x000A39C0`, размер 126–130 б). Пример:

```c
// dynamic initializer for 'UObjectexecLocalVariableBytecodeTemp', RVA 0x000A00D0 (127 б)
if (!g_guard) {                 // CMP byte [0x1448EA529],0
    for (i = 0x20; i; --i)      // MOV ECX,0x20
        for (j = 0; j < 8; ++j)  // 8 × MOV [RAX+k*8],RDX
            GNatives[i*8+j] = &UObject::execUndefined;   // заполнитель
}
if (GNatives[0] != &execUndefined) GNativeDuplicate = 0;  // CMP [0x14491C6B0],RDX ; CMOVNE
GNatives[0] = &UObject::execLocalVariable;                // ← привязка опкода
```
Отсюда: **`GNatives` = ровно 256 слотов (2048 байт)**. Второй статик в каждой паре,
`...Registar`, делает `UClass::AddNativeFunction(UObject::StaticClass, "execLocalVariable", &execLocalVariable)`
— регистрирует то же имя в `UClass::FuncMap`.

### 4.3 Восстановленная карта опкодов (прочитана из байткода PE, не выдумана)

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

`*` — все пять отладочных опкодов указывают на общий стаб `0x001BCBB0` (3 байта).

Незанятые слоты (остаются `execUndefined`): `0x02,0x03,0x04,0x05,0x08,0x0A,0x0C,0x0D,0x0E,0x10,0x11,0x12,0x15,0x18,
0x1E?no, 0x45,0x46,0x47,0x49,0x55..0x59,0x66..0xFF`.
**`0x04` — терминатор `EX_Return`**: обработчик для него не вызывается никогда
(`ProcessInternal` проверяет `*Code != 0x04` и выходит; `CallFunction` использует `0x16`).

Контроль согласованности: полученная карта **точно совпадает** с каноническим `EExprToken` UE4
(`EX_Let=0x0F`, `EX_LetBool=0x14`, `EX_DynamicCast=0x2E`, `EX_EndFunctionParms=0x16`, `EX_Self=0x17`,
`EX_Context=0x19`, `EX_EndOfScript=0x53`, `EX_LetObj=0x5F`…). Отдельно отмечу: **в этом билде
нет ни одного арифметического опкода** — символов `UObject::execAdd/Sub/Mul/...` в PDB нет,
и слоты `0x45,0x46,0x47,0x49` не регистрируются.

---

## 5. `UFunction::Invoke`

**Сигнатура** (по дизассемблированию, `0x141F867C0`):

```
void __fastcall UFunction::Invoke(
    UFunction* this,      // RCX
    UObject*    Obj,      // RDX
    FFrame&     Stack,    // R8  (указатель)
    void*       RESULT);  // R9
```
(это `UObject::ProcessDelegate`/`ProcessEvent`-совместимая форма `FNativeFuncPtr`:
`void(UObject* Obj, FFrame& Stack, RESULT_DECL)`).

**Владелец `UFunction`:** `UFunction` — обычный `UObject` (`UFunction : UStruct : UField : UObject`).
У конкретного UFunction владельцем (`Outer`, `+0x20`) является **владеющий `UClass`** — обход его
`Super`-цепочки (`UClass+0x30`) ради `UInterface` — `0x141F869F5`…`0x141F86A20`. Глобального
"владельца invoke" нет: `Invoke` — метод самого `UFunction`, вызывается у конкретного экземпляра.

**Как получить байткод:** `UFunction+0x48`. Прямо в `Invoke` он не читается — фрейм уже несёт
`Code` (`FFrame+0x20`). Но конструктор `FFrame::FFrame` делает ровно `Code = Function->Script`
(`MOV RAX,[R8+0x48]; MOV [RCX+0x20],RAX` — `0x141FA5820/24`), а `ProcessEvent`/`CallFunction`
создают локальный `FFrame` из `UFunction*` перед вызовом. Итого:
`Function->Script == Frame->Code` для любого корректно построенного фрейма.

**Удобная точка, где известны и UFunction, и фрейм:** сам вход в `Invoke` —
`RCX = this (UFunction*)`, `R8 = FFrame*`. Ещё лучше — **`ProcessInternal`**:
`RDX = FFrame*`, а `FFrame->Node` (`+0x10`) — тот же самый `UFunction`
(в `ProcessInternal` он передаётся в `GetFunctionCallspace` и `UFunction::GetReturnProperty` —
`0x141FC02B7`, `0x141FC036B`). Плюс `Invoke` **не** пишет `FFrame->Node` перед вызовом `Func`
(оно уже проставлено конструктором фрейма), а `Invoke` **дополнительно** сохраняет/восстанавливает
`FFrame->CurrentNativeFunction` (`+0x88`) — `0x141F86A8C`…`0x141F86AB9`.

**Профиль:** `Invoke` = 1.89 %, `ProcessInternal` = 2.17 % кадра.
`ProcessInternal` > `Invoke` потому, что в него попадают и путь `Invoke → Func` (для скриптовых
функций), и **прямой** путь `UObject::CallFunction → ProcessInternal` (`0x141FC01F4`), минуя Invoke.

---

## 6. Эскиз трассировщика

### 6.1 Точка зацепа — выбор

**Выбираю `UObject::ProcessInternal` (RVA `0x01FC0270`), первые 12 байт.**

Обоснование:

| Критерий | `ProcessInternal` | `UFunction::Invoke` |
|---|---|---|
| Частота срабатывания | **1 раз на вход в скриптовую UFunction** (на каждую BP-функцию) | 1 раз на **любой** вызов UFunction, включая native-реализации, которые вызываются **из каждой инструкции байткода** |
| Покрытие | **надмножество**: и `Invoke→Func`, и прямой `CallFunction→ProcessInternal` | не видит `CallFunction→ProcessInternal` (`0x141FC01F4`) |
| Данные на входе | `RDX = FFrame*`; `FFrame->Node(+0x10)` = UFunction, `FFrame->Code(+0x20)` = байткод, `FFrame->Object(+0x18)` = объект | `RCX = UFunction`, `R8 = FFrame` (нужно 2 регистра) |
| Наложенные расходы | ниже в ~K раз, где K — среднее число байткод-инструкций на BP-вызов | сопоставимы с самой Invoke |
| Риск | общий detour (call-site нет) | можно патчить call-site (2 шт.) |

Ключевой довод: **`Invoke` семантически «на каждую UFunction-вызов», а `ProcessInternal` — на каждый
вход в BP-функцию**. Для трассировки «какие UFunction вызываются» это ровно нужная гранулярность и
минимальная частота. Встраивать хук в `GNatives`/каждый `exec*` нельзя — это частота на порядок выше.

Альтернатива с меньшим риском (запасной вариант): хук на `Invoke` патчем **двух** call-site'ов
(`0x141FBFFA2` из `CallFunction`, `0x141FC0FA7` из `ProcessEvent`) — но тогда теряется прямой путь
`CallFunction → ProcessInternal`.

### 6.2 Что логируем

**Ровно одно:** полное имя `UFunction` + счётчик вызовов. Никаких аргументов, никаких значений
параметров, никакого изменения поведения.

- Имя: `UFunction+0x18` (`FName`: `ComparisonIndex` u32, `Number` u32).
- `FName → str` **никогда не делается в горячем пути**. Запись в кольцевой буфер несёт
  `(timestamp u64, UFunction* u64, ComparisonIndex u32, Number u32)` = 24 байта.
  Разрешение строки — на этапе сброса, через
  `NamePoolData` (`RVA 0x0498A1C8`) → `FNameEntry*` = `block[ComparisonIndex]`,
  строка по `entry+0x10` (ASCII) либо UTF-16, если `*(BYTE*)entry & 1`
  (см. `FName::ToString`, `0x141F4330F`–`0x141F43338`). Тот же путь использует
  `UObjectBaseUtility::GetName` (`MOV RAX,[RCX+0x18]` + `MOV [RSP+0x40],RAX`).
- «Полное имя» = `Outer`-цепочка: `UFunction->Outer` (`+0x20`) — это `UClass`; имя класса + имя функции
  склеиваются при сбросе. Строка класса тоже берётся из `+0x18` того же `UClass`.
- **Хэш ключа кэша:** `(UFunction*, ComparisonIndex)` — пара, чтобы переиспользование адреса после GC
  не дало ложное попадание.

### 6.3 Буферизация

**Кольцевой буфер фиксированного размера в памяти плагина:**

- Хранилище: `static` массив в `.data` плагина, размер фиксирован на этапе линковки
  (например `1<<20` записей × 24 байта = 24 МБ; для 60-секундного окна при ~50 k вызовах/с хватит
  `1<<18` = 6 МБ — размер выбирается по факту, см. §6.5 про «калибровку»).
- **Индекс записи — локальный (`__declspec(thread)`), без атомиков и без блокировок.**
  Переполнение кольца фиксируется флагом `dropped` (счётчик потерянных записей) — молча терять нельзя.
- **Счётчики вызовов:** отдельная таблица `slot → uint64`, доступ по индексу слота
  из прямого кэша. Хот-путь только **читает** эту таблицу.
- **Сброс на диск:** отдельный поток плагина, раз в `N` секунд (RCON-команда задаёт `N`,
  по умолчанию 30 с). Поток делает `Query`-режим: останавливает/свопит указатель записи,
  сериализует сырые записи `(ts, UFunction*, ComparisonIndex, Number)` + дампы счётчиков,
  затем разрешает строки и пишет текстовый отчёт. Разрешение имён — **вне** горячего пути.

### 6.4 Оценка накладных

Горячий путь (попадание в кэш, трейлер включён) — оценка по инструкциям, не измерение:

```
mov  rax,[rdx+0x10]            ; FFrame->Node
test byte ptr [g_Enabled],0
jz   out
mov  rcx,gs:[g_TlsSlots]       ; база per-thread счётчиков
mov  rdx,[rax+0x18]            ; FName.ComparisonIndex
mov  rsi,rcx; shr rsi,4
and  rsi,8191                  ; индекс direct-mapped кэша (8192 слотов)
mov  r8,[rsi*16+cache+0]       ; сохранённый UFunction*
cmp  r8,rax
jne  miss
mov  r8,[rsi*16+cache+4]
cmp  r8,edx
jne  miss
inc  qword ptr [rsi*16+counters+8]
out:
ret
```

≈ **10–12 инструкций, ~5–7 циклов** на попадание + ~5–10 циклов накладных от detour'а
(JMP + Indirect Branch Target buffer). **FName→строка на этом пути — ноль.**

База для сравнения: `UObject::ProcessInternal` — 344 байта кода; на один вход в BP-функцию он
выполняет пролог+эпилог c `__security_check_cookie` (~25–30 инструкций) **плюс** цикл диспетчера
минимум одну итерацию (~12 инструкций) на каждую байткод-инструкцию. Реальная BP-функция
выполняет десятки–сотни байткод-инструкций, т.е. `ProcessInternal` на один вызов тратит
**сотни инструкций**, и detour'ом окупается один раз на всю функцию.

Оценка в процентах кадра:

- Хук добавляет к `ProcessInternal` (2.17 % кадра) величину порядка **5–15 %** его стоимости
  (грубая верхняя оценка при очень коротких BP-функциях; типовая — 3–8 %).
- Итого **≈ +0.07…0.33 % кадра**, что составляет **3–14 % от бюджета 1.1 %** и
  **≤ 0.17× от самой `Invoke` (1.89 %)**.
- Целевой критерий «<5 % от 22.8 % (т.е. <1.1 % кадра)» — **выполняется с запасом ×3…×15**.

Оговорка: это **расчётная оценка, а не измерение**. Профилировщика/счётчика для точной цифры
у меня офлайн нет. Но это самоконтролируемая величина: первый же прогон трассировщика с включённым
кольцом даёт `N_PI` — число вызовов `ProcessInternal` за окно; тогда
`накладные % = N_PI × 12_cycles / (T_frame_сек × 3e9) × 100`, и A/B-прогон (выкл/вкл) по A5-протоколу
даёт фактическую дельту. **Без этого замера цифру в RE2.md писать как измеренную нельзя.**

### 6.5 Выключатель

- RCON-команда: `bptrace 0|1` (по умолчанию **0**), `bptrace flush` (форсировать сброс),
  `bptrace reset` (сбросить счётчики), `bptrace stat` (dump счётчиков без сброса).
- **По умолчанию detour НЕ УСТАНАВЛИВАЕТСЯ ВООБЩЕ.** Плагин при загрузке только регистрирует
  RCON-команду и точку `0x141FC0270`; патч `E9` ставится по команде `bptrace 1` и снимается
  обратно по `bptrace 0`. Это даёт **буквальный ноль влияния в проде** (а не «ноль, условно-ветка
  не выполняется»): нет изменённых байтов → нет влияния на instruction cache, branch predictor,
  CET/ENDBR и нет триггера на изменение кода.
- Весь state (кольцо, счётчики, TLS-база) аллоцируется лениво, только при первом `bptrace 1`.
- Значение по умолчанию — выключено; на прод-серверах включать только на окно 30–60 с.

### 6.6 Требования к потокобезопасности

BP выполняется **не только на игровом потоке**: `UFunction::Invoke` вызывается из TaskGraph-воркеров
(асинхронная физика, `UWorld` партиальные операции), и `FFrame`/`ProcessInternal` там не сериализованы.

Требования:

1. **Горячий путь — только чтение.** Прямого кэша `UFunction* → slot` и таблицы имён после прогрева
   никто не пишет. Никаких атомиков в чтении не нужно (x64 даёт атомарные 8/16-байт чтения).
2. **Индекс слота — локальный буфер на поток.** `__declspec(thread) uint32 TlsSlotBase;`
   читается один раз (`mov rcx, gs:[...]`), ~1 цикл при попадании в L1. Размер на поток —
   фиксированный (например 4096 слотов × 8 байт = 32 КБ), аллоцируется в `DllMain(THREAD_ATTACH)`
   из VirtualAlloc (не из кучи, чтобы не зависеть от состояния движка).
3. **Кольцевой буфер — тоже на поток.** Один буфер на поток, без блокировок; слив с потока
   использует `InterlockedExchange` на указатель «конец окна» либо просто читает копию
   (запись идёт только вперёд, поэтому tear невозможен, если сначала скопировать, потом отметить).
4. **Cold path (промах кэша) — под `SRWLOCK` в эксклюзивном режиме.** Промахи монотонно
   убывают и ограничены числом различных `UFunction` (десятки тысяч, все создаются на загрузке).
   Полностью исключены на прогреве при первом `bptrace 1` (обход всех `UFunction`).
5. **Слияние счётчиков на сбросе:** поток-дамп делает `InterlockedExchange64` на каждый счётчик
   в своём окне, затем складывает в общий; падение счётчиков недопустимо.
6. **TLS в DLL:** использовать статический TLS (`__declspec(thread)`), не `TlsAlloc` вручную —
   у TLS-индекса есть лимит на кол-во модулей. В состоянии «выключено» TLS вообще не трогается.
7. **Реентерабельность:** хук не вызывает ни одного API UE (ни `FName::ToString`, ни аллокаций,
   ни логов) — только свои массивы и `Interlocked*`. Иначе риск рекурсии (вызов из деструктора лога).
8. **Отсутствие FP/SSE:** хук не трогает XMM, чтобы не портить состояние SSE-контекста
   (компилировать без SSE-регистров, `-Oi` не применять к хуку).

### 6.7 Риск-класс

**Средний (Medium).**

Почему не низкий: вход — в самую горячую функцию ядра скриптинга; ошибка (сдвиг стека, порча
несохранённого RBX/RSI/RDI, неправильная длина trampoline) проявляется **немедленно и на 100 % вызовов**,
а не редко. Detour длиной 12 байт при длине функции 344 байта — безопасно по длине;
`ProcessInternal` не является hot-patch-кандидатом и не имеет `ENDBR64` в этих 12 байтах
(проверено: первые инструкции — `PUSH RBX; PUSH RSI; PUSH RDI; SUB RSP,0x80`), так что при включённом
CET это потребует отключения или использования shadow-stack совместимого варианта — **это отдельный
пункт для проверки перед выкаткой**.

Почему не высокий:
- нет изменения поведения, нет аргументов, нет записей в память игры;
- по умолчанию **вообще не установлен**;
- откат = снять 12 байт (восстановить `E9` обратно), состояние плагина — только свои буферы.

Снижающие меры: собрать с CET-совместимым trampoline (или `mov r11,imm64; jmp r11` = 12 байт,
не трогает стек), отключить ASLR-зависимость через RVA, прогнать A/B на Genesis с включённым
`bptrace 1` на 30–60 с, сравнить `t/s` по A5-протоколу.

---

## 7. Явно НЕ НАЙДЕНО / не проверено

1. **Не измерено** реальное число вызовов `ProcessInternal` / `Invoke` в секунду — офлайн, без стенда.
   Все проценты накладных в §6.4 — расчёт по инструкциям, не измерение.
2. **Не проверено** включение/состояние `GFullStackTrace` (`0x044909C17`) в рабочем сервере
   и фактическая цена включения `GScriptStack` — не пробовал.
3. **Не определены** точные смещения `FFrame+0x00..0x0F`, `+0x40..0x5F`, `+0x90 и далее`.
   Известны только перечисленные в §3.1 поля. Размер `FFrame` целиком не подтверждён
   (предположительно `0x90`, но это не измерено).
4. **Не определены** поимённо смещения `UObject+0x00`, `+0x08`, `+0x10`, `+0x20` как типизированные
   поля. Косвенно по использованию: `+0x08` — 32-битные флаги (`ObjectFlags`, тест. бит 14 в
   `ProcessEvent` `0x141FC0Dxx`, бит 26 в `Invoke` `0x141F8697A`), `+0x10` — `UClass*`
   (`execDynamicCast` `0x141FC339x`, `Invoke` `0x141F8696B`), `+0x20` — `Outer`.
   `+0x18` = `FName Name` — **подтверждено напрямую** (`0x141F0FE0`, `0x141F86946`).
5. **Не проверено**, что `UFunction+0x20` — именно `Outer`, а не иное поле: следует из обхода
   Super-цепочки в `Invoke` и `Bind` (вывод, а не тип из PDB).
6. **Не проверено** содержимое `GNatives` в памяти (оффлайн): карта §4.3 восстановлена из
   статик-инициализаторов в PE, а не прочитана из рантайма. Совпадение с `EExprToken` UE4 —
   сильный, но косвенный контроль.
7. **Не проверено**, сколько слотов реально перекрыто/используется в `GNatives` (т.е. сколько
   опкодов встречается в байткоде ARK-блюпринтов) — нужен рантайм-статистический дамп.
8. **Не проверено** поведение под CET/shadow stack (см. §6.7).
9. **Не найдено** ни одного `UObject::exec*` для арифметики (`execAdd`, `execSub`, `execMul`,
   `execDiv`, `execLess`, `execJumpIf`, `execSwitch`, `execClassContext`, `execSuper`, `execSeek`,
   `execPop`, `execDuplicate`, `execStringSwitch`, `execArrayIndex`, `execEmptyArray`).
   Отсутствуют и в PDB, и в `GNatives`. **Почему — не выяснено** (реализация компилятора байткода
   этой версии UE или выпиливание); вывод «арифметика не поддерживается» делать нельзя.
10. **Не найден** символ для функции, которую вызывает `UObjectBaseUtility::GetName`
    (`0x141F1004` + `disp32` → `RVA 0x03C632B0`; в `fn`/`sym` записи нет) — вероятно
    ICCU-генерированный хелпер. Само `FName::ToString` найдено отдельно (`0x01F432B0`/`0x01F432F0`).
11. **Не проверено**, что `UObject::ProcessContextOpcode` вызывается ещё откуда-то кроме
    `UObject::execContext` — xref всего 2 (1 вызов + 1 data), но data-xref не разрешён.
12. `dump_index.json` для `UObject::ProcessContextOpcode` и `UObject::CallFunction` отдаёт `None`
    (индекс неполон); вся информация по ним получена напрямую из Ghidra.