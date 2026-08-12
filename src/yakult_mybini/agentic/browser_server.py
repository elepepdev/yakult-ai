"""browser-use MCP server.

Generic browser/form automation plus a macro for SIS Al Uswah Amal Yaumi.
Launches a headed Chromium (system binary) with a persistent profile so portal
login survives across runs. Tools:

  Generic
    browser_navigate, browser_snapshot, browser_fill_by_label,
    browser_select_by_label, browser_click_by_text, browser_screenshot,
    browser_close, browser_status
  Macro
    amal_yaumi_fill(mode, entries)  -> SIS Al Uswah Amal Yaumi
  Data
    browser_save_form_data, browser_load_form_data
"""

import json
import os
import sys
import time
import traceback
from typing import Annotated, Any
from pydantic import Field

_this_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_this_dir)
_grandparent_dir = os.path.dirname(_parent_dir)
for p in [_this_dir, _parent_dir, _grandparent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

if sys.platform == "linux" and "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":0"

mcp = FastMCP("browser-use")

PROJECT_ROOT = os.getcwd()
PROFILE_DIR = os.path.join(PROJECT_ROOT, "browser_data", "profile")
SCREENSHOT_DIR = os.path.join(PROJECT_ROOT, "browser_data", "screenshots")
FORM_DATA_PATH = os.path.join(PROJECT_ROOT, "browser_data", "form_data.json")
DEBUG_PORT = 9222
BASE_URL = "https://app.sisal.uswah.sch.id"

_browser = None
_context = None
_page = None
_pw = None

# ─── Playwright lifecycle ────────────────────────────────────────────────────

async def _ensure_page() -> Any:
    global _browser, _context, _page, _pw
    if _page and not _page.is_closed():
        return _page
    if _pw is None:
        import importlib
        pw_module = importlib.import_module("playwright.async_api")
        _pw = await pw_module.async_playwright().start()
    os.makedirs(PROFILE_DIR, exist_ok=True)
    # ponytail: persistent context keeps portal login; headed so the user can watch
    _context = await _pw.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        executable_path="/usr/bin/chromium",
        headless=False,
        viewport={"width": 1280, "height": 900},
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            f"--remote-debugging-port={DEBUG_PORT}",
        ],
    )
    _browser = _context.browser
    _page = _context.pages[0] if _context.pages else await _context.new_page()
    await _page.add_init_script(AY_JS)
    await _page.add_init_script(GENERIC_JS)
    return _page


async def _close_browser() -> None:
    global _browser, _context, _page, _pw
    try:
        if _context:
            await _context.close()
    except Exception:
        pass
    _browser = _context = _page = None
    if _pw:
        await _pw.stop()
        _pw = None


# ─── Ported DOM helpers from the friend's Amal Yaumi extension (content.js) ──

