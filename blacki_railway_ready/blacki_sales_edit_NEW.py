"""
BLACKI STORE — Mobile Server
Run this on your PC, then open the URL on your phone.
Both devices must be on the same Wi-Fi.
"""

import http.server
import json
import os
import sys
import socket
import base64
import urllib.parse
import uuid
import hashlib
import hmac
import mimetypes
import secrets
import shutil
import time
from http import cookies

if getattr(sys, "frozen", False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))

BUNDLED_DATA = os.path.join(BASE, "blacki_data")
DATA = os.path.abspath(
    os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    or os.environ.get("DATA_DIR")
    or BUNDLED_DATA
)
DB = os.path.join(DATA, "products.json")
SALES_DB = os.path.join(DATA, "sales.json")

def seed_persistent_data():
    """Copy bundled data into a new Railway volume once, without overwriting saved cloud data."""
    os.makedirs(os.path.join(DATA, "images"), exist_ok=True)
    if os.path.abspath(DATA) == os.path.abspath(BUNDLED_DATA):
        return
    if not os.path.isdir(BUNDLED_DATA):
        return

    for filename in ("products.json", "sales.json"):
        source = os.path.join(BUNDLED_DATA, filename)
        destination = os.path.join(DATA, filename)
        if os.path.isfile(source) and not os.path.exists(destination):
            shutil.copy2(source, destination)

    source_images = os.path.join(BUNDLED_DATA, "images")
    destination_images = os.path.join(DATA, "images")
    if os.path.isdir(source_images):
        for filename in os.listdir(source_images):
            source = os.path.join(source_images, filename)
            destination = os.path.join(destination_images, filename)
            if os.path.isfile(source) and not os.path.exists(destination):
                shutil.copy2(source, destination)

