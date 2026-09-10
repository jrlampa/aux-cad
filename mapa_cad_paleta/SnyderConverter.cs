using System;

namespace MapaCadPaleta
{
    /// <summary>
    /// Conversor geodésico analítico Snyder para projeção UTM (SIRGAS 2000 / WGS84).
    /// Rigorosamente equivalente aos módulos Python e AutoLISP do ecossistema aux cad.
    /// </summary>
    public static class SnyderConverter
    {
        // Elipsoide GRS80 / WGS84
        private const double A = 6378137.0;             // Semi-eixo maior
        private const double F = 1.0 / 298.257223563;   // Achatamento
        private const double K0 = 0.9996;               // Fator de escala central
        private const double FALSE_EASTING = 500000.0;  // Falso Este
        private const double FALSE_NORTHING_S = 10000000.0; // Falso Norte (Hemisfério Sul)

        /// <summary>
        /// Converte coordenadas geográficas (Lat/Lon WGS84 em graus decimais) para UTM métrico (SIRGAS 2000).
        /// </summary>
        public static (double Easting, double Northing, int Zone, char Hemisphere) LatLonToUtm(double lat, double lon, int? forcedZone = null)
        {
            int zone = forcedZone ?? (int)Math.Floor((lon + 180.0) / 6.0) + 1;
            char hemisphere = lat < 0 ? 'S' : 'N';

            double latRad = lat * Math.PI / 180.0;
            double lonRad = lon * Math.PI / 180.0;
            double lon0Rad = ((zone - 1) * 6 - 180 + 3) * Math.PI / 180.0;

            double b = A * (1.0 - F);
            double e2 = (A * A - b * b) / (A * A);
            double ep2 = (A * A - b * b) / (b * b);

            double sinLat = Math.Sin(latRad);
            double cosLat = Math.Cos(latRad);
            double tanLat = Math.Tan(latRad);

            double n = A / Math.Sqrt(1.0 - e2 * sinLat * sinLat);
            double t = tanLat * tanLat;
            double c = ep2 * cosLat * cosLat;
            double p = (lonRad - lon0Rad);

            // Meridional arc
            double m = A * ((1.0 - e2 / 4.0 - 3.0 * e2 * e2 / 64.0 - 5.0 * Math.Pow(e2, 3) / 256.0) * latRad
                - (3.0 * e2 / 8.0 + 3.0 * e2 * e2 / 32.0 + 45.0 * Math.Pow(e2, 3) / 1024.0) * Math.Sin(2.0 * latRad)
                + (15.0 * e2 * e2 / 256.0 + 45.0 * Math.Pow(e2, 3) / 1024.0) * Math.Sin(4.0 * latRad)
                - (35.0 * Math.Pow(e2, 3) / 3072.0) * Math.Sin(6.0 * latRad));

            double easting = FALSE_EASTING + K0 * n * (p * cosLat
                + Math.Pow(p, 3) * Math.Pow(cosLat, 3) / 6.0 * (1.0 - t + c)
                + Math.Pow(p, 5) * Math.Pow(cosLat, 5) / 120.0 * (5.0 - 18.0 * t + t * t + 72.0 * c - 58.0 * ep2));

            double northing = K0 * (m + n * tanLat * (p * p * cosLat * cosLat / 2.0
                + Math.Pow(p, 4) * Math.Pow(cosLat, 4) / 24.0 * (5.0 - t + 9.0 * c + 4.0 * c * c)
                + Math.Pow(p, 6) * Math.Pow(cosLat, 6) / 720.0 * (61.0 - 58.0 * t + t * t + 600.0 * c - 330.0 * ep2)));

            if (hemisphere == 'S')
            {
                northing += FALSE_NORTHING_S;
            }

            return (Math.Round(easting, 3), Math.Round(northing, 3), zone, hemisphere);
        }

        /// <summary>
        /// Converte coordenadas UTM (SIRGAS 2000 / WGS84) para coordenadas geográficas (Lat/Lon).
        /// </summary>
        public static (double Lat, double Lon) UtmToLatLon(double easting, double northing, int zone = 23, char hemisphere = 'S')
        {
            double lon0Rad = ((zone - 1) * 6 - 180 + 3) * Math.PI / 180.0;
            double b = A * (1.0 - F);
            double e2 = (A * A - b * b) / (A * A);
            double ep2 = (A * A - b * b) / (b * b);
            double e1 = (1.0 - Math.Sqrt(1.0 - e2)) / (1.0 + Math.Sqrt(1.0 - e2));

            double x = easting - FALSE_EASTING;
            double y = hemisphere == 'S' ? northing - FALSE_NORTHING_S : northing;

            double m = y / K0;
            double mu = m / (A * (1.0 - e2 / 4.0 - 3.0 * e2 * e2 / 64.0 - 5.0 * Math.Pow(e2, 3) / 256.0));

            double phi1 = mu
                + (3.0 * e1 / 2.0 - 27.0 * Math.Pow(e1, 3) / 32.0) * Math.Sin(2.0 * mu)
                + (21.0 * e1 * e1 / 16.0 - 55.0 * Math.Pow(e1, 4) / 32.0) * Math.Sin(4.0 * mu)
                + (151.0 * Math.Pow(e1, 3) / 96.0) * Math.Sin(6.0 * mu)
                + (1097.0 * Math.Pow(e1, 4) / 512.0) * Math.Sin(8.0 * mu);

            double sinPhi1 = Math.Sin(phi1);
            double cosPhi1 = Math.Cos(phi1);
            double tanPhi1 = Math.Tan(phi1);

            double n1 = A / Math.Sqrt(1.0 - e2 * sinPhi1 * sinPhi1);
            double t1 = tanPhi1 * tanPhi1;
            double c1 = ep2 * cosPhi1 * cosPhi1;
            double r1 = A * (1.0 - e2) / Math.Pow(1.0 - e2 * sinPhi1 * sinPhi1, 1.5);
            double d = x / (n1 * K0);

            double latRad = phi1 - (n1 * tanPhi1 / r1) * (d * d / 2.0
                - (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1 * c1 - 9.0 * ep2) * Math.Pow(d, 4) / 24.0
                + (61.0 + 90.0 * t1 + 298.0 * c1 + 45.0 * t1 * t1 - 252.0 * ep2 - 3.0 * c1 * c1) * Math.Pow(d, 6) / 720.0);

            double lonRad = lon0Rad + (d
                - (1.0 + 2.0 * t1 + c1) * Math.Pow(d, 3) / 6.0
                + (5.0 - 2.0 * c1 + 28.0 * t1 - 3.0 * c1 * c1 + 8.0 * ep2 + 24.0 * t1 * t1) * Math.Pow(d, 5) / 120.0) / cosPhi1;

            double lat = latRad * 180.0 / Math.PI;
            double lon = lonRad * 180.0 / Math.PI;

            return (Math.Round(lat, 7), Math.Round(lon, 7));
        }
    }
}