AY_JS = r"""
(() => {
'use strict';
const D = { S: 600, M: 1000, L: 1600, XL: 2400 };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const __ay = {};
window.__ay = __ay;

function findByText(sel, txt, root=document) {
  for (const el of root.querySelectorAll(sel))
    if (el.textContent.trim().includes(txt)) return el;
  return null;
}
const onMainPage = () => !!findByText('button,a.btn','Tambah Data');
const onFormPage = () => !!findByText('td,th,label,b,strong','Shalat Subuh');

function findLabel(txt) {
  for (const el of document.querySelectorAll('td,th,label,b,strong,span,.col-form-label')) {
    const t = el.textContent.trim();
    if (t===txt || t.startsWith(txt)) return el;
  }
  return null;
}
__ay.findLabel = findLabel;
function nearSelect(lbl) {
  if (!lbl) return null;
  let p = lbl.parentElement;
  for (let i=0;i<8;i++) {
    if (!p) break;
    const s = p.querySelector('select');
    if (s) return s;
    if (p.tagName==='TR'||p.tagName==='TBODY') break;
    p = p.parentElement;
  }
  let sib = lbl.nextElementSibling;
  for (let i=0;i<6;i++) {
    if (!sib) break;
    if (sib.tagName==='SELECT') return sib;
    const s = sib.querySelector('select');
    if (s) return s;
    sib = sib.nextElementSibling;
  }
  return null;
}
__ay.nearSelect = nearSelect;
function nearInput(lbl) {
  if (!lbl) return null;
  let p = lbl.parentElement;
  for (let i=0;i<8;i++) {
    if (!p) break;
    const inp = p.querySelector('input[type="text"],input[type="number"],input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"])');
    if (inp) return inp;
    if (p.tagName==='TR'||p.tagName==='TBODY') break;
    p = p.parentElement;
  }
  let sib = lbl.nextElementSibling;
  for (let i=0;i<6;i++) {
    if (!sib) break;
    if (sib.tagName==='INPUT') return sib;
    const inp = sib.querySelector('input');
    if (inp) return inp;
    sib = sib.nextElementSibling;
  }
  return null;
}
__ay.nearInput = nearInput;
async function setSelect(sel, value) {
  if (!sel) return false;
  const opts = Array.from(sel.options);
  let o = opts.find(o=>o.text.trim()===value||o.value===value);
  if (!o) o = opts.find(o=>o.text.trim().includes(value));
  if (!o) return false;
  sel.value = o.value;
  ['change','input'].forEach(ev => sel.dispatchEvent(new Event(ev,{bubbles:true})));
  await sleep(350);
  return true;
}
__ay.setSelect = setSelect;
async function setInput(inp, value) {
  if (!inp) return false;
  inp.focus(); inp.value=''; inp.value=String(value);
  ['input','change'].forEach(ev => inp.dispatchEvent(new Event(ev,{bubbles:true})));
  await sleep(150);
  return true;
}
__ay.setInput = setInput;
async function clickEl(el) {
  if (!el) return false;
  el.scrollIntoView({behavior:'smooth', block:'center'});
  await sleep(250);
  el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));
  await sleep(80);
  el.click();
  await sleep(D.S);
  return true;
}

function findTambahBtn() {
  for (const el of document.querySelectorAll('button,a.btn'))
    if (!el.closest('.modal') && !el.closest('[role="dialog"]') && el.textContent.includes('Tambah Data'))
      return el;
  return null;
}
function findPekanSelect() {
  for (const s of document.querySelectorAll('select')) {
    if (s.options[0]?.text.includes('Pilih Pekan')) return s;
    if (s.id?.toLowerCase().includes('pekan')) return s;
    if (Array.from(s.options).some(o=>o.text.match(/Pekan \d/))) return s;
  }
  return null;
}
async function waitTanggal(ms=12000) {
  const end = Date.now()+ms;
  while (Date.now()<end) {
    for (const s of document.querySelectorAll('select')) {
      if (!s.options[0]?.text.includes('Tanggal') && !s.id?.toLowerCase().includes('tanggal')) continue;
      const real = Array.from(s.options).filter(o=>o.value&&!o.text.includes('--')&&!o.text.includes('Pilih'));
      if (real.length) return s;
      await sleep(400); break;
    }
    await sleep(400);
  }
  return null;
}
function findTampilkan() {
  const m = document.querySelector('.modal.show,.modal[style*="display: block"],[role="dialog"]');
  if (m) for (const b of m.querySelectorAll('button')) if (b.textContent.includes('Tampilkan')) return b;
  return findByText('button','Tampilkan Data')||findByText('button','Tampilkan');
}
function findSimpan() {
  for (const b of document.querySelectorAll('button')) {
    if (b.closest('.modal')||b.closest('[role="dialog"]')) continue;
    if (b.textContent.trim()==='Simpan'||b.textContent.includes('Simpan')) return b;
  }
  return document.querySelector('button[type="submit"]');
}
async function getNthSelectAfter(mainSel, n, timeout) {
  const end = Date.now() + (timeout||4000);
  while (Date.now() < end) {
    const vis = Array.from(document.querySelectorAll('select')).filter(s => s.offsetParent !== null);
    const mIdx = vis.indexOf(mainSel);
    if (mIdx !== -1 && vis[mIdx + n]) return vis[mIdx + n];
    await sleep(250);
  }
  return null;
}
async function fillSholat(name, data, dayIdx, log) {
  const doMain = dayIdx < (data.hari||0);
  const lbl = findLabel('Shalat ' + name);
  if (!lbl) { log.push('SKIP label Shalat '+name); return; }
  const mainSel = nearSelect(lbl);
  if (!mainSel) { log.push('SKIP select Shalat '+name); return; }
  await setSelect(mainSel, doMain?'Ya':'Tidak');
  if (!doMain) { log.push(name+': Tidak'); return; }
  await sleep(D.M);
  const ber = await getNthSelectAfter(mainSel, 1, 4000);
  if (!ber) { log.push('WARN Berjamaah '+name); return; }
  await setSelect(ber, dayIdx < (data.berjamaah||0) ? 'Ya':'Tidak');
  await sleep(D.M);
  const mas = await getNthSelectAfter(mainSel, 2, 4000);
  if (!mas) { log.push('WARN Masjid '+name); return; }
  await setSelect(mas, dayIdx < (data.masjid||0) ? 'Ya':'Tidak');
  await sleep(D.M);
  const awal = await getNthSelectAfter(mainSel, 3, 4000);
  if (!awal) { log.push('WARN Awal '+name); return; }
  await setSelect(awal, dayIdx < (data.awalWaktu||0) ? 'Ya':'Tidak');
  await sleep(D.S);
  log.push(name+': Ya');
}
async function fillYn(labelTxt, doYes, log) {
  const lbl = findLabel(labelTxt);
  if (!lbl) { log.push('SKIP label '+labelTxt); return; }
  const s = nearSelect(lbl);
  if (!s) { log.push('SKIP select '+labelTxt); return; }
  await setSelect(s, doYes?'Ya':'Tidak');
  log.push(labelTxt+': '+(doYes?'Ya':'Tidak'));
}
async function fillInput(labelTxt, value, log) {
  const lbl = findLabel(labelTxt);
  if (!lbl) { log.push('SKIP label '+labelTxt); return; }
  const inp = nearInput(lbl);
  if (!inp) { log.push('SKIP input '+labelTxt); return; }
  await setInput(inp, value);
  log.push(labelTxt+': '+value);
}
window.__ayFillDay = async (cfg) => {
  const log = [];
  const { dayIdx, mode, sholat, extras, rawatib, tilawah } = cfg;
  window.scrollTo({top:0,behavior:'instant'});
  await sleep(300);
  for (const n of ['Subuh','Dzuhur','Ashar','Maghrib','Isya']) {
    await fillSholat(n, sholat[n.toLowerCase()]||{}, dayIdx, log);
    await sleep(D.S);
  }
  if (mode==='ramadhan') {
    await fillYn('Puasa Ramadhan', dayIdx<(extras.puasaRamadhan||0), log);
    await fillYn('Shalat Tarawih', dayIdx<(extras.tarawih||0), log);
  } else {
    await fillYn('Puasa Sunnah', dayIdx<(extras.puasaSunnah||0), log);
    await fillYn('Qiyamul Lail', dayIdx<(extras.qiyamulLail||0), log);
  }
  await fillYn('Shalat Dhuha', dayIdx<(extras.dhuha||0), log);
  await fillYn("Al Ma'tsurat", dayIdx<(extras.matsurat||0), log);
  await fillYn('Infaq', dayIdx<(extras.infaq||0), log);
  await fillYn('Jam Tidur', dayIdx<(extras.jamTidur||0), log);
  await fillInput('Shalat Rawatib', rawatib, log);
  await fillInput("Tilawah Al Qur'an", tilawah, log);
  return log;
};
window.__aySnapshot = () => {
  const out = [];
  const seen = new Set();
  for (const el of document.querySelectorAll('td,th,label,b,strong,span,.col-form-label')) {
    const txt = el.textContent.trim();
    if (!txt || txt.length>80 || seen.has(txt)) continue;
    const sel = nearSelect(el);
    if (sel) {
      seen.add(txt);
      out.push({label:txt, control:'select', value:sel.value,
        options:Array.from(sel.options).map(o=>o.text.trim()).filter(Boolean).slice(0,20)});
      continue;
    }
    const inp = nearInput(el);
    if (inp) {
      seen.add(txt);
      out.push({label:txt, control:'input', type:inp.type, value:inp.value});
    }
  }
  const buttons = [];
  for (const b of document.querySelectorAll('button,a.btn')) {
    const t = b.textContent.trim();
    if (t && !buttons.includes(t)) buttons.push(t.slice(0,60));
  }
  return {fields: out, buttons: buttons.slice(0,40), url: location.href,
          mainPage: onMainPage(), formPage: onFormPage()};
};
window.__ayOnMain = () => onMainPage();
window.__ayOnForm = () => onFormPage();
window.__ayClickTambah = () => clickEl(findTambahBtn());
window.__aySelectPekan = async (name) => setSelect(findPekanSelect(), name);
window.__ayWaitTanggal = async () => {
  const s = await waitTanggal(12000);
  if (!s) return null;
  return Array.from(s.options)
    .filter(o=>o.value&&!o.text.includes('--')&&!o.text.includes('Pilih'))
    .map(o=>({value:o.value, text:o.text.trim()}));
};
window.__aySelectDate = async (value) => setSelect(await waitTanggal(8000), value);
window.__ayClickTampilkan = () => clickEl(findTampilkan());
window.__ayClickSimpan = () => clickEl(findSimpan());
})();
"""


