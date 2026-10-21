import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
add = '''
	// ------------------------------------------------- патч зажима тикрейта
	// UGameEngine::GetMaxTickRate (RVA 0x253B1C0) зажимает NetServerMaxTickRate
	// в диапазон [10, 0x78=120]: "MOV ECX,0x78 / CMP EDX,ECX / CMOVL ECX,EDX".
	// Байты по RVA 0x253B26E: B9 78 00 00 00 (MOV ECX, imm32).
	// Меняем верхнюю границу 120 на 100000: RVA 0x253B26F, четыре байта.
	constexpr uint32_t CLAMP_RVA = 0x253B26F;
	const uint8_t CLAMP_OLD[4] = {0x78, 0x00, 0x00, 0x00};
	const uint8_t CLAMP_NEW[4] = {0xA0, 0x86, 0x01, 0x00}; // 100000

	bool PatchTickClamp(bool raise)
	{
		auto* base = reinterpret_cast<uint8_t*>(GetModuleHandle(nullptr));
		auto* target = base + CLAMP_RVA;
		if (target[-1] != 0xB9 || std::memcmp(target, CLAMP_OLD, 4) != 0)
		{
			// уже пропатчено?
			if (target[-1] == 0xB9 && std::memcmp(target, CLAMP_NEW, 4) == 0)
			{
				LogLine(S("tickclamp: уже поднят до 100000"));
				if (!raise)
					return true;
			}
			else
			{
				LogLine(S("tickclamp: неожиданные байты, патч отменён"));
				return false;
			}
		}
		DWORD old_prot = 0;
		if (!VirtualProtect(target, 4, PAGE_EXECUTE_READWRITE, &old_prot))
			return false;
		std::memcpy(target, raise ? CLAMP_NEW : CLAMP_OLD, 4);
		FlushInstructionCache(GetCurrentProcess(), target, 4);
		DWORD restore = 0;
		VirtualProtect(target, 4, old_prot, &restore);
		LogLine(S("tickclamp: верхняя граница {} -> {}", raise ? 120 : 100000,
			raise ? 100000 : 120));
		return true;
	}

	void CmdFixClamp(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		PatchTickClamp(ArgInt(packet, 0) != 0);
	}

	// ------------------------------------------------- census overlap-событий'''
s = s.replace("	// ------------------------------------------------- census overlap-событий", add, 1)
s = s.replace('\tcmds.AddRconCommand("TickProf.fix", CmdFix);',
 '\tcmds.AddRconCommand("TickProf.fix", CmdFix);\n\tcmds.AddRconCommand("TickProf.fixclamp", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdFixClamp(c, p, w); });')
s = s.replace('"TickProf.fix", "TickProf.verify", "TickProf.ticklist",',
              '"TickProf.fix", "TickProf.fixclamp", "TickProf.verify", "TickProf.ticklist",')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")
