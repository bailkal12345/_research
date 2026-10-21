# -*- coding: utf-8 -*-
# Слот C (doit6 §3): правка белого списка overlaptrim3 по A2 (ARCH.md §3.1).
# - добавить ABaseBoxTrigger, AHazardTrigger_Slide, APrimalStructureBearTrap,
#   APrimalStructureTurret, APrimalStructureTurretBallista,
#   APrimalProjectileGrapplingHook, APrimalDinoCharacter;
# - заменить широкие подстроки Trigger/Turret/GrapplingHook полными именами классов.
import io, re, sys

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
KEEP_TXT = r'C:\Dev\ARK-Server-Plugins\TickProf\Configs\tickprof_overlap_keep.txt'

NEW_DEFAULT = '''\t// ВАЖНО (правка по A2): подстроки "Trigger"/"Turret"/"GrapplingHook" слишком широки
\t// и задевали чужие классы, поэтому используются ТОЛЬКО полные имена классов из A2.
\t// Порядок: более специфичные раньше.
\tconst char* DEFAULT_KEEP[] = {
\t\t"ShapeComponent", "SphereComponent", "BoxComponent", "CapsuleComponent",
\t\t"ABaseBoxTrigger",
\t\t"AHazardTrigger_Slide",
\t\t"APrimalStructureBearTrap",
\t\t"APrimalStructureTurretBallista",
\t\t"APrimalStructureTurret",
\t\t"APrimalProjectileGrapplingHook",
\t\t"APrimalDinoCharacter",
\t};'''

KEEP_FILE = '''# Белый список классов для TickProf.overlaptrim3 / overlapcache / turrettick.
# По одному ПОЛНОМУ имени класса в строке; "#" - комментарий.
# Правка по A2 (ARCH.md §3.1): широкие подстроки Trigger/Turret/GrapplingHook
# заменены на полные имена классов.
ShapeComponent
SphereComponent
BoxComponent
CapsuleComponent
ABaseBoxTrigger
AHazardTrigger_Slide
APrimalStructureBearTrap
APrimalStructureTurretBallista
APrimalStructureTurret
APrimalProjectileGrapplingHook
APrimalDinoCharacter
'''

src = io.open(CPP, 'r', encoding='utf-8', newline='').read()

pat = re.compile(r'\tconst char\* DEFAULT_KEEP\[\] = \{.*?\};', re.S)
m = pat.search(src)
if not m:
    print('!! шаблон DEFAULT_KEEP не найден')
    sys.exit(1)
old = m.group(0)
if old == NEW_DEFAULT:
    print('уже применено')
else:
    src = src[:m.start()] + NEW_DEFAULT + src[m.end():]
    io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
    print('DEFAULT_KEEP обновлён')
    print('--- было ---')
    print(old)
    print('--- стало ---')
    print(NEW_DEFAULT)

io.open(KEEP_TXT, 'w', encoding='utf-8', newline='\r\n').write(KEEP_FILE)
print('\nзаписан белый список:', KEEP_TXT)
for ln in KEEP_FILE.strip().splitlines():
    print('   ', ln)