# ─── Helpers ─────────────────────────────────────────────────────────────────

def distribute(total: int, days: int) -> list[int]:
    if days <= 0:
        return []
    base, rem = divmod(int(total or 0), days)
    return [base + (1 if i < rem else 0) for i in range(days)]


def _result(payload: dict, live: bool = False) -> CallToolResult:
    result = CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]
    )
    if live:
        result.meta = {"liveViewData": {"debuggerUrl": f"http://127.0.0.1:{DEBUG_PORT}"}}
    return result


async def _wait_until(page, js_expr: str, timeout_ms: int = 25000, poll: int = 400) -> bool:
    end = time.time() + timeout_ms / 1000
    while time.time() < end:
        try:
            if await page.evaluate(js_expr):
                return True
        except Exception:
            pass
        await page.wait_for_timeout(poll)
    return False


# ─── Generic browser tools ───────────────────────────────────────────────────

@mcp.tool(name="browser_navigate", description="Open a URL in the automation browser (headed Chromium). Use for any web form or portal the user asks you to fill in. Returns current URL, page title, and a snapshot of the form fields found on the page.")
async def browser_navigate(url: str) -> CallToolResult:
    try:
        page = await _ensure_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(1500)
        snap = await page.evaluate("window.__aySnapshot ? window.__aySnapshot() : {url: location.href}")
        return _result({"success": True, "url": page.url, "title": await page.title(), "snapshot": snap}, live=True)
    except Exception as e:
        return _result({"success": False, "error": str(e)})


