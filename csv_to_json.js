const fs = require('fs');

const csvData = fs.readFileSync('Laptop Benchmark - Laptop Benchmark(5).csv', 'utf8');
const lines = csvData.split(/\r?\n/).map(l => l.trim()).filter(l => l);

const dataLines = lines.slice(3);
const results = [];
let currentBrand = '';
let currentSeries = '';

dataLines.forEach(line => {
  const parts = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      parts.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  parts.push(current);

  if (parts.length < 4) return;

  const brand = parts[0] ? parts[0].trim() : currentBrand;
  const series = parts[1] ? parts[1].trim() : currentSeries;
  const model = parts[2] ? parts[2].trim() : '';
  
  if (!model) return;

  currentBrand = brand;
  currentSeries = series;

  const parseNum = v => {
    if (v == null || v === '' || v === '-') return null;
    const n = v.replace(/,/g, '').trim();
    return isNaN(n) ? null : parseFloat(n);
  };

  results.push({
    brand,
    series,
    model,
    spec: parts[3] ? parts[3].trim() : '',
    year: parseNum(parts[4]),
    timeSpy: parseNum(parts[5]),
    tsGfx: parseNum(parts[6]),
    tsExtreme: parseNum(parts[7]),
    tsExtremeGfx: parseNum(parts[8]),
    fsExt: parseNum(parts[9]),
    fsExtGfx: parseNum(parts[10]),
    fsExtPhys: parseNum(parts[11]),
    fsUltra: parseNum(parts[12]),
    fsUltraGfx: parseNum(parts[13]),
    fsUltraPhys: parseNum(parts[14]),
    steelNomad: parseNum(parts[15]),
    cbR23S: parseNum(parts[17]),
    cbR23M: parseNum(parts[18]),
    cbR24S: parseNum(parts[19]),
    cbR24M: parseNum(parts[20]),
    battery: parseNum(parts[22]),
    standby: parseNum(parts[23]),
    pcmark: parseNum(parts[25]),
    pcEss: parseNum(parts[26]),
    pcProd: parseNum(parts[27]),
    pcCC: parseNum(parts[28]),
    pcGaming: parseNum(parts[29]),
    cpuIdle: parseNum(parts[31]),
    cpuLoad: parseNum(parts[32]),
    gpuIdle: parseNum(parts[33]),
    gpuLoad: parseNum(parts[34]),
  });
});

console.log(JSON.stringify(results, null, 2));
