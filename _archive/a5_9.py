for n,v,s in [("UObject::ProcessInternal",33292912,344),("UObject::ProcessContextOpcode",33300384,184),("UFunction::Invoke",33056704,792),("UObject::CallFunction",33292016,889),("UObject::execLocalVariable",0x1FC1070,53),("UObject::CallFunctionByNameWithArguments",33293264,2401)]:
    print("%-40s RVA=0x%08X  size=%d  end=0x%08X" % (n,v,s,v+s))
print("image base 0x140000000 -> ProcessInternal VA = 0x%X" % (0x140000000+33292912))