@mcp.tool(name="browser_snapshot", description="Dump the current page's interactive structure: every labeled select (with its options) and input found on the page, plus the list of visible buttons. Use this to understand an unfamiliar form before filling it.")
async def browser_snapshot() -> str:
    try:
        page = await _ensure_page()
        snap = await page.evaluate("window.__aySnapshot ? window.__aySnapshot() : {fields: [], buttons: [], url: location.href}")
        return _result({"success": True, "snapshot": snap})
    except Exception as e:
        return _result({"success": False, "error": str(e)})


@mcp.tool(name="browser_fill_by_label", description="Fill a text/number input field by its visible label text (e.g. 'Shalat Rawatib'). Finds the input closest to the label and sets its value.")
async def browser_fill_by_label(label: str, value: Any) -> str:
    try:
        page = await _ensure_page()
        js = f"window.__ayFillInputByLabel({json.dumps(label)}, {json.dumps(value)})"
        ok = await page.evaluate(js)
        return _result({"success": bool(ok), "label": label, "value": value})
    except Exception as e:
        return _result({"success": False, "error": str(e)})


@mcp.tool(name="browser_select_by_label", description="Pick an option from a dropdown/select by its visible label text (e.g. choose 'Ya'/'Tidak' for a labeled select). The value can be the exact option text or a substring.")
async def browser_select_by_label(label: str, value: str) -> str:
    try:
        page = await _ensure_page()
        js = f"window.__aySelectByLabel({json.dumps(label)}, {json.dumps(value)})"
        ok = await page.evaluate(js)
        return _result({"success": bool(ok), "label": label, "value": value})
    except Exception as e:
        return _result({"success": False, "error": str(e)})


@mcp.tool(name="browser_click_by_text", description="Click a button/link whose text contains the given string (e.g. 'Tampilkan Data', 'Simpan', 'Tambah Data').")
async def browser_click_by_text(text: str) -> str:
    try:
        page = await _ensure_page()
        js = f"window.__ayClickByText({json.dumps(text)})"
        ok = await page.evaluate(js)
        return _result({"success": bool(ok), "text": text})
    except Exception as e:
        return _result({"success": False, "error": str(e)})


