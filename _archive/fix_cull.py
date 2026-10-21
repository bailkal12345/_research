import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

# AActor::GetActorLocation в PDB отсутствует (инлайнится) — читаем позицию
# напрямую: AActor::RootComponent @592 -> USceneComponent::ComponentToWorld @224,
# FTransform: кватернион 0..15, трансляция 16..27.
s = s.replace('''	// Радиус берётся от позиций игроков, список обновляется раз в 30 тиков.''',
'''	// Радиус берётся от позиций игроков, список обновляется раз в 30 тиков.
	// Позиция актора читается напрямую: AActor::GetActorLocation в PDB нет
	// (инлайнится движком), поэтому RootComponent @592 -> ComponentToWorld @224,
	// в FTransform трансляция лежит со смещением 16.''')
s = s.replace('''	constexpr int NETDRIVER_MAXTICKRATE = 72;''',
              '''	constexpr int NETDRIVER_MAXTICKRATE = 72;''')
s = s.replace('''	float g_player_xy[16][2];
	int g_player_count = 0;''',
'''	float g_player_xy[16][2];
	int g_player_count = 0;

	// позиция актора из корневого компонента, без вызова движка
	inline void ActorXY(const void* actor, float& x, float& y)
	{
		const auto* root = *reinterpret_cast<void* const*>(
			reinterpret_cast<const char*>(actor) + 592); // AActor::RootComponent
		if (!root)
		{
			x = 0.0f;
			y = 0.0f;
			return;
		}
		// USceneComponent::ComponentToWorld @224, FTransform::Translation @+16
		const auto* t = reinterpret_cast<const float*>(reinterpret_cast<const char*>(root) + 240);
		x = t[0];
		y = t[1];
	}''')
s = s.replace('''			FVector loc = NativeCall<FVector>(pawn, "AActor.GetActorLocation");
			g_player_xy[g_player_count][0] = loc.X;
			g_player_xy[g_player_count][1] = loc.Y;''',
'''			ActorXY(pawn, g_player_xy[g_player_count][0], g_player_xy[g_player_count][1]);''')
s = s.replace('''		FVector loc = NativeCall<FVector>(self, "AActor.GetActorLocation");
		const float r2 = g_cull_radius.load(std::memory_order_relaxed);
		const float r2sq = r2 * r2;
		const float d2 = (loc.X - g_player_xy[0][0]) * (loc.X - g_player_xy[0][0]) +
			(loc.Y - g_player_xy[0][1]) * (loc.Y - g_player_xy[0][1]);
		if (d2 > r2sq)
		{
			for (int i = 1; i < g_player_count; ++i)
			{
				const float dx = loc.X - g_player_xy[i][0];
				const float dy = loc.Y - g_player_xy[i][1];''',
'''		float x = 0.0f, y = 0.0f;
		ActorXY(self, x, y);
		const float r2 = g_cull_radius.load(std::memory_order_relaxed);
		const float r2sq = r2 * r2;
		const float dx0 = x - g_player_xy[0][0];
		const float dy0 = y - g_player_xy[0][1];
		if (dx0 * dx0 + dy0 * dy0 > r2sq)
		{
			for (int i = 1; i < g_player_count; ++i)
			{
				const float dx = x - g_player_xy[i][0];
				const float dy = y - g_player_xy[i][1];''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")