seed_persistent_data()

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def load_products():
    try:
        with open(DB, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_products(products):
    os.makedirs(DATA, exist_ok=True)
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

def load_sales():
    try:
        with open(SALES_DB, "r", encoding="utf-8") as f:
            sales = json.load(f)
        if not isinstance(sales, list):
            return []

        # Older sales were saved before IDs were added. Give each old sale
        # a permanent ID so it can be edited or deleted.
        changed = False
        for sale in sales:
            if not isinstance(sale, dict):
                continue
            if not sale.get("id"):
                sale["id"] = uuid.uuid4().hex
                changed = True

        if changed:
            save_sales(sales)
        return sales
    except:
        return []

def save_sales(sales):
    os.makedirs(DATA, exist_ok=True)
    with open(SALES_DB, "w", encoding="utf-8") as f:
        json.dump(sales, f, ensure_ascii=False, indent=2)

PORT = int(os.environ.get("PORT", "8000"))

HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0A0A0A">
<title>BLACKI STORE</title>
<!-- SALES INLINE EDIT BUILD -->
<link rel="apple-touch-icon" href="/icon.png">
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{background:#0A0A0A;color:#F0F0F0;font-family:-apple-system,system-ui,'Segoe UI',sans-serif;
  min-height:100vh;min-height:100dvh;overflow-x:hidden;-webkit-font-smoothing:antialiased}
input,textarea,button{font-family:inherit;outline:none}

.page{max-width:480px;margin:0 auto;min-height:100vh;min-height:100dvh;
  padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}

.header{display:flex;justify-content:space-between;align-items:center;padding:20px 18px 6px}
.logo{font-size:22px;font-weight:900;letter-spacing:-0.5px;color:#E8C547;direction:ltr}
.count{font-size:11px;color:#555;letter-spacing:1.5px;text-transform:uppercase;margin-top:2px}
.add-btn{width:44px;height:44px;border-radius:14px;border:none;background:#E8C547;
  display:flex;align-items:center;justify-content:center;cursor:pointer}

.search-wrap{padding:8px 18px 14px;position:relative}
.search-icon{position:absolute;right:32px;top:50%;transform:translateY(-50%)}
.search-input{width:100%;padding:13px 44px 13px 40px;border-radius:14px;border:1px solid #1E1E1E;
  background:#111;color:#F0F0F0;font-size:15px;direction:rtl}
.search-input::placeholder{color:#555}
.clear-btn{position:absolute;left:28px;top:50%;transform:translateY(-50%);background:none;
  border:none;color:#555;font-size:14px;cursor:pointer}

.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 18px 100px}
.card{border-radius:16px;overflow:hidden;background:#111;border:1px solid #1A1A1A;cursor:pointer}
.card-img{width:100%;aspect-ratio:1;overflow:hidden;background:#141414}
.card-img img{width:100%;height:100%;object-fit:cover;display:block}
.card-info{padding:10px 12px 12px}
.card-label{font-size:14px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card-price{font-size:12px;color:#E8C547;margin-top:3px;font-weight:600}
.card-tags{font-size:11px;color:#555;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.empty{text-align:center;padding:80px 20px;color:#555;font-size:15px}
.empty-icon{font-size:44px;margin-bottom:8px}

.top-bar{display:flex;align-items:center;justify-content:space-between;padding:16px 18px 10px}
.back-btn{width:36px;height:36px;border-radius:10px;border:none;background:rgba(255,255,255,0.08);
  display:flex;align-items:center;justify-content:center;cursor:pointer}
.top-title{font-size:17px;font-weight:700}

.form-body{padding:0 18px 40px}
.img-row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}
.img-thumb{width:72px;height:72px;border-radius:12px;overflow:hidden;position:relative;flex-shrink:0}
.img-thumb img{width:100%;height:100%;object-fit:cover}
.img-remove{position:absolute;top:3px;left:3px;width:22px;height:22px;border-radius:50%;border:none;
  background:rgba(0,0,0,0.7);color:#fff;font-size:11px;cursor:pointer;display:flex;align-items:center;justify-content:center}
.img-add{width:72px;height:72px;border-radius:12px;border:2px dashed #2A2A2A;background:none;
  display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0}
.field-label{font-size:12px;font-weight:700;color:#555;text-transform:uppercase;
  letter-spacing:0.5px;margin-bottom:6px;margin-top:18px}
.form-input{width:100%;padding:13px 14px;border-radius:12px;border:1px solid #1E1E1E;
  background:#111;color:#F0F0F0;font-size:15px;direction:rtl}
.form-input::placeholder{color:#444}
.form-textarea{height:80px;resize:none}
.save-btn{width:100%;padding:16px;border-radius:14px;border:none;background:#E8C547;
  color:#0A0A0A;font-size:16px;font-weight:800;cursor:pointer;margin-top:28px}
.save-btn:disabled{opacity:0.35}

.detail-img{width:100%;aspect-ratio:1;background:#111;position:relative;overflow:hidden;touch-action:pan-y}
.detail-img img{width:100%;height:100%;object-fit:contain}
.detail-back{position:absolute;top:14px;right:14px;width:38px;height:38px;border-radius:12px;
  border:none;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;cursor:pointer}
.dots{position:absolute;bottom:14px;left:50%;transform:translateX(-50%);display:flex;gap:5px;align-items:center}
.dot{height:7px;border-radius:4px;transition:all 0.2s}
.dot-active{width:18px;background:#E8C547}
.dot-inactive{width:7px;background:rgba(255,255,255,0.4)}
.detail-info{padding:20px 18px 40px}
.detail-label{font-size:22px;font-weight:800}
.detail-price{font-size:18px;color:#E8C547;font-weight:700;margin-top:6px}
.tag-row{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.tag{padding:5px 12px;border-radius:20px;background:#151515;border:1px solid #1E1E1E;font-size:12px;color:#888}
.detail-notes{margin-top:16px;font-size:14px;color:#888;line-height:1.6;white-space:pre-wrap}
.detail-actions{display:flex;gap:10px;margin-top:28px}
.edit-btn{flex:1;padding:14px;border-radius:12px;border:1px solid #2A2A2A;background:#141414;
  color:#F0F0F0;font-size:15px;font-weight:700;cursor:pointer}
.delete-btn{flex:1;padding:14px;border-radius:12px;border:1px solid rgba(224,85,85,0.2);
  background:transparent;color:#E05555;font-size:15px;font-weight:700;cursor:pointer}
.confirm-del{background:#E05555!important;color:#fff!important;border-color:#E05555!important}


.bottom-nav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:min(480px,100%);
  display:grid;grid-template-columns:1fr 1fr;background:rgba(10,10,10,.97);border-top:1px solid #1E1E1E;
  padding:8px 12px calc(8px + env(safe-area-inset-bottom,0px));z-index:50;backdrop-filter:blur(14px)}
.nav-btn{border:none;background:none;color:#666;padding:8px;border-radius:12px;font-size:12px;font-weight:700;cursor:pointer}
.nav-btn svg{display:block;margin:0 auto 4px}.nav-active{color:#E8C547;background:#151515}
.sales-body{padding:4px 18px calc(100px + env(safe-area-inset-bottom,0px))}
.sales-summary{background:linear-gradient(135deg,#17150d,#111);border:1px solid #2a2511;border-radius:18px;padding:18px;margin-bottom:14px}
.sales-summary-label{font-size:12px;color:#777}.sales-total{font-size:28px;font-weight:900;color:#E8C547;margin-top:5px;direction:ltr;text-align:right}
.filter-row{display:flex;gap:7px;overflow-x:auto;padding-bottom:12px;scrollbar-width:none}
.filter-row::-webkit-scrollbar{display:none}.filter-btn{flex-shrink:0;border:1px solid #232323;background:#111;color:#777;padding:9px 13px;border-radius:20px;font-size:12px;font-weight:700;cursor:pointer}
.filter-active{background:#E8C547;color:#0A0A0A;border-color:#E8C547}
.sale-card{width:100%;display:block;text-align:right;background:linear-gradient(135deg,#16112a,#101820);border:1px solid #382b65;border-radius:18px;padding:15px;margin-bottom:11px;color:#F0F0F0;cursor:pointer;box-shadow:0 8px 24px rgba(0,0,0,.22);transition:transform .12s,border-color .12s}
.sale-card:active{transform:scale(.985);border-color:#E8C547}.sale-head{display:flex;justify-content:space-between;align-items:center;gap:10px}.sale-date{font-size:12px;color:#a89bc9}.sale-amount{font-size:17px;color:#FFD95A;font-weight:900;direction:ltr}.sale-items{margin-top:9px;color:#d0c8df;font-size:13px;line-height:1.7}.sale-open{margin-top:12px;display:flex;align-items:center;justify-content:space-between;color:#73d7ff;font-size:12px;font-weight:800}.sale-detail-wrap{padding:8px 18px 120px}.sale-detail-hero{background:linear-gradient(135deg,#432371,#1f5f78);border:1px solid rgba(255,255,255,.15);border-radius:22px;padding:20px;box-shadow:0 14px 34px rgba(0,0,0,.28)}
.sale-detail-emoji{font-size:42px}.sale-detail-title{font-size:14px;color:#ddd;margin-top:8px}.sale-detail-total{font-size:32px;font-weight:950;color:#FFE36E;direction:ltr;text-align:right;margin-top:5px}.sale-detail-date{font-size:12px;color:#c8bce0;margin-top:5px}.sale-detail-items{margin-top:14px;background:rgba(0,0,0,.2);border-radius:15px;padding:12px;line-height:1.9;color:#f1edf7;font-size:14px}.sale-detail-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:16px}.sale-detail-btn{padding:14px;border-radius:14px;font-size:14px;font-weight:900;cursor:pointer}.sale-detail-edit{background:#35c98b;color:#061b13;border:none}.sale-detail-delete{background:#ff5f6d;color:white;border:none}.sale-price-editor{display:none;margin-top:14px;background:#111827;border:1px solid #334155;border-radius:16px;padding:14px}.sale-price-editor.open{display:block}.sale-price-label{font-size:12px;color:#94a3b8;margin-bottom:7px}.sale-price-input{width:100%;padding:13px;border-radius:12px;border:1px solid #475569;background:#080d16;color:#fff;font-size:18px;direction:ltr;text-align:right}.sale-editor-buttons{display:flex;gap:8px;margin-top:9px}.sale-editor-save{flex:1;background:#FFD95A;color:#111;border:none;padding:12px;border-radius:11px;font-weight:900}.sale-editor-cancel{flex:1;background:#222b3a;color:#ddd;border:1px solid #3c4656;padding:12px;border-radius:11px;font-weight:800}.build-badge{display:inline-block;margin-top:4px;padding:3px 8px;border-radius:10px;background:#2b1745;color:#d9a7ff;font-size:9px;font-weight:900;letter-spacing:.4px}
.product-pick{display:flex;align-items:center;gap:11px;background:#111;border:1px solid #1C1C1C;border-radius:14px;padding:10px;margin-bottom:8px}
.pick-img{width:54px;height:54px;border-radius:10px;object-fit:cover;background:#171717}
.pick-info{min-width:0;flex:1}.pick-name{font-size:14px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pick-price{font-size:12px;color:#E8C547;margin-top:3px}.qty{display:flex;align-items:center;gap:9px;direction:ltr}
.qty-btn{width:31px;height:31px;border-radius:9px;border:1px solid #2A2A2A;background:#191919;color:#eee;font-size:19px;cursor:pointer}
.qty-num{min-width:20px;text-align:center;font-weight:800}.sale-footer{position:sticky;bottom:0;background:#0A0A0A;padding:12px 18px 20px;border-top:1px solid #191919}
.sale-total-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}.sale-total-label{color:#888;font-size:13px}
.sale-total-value{color:#E8C547;font-size:20px;font-weight:900;direction:ltr}.no-price{opacity:.45}

.loading{display:flex;align-items:center;justify-content:center;height:100vh;color:#555;font-size:15px}
</style>
</head>
<body>
<div id="app" class="page"><div class="loading">جاري التحميل...</div></div>
<script>
const app = document.getElementById("app");
let products = [];
let sales = [];
let saleCart = {};
let salesFilter = "today";
let currentView = "home";
let selected = null;
let selectedSale = null;
let viewIdx = 0;
let touchStartX = null;
let pendingImages = [];
let confirmingDelete = false;

// ============ API ============
async function fetchProducts() {
  const r = await fetch("/api/products");
  products = await r.json();
  renderHome();
}

async function fetchSales(render = true) {
  const r = await fetch("/api/sales");
  sales = await r.json();
  if (render) renderSales();
}

async function apiSaveSale(sale) {
  await fetch("/api/sales", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(sale)
  });
}

async function apiDeleteSale(id) {
  await fetch("/api/sales/" + encodeURIComponent(id), { method: "DELETE" });
}

async function apiSave(product) {
  await fetch("/api/products", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(product)
  });
}

async function apiDelete(id) {
  await fetch("/api/products/" + id, { method: "DELETE" });
}

function imgUrl(path) {
  return "/img?path=" + encodeURIComponent(path);
}


function bottomNav(active) {
  return `<div class="bottom-nav">
    <button class="nav-btn ${active==='home'?'nav-active':''}" onclick="renderHome()">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 10.5 12 3l9 7.5V21H3z"/><path d="M9 21v-7h6v7"/></svg>
      المنتجات
    </button>
    <button class="nav-btn ${active==='sales'?'nav-active':''}" onclick="fetchSales()">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/></svg>
      المبيعات
    </button>
  </div>`;
}

function money(n) {
  return Math.round(Number(n)||0).toLocaleString("en-US") + " IQD";
}

function priceNumber(price) {
  return Number(String(price||"").replace(/[^0-9]/g,"")) || 0;
}

// ============ HOME ============
function buildGrid(searchQ) {
  const q = (searchQ || "").toLowerCase();
  const filtered = products.filter(p =>
    !q || p.label.toLowerCase().includes(q) ||
    (p.price||"").toLowerCase().includes(q)
  );

  if (filtered.length === 0) {
    return `<div class="empty">
      ${products.length === 0 ? '<div class="empty-icon">📦</div><div>اضف اول منتج</div>' : `لا نتائج لـ "${esc(searchQ)}"`}
    </div>`;
  }
  return `<div class="grid">${filtered.map(p => {
    return `
    <div class="card" onclick="openDetail('${p.id}')">
      <div class="card-img"><img src="${imgUrl(p.images[0])}" alt="" loading="lazy"></div>
      <div class="card-info">
        <div class="card-label">${esc(p.label)}</div>
        ${p.price ? `<div class="card-price">${esc(p.price)} IQD</div>` : ''}
      </div>
    </div>`;
  }).join("")}</div>`;
}

function filterGrid() {
  const input = document.getElementById("searchInput");
  const grid = document.getElementById("gridArea");
  if (!input || !grid) return;
  grid.innerHTML = buildGrid(input.value);
}

function renderHome(searchQ = "") {
  currentView = "home";

  app.innerHTML = `
    <div class="header">
      <div>
        <div class="logo">BLACKI STORE</div>
        <div class="count">${products.length} منتج</div>
      </div>
      <button class="add-btn" onclick="renderForm()">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0A0A0A" stroke-width="2.5" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
      </button>
    </div>
    <div class="search-wrap">
      <svg class="search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#555" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
      <input class="search-input" id="searchInput" placeholder="ابحث عن منتج..." value="${esc(searchQ)}" oninput="filterGrid()">
    </div>
    <div id="gridArea">${buildGrid(searchQ)}</div>
    ${bottomNav("home")}`;
}

function formatPrice(val) {
  if (!val) return "";
  // Convert Arabic/Persian numerals to English
  val = val.replace(/[٠-٩]/g, d => "٠١٢٣٤٥٦٧٨٩".indexOf(d));
  val = val.replace(/[۰-۹]/g, d => "۰۱۲۳۴۵۶۷۸۹".indexOf(d));
  // Remove everything except digits
  val = val.replace(/[^0-9]/g, "");
  if (!val) return "";
  // Add commas
  return val.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// ============ FORM ============
function renderForm(editId) {
  currentView = "form";
  const p = editId ? products.find(x => x.id === editId) : null;
  pendingImages = p ? [...p.images] : [];

  app.innerHTML = `
    <div class="top-bar">
      <button class="back-btn" onclick="renderHome()">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#F0F0F0" stroke-width="2" stroke-linecap="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
      </button>
      <div class="top-title">${p ? 'تعديل' : 'منتج جديد'}</div>
      <div style="width:36px"></div>
    </div>
    <div class="form-body">
      <input type="file" id="filePicker" accept="image/*" multiple style="display:none" onchange="handleFiles(this)">
      <div class="img-row" id="imgRow"></div>
      <div class="field-label">الاسم</div>
      <input class="form-input" id="fLabel" placeholder="مثال: ايرون مان" value="${p ? esc(p.label) : ''}">
      <div class="field-label">السعر (IQD)</div>
      <input class="form-input" id="fPrice" type="text" inputmode="numeric" placeholder="مثال: 25,000" value="${p ? esc(p.price||'') : ''}">
      <button class="save-btn" onclick="doSave('${editId||''}')">${p ? 'حفظ التعديلات' : 'اضافة منتج'}</button>
    </div>`;
  renderImgRow();
}

function renderImgRow() {
  const row = document.getElementById("imgRow");
  if (!row) return;
  row.innerHTML = pendingImages.map((img, i) => {
    const src = img.startsWith("data:") ? img : imgUrl(img);
    return `<div class="img-thumb">
      <img src="${src}" alt="">
      <button class="img-remove" onclick="removeImg(${i})">✕</button>
    </div>`;
  }).join("") +
    `<button class="img-add" onclick="document.getElementById('filePicker').click()">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#555" stroke-width="1.5" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
    </button>`;
}

function removeImg(i) { pendingImages.splice(i, 1); renderImgRow(); }

async function handleFiles(input) {
  for (const f of input.files) {
    // Upload to server
    const formData = new FormData();
    formData.append("file", f);
    const r = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await r.json();
    pendingImages.push(data.path);
  }
  input.value = "";
  renderImgRow();
}

async function doSave(editId) {
  const label = document.getElementById("fLabel").value.trim();
  if (!label) return alert("ادخل اسم المنتج");
  if (!pendingImages.length) return alert("اضف صورة واحدة على الاقل");
  const price = formatPrice(document.getElementById("fPrice").value.trim());

  if (editId) {
    const p = products.find(x => x.id === editId);
    if (p) { p.label=label; p.price=price; p.images=pendingImages; }
    await apiSave(p);
  } else {
    const newP = { id: Date.now().toString(), label, price, images: pendingImages };
    products.unshift(newP);
    await apiSave(newP);
  }
  await fetchProducts();
}


// ============ SALES ============
function localDateString(d = new Date()) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function filteredSales() {
  const today = new Date();
  const todayString = localDateString(today);
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const yesterdayString = localDateString(yesterday);

  return sales.filter(sale => {
    if (salesFilter === "all") return true;
    if (salesFilter === "today") return sale.date === todayString;
    if (salesFilter === "yesterday") return sale.date === yesterdayString;
    if (salesFilter === "week") {
      const start = new Date(today);
      start.setHours(0, 0, 0, 0);
      start.setDate(today.getDate() - 6);
      return Number(sale.createdAt || 0) >= start.getTime();
    }
    if (salesFilter === "month") {
      return String(sale.date || "").slice(0, 7) === todayString.slice(0, 7);
    }
    return true;
  });
}

function setSalesFilter(filter) {
  salesFilter = filter;
  renderSales();
}

function renderSales() {
  currentView = "sales";
  const visibleSales = filteredSales();
  const total = visibleSales.reduce((sum, sale) => sum + Number(sale.total || 0), 0);
  const labels = {today:"اليوم", yesterday:"أمس", week:"آخر 7 أيام", month:"هذا الشهر", all:"الكل"};

  app.innerHTML = `
    <div class="header">
      <div>
        <div class="logo">BLACKI STORE 🎉</div>
        <div class="count">المبيعات 💰</div>
        <div class="build-badge">NEW SALE EDIT BUILD 2026</div>
      </div>
      <button class="add-btn" onclick="renderNewSale()" aria-label="عملية بيع جديدة">➕</button>
    </div>
    <div class="sales-body">
      <div class="sales-summary">
        <div class="sales-summary-label">✨ إجمالي مبيعات ${labels[salesFilter]}</div>
        <div class="sales-total">${money(total)}</div>
      </div>
      <div class="filter-row">
        ${Object.entries(labels).map(([key,label]) => `<button class="filter-btn ${salesFilter===key?'filter-active':''}" onclick="setSalesFilter('${key}')">${label}</button>`).join("")}
      </div>
      <div>
        ${visibleSales.length ? visibleSales.map((sale,index) => `
          <button class="sale-card" onclick="openSaleDetail('${sale.id}')">
            <div class="sale-head">
              <div class="sale-date">🧾 بيع رقم ${visibleSales.length-index} · ${esc(sale.displayDate || sale.date || "")}</div>
              <div class="sale-amount">${money(sale.total)}</div>
            </div>
            <div class="sale-items">${(sale.items||[]).map(item => `📦 ${esc(item.label)} × ${item.qty}`).join("<br>")}</div>
            <div class="sale-open"><span>اضغط لفتح البيع</span><span>←</span></div>
          </button>`).join("") : `<div class="empty"><div class="empty-icon">🌈</div><div>لا توجد مبيعات في هذه الفترة</div></div>`}
      </div>
    </div>
    ${bottomNav("sales")}`;
}

function openSaleDetail(id) {
  selectedSale = sales.find(sale => String(sale.id) === String(id));
  if (!selectedSale) return alert("تعذر العثور على عملية البيع");
  renderSaleDetail();
}

function renderSaleDetail() {
  currentView = "saleDetail";
  const sale = selectedSale;
  if (!sale) return renderSales();
  app.innerHTML = `
    <div class="top-bar">
      <button class="back-btn" onclick="renderSales()">←</button>
      <div class="top-title">تفاصيل البيع 🧾</div>
      <div style="width:36px"></div>
    </div>
    <div class="sale-detail-wrap">
      <div class="sale-detail-hero">
        <div class="sale-detail-emoji">💸</div>
        <div class="sale-detail-title">السعر الذي تم البيع به</div>
        <div class="sale-detail-total">${money(sale.total)}</div>
        <div class="sale-detail-date">📅 ${esc(sale.displayDate || sale.date || "")}</div>
        <div class="sale-detail-items">${(sale.items||[]).map(item => `📦 ${esc(item.label)} × ${item.qty} — ${money(item.subtotal)}`).join("<br>")}</div>
        <div class="sale-detail-actions">
          <button class="sale-detail-btn sale-detail-edit" onclick="showSalePriceEditor()">✏️ تعديل السعر</button>
          <button class="sale-detail-btn sale-detail-delete" onclick="deleteSelectedSale()">🗑️ حذف البيع</button>
        </div>
        <div class="sale-price-editor" id="salePriceEditor">
          <div class="sale-price-label">اكتب سعر البيع الجديد (IQD)</div>
          <input class="sale-price-input" id="selectedSalePrice" type="text" inputmode="numeric" value="${formatPrice(String(sale.total||''))}">
          <div class="sale-editor-buttons">
            <button class="sale-editor-save" onclick="saveSelectedSalePrice()">✅ حفظ</button>
            <button class="sale-editor-cancel" onclick="hideSalePriceEditor()">إلغاء</button>
          </div>
        </div>
      </div>
    </div>`;
}

function showSalePriceEditor() {
  const editor = document.getElementById("salePriceEditor");
  if (editor) editor.classList.add("open");
  const input = document.getElementById("selectedSalePrice");
  if (input) { input.focus(); input.select(); }
}
function hideSalePriceEditor() {
  const editor = document.getElementById("salePriceEditor");
  if (editor) editor.classList.remove("open");
}
async function saveSelectedSalePrice() {
  if (!selectedSale) return;
  const input = document.getElementById("selectedSalePrice");
  const newTotal = priceNumber(formatPrice(input ? input.value : ""));
  if (newTotal <= 0) return alert("ادخل سعراً صحيحاً");
  const updated = {...selectedSale, total:newTotal};
  const response = await fetch("/api/sales", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(updated)});
  if (!response.ok) return alert("لم يتم حفظ السعر");
  await fetchSales(false);
  selectedSale = sales.find(sale => String(sale.id) === String(updated.id));
  renderSaleDetail();
}
async function deleteSelectedSale() {
  if (!selectedSale) return;
  if (!confirm("هل تريد حذف عملية البيع نهائياً؟")) return;
  const response = await fetch("/api/sales/" + encodeURIComponent(selectedSale.id), {method:"DELETE"});
  if (!response.ok) return alert("لم يتم حذف عملية البيع");
  selectedSale = null;
  await fetchSales(false);
  renderSales();
}

function renderNewSale() {
  currentView = "newSale";
  saleCart = {};

  app.innerHTML = `
    <div class="top-bar">
      <button class="back-btn" onclick="renderSales()">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#F0F0F0" stroke-width="2" stroke-linecap="round">
          <path d="M19 12H5M12 19l-7-7 7-7"/>
        </svg>
      </button>
      <div class="top-title">عملية بيع جديدة</div>
      <div style="width:36px"></div>
    </div>

    <div class="form-body" id="saleProducts" style="padding-bottom:10px"></div>

    <div class="sale-footer">
      <div class="sale-total-row">
        <span class="sale-total-label">المجموع</span>
        <span class="sale-total-value" id="newSaleTotal">0 IQD</span>
      </div>
      <button class="save-btn" id="completeSaleBtn" onclick="completeSale()" disabled>حفظ عملية البيع</button>
    </div>`;

  renderSaleProducts();
}

function renderSaleProducts() {
  const container = document.getElementById("saleProducts");
  if (!container) return;

  if (!products.length) {
    container.innerHTML = `<div class="empty"><div class="empty-icon">📦</div><div>لا توجد منتجات</div></div>`;
    updateSaleTotal();
    return;
  }

  container.innerHTML = products.map(product => {
    const qty = saleCart[product.id] || 0;
    const price = priceNumber(product.price);
    const disabledClass = price ? "" : "no-price";
    const image = product.images && product.images[0] ? imgUrl(product.images[0]) : "";

    return `
      <div class="product-pick ${disabledClass}">
        ${image ? `<img class="pick-img" src="${image}" alt="">` : `<div class="pick-img"></div>`}
        <div class="pick-info">
          <div class="pick-name">${esc(product.label)}</div>
          <div class="pick-price">${price ? money(price) : "لا يوجد سعر"}</div>
        </div>
        <div class="qty">
          <button class="qty-btn" onclick="changeSaleQty('${product.id}', -1)" ${price ? "" : "disabled"}>−</button>
          <div class="qty-num">${qty}</div>
          <button class="qty-btn" onclick="changeSaleQty('${product.id}', 1)" ${price ? "" : "disabled"}>+</button>
        </div>
      </div>`;
  }).join("");

  updateSaleTotal();
}

function changeSaleQty(productId, change) {
  const current = saleCart[productId] || 0;
  const next = Math.max(0, current + change);
  if (next === 0) delete saleCart[productId];
  else saleCart[productId] = next;
  renderSaleProducts();
}

function calculateSaleTotal() {
  return Object.entries(saleCart).reduce((sum, [productId, qty]) => {
    const product = products.find(item => item.id === productId);
    return sum + (product ? priceNumber(product.price) * qty : 0);
  }, 0);
}

function updateSaleTotal() {
  const total = calculateSaleTotal();
  const totalElement = document.getElementById("newSaleTotal");
  const saveButton = document.getElementById("completeSaleBtn");
  if (totalElement) totalElement.textContent = money(total);
  if (saveButton) saveButton.disabled = total <= 0;
}

async function completeSale() {
  const items = Object.entries(saleCart).map(([productId, qty]) => {
    const product = products.find(item => item.id === productId);
    if (!product) return null;
    const unitPrice = priceNumber(product.price);
    return {
      productId,
      label: product.label,
      qty,
      unitPrice,
      subtotal: unitPrice * qty
    };
  }).filter(Boolean);

  if (!items.length) return alert("اختر منتجاً واحداً على الأقل");

  const now = new Date();
  const sale = {
    id: Date.now().toString(),
    createdAt: now.getTime(),
    date: localDateString(now),
    displayDate: now.toLocaleString("ar-IQ"),
    items,
    total: items.reduce((sum, item) => sum + item.subtotal, 0)
  };

  await apiSaveSale(sale);
  sales.unshift(sale);
  renderSales();
}

// ============ DETAIL ============
function openDetail(id) {
  selected = products.find(p => p.id === id);
  if (!selected) return;
  viewIdx = 0;
  renderDetail();
}

function renderDetail() {
  currentView = "detail";
  const p = selected;
  const n = p.images.length;
  confirmingDelete = false;

  app.innerHTML = `
    <div class="detail-img" id="detailImg"
      ontouchstart="touchStartX=event.touches[0].clientX"
      ontouchend="handleSwipe(event)">
      <img src="${imgUrl(p.images[viewIdx])}" alt="">
      <button class="detail-back" onclick="renderHome()">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
      </button>
      ${n > 1 ? `<div class="dots">${p.images.map((_,i) => `<div class="dot ${i===viewIdx?'dot-active':'dot-inactive'}"></div>`).join("")}</div>` : ''}
    </div>
    <div class="detail-info">
      <div class="detail-label">${esc(p.label)}</div>
      ${p.price ? `<div class="detail-price">${esc(p.price)} IQD</div>` : ''}
      <div class="detail-actions" style="margin-top:16px">
        <button class="edit-btn" style="background:#1a3a1a;color:#4ade80;border-color:#2a4a2a;flex:2" onclick="shareImg('${p.id}')">مشاركة / حفظ</button>
      </div>
      <div class="detail-actions">
        <button class="edit-btn" onclick="renderForm('${p.id}')">تعديل</button>
        <button class="delete-btn" id="delBtn" onclick="handleDelete('${p.id}')">حذف</button>
      </div>
    </div>`;
}

function handleSwipe(e) {
  if (touchStartX === null || selected.images.length < 2) return;
  const diff = e.changedTouches[0].clientX - touchStartX;
  const n = selected.images.length;
  if (diff > 50) viewIdx = (viewIdx - 1 + n) % n;
  else if (diff < -50) viewIdx = (viewIdx + 1) % n;
  else return;
  touchStartX = null;
  renderDetail();
}

async function handleDelete(id) {
  if (!confirmingDelete) {
    confirmingDelete = true;
    const btn = document.getElementById("delBtn");
    btn.textContent = "تأكيد الحذف";
    btn.classList.add("confirm-del");
    return;
  }
  await apiDelete(id);
  products = products.filter(p => p.id !== id);
  renderHome();
}

function esc(s) { if(!s)return''; const d=document.createElement("div"); d.textContent=s; return d.innerHTML; }

function fullImgUrl(path) {
  return "/img-full?path=" + encodeURIComponent(path);
}

async function shareImg(id) {
  const p = products.find(x => x.id === id);
  if (!p) return;
  try {
    const url = fullImgUrl(p.images[viewIdx]);
    const res = await fetch(url);
    const blob = await res.blob();
    const file = new File([blob], p.label + ".jpg", { type: "image/jpeg" });
    if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
      navigator.share({ files: [file] }).catch(() => {});
      setTimeout(() => renderDetail(), 500);
    } else {
      // Fallback: open image in new tab
      const blobUrl = URL.createObjectURL(blob);
      window.open(blobUrl, "_blank");
    }
  } catch(e) {
    alert("حدث خطأ: " + e.message);
  }
}

function downloadImg(id) {
  // On iOS there's no real "download" — use share sheet instead
  shareImg(id);
}

Promise.all([fetchProducts(), fetchSales(false)]);
</script>
</body>
</html>"""


AUTH_USERNAME = os.environ.get("BLACKI_USERNAME", "blacki")
AUTH_PASSWORD = os.environ.get("BLACKI_PASSWORD", "change-this-password")
AUTH_SECRET = os.environ.get("BLACKI_SECRET_KEY") or hashlib.sha256(
    (AUTH_USERNAME + "|" + AUTH_PASSWORD + "|BLACKI STORE").encode("utf-8")
).hexdigest()
SESSION_SECONDS = 60 * 60 * 24 * 30
COOKIE_NAME = "blacki_session"

LOGIN_HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, viewport-fit=cover">
<meta name="theme-color" content="#0A0A0A">
<meta name="robots" content="noindex,nofollow,noarchive">
<title>BLACKI STORE — تسجيل الدخول</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{min-height:100vh;min-height:100dvh;background:#0A0A0A;color:#f2f2f2;font-family:-apple-system,system-ui,'Segoe UI',sans-serif;display:flex;align-items:center;justify-content:center;padding:24px}
.login{width:100%;max-width:420px;background:#111;border:1px solid #252525;border-radius:24px;padding:26px 20px;box-shadow:0 24px 70px rgba(0,0,0,.45)}
.logo{direction:ltr;text-align:center;color:#E8C547;font-size:26px;font-weight:950;letter-spacing:-.6px}.sub{text-align:center;color:#777;font-size:13px;margin:7px 0 24px}
label{display:block;color:#777;font-size:12px;font-weight:800;margin:15px 2px 7px}input{width:100%;border:1px solid #292929;background:#090909;color:#fff;border-radius:14px;padding:15px;font-size:16px;outline:none;direction:ltr}input:focus{border-color:#E8C547}
button{width:100%;margin-top:22px;border:0;border-radius:14px;background:#E8C547;color:#080808;padding:16px;font-size:16px;font-weight:950;cursor:pointer}.error{background:#301515;border:1px solid #5c2626;color:#ffb4b4;border-radius:12px;padding:11px;text-align:center;font-size:13px;margin-bottom:14px}.lock{text-align:center;font-size:38px;margin-bottom:8px}
</style>
</head>
<body>
<form class="login" method="post" action="/login" autocomplete="on">
<div class="lock">🔐</div>
<div class="logo">BLACKI STORE</div>
<div class="sub">سجّل الدخول لفتح المتجر</div>
{{ERROR}}
<label for="username">اسم المستخدم</label>
<input id="username" name="username" type="text" autocomplete="username" required autofocus>
<label for="password">كلمة المرور</label>
<input id="password" name="password" type="password" autocomplete="current-password" required>
<button type="submit">دخول</button>
</form>
</body>
</html>"""


def _b64encode(value):
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def make_session_token():
    expires = int(time.time()) + SESSION_SECONDS
    payload = f"{AUTH_USERNAME}|{expires}|{secrets.token_hex(12)}".encode("utf-8")
    payload_text = _b64encode(payload)
    signature = hmac.new(AUTH_SECRET.encode("utf-8"), payload_text.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload_text}.{signature}"


def valid_session_token(token):
    try:
        payload_text, signature = token.rsplit(".", 1)
        expected = hmac.new(AUTH_SECRET.encode("utf-8"), payload_text.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        username, expires, _nonce = _b64decode(payload_text).decode("utf-8").split("|", 2)
        return hmac.compare_digest(username, AUTH_USERNAME) and int(expires) >= int(time.time())
    except (ValueError, TypeError, UnicodeDecodeError):
        return False


def cookie_is_secure():
    explicit = os.environ.get("BLACKI_COOKIE_SECURE")
    if explicit is not None:
        return explicit.strip().lower() not in ("0", "false", "no", "off")
    return bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PUBLIC_DOMAIN"))


def safe_image_path(raw_path):
    """Resolve old Windows image paths and new relative image paths inside blacki_data/images."""
    if not raw_path:
        return None
    decoded = urllib.parse.unquote(str(raw_path)).replace("\\", "/")
    filename = decoded.rsplit("/", 1)[-1]
    if not filename or filename in (".", ".."):
        return None
    candidate = os.path.abspath(os.path.join(DATA, "images", filename))
    image_root = os.path.abspath(os.path.join(DATA, "images"))
    try:
        if os.path.commonpath([candidate, image_root]) != image_root:
            return None
    except ValueError:
        return None
    return candidate if os.path.isfile(candidate) else None


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # quiet

    def send_bytes(self, status, content_type, data, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
        if extra_headers:
            for name, value in extra_headers:
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location, cookie_header=None):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        if cookie_header:
            self.send_header("Set-Cookie", cookie_header)
        self.end_headers()

    def authenticated(self):
        raw_cookie = self.headers.get("Cookie", "")
        jar = cookies.SimpleCookie()
        try:
            jar.load(raw_cookie)
        except cookies.CookieError:
            return False
        morsel = jar.get(COOKIE_NAME)
        return bool(morsel and valid_session_token(morsel.value))

    def require_auth(self):
        if self.authenticated():
            return True
        if self.path.startswith("/api/") or self.command in ("POST", "DELETE"):
            self.send_bytes(401, "application/json; charset=utf-8", b'{"error":"login required"}')
        else:
            self.redirect("/login")
        return False

    def show_login(self, error=False):
        message = '<div class="error">اسم المستخدم أو كلمة المرور غير صحيحة</div>' if error else ""
        page = LOGIN_HTML.replace("{{ERROR}}", message).encode("utf-8")
        self.send_bytes(200, "text/html; charset=utf-8", page, [("Cache-Control", "no-store")])

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/health":
            self.send_bytes(200, "text/plain; charset=utf-8", b"ok")
            return
        if path == "/robots.txt":
            self.send_bytes(200, "text/plain; charset=utf-8", b"User-agent: *\nDisallow: /\n")
            return
        if path == "/login":
            if self.authenticated():
                self.redirect("/")
            else:
                self.show_login(error=False)
            return
        if path == "/logout":
            cookie = f"{COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict"
            if cookie_is_secure():
                cookie += "; Secure"
            self.redirect("/login", cookie)
            return
        if not self.require_auth():
            return
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))

        elif self.path == "/api/products":
            prods = load_products()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(prods, ensure_ascii=False).encode("utf-8"))

        elif self.path == "/api/sales":
            sales = load_sales()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(sales, ensure_ascii=False).encode("utf-8"))

        elif self.path == "/icon.png":
            icon_path = os.path.join(BASE, "icon.png")
            if os.path.exists(icon_path):
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "max-age=604800")
                self.end_headers()
                with open(icon_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()

        elif self.path.startswith("/img?"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            img_path = safe_image_path(params.get("path", [""])[0])
            if img_path:
                try:
                    from PIL import Image as PILImage
                    import io
                    img = PILImage.open(img_path)
                    # Resize large images for faster loading
                    max_size = 800
                    if img.width > max_size or img.height > max_size:
                        img.thumbnail((max_size, max_size))
                    buf = io.BytesIO()
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    img.save(buf, "JPEG", quality=75, optimize=True)
                    data = buf.getvalue()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Cache-Control", "max-age=604800")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except:
                    # Fallback: serve raw file
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Cache-Control", "max-age=604800")
                    self.end_headers()
                    with open(img_path, "rb") as f:
                        self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()

        elif self.path.startswith("/img-full?"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            img_path = safe_image_path(params.get("path", [""])[0])
            if img_path:
                ext = os.path.splitext(img_path)[1].lower()
                ct = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                      ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
                self.send_response(200)
                self.send_header("Content-Type", ct.get(ext, "image/jpeg"))
                self.end_headers()
                with open(img_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/login":
            length = min(int(self.headers.get("Content-Length", 0)), 8192)
            form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
            username = form.get("username", [""])[0]
            password = form.get("password", [""])[0]
            valid_user = hmac.compare_digest(username, AUTH_USERNAME)
            valid_password = hmac.compare_digest(password, AUTH_PASSWORD)
            if valid_user and valid_password:
                cookie = f"{COOKIE_NAME}={make_session_token()}; Path=/; Max-Age={SESSION_SECONDS}; HttpOnly; SameSite=Strict"
                if cookie_is_secure():
                    cookie += "; Secure"
                self.redirect("/", cookie)
            else:
                self.show_login(error=True)
            return
        if not self.require_auth():
            return
        if self.path == "/api/products":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            product = json.loads(body)
            prods = load_products()
            # Update or add
            found = False
            for i, p in enumerate(prods):
                if p["id"] == product["id"]:
                    prods[i] = product
                    found = True
                    break
            if not found:
                prods.insert(0, product)
            save_products(prods)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        elif self.path == "/api/sales":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            sale = json.loads(body)
            sales = load_sales()
            found = False
            for i, existing in enumerate(sales):
                if existing.get("id") == sale.get("id"):
                    sales[i] = sale
                    found = True
                    break
            if not found:
                sales.insert(0, sale)
            save_sales(sales)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        elif self.path == "/api/upload":
            content_type = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            # Parse multipart
            boundary = content_type.split("boundary=")[1].encode()
            parts = body.split(b"--" + boundary)
            for part in parts:
                if b"filename=" in part:
                    header_end = part.index(b"\r\n\r\n") + 4
                    file_data = part[header_end:].rstrip(b"\r\n--")
                    # Get filename
                    header = part[:header_end].decode("utf-8", errors="replace")
                    fn = "upload.jpg"
                    if 'filename="' in header:
                        fn = header.split('filename="')[1].split('"')[0]
                    import uuid
                    ext = os.path.splitext(fn)[1] or ".jpg"
                    new_name = uuid.uuid4().hex + ext
                    dest = os.path.join(DATA, "images", new_name)
                    os.makedirs(os.path.join(DATA, "images"), exist_ok=True)
                    with open(dest, "wb") as f:
                        f.write(file_data)

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"path": "images/" + new_name}).encode("utf-8"))
                    return

            self.send_response(400)
            self.end_headers()

    def do_DELETE(self):
        if not self.require_auth():
            return
        if self.path.startswith("/api/products/"):
            pid = self.path.split("/")[-1]
            prods = load_products()
            prods = [p for p in prods if p["id"] != pid]
            save_products(prods)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        elif self.path.startswith("/api/sales/"):
            sid = urllib.parse.unquote(self.path.split("/")[-1])
            sales = load_sales()
            sales = [sale for sale in sales if sale.get("id") != sid]
            save_sales(sales)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')


if __name__ == "__main__":
    ip = get_local_ip()
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("=" * 50)
    print("   BLACKI STORE - NEW SALE EDIT BUILD 2026")
    print("=" * 50)
    print("   RUNNING FILE: blacki_sales_edit_NEW.py")
    print(f"   DATA FOLDER: {DATA}")
    print("   BUILD: NEW SALE EDIT BUILD 2026")
    print()
    print(f"   Open this on your phone:")
    print(f"   http://{ip}:{PORT}")
    print()
    print("   Keep this window open!")
    print("   Press Ctrl+C to stop")
    print("=" * 50)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