@mcp.tool(name="browser_screenshot", description="Save a screenshot of the current automation browser page to browser_data/screenshots/. Returns the absolute PNG path.")
async def browser_screenshot(path: str = "") -> str:
    try:
        page = await _ensure_page()
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        if not path:
            path = os.path.join(SCREENSHOT_DIR, f"browser_{int(time.time())}.png")
        await page.screenshot(path=path)
        return _result({"success": True, "path": os.path.abspath(path)})
    except Exception as e:
        return _result({"success": False, "error": str(e)})


@mcp.tool(name="browser_close", description="Close the automation browser (persistent profile is kept, so portal login survives).")
async def browser_close() -> str:
    try:
        await _close_browser()
        return _result({"success": True})
    except Exception as e:
        return _result({"success": False, "error": str(e)})


@mcp.tool(name="browser_status", description="Report whether the automation browser is running, the current URL, and whether it is on the SIS main page or a form page.")
async def browser_status() -> str:
    try:
        page = await _ensure_page()
        snap = await page.evaluate("window.__aySnapshot ? window.__aySnapshot() : {url: location.href}")
        return _result({
            "success": True,
            "url": page.url,
            "title": await page.title(),
            "mainPage": snap.get("mainPage"),
            "formPage": snap.get("formPage"),
        }, live=True)
    except Exception as e:
        return _result({"success": False, "error": str(e)})


# ─── Extra JS for generic fill/click (injected alongside AY_JS) ──────────────

GENERIC_JS = r"""
(() => {
'use strict';
const sleep = ms => new Promise(r => setTimeout(r, ms));
window.__ayFillInputByLabel = async (labelTxt, value) => {
  const lbl = window.__ay.findLabel(labelTxt);
  if (!lbl) return false;
  const inp = window.__ay.nearInput(lbl);
  if (!inp) return false;
  return window.__ay.setInput(inp, value);
};
window.__aySelectByLabel = async (labelTxt, value) => {
  const lbl = window.__ay.findLabel(labelTxt);
  if (!lbl) return false;
  const s = window.__ay.nearSelect(lbl);
  if (!s) return false;
  return window.__ay.setSelect(s, value);
};
window.__ayClickByText = async (txt) => {
  for (const el of document.querySelectorAll('button,a.btn')) {
    if (el.textContent.trim().includes(txt)) {
      el.scrollIntoView({behavior:'smooth', block:'center'});
      await sleep(200);
      el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));
      await sleep(80);
      el.click();
      await sleep(600);
      return true;
    }
  }
  return false;
};
})();
"""


# ─── Data persistence tools ──────────────────────────────────────────────────

