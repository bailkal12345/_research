import sqlite3
c = sqlite3.connect(r'C:\Dev\_research\v361.sqlite')
names = ['AShooterGameMode::Tick','UPaintingCache::SaveCache','UObjectSerializer::SerializeObject',
 'UObjectSerializer::DeSerializeObject','AActor::GetIsMapActor','AActor::AllowSaving','APrimalCharacter::AllowSaving',
 'AActor::PreSave','UStruct::SerializeScriptProperties','UStruct::SerializeTaggedProperties','UObject::Serialize',
 'UProperty::ShouldSerializeValue','TMemoryWriter<32>::Serialize','FObjectWriter::operator<<',
 'WorldSerializedObject::WorldSerializedObject','WorldSerializedObject::SetObject','WorldSerializedObject::SerializeHeaders',
 'ShouldSerializeTransform','ParseCommandline','UWorld::PreSaveRoot','AActor::AllowSaving',
 'UPackage::SetDirtyFlag','UPackage::TagSubobjects','AShooterGameMode::GetSaveDirectoryName',
 'UPaintingTexture::SaveToFile','FArchiveFileWriterGeneric::Serialize','FFileManagerGeneric::CreateFileWriter']
for n in names:
    r = c.execute("select rva,size from fn where name=? limit 1",(n,)).fetchone()
    print("%-46s %s" % (n, ("%08X  %d"%(r[0],r[1])) if r else "<none>"))
