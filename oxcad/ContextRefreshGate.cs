using System;

namespace OxCad
{
    public sealed class ContextRefreshTicket
    {
        internal ContextRefreshTicket(
            long generation,
            object document,
            object database,
            string? databaseIdentity = null)
        {
            Generation = generation;
            Document = document;
            Database = database;
            DatabaseIdentity = databaseIdentity;
        }

        public long Generation { get; }
        public string? DatabaseIdentity { get; }
        internal object Document { get; }
        internal object Database { get; }
    }

    public sealed class ContextRefreshGate
    {
        private readonly object _sync = new object();
        private long _generation;
        private object? _document;
        private object? _database;
        private string? _databaseIdentity;

        public long CurrentGeneration
        {
            get
            {
                lock (_sync)
                    return _generation;
            }
        }

        public ContextRefreshTicket Begin(
            object document,
            object database,
            string? databaseIdentity = null)
        {
            if (document == null)
                throw new ArgumentNullException(nameof(document));
            if (database == null)
                throw new ArgumentNullException(nameof(database));

            lock (_sync)
            {
                _generation++;
                _document = document;
                _database = database;
                _databaseIdentity = databaseIdentity;
                return new ContextRefreshTicket(_generation, document, database, databaseIdentity);
            }
        }

        public long Invalidate()
        {
            lock (_sync)
            {
                _generation++;
                _document = null;
                _database = null;
                _databaseIdentity = null;
                return _generation;
            }
        }

        public bool IsCurrent(
            ContextRefreshTicket ticket,
            object? activeDocument,
            object? activeDatabase,
            string? activeDatabaseIdentity = null)
        {
            if (ticket == null || activeDocument == null || activeDatabase == null)
                return false;

            lock (_sync)
            {
                if (ticket.Generation != _generation)
                    return false;

                if (!ReferenceEquals(ticket.Document, _document) ||
                    !ReferenceEquals(ticket.Document, activeDocument))
                    return false;

                if (!string.IsNullOrEmpty(ticket.DatabaseIdentity) && !string.IsNullOrEmpty(activeDatabaseIdentity))
                {
                    return string.Equals(ticket.DatabaseIdentity, _databaseIdentity, StringComparison.OrdinalIgnoreCase) &&
                           string.Equals(ticket.DatabaseIdentity, activeDatabaseIdentity, StringComparison.OrdinalIgnoreCase);
                }

                return (ReferenceEquals(ticket.Database, _database) || Equals(ticket.Database, _database)) &&
                       (ReferenceEquals(ticket.Database, activeDatabase) || Equals(ticket.Database, activeDatabase));
            }
        }

        public bool IsCurrentDocument(object? document)
        {
            lock (_sync)
            {
                return document != null && ReferenceEquals(document, _document);
            }
        }

        public bool IsCurrentGeneration(long generation)
        {
            lock (_sync)
            {
                return generation == _generation;
            }
        }
    }
}