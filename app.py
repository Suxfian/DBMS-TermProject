from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import psycopg2
from psycopg2 import errors
from werkzeug.security import check_password_hash, generate_password_hash
from cryptography.fernet import Fernet  
from authlib.integrations.flask_client import OAuth
import random
import datetime
import time
import os
import pandas as pd
import io
import json
import re  # Şifre kontrolü için eklendi

app = Flask(__name__)

# Google OAuth Ayarları
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id='XXXXXXXXXXXXXXXXXXX',
    client_secret='XXXXXXXXXXXXXXXXXXXXXX',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

app.secret_key = 'key'

# --- AYARLAR ---
DB_HOST = "localhost"
DB_NAME = "project_db"
DB_USER = "XXXXXXXXXX"
DB_PASS = "XXXXXXXXXX" 
DB_PORT = "5432"

ENCRYPTION_KEY = b"XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX="
cipher_suite = Fernet(ENCRYPTION_KEY)

# --- YARDIMCI FONKSİYONLAR ---

def get_db_connection():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT)

def encrypt_data(data):
    if not data: return None
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(data):
    if not data: return None
    try: return cipher_suite.decrypt(data.encode()).decode()
    except: return "[Şifre Çözülemedi]"

def add_log(company_id, message, log_type="INFO"):
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("INSERT INTO system_logs (company_id, log_level, message) VALUES (%s, %s, %s)", (company_id, log_type, message))
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"Loglama Hatası: {e}")

