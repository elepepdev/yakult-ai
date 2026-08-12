// Ensures the electron binary is installed even when extract-zip fails
// on newer Node versions (it silently stops after 'locales').
const { execSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const electronDir = path.join(__dirname, '..', 'node_modules', 'electron');
const dist = path.join(electronDir, 'dist');

// Some Node versions make electron's install.js write path.txt with a
// trailing newline, which breaks `require('electron')` (spawn ENOENT).
// Always clean it, even when the binary already exists.
const pathTxt = path.join(electronDir, 'path.txt');
try {
  if (fs.existsSync(pathTxt)) {
    const cleaned = fs.readFileSync(pathTxt, 'utf8').trim();
    fs.writeFileSync(pathTxt, cleaned);
    console.log(`electron-binary-fix: path.txt cleaned ('${cleaned}')`);
  }
} catch (e) {
  console.error('electron-binary-fix: could not clean path.txt:', e.message);
}

try {
  const pkg = require(path.join(electronDir, 'package.json'));
  const binary = process.platform === 'win32' ? 'electron.exe' : 'electron';
  if (fs.existsSync(path.join(dist, binary))) {
    process.exit(0);
  }
  const cacheRoot = path.join(
    os.homedir(),
    '.cache',
    'electron',
  );
  const dirs = fs.readdirSync(cacheRoot);
  const zip = dirs
    .map((d) => path.join(cacheRoot, d))
    .map((d) => {
      try {
        return fs.readdirSync(d).map((f) => path.join(d, f));
      } catch {
        return [];
      }
    })
    .flat()
    .find((f) => f.endsWith(`electron-v${pkg.version}-${process.platform}-${process.arch}.zip`));
  if (!zip) {
    console.error(`electron-binary-fix: cached zip not found for v${pkg.version}`);
    process.exit(1);
  }
  fs.rmSync(dist, { recursive: true, force: true });
  fs.mkdirSync(dist, { recursive: true });
  execSync(`unzip -o -q "${zip}" -d "${dist}"`, { stdio: 'inherit' });
  fs.writeFileSync(path.join(electronDir, 'path.txt'), binary);
  console.log(`electron-binary-fix: extracted v${pkg.version} via unzip`);
} catch (e) {
  console.error('electron-binary-fix:', e.message);
  process.exit(1);
}
