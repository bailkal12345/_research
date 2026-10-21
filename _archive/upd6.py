import io
p = r"C:\Dev\_research\REPORT.md"
s = io.open(p, encoding="utf-8").read()
add = """

---

## 13. Разгадка «стены»: NtDelayExecution и зажим 120

### Топ профиля из того же окна, где мерились 41%

Окно 40 с, 20 170 сэмплов, 111.6 тиков/с (без `--exclude-idle`):

| Доля | Адрес | Что это |
|---|---|---|
| **24.37%** | `ntdll+0x15F484` | **`NtDelayExecution`** — поток спит |
| 4.14% | `ntdll+0x15EE84` | `NtWaitForSingleObject` |
| 1.76% | `APrimalDinoCharacter::Tick` | ИИ динозавров |
| 1.62% | `ntdll+0x15F124` | `NtQueryInformationProcess` |
| 1.56% | `ntdll+0x15EFC4` | `NtSetEvent` |
| 1.40% | `ntdll+0x15F4C4` | `NtQuerySystemInformation` |
| 1.21% | `ntdll+0x15EEE4` | `NtDeviceIoControlFile` |
| 0.57% | `FTickTaskManager::StartFrame` | собственный код диспетчера |

Итог: внешние модули 53.8%, наш образ 45.9%, неизвестно 0.2%.

**Третий исход из брифа: дыры в символизации нет.** «Спрятанные 40%» — это
не вызываемые StartFrame, а `NtDelayExecution`: GameThread четверть времени
窗口 лежит в syscall сна. Собственный код StartFrame 0.57% — и это честно.

### Найден потолок: зажим 120 в `UGameEngine::GetMaxTickRate`

`UEngine::UpdateTimeAndHandleMaxTickRate` вызывает геттер **виртуально**
(слот vtable +0x290). Переопределение `UGameEngine::GetMaxTickRate`
(RVA `0x253B1C0`, 287 байт) декомпилировано целиком:

```c
int32_t MaxTickRate = *(int32_t *)(Driver + 0x48);      // NetServerMaxTickRate
int32_t Clamped = (MaxTickRate < 10) ? 10
               : ((MaxTickRate < 0x78) ? MaxTickRate : 0x78);
Rate = (float)Clamped;
```

`0x78` = **120**. Лимит зажат в диапазон **[10; 120]**, а просьба «200000»
превращается в 120. Наблюдаемый потолок 114–117 тиков/с подозрительно точно
упирается в это число.

Инструкция (RVA `0x253B26E`): `B9 78 00 00 00` = `MOV ECX, 0x78`, далее
`CMP EDX,ECX` / `CMOVL ECX,EDX`. Патч поднимает верхнюю границу до 100000
(`A0 86 01 00`), нижнюю (10) не трогает — семантика зажима сохраняется.

Команда: `TickProf.fixclamp 1` / `TickProf.fixclamp 0`, с проверкой опкода.

Это первая найденная причина потолка, которую можно снять патчем, и она
переводит всю работу по оптимизации CPU в пропускную способность: если
потолок уедет выше 120, наши −77% CPU начнут конвертироваться в тики.

### Гипотеза скана закрыта окончательно

Два независимых измерения:

| Что | Значение |
|---|---|
| записей в `AllEnabledTickFunctions` по 104 уровням | **3510** |
| задач, поставленных в очередь за кадр | **223** |

Ни 3510 × 72 нс (0.25 мс), ни 223 × 5.4 мкс не дают 2.7 мс. Скан не виноват.

Замечание по инструменту: перепись отдала мусор для FastPath/AllDisabled/
NewlySpawned — их смещения в `FTickTaskLevel` читаются неверно (нужна
перепроверка через `fieldcheck`). На вывод это не влияет: `AllEnabledTickFunctions`
прочитан корректно (3510).

### Опасные хуки, найденные в этом раунде

| Хук | Что делает |
|---|---|
| `FTickTaskManager.FillLevelList` | **установка вешает сервер** (подпись неизвестна, регистры-аргументы теряются) |
| `FTickTaskLevel.QueueAllTicks` | не проверялся — вероятно та же причина |
| `FTickTaskLevel.QueueNewlySpawned` | не проверялся |

Из таблицы хуков убраны; диспетчер измеряется флагом окна `StartFrame`
плюс стековый сэмплер внутри этого окна (`prof_*.sfstack`, анализатор
`sfstack.py`).
"""
if "## 13. Разгадка «стены»" not in s:
    io.open(p, "w", encoding="utf-8").write(s.rstrip() + "\n" + add)
    print("report updated")
else:
    print("уже есть")
