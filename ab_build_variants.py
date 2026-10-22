"""Build both Mimalloc variants (counters on / off) without touching the repo state.

* adds MIMALLOC_COUNTERS=1 to the Release config, builds, keeps the artifact
* restores the project file, rebuilds the default (counters off) artifact
"""
import os
import shutil
import subprocess
import sys

PROJ = r"C:\Dev\ARK-Server-Plugins\EngineSwap\Mimalloc\Mimalloc.vcxproj"
OUT = r"C:\Dev\_research\ab"
MSBUILD = r"C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe"
REL = "NDEBUG;_WINDOWS;_USRDLL;ARK_GAME;%(PreprocessorDefinitions)"
REL_ON = "NDEBUG;_WINDOWS;_USRDLL;ARK_GAME;MIMALLOC_COUNTERS=1;%(PreprocessorDefinitions)"

os.makedirs(OUT, exist_ok=True)
backup = PROJ + ".bak_ab"
shutil.copyfile(PROJ, backup)


def build():
    r = subprocess.run([MSBUILD, PROJ, "/p:Configuration=Release", "/p:Platform=x64", "/m", "/v:m", "/nologo"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:])
        raise SystemExit("build failed")
    print("build ok")


try:
    src = open(PROJ, encoding="utf-8-sig").read()
    if REL not in src:
        raise SystemExit("release defines not found")
    open(PROJ, "w", encoding="utf-8").write(src.replace(REL, REL_ON))
    build()
    shutil.copyfile(r"C:\Dev\ARK-Server-Plugins\EngineSwap\Mimalloc\build\Release\Mimalloc.dll",
                    os.path.join(OUT, "Mimalloc-counters.dll"))
    print("saved Mimalloc-counters.dll")
finally:
    shutil.copyfile(backup, PROJ)
    os.remove(backup)

build()
shutil.copyfile(r"C:\Dev\ARK-Server-Plugins\EngineSwap\Mimalloc\build\Release\Mimalloc.dll",
                os.path.join(OUT, "Mimalloc-nocounters.dll"))
print("saved Mimalloc-nocounters.dll")
print("project file restored:", open(PROJ, encoding="utf-8-sig").read().count("MIMALLOC_COUNTERS") == 0)
