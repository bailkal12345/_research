# RE-SESSION.md — путь подключения в сервер-браузере ARK v361

Разобрано в Ghidra по `v361_ShooterGame.exe` (клиент), 2026-10-19.

## Вывод в одном абзаце

Рабочий вход идёт **не через прямой `Browse`**, а через онлайн-сессию. Бот
воспроизводил только последний шаг и поэтому упирался в таймаут: сервер —
Steam-сервер, а токен авторизации выдаёт сессионный слой. Прямой travel
уходит с запросом без валидного токена, и сервер не завершает handshake.

## Цепочка (класс `UUI_ListSessions`)

| Функция | Адрес | Роль |
|---|---|---|
| `SlotButtonSelected` | `141560d70` | только включает кнопку Join |
| `JoinSelectedSession` | `14154fcf0` | берёт выбранную запись списка, `local_1a8._40_8_ = &JoiningSessionOwnerName` |
| `DoJoinSession` | `141551220` | **вызов JoinSession** |
| `QueueJoinSession` | `14154dda0` | очередь подключения |
| `JoinFromQueue` | `14154f5f0` | выход из очереди |
| `RetryJoin` | `14154bc60` | повтор |
| `OnJoinSessionComplete` | `14154c9a0` | результат; `SaveJoiningSessionName`, FName `SESSIONNAME` |
| `OnJoinTimedOut` | `14154c0b0` | таймаут |

### `DoJoinSession` — точка входа

```cpp
UWorld*  w   = <widget world>;
UGameInstance* gi = Cast<UShooterGameInstance>(w->GetGameInstance());
AShooterGameSession* gs = <gi->GetGameSession()>();
ULocalPlayer* lp  = gi->GetFirstGamePlayer();
TSharedPtr<FUniqueNetId> pid;
lp->GetPreferredUniqueNetId(pid);

// имя сессии = владелец; для Steam-сервера это SteamID64-строка.
// при пустом JoiningSessionOwnerName подставляется строка 0x14473fcc8,
// которая в бинарнике оказывается путём из PDB - то есть мусор,
// нормальное имя всегда приходит из записи списка.
FName name(this->JoiningSessionOwnerName);

gs->JoinSession(pid, name, &this->JoiningSessionSearchResult);
```

## Требования к `JoinSession` (ARK SDK, GameState.h:344)

```cpp
bool JoinSession(TSharedPtr<FUniqueNetId,0> UserId, FName SessionName,
                 FOnlineSessionSearchResult* SearchResult);
bool JoinSession(TSharedPtr<FUniqueNetId,0> UserId, FName SessionName,
                 int SessionIndexInSearchResults);
bool TravelToSession(int ControllerId, FName SessionName);
```

Реализация (`14102b160`) требует:
* `IOnlineSubsystem::Get()` — непустой;
* интерфейс сессий (vtable `+0x198`) — непустой;
* `UserId->Object != nullptr` — валидный `FUniqueNetId` локального игрока.

## Переход после джойна

`AGameSession::TravelToSession` (`142acfe60`):

1. `IOnlineSubsystem::Get()`
2. `FindSession(SessionName, &HostAddress)` — vtable `+800`
3. `APlayerController::ClientTravelInternal(HostAddress)`

URL берётся из `HostAddress` самой сессии, а не из строки, которую набрал игрок.

## Что уже совпадает у бота

Команда `ctx` после ручного входа показала FURL, который бот теперь строит
поле в поле:

```
proto=unreal host=192.168.8.218 port=7777 valid=1
map=/Game/Maps/TheIslandSubMaps/TheIsland
Op[0]=ModId=0
Op[1]=game=/Game/PrimalEarth/CoreBlueprints/TestGameMode.TestGameMode_C
```

Движок такой URL принимает (`valid=1`), но handshake не завершается —
потому что отсутствует сессионный слой.

## Чего не хватает для автоматики

| Что | Статус в ArkApi SDK |
|---|---|
| `UShooterGameInstance::GetGameSession()` | **есть** (GameMode.h:387) |
| `AShooterGameSession::JoinSession(...)` | **есть** (GameState.h) |
| валидный `TSharedPtr<FUniqueNetId>` игрока | **нет** — `GetPreferredUniqueNetId` не объявлен |
| `FOnlineSessionSearchResult` | **нет** — объявлен только как пустой forward-decl |
| `IOnlineSubsystem` | **пустая структура** (Base.h:184), методы только через vtable |
| `IOnlineSubsystem::GetSessionInterface` (vtable +0x198) | нет, но известен из дизассемблера |

## Варианты реализации

1. **Через UI-класс.** Найти/создать `UUI_ListSessions`, заполнить
   `EntryWidgets`/`SearchSettings`, вызвать `JoinSelectedSession()`. Не требует
   отсутствующих типов, но нужна точка входа к виджету и наполнение списка.
2. **Через сессионный слой напрямую.** Взять `IOnlineSubsystem` из
   `AShooterPlayerController::OnlineSubField()` (Actor.h:2405), дёрнуть
   vtable-метод сессий и реализовать `IOnlineSession::JoinSession` руками.
   Нужно знать раскладку `FOnlineSessionSearchResult` и `FUniqueNetIdUInt64`.
3. **Собрать `FOnlineSessionSearchResult` вручную** и вызвать первый
   `JoinSession`: раскладку структуры взять из PDB (структура в бинарнике есть),
   `FUniqueNetIdUInt64` описан в UE.h:272. Наиболее прямой путь, но требует
   аккуратной реконструкции.

Любой из вариантов требует RE-работы; на текущий момент выполнен только разбор.