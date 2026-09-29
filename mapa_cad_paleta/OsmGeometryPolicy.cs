using System;
using System.Collections.Generic;
using System.Text.Json;

namespace MapaCadPaleta
{
    internal readonly struct OsmCoordinate
    {
        internal OsmCoordinate(double x, double y)
        {
            X = x;
            Y = y;
        }

        internal double X { get; }
        internal double Y { get; }
    }

    internal static class OsmGeometryPolicy
    {
        internal static bool ShouldClose(string? type, bool fallback)
        {
            if (string.Equals(type, "EDIFICACAO", StringComparison.Ordinal))
                return true;
            if (string.Equals(type, "BARREIRA", StringComparison.Ordinal))
                return false;
            return fallback;
        }

        internal static bool TryReadCoordinates(JsonElement points, out List<OsmCoordinate> coordinates)
        {
            coordinates = new List<OsmCoordinate>();
            if (points.ValueKind != JsonValueKind.Array || points.GetArrayLength() < 2)
                return false;

            foreach (JsonElement point in points.EnumerateArray())
            {
                if (point.ValueKind != JsonValueKind.Array || point.GetArrayLength() != 2
                    || point[0].ValueKind != JsonValueKind.Number
                    || point[1].ValueKind != JsonValueKind.Number
                    || !point[0].TryGetDouble(out double x)
                    || !point[1].TryGetDouble(out double y)
                    || double.IsNaN(x) || double.IsInfinity(x)
                    || double.IsNaN(y) || double.IsInfinity(y))
                {
                    coordinates.Clear();
                    return false;
                }

                coordinates.Add(new OsmCoordinate(x, y));
            }

            return true;
        }
    }
}
