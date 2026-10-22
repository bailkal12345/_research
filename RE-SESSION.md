# RE-SESSION.md — the join path in the ARK v361 server browser

Disassembled in Ghidra on `v361_ShooterGame.exe` (client), 2026-10-19.

## Conclusion in one paragraph

The working join goes **not through a direct `Browse`**, but through the online session.
The bot reproduced only the last step and therefore kept hitting a timeout: the server is
a Steam server, and the authorization token is issued by the session layer. A direct travel
departs with the request carrying no valid token, and the server never completes
the handshake.

## Chain (class `UUI_ListSessions`)

| Function | Address | Role |
|---|---|---|
| `SlotButtonSelected` | `141560d70` | only enables the Join button |
| `JoinSelectedSession` | `14154fcf0` | takes the selected list entry, `local_1a8._40_8_ = &JoiningSessionOwnerName` |
| `DoJoinSession` | `141551220` | **the JoinSession call** |
| `QueueJoinSession` | `14154dda0` | join queue |
| `JoinFromQueue` | `14154f5f0` | leaving the queue |
| `RetryJoin` | `14154bc60` | retry |
| `OnJoinSessionComplete` | `14154c9a0` | result; `SaveJoiningSessionName`, FName `SESSIONNAME` |
| `OnJoinTimedOut` | `14154c0b0` | timeout |

### `DoJoinSession` — entry point

```cpp
UWorld*  w   = <widget world>;
UGameInstance* gi = Cast<UShooterGameInstance>(w->GetGameInstance());
AShooterGameSession* gs = <gi->GetGameSession()>();
ULocalPlayer* lp  = gi->GetFirstGamePlayer();
TSharedPtr<FUniqueNetId> pid;
lp->GetPreferredUniqueNetId(pid);

// session name = owner; for a Steam server this is the SteamID64 string.
// when JoiningSessionOwnerName is empty, the string 0x14473fcc8 is substituted,
// which in the binary turns out to be a path from the PDB - i.e. garbage;
// the proper name always comes from the list entry.
FName name(this->JoiningSessionOwnerName);

gs->JoinSession(pid, name, &this->JoiningSessionSearchResult);
```

## Requirements for `JoinSession` (ARK SDK, GameState.h:344)

```cpp
bool JoinSession(TSharedPtr<FUniqueNetId,0> UserId, FName SessionName,
                 FOnlineSessionSearchResult* SearchResult);
bool JoinSession(TSharedPtr<FUniqueNetId,0> UserId, FName SessionName,
                 int SessionIndexInSearchResults);
bool TravelToSession(int ControllerId, FName SessionName);
```

The implementation (`14102b160`) requires:
* `IOnlineSubsystem::Get()` — non-null;
* the session interface (vtable `+0x198`) — non-null;
* `UserId->Object != nullptr` — a valid local player `FUniqueNetId`.

## The step after the join

`AGameSession::TravelToSession` (`142acfe60`):

1. `IOnlineSubsystem::Get()`
2. `FindSession(SessionName, &HostAddress)` — vtable `+800`
3. `APlayerController::ClientTravelInternal(HostAddress)`

The URL is taken from the session's own `HostAddress`, not from the string the player typed.

## What the bot already matches

The `ctx` command after manual join showed a FURL that the bot now builds
field by field:

```
proto=unreal host=192.168.8.218 port=7777 valid=1
map=/Game/Maps/TheIslandSubMaps/TheIsland
Op[0]=ModId=0
Op[1]=game=/Game/PrimalEarth/CoreBlueprints/TestGameMode.TestGameMode_C
```

The engine accepts such a URL (`valid=1`), but the handshake never completes —
because the session layer is missing.

## What is missing for full automation

| What | Status in the ArkApi SDK |
|---|---|
| `UShooterGameInstance::GetGameSession()` | **present** (GameMode.h:387) |
| `AShooterGameSession::JoinSession(...)` | **present** (GameState.h) |
| a valid player `TSharedPtr<FUniqueNetId>` | **absent** — `GetPreferredUniqueNetId` is not declared |
| `FOnlineSessionSearchResult` | **absent** — declared only as an empty forward-decl |
| `IOnlineSubsystem` | **empty struct** (Base.h:184), methods only via the vtable |
| `IOnlineSubsystem::GetSessionInterface` (vtable +0x198) | not declared, but known from the disassembler |

## Implementation options

1. **Via the UI class.** Find/create `UUI_ListSessions`, fill in
   `EntryWidgets`/`SearchSettings`, call `JoinSelectedSession()`. Requires none of the
   missing types, but needs an entry point to the widget and list population.
2. **Via the session layer directly.** Take `IOnlineSubsystem` from
   `AShooterPlayerController::OnlineSubField()` (Actor.h:2405), invoke
   the sessions vtable method, and implement `IOnlineSession::JoinSession` by hand.
   Requires knowing the layout of `FOnlineSessionSearchResult` and `FUniqueNetIdUInt64`.
3. **Assemble `FOnlineSessionSearchResult` manually** and call the first
   `JoinSession`: take the struct layout from the PDB (the struct is present in the binary),
   `FUniqueNetIdUInt64` is described in UE.h:272. The most direct path, but requires
   careful reconstruction.

Any of these options requires RE work; only the analysis has been done so far.
