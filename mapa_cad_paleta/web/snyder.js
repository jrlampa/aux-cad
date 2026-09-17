/**
 * Snyder - Conversor Geodésico Analítico Snyder no Frontend (Zero Latência)
 * Projeção Transversa de Mercator (UTM SIRGAS 2000 / WGS84)
 */
const Snyder = {
    A: 6378137.0,
    F: 1.0 / 298.257223563,
    K0: 0.9996,
    FALSE_EASTING: 500000.0,
    FALSE_NORTHING_S: 10000000.0,

    latLonToUtm(lat, lon, forcedZone = 23) {
        const zone = forcedZone || Math.floor((lon + 180.0) / 6.0) + 1;
        const latRad = lat * Math.PI / 180.0;
        const lonRad = lon * Math.PI / 180.0;
        const lon0Rad = ((zone - 1) * 6 - 180 + 3) * Math.PI / 180.0;

        const b = this.A * (1.0 - this.F);
        const e2 = (this.A * this.A - b * b) / (this.A * this.A);
        const ep2 = (this.A * this.A - b * b) / (b * b);

        const sinLat = Math.sin(latRad);
        const cosLat = Math.cos(latRad);
        const tanLat = Math.tan(latRad);

        const n = this.A / Math.sqrt(1.0 - e2 * sinLat * sinLat);
        const t = tanLat * tanLat;
        const c = ep2 * cosLat * cosLat;
        const p = (lonRad - lon0Rad);

        const m = this.A * ((1.0 - e2 / 4.0 - 3.0 * e2 * e2 / 64.0 - 5.0 * Math.pow(e2, 3) / 256.0) * latRad
            - (3.0 * e2 / 8.0 + 3.0 * e2 * e2 / 32.0 + 45.0 * Math.pow(e2, 3) / 1024.0) * Math.sin(2.0 * latRad)
            + (15.0 * e2 * e2 / 256.0 + 45.0 * Math.pow(e2, 3) / 1024.0) * Math.sin(4.0 * latRad)
            - (35.0 * Math.pow(e2, 3) / 3072.0) * Math.sin(6.0 * latRad));

        const easting = this.FALSE_EASTING + this.K0 * n * (p * cosLat
            + Math.pow(p, 3) * Math.pow(cosLat, 3) / 6.0 * (1.0 - t + c)
            + Math.pow(p, 5) * Math.pow(cosLat, 5) / 120.0 * (5.0 - 18.0 * t + t * t + 72.0 * c - 58.0 * ep2));

        let northing = this.K0 * (m + n * tanLat * (p * p * cosLat * cosLat / 2.0
            + Math.pow(p, 4) * Math.pow(cosLat, 4) / 24.0 * (5.0 - t + 9.0 * c + 4.0 * c * c)
            + Math.pow(p, 6) * Math.pow(cosLat, 6) / 720.0 * (61.0 - 58.0 * t + t * t + 600.0 * c - 330.0 * ep2)));

        if (lat < 0) {
            northing += this.FALSE_NORTHING_S;
        }

        return { x: Math.round(easting * 100) / 100, y: Math.round(northing * 100) / 100, zone };
    },

    utmToLatLon(x, y, zone = 23) {
        const lon0Rad = ((zone - 1) * 6 - 180 + 3) * Math.PI / 180.0;
        const b = this.A * (1.0 - this.F);
        const e2 = (this.A * this.A - b * b) / (this.A * this.A);
        const ep2 = (this.A * this.A - b * b) / (b * b);
        const e1 = (1.0 - Math.sqrt(1.0 - e2)) / (1.0 + Math.sqrt(1.0 - e2));

        const dx = x - this.FALSE_EASTING;
        const dy = y - this.FALSE_NORTHING_S;

        const m = dy / this.K0;
        const mu = m / (this.A * (1.0 - e2 / 4.0 - 3.0 * e2 * e2 / 64.0 - 5.0 * Math.pow(e2, 3) / 256.0));

        const phi1 = mu
            + (3.0 * e1 / 2.0 - 27.0 * Math.pow(e1, 3) / 32.0) * Math.sin(2.0 * mu)
            + (21.0 * e1 * e1 / 16.0 - 55.0 * Math.pow(e1, 4) / 32.0) * Math.sin(4.0 * mu)
            + (151.0 * Math.pow(e1, 3) / 96.0) * Math.sin(6.0 * mu);

        const sinPhi1 = Math.sin(phi1);
        const cosPhi1 = Math.cos(phi1);
        const tanPhi1 = Math.tan(phi1);

        const n1 = this.A / Math.sqrt(1.0 - e2 * sinPhi1 * sinPhi1);
        const t1 = tanPhi1 * tanPhi1;
        const c1 = ep2 * cosPhi1 * cosPhi1;
        const r1 = this.A * (1.0 - e2) / Math.pow(1.0 - e2 * sinPhi1 * sinPhi1, 1.5);
        const d = dx / (n1 * this.K0);

        const latRad = phi1 - (n1 * tanPhi1 / r1) * (d * d / 2.0
            - (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1 * c1 - 9.0 * ep2) * Math.pow(d, 4) / 24.0);

        const lonRad = lon0Rad + (d
            - (1.0 + 2.0 * t1 + c1) * Math.pow(d, 3) / 6.0) / cosPhi1;

        return {
            lat: latRad * 180.0 / Math.PI,
            lon: lonRad * 180.0 / Math.PI
        };
    }
// Exportação para navegador e ambientes de módulo
if (typeof window !== 'undefined') {
    window.Snyder = Snyder;
}
if (typeof globalThis !== 'undefined') {
    globalThis.Snyder = Snyder;
}
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Snyder;
}