# Şifre Güvenlik Kontrolü (YENİ)
def validate_password(password):
    if len(password) < 8:
        return False, "Şifre en az 8 karakter olmalıdır."
    if not re.search(r"[a-z]", password):
        return False, "Şifre en az bir küçük harf içermelidir."
    if not re.search(r"[A-Z]", password):
        return False, "Şifre en az bir büyük harf içermelidir."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Şifre en az bir özel karakter (!@#$%^&* vb.) içermelidir."
    return True, ""

# Yetki Kontrol Fonksiyonu
def check_access(allowed_roles):
    if 'user_id' not in session: return False
    if session['role'] == 'Super_Admin': return True
    if session['role'] in allowed_roles: return True
    return False

# ================= ROTALAR =================

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.password_hash, u.first_name, u.last_name, c.id, c.name, r.name 
            FROM users u 
            JOIN user_company uc ON u.id = uc.usersid 
            JOIN companies c ON uc.companyid = c.id 
            JOIN user_company_roles ucr ON uc.id = ucr.user_companyid 
            JOIN roles r ON ucr.rolesid = r.id 
            WHERE u.email_address = %s AND u.is_deleted IS FALSE AND c.is_deleted IS FALSE
        """, (request.form['email'],))
        user = cur.fetchone()
        
        if user and check_password_hash(user[1], request.form['password']):
            session['user_id'] = user[0]
            session['full_name'] = f"{user[2]} {user[3]}"
            session['company_id'] = user[4]
            session['company_name'] = user[5]
            session['role'] = user[6]
            
            user_ip = request.remote_addr
            cur.execute("UPDATE users SET last_login = NOW(), last_ip = %s WHERE id = %s", (user_ip, user[0]))
            conn.commit()
            add_log(user[4], f"Giriş yapıldı: {user[2]} {user[3]} ({session['role']})", "SUCCESS")
            flash(f"Hoş geldiniz {session['full_name']}.", "success")
            cur.close(); conn.close()
            return redirect(url_for('dashboard'))
        
        cur.close(); conn.close()
        flash('❌ Hatalı giriş.', 'error')
    return render_template('login.html')

@app.route('/login/google')
def google_login():
    redirect_uri = url_for('google_authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/login/google/callback')
def google_authorize():
    try:
        token = google.authorize_access_token()
        user_info = google.userinfo()
        email = user_info['email']

        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.first_name, u.last_name, c.id, c.name, r.name 
            FROM users u 
            JOIN user_company uc ON u.id = uc.usersid 
            JOIN companies c ON uc.companyid = c.id 
            JOIN user_company_roles ucr ON uc.id = ucr.user_companyid 
            JOIN roles r ON ucr.rolesid = r.id 
            WHERE u.email_address = %s AND u.is_deleted IS FALSE
        """, (email,))
        user = cur.fetchone()
        cur.close(); conn.close()

        if user:
            session['user_id'] = user[0]
            session['full_name'] = f"{user[1]} {user[2]}"
            session['company_id'] = user[3]
            session['company_name'] = user[4]
            session['role'] = user[5]
            add_log(user[3], f"Google ile Giriş: {email}", "SUCCESS")
            flash(f"Hoş geldiniz {session['full_name']}", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("⛔ Bu Google hesabı sistemde kayıtlı değil.", "error")
            return redirect(url_for('login'))
    except Exception as e:
        flash(f"Google Giriş Hatası: {str(e)}", "error")
        return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection(); cur = conn.cursor()
    
    if session['role'] == 'Super_Admin':
        cur.execute("SELECT c.id, c.name, c.tax_number, c.created_at, COUNT(uc.usersid) FROM companies c LEFT JOIN user_company uc ON c.id = uc.companyid WHERE c.is_deleted IS FALSE GROUP BY c.id ORDER BY c.created_at DESC")
        data = cur.fetchall()
        cur.close(); conn.close()
        return render_template('super_admin_dashboard.html', companies=data, user_name=session['full_name'], company_name=session['company_name'], role=session['role'])
    else:
        cid = session['company_id']
        pending = 0; critical = 0; sku = 0; rev = 0
        
        if session['role'] != 'Muhasebe_Gorevlisi':
            cur.execute("SELECT COUNT(*) FROM orders WHERE company_id = %s AND status < 200 AND is_deleted IS FALSE", (cid,))
            pending = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM inventory_stocks s JOIN inventories i ON s.inventoriesid = i.id WHERE i.company_id = %s AND s.quantity <= 10 AND i.is_deleted IS FALSE", (cid,))
            critical = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM products WHERE company_id = %s AND is_deleted IS FALSE", (cid,))
            sku = cur.fetchone()[0]

        if session['role'] != 'Depo_Gorevlisi':
            cur.execute("SELECT COALESCE(SUM(total_price_amount), 0) FROM orders WHERE company_id = %s AND status = 300 AND is_deleted IS FALSE", (cid,))
            rev = cur.fetchone()[0]
        
        cur.execute("SELECT marketplace FROM marketplace_stores WHERE company_id = %s AND is_deleted IS FALSE", (cid,))
        stores = [r[0] for r in cur.fetchall()]
        
        products_data = []
        if session['role'] != 'Muhasebe_Gorevlisi':
            cur.execute("SELECT billing_name, list_price FROM products WHERE company_id = %s AND is_deleted IS FALSE ORDER BY created_at DESC LIMIT 100", (cid,))
            products_data = [{'name': r[0], 'price': float(r[1] if r[1] else 0)} for r in cur.fetchall()]
        
        cur.close(); conn.close()
        return render_template('index.html', products=products_data, pending_count=pending, critical_stock=critical, total_sku=sku, total_revenue=rev, connected_stores=stores, user_name=session['full_name'], company_name=session['company_name'], role=session['role'])

@app.route('/api/get_logs')
def get_logs():
    if 'user_id' not in session: return jsonify([])
    if session['role'] not in ['Sirket_Admin', 'Super_Admin']: return jsonify([])
    cid = str(session['company_id']); conn = get_db_connection(); cur = conn.cursor()
    if session['role'] == 'Super_Admin':
        cur.execute("SELECT to_char(created_at, 'HH24:MI:SS'), message, log_level FROM system_logs ORDER BY created_at DESC LIMIT 20")
    else:
        cur.execute("SELECT to_char(created_at, 'HH24:MI:SS'), message, log_level FROM system_logs WHERE company_id = %s ORDER BY created_at DESC LIMIT 20", (cid,))
    logs = [{'time': r[0], 'message': r[1], 'type': r[2]} for r in cur.fetchall()]
    cur.close(); conn.close()
    return jsonify(logs)

@app.route('/api/dashboard_charts')
def dashboard_charts():
    if 'user_id' not in session: return jsonify({})
    if session['role'] == 'Depo_Gorevlisi': return jsonify({}) 
    cid = session['company_id']; conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT day_label, total_revenue FROM view_dashboard_daily_sales WHERE company_id = %s AND exact_date >= NOW() - INTERVAL '7 days' ORDER BY exact_date ASC", (cid,))
    sales_data = cur.fetchall()
    cur.execute("SELECT platform_name, usage_count FROM view_dashboard_platform_stats WHERE company_id = %s", (cid,))
    platform_data = cur.fetchall()
    cur.close(); conn.close()
    return jsonify({'sales_labels': [r[0] for r in sales_data], 'sales_values': [float(r[1]) for r in sales_data], 'platform_labels': [r[0] for r in platform_data], 'platform_values': [r[1] for r in platform_data]})

# --- ÜRÜN & STOK YÖNETİMİ ---
@app.route('/products')
def products():
    if 'user_id' not in session: return redirect(url_for('login'))
    if not check_access(['Sirket_Admin', 'Depo_Gorevlisi']): 
        flash("⛔ Bu sayfaya erişim yetkiniz yok.", "error"); return redirect(url_for('dashboard'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.billing_name, p.gtin, s.quantity, i.id, p.list_price, p.mpn_id, i.width, i.height, i.length, i.weight,
        (SELECT json_agg(json_build_object('name', p2.billing_name, 'qty', t.child_quantity, 'child_inv_id', i2.id)) FROM inventory_trees t JOIN inventories i2 ON t.inventoriesid2 = i2.id JOIN products p2 ON i2.id = p2.inventoriesid WHERE t.inventoriesid = i.id AND t.is_deleted IS FALSE) as children,
        (SELECT p3.billing_name FROM inventory_trees t2 JOIN inventories i3 ON t2.inventoriesid = i3.id JOIN products p3 ON i3.id = p3.inventoriesid WHERE t2.inventoriesid2 = i.id AND t2.is_deleted IS FALSE LIMIT 1) as parent_name
        FROM products p JOIN inventories i ON p.inventoriesid = i.id JOIN inventory_stocks s ON i.id = s.inventoriesid WHERE p.company_id = %s AND p.is_deleted IS FALSE ORDER BY p.created_at DESC
    """, (session['company_id'],))
    data = cur.fetchall(); cur.close(); conn.close()
    products_list = [{'id': row[0], 'name': row[1], 'sku': row[2], 'stock': row[3], 'inv_id': row[4], 'price': row[5] if row[5] else 0, 'mpn': row[6] if row[6] else '', 'dims': f"{row[7] or 0}x{row[8] or 0}x{row[9] or 0} cm / {row[10] or 0} kg", 'raw_dims': {'w': row[7], 'h': row[8], 'l': row[9], 'kg': row[10]}, 'children': row[11], 'parent': row[12], 'is_bundle': True if row[11] else False} for row in data]
    return render_template('products.html', products=products_list, user_name=session['full_name'], company_name=session['company_name'], role=session['role'])

@app.route('/add_product', methods=['POST'])
def add_product():
    if not check_access(['Sirket_Admin', 'Depo_Gorevlisi']): return redirect(url_for('dashboard'))
    cid = session['company_id']; name = request.form['name']; sku = request.form['sku']; mpn = request.form.get('mpn', ''); stock = request.form['stock']; price = request.form.get('price', 0)
    w = request.form.get('width') or 0; h = request.form.get('height') or 0; l = request.form.get('length') or 0; kg = request.form.get('weight') or 0
    try: vol_desi = (float(w) * float(h) * float(l)) / 3000
    except: vol_desi = 0
    conn = get_db_connection(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO inventories (company_id, name, sku_id, width, height, length, weight, volume_in_decimeter) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id", (cid, name, sku, w, h, l, kg, vol_desi)); inv_id = cur.fetchone()[0]
        cur.execute("INSERT INTO products (company_id, inventoriesid, billing_name, gtin, mpn_id, list_price) VALUES (%s, %s, %s, %s, %s, %s)", (cid, inv_id, name, sku, mpn, price))
        cur.execute("SELECT id FROM stock_types WHERE company_id = %s AND name = 'Sağlam' LIMIT 1", (cid,)); row = cur.fetchone(); stid = row[0] if row else cur.execute("INSERT INTO stock_types (name, company_id) VALUES ('Sağlam', %s) RETURNING id", (cid,)).fetchone()[0]
        cur.execute("INSERT INTO inventory_stocks (inventoriesid, stock_typesid, quantity) VALUES (%s, %s, %s)", (inv_id, stid, stock))
        conn.commit(); add_log(cid, f"Ürün Eklendi: {name}", "SUCCESS"); flash("✅ Ürün eklendi.", "success")
    except Exception as e: conn.rollback(); flash(f"Hata: {str(e)}", "error")
    cur.close(); conn.close(); return redirect(url_for('products'))

@app.route('/edit_product', methods=['POST'])
def edit_product():
    if not check_access(['Sirket_Admin', 'Depo_Gorevlisi']): return redirect(url_for('dashboard'))
    prod_id = request.form['prod_id']; inv_id = request.form['inv_id']; w = request.form.get('width') or 0; h = request.form.get('height') or 0; l = request.form.get('length') or 0; kg = request.form.get('weight') or 0
    try: vol_desi = (float(w) * float(h) * float(l)) / 3000
    except: vol_desi = 0
    conn = get_db_connection(); cur = conn.cursor()
    try: 
        cur.execute("UPDATE products SET billing_name=%s, gtin=%s, mpn_id=%s, list_price=%s WHERE id=%s", (request.form['name'], request.form['sku'], request.form.get('mpn'), request.form.get('price'), prod_id))
        cur.execute("UPDATE inventories SET name=%s, width=%s, height=%s, length=%s, weight=%s, volume_in_decimeter=%s WHERE id=%s", (request.form['name'], w, h, l, kg, vol_desi, inv_id))
        cur.execute("UPDATE inventory_stocks SET quantity=%s WHERE inventoriesid=%s", (request.form['stock'], inv_id))
        conn.commit(); add_log(session['company_id'], "Ürün güncellendi.", "INFO"); flash("Güncellendi", "success")
    except Exception as e: conn.rollback(); flash(str(e), "error")
    cur.close(); conn.close(); return redirect(url_for('products'))

@app.route('/delete_product/<product_id>', methods=['POST'])
def delete_product(product_id):
    if not check_access(['Sirket_Admin', 'Depo_Gorevlisi']): return redirect(url_for('dashboard'))
    conn = get_db_connection(); cur = conn.cursor()
    try: cur.execute("UPDATE products SET is_deleted = TRUE WHERE id = %s RETURNING inventoriesid", (product_id,)); inv_id = cur.fetchone()[0]; cur.execute("UPDATE inventories SET is_deleted = TRUE WHERE id = %s", (inv_id,)); conn.commit(); add_log(session['company_id'], "Ürün silindi.", "WARNING"); flash("Silindi","info")
    except: conn.rollback(); flash("Hata","error")
    cur.close(); conn.close(); return redirect(url_for('products'))

# --- SİPARİŞLER ---
@app.route('/orders')
def orders():
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("""
        SELECT c.name, o.order_number, o.customer_full_name, o.cargo_tracking_number, o.status, o.id, o.order_source 
        FROM orders o 
        JOIN companies c ON o.company_id = c.id 
        WHERE o.company_id = %s AND o.is_deleted IS FALSE 
        ORDER BY o.order_date DESC LIMIT 50
    """, (session['company_id'],))
    data = cur.fetchall()
    status_map = {100:'Yeni', 101:'Hazırlanıyor', 102:'Paketlendi', 200:'Kargolandı', 300:'Teslim Edildi', 400:'İptal'}
    orders_list = []
    for r in data:
        status_code = r[4]
        status_text = status_map.get(status_code, "Bilinmiyor")
        status_class = "bg-gray-500/20 text-gray-400"
        if status_code == 100: status_class = "bg-blue-500/20 text-blue-400"
        elif status_code == 300: status_class = "bg-green-500/20 text-green-400"
        elif status_code == 400: status_class = "bg-red-500/20 text-red-400"
        orders_list.append({'platform': r[6], 'order_no': r[1], 'customer': r[2], 'tracking': r[3], 'status': status_text, 'status_class': status_class, 'id': r[5]})
    cur.close(); conn.close()
    return render_template('orders.html', orders=orders_list, user_name=session['full_name'], company_name=session['company_name'], role=session['role'])

@app.route('/order/<order_id>', methods=['GET','POST'])
def order_detail(order_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection(); cur = conn.cursor()
    if request.method == 'POST': 
        if not check_access(['Sirket_Admin', 'Depo_Gorevlisi']):
            flash("⛔ Durum değiştirme yetkiniz yok.", "error")
        else:
            new_status = int(request.form['new_status'])
            if new_status == 200:
                fake_tracking = f"TR-{random.randint(100000,999999)}"
                cur.execute("UPDATE orders SET status=%s, cargo_tracking_number=%s WHERE id=%s", (new_status, fake_tracking, order_id))
            else:
                cur.execute("UPDATE orders SET status=%s WHERE id=%s", (new_status, order_id))
            conn.commit()
            status_msgs = {101: "Sipariş hazırlanıyor.", 200: "Sipariş kargolandı.", 300: "Sipariş teslim edildi.", 400: "Sipariş iptal edildi."}
            msg = status_msgs.get(new_status, "Sipariş durumu güncellendi.")
            add_log(session['company_id'], f"{msg} (ID: {order_id})", "INFO")
            flash(msg, "success")
            
    cur.execute("SELECT o.id, o.order_number, o.customer_full_name, o.total_price_amount, o.status, o.order_date, o.shipment_address_city, o.cargo_tracking_number, c.name, o.cargo_provider_name, o.shipment_address_full, o.shipment_address_district, o.customer_identity_number, o.shipment_package_desi FROM orders o JOIN companies c ON o.company_id = c.id WHERE o.id=%s", (order_id,)); order = cur.fetchone()
    cur.execute("SELECT p.billing_name, ol.quantity, ol.unit_price_amount, (ol.quantity*ol.unit_price_amount) FROM order_lines ol JOIN products p ON ol.productsid = p.id WHERE ol.ordersid = %s", (order_id,)); items = cur.fetchall()
    cur.execute("SELECT status, changed_at FROM order_status_history WHERE ordersid = %s ORDER BY changed_at DESC", (order_id,)); history = cur.fetchall(); cur.close(); conn.close()
    return render_template('order_detail.html', order=order, items=items, history=history, status_map={100:'Yeni', 101:'Hazırlanıyor', 102:'Paketlendi', 200:'Kargolandı', 300:'Teslim Edildi', 400:'İptal'}, user_name=session['full_name'], company_name=session['company_name'], role=session['role'])

@app.route('/integrations')
def integrations():
    if 'user_id' not in session: return redirect(url_for('login'))
    if not check_access(['Sirket_Admin']): 
        flash("⛔ Bu alan sadece Şirket Yöneticisine aittir.", "error"); return redirect(url_for('dashboard'))
    conn = get_db_connection(); cur = conn.cursor(); cid = session['company_id']
    cur.execute("SELECT id, marketplace, name FROM marketplace_stores WHERE company_id = %s AND is_deleted IS FALSE ORDER BY marketplace", (cid,))
    stores_raw = cur.fetchall(); stores = [{'id': str(r[0]), 'type': r[1], 'name': r[2]} for r in stores_raw]
    cur.execute("SELECT p.id, p.billing_name, p.gtin, s.quantity FROM products p JOIN inventory_stocks s ON p.inventoriesid = s.inventoriesid WHERE p.company_id = %s AND p.is_deleted IS FALSE ORDER BY p.created_at DESC", (cid,))
    products_raw = cur.fetchall()
    cur.execute("SELECT pp.productsid, ms.id, pp.platform_sku_id, pp.price, pp.is_active FROM product_platforms pp JOIN marketplace_stores ms ON pp.marketplace_storesid = ms.id WHERE ms.company_id = %s AND pp.is_deleted IS FALSE", (cid,))
    links_map = {}; 
    for r in cur.fetchall(): links_map[(str(r[0]), str(r[1]))] = {'code': r[2], 'price': r[3], 'active': r[4]}
    products_data = []
    for p in products_raw:
        prod_obj = {'id': str(p[0]), 'name': p[1], 'sku': p[2], 'stock': p[3], 'stores': {}}
        for s in stores: prod_obj['stores'][s['id']] = links_map.get((str(p[0]), s['id']))
        products_data.append(prod_obj)
    cur.close(); conn.close()
    return render_template('integrations.html', products=products_data, stores=stores, user_name=session['full_name'], company_name=session['company_name'], role=session['role'])

@app.route('/add_marketplace', methods=['POST'])
def add_marketplace():
    if not check_access(['Sirket_Admin']): return redirect(url_for('dashboard'))
    name = request.form['store_name']; m_type = request.form['marketplace_type']
    enc_key = encrypt_data(request.form.get('api_key', '')); enc_secret = encrypt_data(request.form.get('api_secret', '')); raw_merchant = request.form.get('merchant_id', '')
    conn = get_db_connection(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO marketplace_stores (company_id, name, marketplace, api_key_enc, api_secret_enc, merchant_id) VALUES (%s, %s, %s, %s, %s, %s)", (session['company_id'], name, m_type, enc_key, enc_secret, raw_merchant))
        conn.commit(); add_log(session['company_id'], f"Yeni Mağaza Eklendi: {name}", "INFO"); flash("✅ Mağaza güvenle eklendi.", "success")
    except Exception as e: conn.rollback(); flash(str(e), "error")
    cur.close(); conn.close(); return redirect(url_for('integrations'))

@app.route('/save_integration', methods=['POST'])
def save_integration():
    if not check_access(['Sirket_Admin']): return redirect(url_for('dashboard'))
    conn = get_db_connection(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO product_platforms (productsid, marketplace_storesid, platform_sku_id, price, is_active) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (productsid, marketplace_storesid) DO UPDATE SET platform_sku_id = EXCLUDED.platform_sku_id, price = EXCLUDED.price, is_active = EXCLUDED.is_active, is_deleted = FALSE", (request.form['product_id'], request.form['store_id'], request.form['remote_code'], request.form['price'], 'active' in request.form))
        conn.commit(); flash("✅ Güncellendi.", "success")
    except Exception as e: conn.rollback(); flash(str(e), "error")
    cur.close(); conn.close(); return redirect(url_for('integrations'))

@app.route('/bulk_link_marketplace', methods=['POST'])
def bulk_link_marketplace():
    if not check_access(['Sirket_Admin']): return redirect(url_for('dashboard'))
    store_id = request.form['bulk_store_id']; 
    try: percentage = float(request.form['price_percentage']) 
    except: percentage = 0
    conn = get_db_connection(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO product_platforms (productsid, marketplace_storesid, platform_sku_id, price, is_active) SELECT p.id, %s, p.gtin, ROUND((p.list_price * (1 + (%s::decimal / 100))), 2), TRUE FROM products p WHERE p.company_id = %s AND p.is_deleted IS FALSE AND NOT EXISTS (SELECT 1 FROM product_platforms pp WHERE pp.productsid = p.id AND pp.marketplace_storesid = %s)", (store_id, percentage, session['company_id'], store_id))
        count = cur.rowcount; conn.commit()
        add_log(session['company_id'], f"Toplu Eşleştirme: {count} ürün %{percentage} farkla bağlandı.", "INFO"); flash(f"✅ {count} ürün bağlandı.", "success")
    except Exception as e: conn.rollback(); flash(str(e), "error")
    cur.close(); conn.close(); return redirect(url_for('integrations'))

@app.route('/reports')
def reports():
    if 'user_id' not in session: return redirect(url_for('login'))
    if not check_access(['Sirket_Admin', 'Muhasebe_Gorevlisi']):
        flash("⛔ Yetkisiz Erişim.", "error"); return redirect(url_for('dashboard'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM view_detailed_sales_report WHERE company_id = %s LIMIT 100", (session['company_id'],))
    report_data = cur.fetchall()
    cur.execute("SELECT COALESCE(SUM(total_line_amount), 0) FROM view_detailed_sales_report WHERE company_id = %s AND status = 300", (session['company_id'],))
    total_sales = cur.fetchone()[0] or 0
    cur.execute("SELECT shipment_address_city, COUNT(*) as cnt FROM view_detailed_sales_report WHERE company_id = %s GROUP BY shipment_address_city ORDER BY cnt DESC LIMIT 1", (session['company_id'],))
    top_city = cur.fetchone(); top_city_name = top_city[0] if top_city else "-"
    cur.close(); conn.close()
    return render_template('reports.html', report_data=report_data, total_sales=total_sales, top_city=top_city_name, status_map={100:'Yeni', 101:'Hazırlanıyor', 102:'Paketlendi', 200:'Kargolandı', 300:'Teslim Edildi', 400:'İptal'}, user_name=session['full_name'], company_name=session['company_name'], role=session['role'])

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection(); cur = conn.cursor()
    staff = []

    if request.method == 'POST':
        action = request.form.get('action')
        
        # 1. Şifre Değiştirme (Herkes Yapabilir) - GÜVENLİK KONTROLÜ EKLENDİ
        if action == 'change_password':
            new_pass = request.form.get('new_password')
            conf_pass = request.form.get('confirm_password')
            
            # YENİ: Şifre Güvenlik Kontrolü
            is_valid, msg = validate_password(new_pass)
            
            if not is_valid:
                flash(f"❌ {msg}", "error")
            elif new_pass != conf_pass:
                flash("❌ Şifreler uyuşmuyor!", "error")
            else:
                hashed = generate_password_hash(new_pass)
                try:
                    cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hashed, session['user_id']))
                    conn.commit()
                    add_log(session['company_id'], f"Kullanıcı şifresini değiştirdi: {session['full_name']}", "INFO")
                    flash("✅ Şifreniz başarıyla güncellendi.", "success")
                except Exception as e:
                    conn.rollback()
                    flash(f"Hata: {str(e)}", "error")

        # 2. Personel Ekleme (Sadece Admin) - GÜVENLİK KONTROLÜ EKLENDİ
        elif action == 'add_staff':
            if not check_access(['Sirket_Admin']):
                flash("⛔ Bu işlem için yetkiniz yok.", "error")
            else:
                # YENİ: Şifre Güvenlik Kontrolü
                new_pass = request.form['staff_pass']
                is_valid, msg = validate_password(new_pass)
                
                if not is_valid:
                    flash(f"❌ Personel eklenemedi: {msg}", "error")
                else:
                    try:
                        cur.execute("INSERT INTO users (email_address, first_name, last_name, password_hash) VALUES (%s,%s,%s,%s) RETURNING id", (request.form['staff_email'], request.form['staff_name'], request.form['staff_surname'], generate_password_hash(new_pass))); uid=cur.fetchone()[0]
                        cur.execute("INSERT INTO user_company (usersid, companyid) VALUES (%s,%s) RETURNING id", (uid, session['company_id'])); ucid=cur.fetchone()[0]
                        cur.execute("SELECT id FROM roles WHERE name=%s",(request.form['staff_role'],)); rid=cur.fetchone()[0]
                        cur.execute("INSERT INTO user_company_roles (user_companyid, rolesid) VALUES (%s,%s)", (ucid, rid)); conn.commit(); flash("✅ Personel eklendi.", "success")
                    except Exception as e: conn.rollback(); flash(f"Hata: {str(e)}", "error")

        # 3. Yedek Alma (Sadece Admin)
        elif action == 'backup_db':
            if not check_access(['Sirket_Admin']):
                flash("⛔ Yetkisiz işlem.", "error")
            else:
                cid = session['company_id']; backup_data = {}
                cur.execute("SELECT billing_name, gtin, list_price FROM products WHERE company_id = %s", (cid,)); backup_data['products'] = cur.fetchall()
                cur.execute("SELECT order_number, customer_full_name, total_price_amount, order_date FROM orders WHERE company_id = %s", (cid,)); backup_data['orders'] = cur.fetchall()
                mem = io.BytesIO(); mem.write(json.dumps(backup_data, default=str, indent=4).encode('utf-8')); mem.seek(0)
                conn.close(); return send_file(mem, as_attachment=True, download_name=f"backup_{cid}_{int(time.time())}.json", mimetype='application/json')
        
        # 4. Önbellek Temizle (Sadece Admin)
        elif action == 'clear_cache':
            if not check_access(['Sirket_Admin']):
                flash("⛔ Yetkisiz işlem.", "error")
            else:
                cur.execute("DELETE FROM system_logs WHERE company_id = %s", (session['company_id'],)); conn.commit(); flash("✅ Sistem önbelleği ve eski loglar temizlendi.", "success")

    # Personel Listesi
    if check_access(['Sirket_Admin']):
        cur.execute("SELECT u.first_name, u.last_name, u.email_address, r.name, u.created_at, u.id FROM users u JOIN user_company uc ON u.id=uc.usersid JOIN user_company_roles ucr ON uc.id=ucr.user_companyid JOIN roles r ON ucr.rolesid=r.id WHERE uc.companyid=%s AND u.is_deleted IS FALSE", (session['company_id'],))
        staff = cur.fetchall()
    
    cur.close(); conn.close()
    return render_template('settings.html', user_name=session['full_name'], company_name=session['company_name'], role=session['role'], settings={"maintenance_mode":False}, staff_list=staff, user_id=session['user_id'])

# --- Simülasyon Rotaları ---
@app.route('/simulate_products', methods=['POST'])
def simulate_products():
    if not check_access(['Sirket_Admin', 'Depo_Gorevlisi']): return redirect(url_for('dashboard'))
    cid = session['company_id']; conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT id FROM stock_types WHERE company_id = %s AND name = 'Sağlam' LIMIT 1", (cid,))
    row = cur.fetchone(); stid = row[0] if row else cur.execute("INSERT INTO stock_types (name, company_id) VALUES ('Sağlam', %s) RETURNING id", (cid,)).fetchone()[0]
    brands = ["Asus", "Logitech", "Samsung", "Dell", "Razer", "MSI", "Apple", "Sony", "Philips", "Canon"]
    types = ["Gaming Laptop", "Kablosuz Mouse", "Mekanik Klavye", "27' Monitör", "Bluetooth Kulaklık", "Akıllı Saat", "Tablet", "Webcam", "Yazıcı", "SSD Disk"]
    generated_count = 0
    for _ in range(5):
        brand = random.choice(brands); prod_type = random.choice(types); name = f"{brand} {prod_type} {random.randint(100, 900)} Serisi"
        price = round(random.uniform(500, 35000), 2); stock = random.randint(50, 200); sku = f"SKU-{random.randint(10000, 99999)}"
        w, h, l, kg = random.randint(10,50), random.randint(5,30), random.randint(20,60), random.randint(1,5); vol_desi = (w * h * l) / 3000
        try:
            cur.execute("INSERT INTO inventories (company_id, name, sku_id, width, height, length, weight, volume_in_decimeter) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id", (cid, name, sku, w, h, l, kg, vol_desi)); inv_id = cur.fetchone()[0]
            cur.execute("INSERT INTO products (company_id, inventoriesid, billing_name, gtin, list_price) VALUES (%s, %s, %s, %s, %s)", (cid, inv_id, name, sku, price))
            cur.execute("INSERT INTO inventory_stocks (inventoriesid, stock_typesid, quantity) VALUES (%s, %s, %s)", (inv_id, stid, stock)); generated_count += 1
        except Exception as e: print(f"Simülasyon Hatası: {e}")
    conn.commit(); add_log(cid, f"Simülasyon: {generated_count} yeni ürün eklendi.", "INFO"); flash(f"✅ {generated_count} adet rastgele ürün stoğa eklendi.", "success"); cur.close(); conn.close(); return redirect(url_for('dashboard'))

@app.route('/simulate_history', methods=['POST'])
def simulate_history():
    if not check_access(['Sirket_Admin']): return redirect(url_for('dashboard'))
    cid = session['company_id']; conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT p.id, p.billing_name, p.list_price FROM products p WHERE p.company_id = %s AND p.is_deleted IS FALSE", (cid,))
    products = cur.fetchall()
    if not products: flash("❌ Envanterde ürün yok! Önce ürün ekleyin.", "error"); return redirect(url_for('dashboard'))
    
    customers = ["Ahmet Yılmaz", "Ayşe Demir", "Mehmet Kaya", "Fatma Çelik", "Ali Koç", "Zeynep Şen"]
    cities = ["İstanbul", "Ankara", "İzmir", "Bursa", "Antalya"]
    cargo_firms = ["Yurtiçi Kargo", "Aras Kargo", "MNG Kargo", "Trendyol Express"]
    sources = ["Trendyol", "Hepsiburada", "N11", "Web"]

    created_orders = 0
    for _ in range(10): 
        prod = random.choice(products); prod_id, prod_name, list_price = prod[0], prod[1], float(prod[2]) if prod[2] else 100.0
        days_ago = random.randint(0, 7); random_date = datetime.datetime.now() - datetime.timedelta(days=days_ago)
        status = random.choice([101, 200, 300, 300, 300]); order_num = f"HIS-{random.randint(10000,99999)}-{random.randint(10,99)}"
        source = random.choice(sources); cargo = random.choice(cargo_firms)
        try:
            cur.execute("INSERT INTO orders (company_id, order_number, customer_full_name, total_price_amount, status, cargo_provider_name, order_source, order_date, shipment_address_city, shipment_address_full, customer_identity_number, shipment_package_desi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Simülasyon Mah.', '11111111111', 1) RETURNING id", (cid, order_num, random.choice(customers), list_price, status, cargo, source, random_date, random.choice(cities))); oid = cur.fetchone()[0]
            cur.execute("INSERT INTO order_lines (ordersid, productsid, product_name, quantity, unit_price_amount) VALUES (%s, %s, %s, 1, %s)", (oid, prod_id, prod_name, list_price)); created_orders += 1
        except Exception as e: print(e)
    conn.commit(); add_log(cid, f"Geçmiş Veri: {created_orders} sipariş üretildi.", "SUCCESS"); flash(f"✅ Geçmişe dönük {created_orders} adet sipariş oluşturuldu.", "success"); cur.close(); conn.close(); return redirect(url_for('dashboard'))

@app.route('/simulate_order', methods=['POST'])
def simulate_order():
    if 'user_id' not in session: return jsonify({'status': 'error', 'message': 'Oturum kapalı'})
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("""SELECT p.id, p.billing_name, p.list_price FROM products p JOIN inventory_stocks s ON p.inventoriesid = s.inventoriesid JOIN stock_types st ON s.stock_typesid = st.id WHERE p.company_id = %s AND p.is_deleted IS FALSE AND s.quantity > 0 AND st.name = 'Sağlam' ORDER BY RANDOM() LIMIT 1""", (session['company_id'],)); prod = cur.fetchone()
    if prod:
        source = request.json.get('source', 'Web') if request.is_json else request.form.get('source', 'Web')
        cust = random.choice(["Ahmet Y.", "Ayşe D.", "Mehmet K.", "Fatma Ç."]); price = float(prod[2]) if prod[2] else 100.0; order_num = f"{source[:2]}-{random.randint(1000,9999)}-{int(time.time())}"
        cargo_firm = random.choice(["Yurtiçi Kargo", "Aras Kargo", "MNG Kargo", "Sürat Kargo"])
        try:
            cur.execute("INSERT INTO orders (company_id, order_number, customer_full_name, total_price_amount, status, cargo_provider_name, order_source, order_date, shipment_address_city, shipment_address_full, customer_identity_number, shipment_package_desi) VALUES (%s, %s, %s, %s, 100, %s, %s, NOW(), 'İstanbul', 'Canlı Mah.', '111', 1) RETURNING id", (session['company_id'], order_num, cust, price, cargo_firm, source)); oid = cur.fetchone()[0]
            cur.execute("INSERT INTO order_lines (ordersid, productsid, product_name, quantity, unit_price_amount) VALUES (%s, %s, %s, 1, %s)", (oid, prod[0], prod[1], price))
            conn.commit(); add_log(session['company_id'], f"Sipariş Geldi ({source}): {prod[1]}", "SUCCESS"); cur.close(); conn.close(); return jsonify({'status': 'success', 'product_name': prod[1], 'price': price, 'customer': cust, 'source': source})
        except Exception as e: cur.close(); conn.close(); return jsonify({'status': 'error', 'message': str(e)})
    else: cur.close(); conn.close(); return jsonify({'status': 'error', 'message': 'Stokta satılabilir ürün bulunamadı!'})

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
@app.route('/export_products')
def export_products():
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection(); df = pd.read_sql_query("SELECT p.billing_name as \"Urun Adi\", p.gtin as \"Barkod\", s.quantity as \"Stok\" FROM products p JOIN inventory_stocks s ON p.inventoriesid = s.inventoriesid WHERE p.company_id = %s", conn, params=(session['company_id'],)); conn.close()
    output = io.BytesIO(); 
    with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False); output.seek(0)
    return send_file(output, as_attachment=True, download_name="urunler.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/import_products', methods=['POST'])
def import_products():
    if not check_access(['Sirket_Admin', 'Depo_Gorevlisi']): return redirect(url_for('dashboard'))
    try:
        df = pd.read_excel(request.files['excel_file']); cid = session['company_id']; conn = get_db_connection(); cur = conn.cursor()
        cur.execute("SELECT id FROM stock_types WHERE company_id = %s AND name = 'Sağlam' LIMIT 1", (cid,))
        row = cur.fetchone(); stid = row[0] if row else cur.execute("INSERT INTO stock_types (name, company_id) VALUES ('Sağlam', %s) RETURNING id", (cid,)).fetchone()[0]
        for i, row in df.iterrows():
            cur.execute("INSERT INTO inventories (company_id, name, sku_id) VALUES (%s, %s, %s) RETURNING id", (cid, row['Urun Adi'], row['Barkod'])); inv_id = cur.fetchone()[0]
            cur.execute("INSERT INTO products (company_id, inventoriesid, billing_name, gtin) VALUES (%s, %s, %s, %s)", (cid, inv_id, row['Urun Adi'], row['Barkod']))
            cur.execute("INSERT INTO inventory_stocks (inventoriesid, stock_typesid, quantity) VALUES (%s, %s, %s)", (inv_id, stid, row['Stok']))
        conn.commit(); add_log(cid, "Excel ile toplu ürün yüklendi.", "INFO"); flash("✅ Yüklendi.", "success")
    except Exception as e: conn.rollback(); flash(str(e), "error")
    cur.close(); conn.close(); return redirect(url_for('products'))

@app.route('/invoice/<order_id>')
def invoice(order_id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT o.id, o.order_number, o.customer_full_name, o.total_price_amount, o.order_date, o.shipment_address_city, c.name, c.tax_number FROM orders o JOIN companies c ON o.company_id=c.id WHERE o.id=%s", (order_id,)); order=cur.fetchone()
    cur.execute("SELECT p.billing_name, ol.quantity, ol.unit_price_amount, (ol.quantity*ol.unit_price_amount) FROM order_lines ol JOIN products p ON ol.productsid=p.id WHERE ol.ordersid=%s", (order_id,)); items=cur.fetchall(); cur.close(); conn.close()
    return render_template('invoice.html', order=order, items=items)

@app.route('/delete_staff/<user_id>', methods=['POST'])
def delete_staff(user_id):
    conn = get_db_connection(); cur = conn.cursor()
    try: cur.execute("UPDATE users SET is_deleted=TRUE WHERE id=%s", (user_id,)); conn.commit()
    except: conn.rollback()
    cur.close(); conn.close(); return redirect(url_for('settings'))

@app.route('/create_company', methods=['POST'])
def create_company():
    # YENİ: Şirket oluştururken de şifre kontrolü
    is_valid, msg = validate_password(request.form['admin_pass'])
    if not is_valid:
        flash(f"❌ Şirket oluşturulamadı: {msg}", "error")
        return redirect(url_for('dashboard'))

    conn = get_db_connection(); cur = conn.cursor()
    try: cur.execute("CALL sp_create_company(%s, %s, %s, %s, %s, %s)", (request.form['comp_name'], request.form['tax_no'], request.form['admin_email'], generate_password_hash(request.form['admin_pass']), 'Firma', 'Yöneticisi')); conn.commit(); flash("✅ Şirket oluşturuldu.", "success")
    except Exception as e: conn.rollback(); flash(str(e), "error")
    cur.close(); conn.close(); return redirect(url_for('dashboard'))

@app.route('/edit_company', methods=['POST'])
def edit_company():
    conn = get_db_connection(); cur = conn.cursor()
    try: cur.execute("UPDATE companies SET name=%s WHERE id=%s", (request.form['edit_comp_name'], request.form['comp_id'])); conn.commit()
    except: conn.rollback()
    cur.close(); conn.close(); return redirect(url_for('dashboard'))

@app.route('/delete_company/<company_id>', methods=['POST'])
def delete_company(company_id):
    conn = get_db_connection(); cur = conn.cursor()
    try: cur.execute("UPDATE companies SET is_deleted=TRUE WHERE id=%s", (company_id,)); conn.commit()
    except: conn.rollback()
    cur.close(); conn.close(); return redirect(url_for('dashboard'))

@app.route('/create_bundle', methods=['POST'])
def create_bundle():
    if not check_access(['Sirket_Admin', 'Depo_Gorevlisi']): return redirect(url_for('dashboard'))
    parent_prod_id = request.form.get('parent_product_id'); child_sku = request.form.get('child_sku', '').strip()
    try: qty = int(request.form.get('quantity'))
    except: qty = 1
    conn = get_db_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT inventoriesid, billing_name FROM products WHERE id = %s", (parent_prod_id,)); parent_res = cur.fetchone(); parent_inv_id = parent_res[0]; parent_name = parent_res[1]
        cur.execute("SELECT inventoriesid, id, billing_name FROM products WHERE lower(gtin) = lower(%s) AND company_id = %s AND is_deleted IS FALSE", (child_sku, session['company_id'])); child_res = cur.fetchone()
        if not child_res: flash(f"❌ '{child_sku}' bulunamadı.", "error")
        elif str(child_res[0]) == str(parent_inv_id): flash("❌ Kendi kendine set olamaz.", "error")
        else: cur.execute("INSERT INTO inventory_trees (inventoriesid, inventoriesid2, child_quantity) VALUES (%s, %s, %s) ON CONFLICT (inventoriesid, inventoriesid2) DO UPDATE SET child_quantity = EXCLUDED.child_quantity, is_deleted = FALSE", (parent_inv_id, child_res[0], qty)); conn.commit(); add_log(session['company_id'], f"Set güncellendi: {parent_name}", "INFO"); flash(f"✅ Set içeriği eklendi.", "success")
    except Exception as e: conn.rollback(); flash(f"Hata: {str(e)}", "error")
    cur.close(); conn.close(); return redirect(url_for('products'))

@app.route('/remove_from_bundle', methods=['POST'])
def remove_from_bundle():
    if not check_access(['Sirket_Admin', 'Depo_Gorevlisi']): return redirect(url_for('dashboard'))
    conn = get_db_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT inventoriesid FROM products WHERE id = %s", (request.form['parent_prod_id'],)); parent_inv_id = cur.fetchone()[0]
        cur.execute("UPDATE inventory_trees SET is_deleted = TRUE WHERE inventoriesid = %s AND inventoriesid2 = %s", (parent_inv_id, request.form['child_inv_id']))
        conn.commit(); add_log(session['company_id'], "Set içeriği silindi.", "WARNING"); flash("✅ Parça setten çıkarıldı.", "info")
    except Exception as e: conn.rollback(); flash(str(e), "error")
    cur.close(); conn.close(); return redirect(url_for('products'))

if __name__ == '__main__':
    app.run(debug=True)