def _load_form_data() -> dict:
    if os.path.exists(FORM_DATA_PATH):
        try:
            with open(FORM_DATA_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


@mcp.tool(name="browser_save_form_data", description="Save a named blob of form data (JSON) to browser_data/form_data.json so it can be reused for later fills. Use this after the user answers questions once.")
def browser_save_form_data(name: str, data: dict) -> str:
    try:
        store = _load_form_data()
        store[name] = data
        os.makedirs(os.path.dirname(FORM_DATA_PATH), exist_ok=True)
        with open(FORM_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, ensure_ascii=False)
        return _result({"success": True, "name": name})
    except Exception as e:
        return _result({"success": False, "error": str(e)})


@mcp.tool(name="browser_load_form_data", description="Load a previously saved named blob of form data (JSON) from browser_data/form_data.json.")
def browser_load_form_data(name: str) -> str:
    try:
        store = _load_form_data()
        if name not in store:
            return _result({"success": False, "error": f"No saved form data named '{name}'", "available": list(store.keys())})
        return _result({"success": True, "name": name, "data": store[name]})
    except Exception as e:
        return _result({"success": False, "error": str(e)})


# ─── Amal Yaumi macro ────────────────────────────────────────────────────────

async def _open_pekan(page, pekan_name: str) -> list | None:
    if not await page.evaluate("window.__ayClickTambah()"):
        return None
    await page.wait_for_timeout(1200)
    if not await page.evaluate(f"window.__aySelectPekan({json.dumps(pekan_name)})"):
        return None
    dates = await page.evaluate("window.__ayWaitTanggal()")
    if not dates:
        return None
    return dates


async def _fill_one_pekan(page, entry: dict, mode: str) -> dict:
    pekan_name = entry.get("pekanName", "")
    data = entry.get("data", {}) or {}
    sholat = data.get("sholat", {}) or {}
    extras = data.get("extras", {}) or {}

    dates = await _open_pekan(page, pekan_name)
    if not dates:
        return {"pekan": pekan_name, "success": False, "error": "Tidak bisa membuka modal / pekan tidak ditemukan"}

    n_days = len(dates)
    rawatib_per_day = distribute(extras.get("rawatib", 0), n_days)
    tilawah_per_day = distribute(extras.get("tilawah", 0), n_days)

    days_done = 0
    for day_idx, date_obj in enumerate(dates):
        if day_idx > 0:
            # re-open modal for the next day
            if not await page.evaluate("window.__ayClickTambah()"):
                return {"pekan": pekan_name, "success": False, "error": "Modal gagal dibuka ulang", "days_done": days_done}
            await page.wait_for_timeout(1200)
            await page.evaluate(f"window.__aySelectPekan({json.dumps(pekan_name)})")
            await page.wait_for_timeout(1200)
        if not await page.evaluate(f"window.__aySelectDate({json.dumps(date_obj['value'])})"):
            return {"pekan": pekan_name, "success": False, "error": f"Tanggal {date_obj['text']} gagal dipilih", "days_done": days_done}
        if not await page.evaluate("window.__ayClickTampilkan()"):
            return {"pekan": pekan_name, "success": False, "error": "Tombol Tampilkan Data tidak ditemukan", "days_done": days_done}

        await page.wait_for_load_state("networkidle")
        if not await _wait_until(page, "window.__ayOnForm()", 25000):
            return {"pekan": pekan_name, "success": False, "error": "Form tidak muncul setelah Tampilkan Data", "days_done": days_done}

        cfg = {
            "dayIdx": day_idx,
            "mode": mode,
            "sholat": sholat,
            "extras": extras,
            "rawatib": rawatib_per_day[day_idx],
            "tilawah": tilawah_per_day[day_idx],
        }
        fill_log = await page.evaluate(f"window.__ayFillDay({json.dumps(cfg)})")

        if not await page.evaluate("window.__ayClickSimpan()"):
            return {"pekan": pekan_name, "success": False, "error": "Tombol Simpan tidak ditemukan", "days_done": days_done, "fill_log": fill_log}
        await page.wait_for_load_state("networkidle")
        await _wait_until(page, "window.__ayOnMain()", 25000)
        days_done += 1

    return {"pekan": pekan_name, "success": True, "days": days_done}


@mcp.tool(name="amal_yaumi_fill", description="Port of the Amal Yaumi Auto-Fill extension for SIS Al Uswah (app.sisal.uswah.sch.id). mode='ramadhan' or 'biasa'. entries is a list of {pekanName, data:{sholat:{subuh/dzuhur/ashar/maghrib/isya: {hari, berjamaah, masjid, awalWaktu}}, extras:{puasaRamadhan/tarawih (ramadhan) atau puasaSunnah/qiyamulLail (biasa), dhuha, matsurat, infaq, jamTidur, rawatib (total), tilawah (total)}}}. Browser runs headed so the user can watch; portal login persists in browser_data/profile. Returns a per-pekan report.")
async def amal_yaumi_fill(
    mode: Annotated[str, Field(description="'ramadhan' or 'biasa'")],
    entries: Annotated[list, Field(description="List of pekan entries, each {pekanName, data:{sholat, extras}}")],
) -> str:
    try:
        page = await _ensure_page()
        if "sisal.uswah.sch.id" not in page.url:
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(1500)
        if not await _wait_until(page, "window.__ayOnMain()", 30000):
            return _result({"success": False, "error": "Halaman utama SIS tidak terdeteksi (login?). Browser sudah dibuka — silakan login di window Chromium, lalu ulangi."}, live=True)

        report = []
        for entry in entries:
            r = await _fill_one_pekan(page, entry, mode)
            report.append(r)
            if not r["success"]:
                break
        return _result({"success": all(r["success"] for r in report), "report": report}, live=True)
    except Exception as e:
        traceback.print_exc()
        return _result({"success": False, "error": str(e)})


def main():
    mcp.run()


if __name__ == "__main__":
    main()
