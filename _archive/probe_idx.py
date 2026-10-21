import io, json, itertools
idx = json.load(io.open("dump_index.json", encoding="utf-8"))
src = r"C:\Dev\ARK_SE_code_dump\game_aquatica.c"
keys = [k for k in idx if "NPCZoneManager" in k]
print("NPCZoneManager:", len(keys))
for k in sorted(keys)[:14]:
    print("   %-70s line %s" % (k[:70], idx[k]))
print()
keys2 = [k for k in idx if k.startswith("UVictoryCore::")]
print("UVictoryCore::", len(keys2))
for k in sorted(keys2)[:14]:
    print("   %-70s" % k[:70])
print()
for probe in ("APrimalDinoCharacter::Tick","APrimalCharacter::Tick","UPrimalCharacterStatusComponent::Tick"):
    print(probe, "->", idx.get(probe))
