using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;

namespace MapaCadPaleta
{
    public static class DwgProjectScopeStore
    {
        public static bool TryReconcile(
            Document document,
            Database database,
            string dwgFilename,
            out ProjectScope reconciledScope)
        {
            if (document == null)
                throw new ArgumentNullException(nameof(document));
            if (database == null)
                throw new ArgumentNullException(nameof(database));

            reconciledScope = ProjectScopeContract.ReconcileCompletedManifest(dwgFilename);
            if (!reconciledScope.IsBound)
                return false;

            try
            {
                using (document.LockDocument())
                {
                    Write(database, reconciledScope.SobId!);
                }

                TryControlledSave(database, dwgFilename);
                return true;
            }
            catch (Exception ex)
            {
                reconciledScope = ProjectScopeContract.Invalid($"RECONCILIATION_WRITE_FAILED: {ex.Message}");
                return false;
            }
        }

        private static void TryControlledSave(Database database, string dwgFilename)
        {
            try
            {
                database.SaveAs(dwgFilename, DwgVersion.Current);
            }
            catch
            {
                // Fallback seguro: se o arquivo já estiver bloqueado pelo editor do AutoCAD,
                // o XRecord permanece ativo na memória da Database e será persistido no próximo save.
            }
        }
        public static void Write(Database database, string sobId)
        {
            if (database == null)
                throw new ArgumentNullException(nameof(database));

            ProjectScope existingScope = Read(database);
            string normalizedSobId = ProjectScopeContract.ValidateWrite(existingScope, sobId);
            if (existingScope.IsBound)
                return;

            IReadOnlyList<KeyValuePair<string, string>> fields = ProjectScopeContract.Encode(normalizedSobId);
            var values = new TypedValue[1 + fields.Count * 2];
            values[0] = new TypedValue((int)DxfCode.Int32, ProjectScopeContract.MetadataVersion);

            int index = 1;
            foreach (KeyValuePair<string, string> field in fields)
            {
                values[index++] = new TypedValue((int)DxfCode.Text, field.Key);
                values[index++] = new TypedValue((int)DxfCode.Text, field.Value);
            }

            using (Transaction transaction = database.TransactionManager.StartTransaction())
            {
                var dictionary = (DBDictionary)transaction.GetObject(
                    database.NamedObjectsDictionaryId,
                    OpenMode.ForWrite);

                if (dictionary.Contains(ProjectScopeContract.MetadataKey))
                    throw new InvalidOperationException("ProjectScope metadata foi criada concorrentemente; vínculo não sobrescrito.");
                else
                {
                    var record = new Xrecord
                    {
                        Data = new ResultBuffer(values)
                    };
                    dictionary.SetAt(ProjectScopeContract.MetadataKey, record);
                    transaction.AddNewlyCreatedDBObject(record, true);
                }

                transaction.Commit();
            }
        }

        public static ProjectScope Read(Database database)
        {
            if (database == null)
                throw new ArgumentNullException(nameof(database));

            using (Transaction transaction = database.TransactionManager.StartTransaction())
            {
                var dictionary = (DBDictionary)transaction.GetObject(
                    database.NamedObjectsDictionaryId,
                    OpenMode.ForRead);

                if (!dictionary.Contains(ProjectScopeContract.MetadataKey))
                {
                    transaction.Commit();
                    return ProjectScopeContract.Unbound();
                }

                DBObject storedObject = transaction.GetObject(
                    dictionary.GetAt(ProjectScopeContract.MetadataKey),
                    OpenMode.ForRead);

                if (storedObject is not Xrecord record)
                {
                    transaction.Commit();
                    return ProjectScopeContract.Invalid("METADATA_IS_NOT_XRECORD");
                }

                using (ResultBuffer? data = record.Data)
                {
                    if (data == null)
                    {
                        transaction.Commit();
                        return ProjectScopeContract.Invalid("EMPTY_XRECORD");
                    }

                    TypedValue[] values = data.AsArray();
                    if (values.Length < 1 ||
                        values[0].TypeCode != (int)DxfCode.Int32 ||
                        values[0].Value is not int version)
                    {
                        transaction.Commit();
                        return ProjectScopeContract.Invalid("INVALID_METADATA_HEADER");
                    }

                    if ((values.Length - 1) % 2 != 0)
                    {
                        transaction.Commit();
                        return ProjectScopeContract.Invalid("INVALID_METADATA_FIELDS");
                    }

                    var fields = new List<KeyValuePair<string, string>>();
                    for (int index = 1; index < values.Length; index += 2)
                    {
                        if (values[index].TypeCode != (int)DxfCode.Text ||
                            values[index + 1].TypeCode != (int)DxfCode.Text ||
                            values[index].Value is not string key ||
                            values[index + 1].Value is not string value)
                        {
                            transaction.Commit();
                            return ProjectScopeContract.Invalid("INVALID_METADATA_FIELDS");
                        }

                        fields.Add(new KeyValuePair<string, string>(key, value));
                    }

                    ProjectScope scope = ProjectScopeContract.Resolve(version, fields);
                    transaction.Commit();
                    return scope;
                }
            }
        }
    }
}
