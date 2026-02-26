CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================================================
-- [1] TEMEL YAPILAR (AUTH & ORG)
-- =========================================================

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    tax_number VARCHAR(20) UNIQUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_address VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(500) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
    -- last_login ve last_ip sütunları ALTER ile aşağıda eklenecek
);

CREATE TABLE IF NOT EXISTS user_company (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usersid UUID REFERENCES users(id) ON DELETE CASCADE,
    companyid UUID REFERENCES companies(id) ON DELETE CASCADE,
    is_deleted BOOLEAN DEFAULT FALSE,
    UNIQUE(usersid, companyid)
);

CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_company_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_companyid UUID REFERENCES user_company(id) ON DELETE CASCADE,
    rolesid UUID REFERENCES roles(id) ON DELETE CASCADE,
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS user_company_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_companyid UUID REFERENCES user_company(id) ON DELETE CASCADE,
    permission VARCHAR(100),
    is_deleted BOOLEAN DEFAULT FALSE
);

-- Rolleri güvenli ekleme (Varsa atla)
INSERT INTO roles (name) VALUES ('Sirket_Admin'), ('Depo_Gorevlisi'), ('Muhasebe_Gorevlisi'), ('Super_Admin') 
ON CONFLICT (name) DO NOTHING;

-- =========================================================
-- [2] SİSTEM LOGLAMA (YENİ TABLO)
-- =========================================================
CREATE TABLE IF NOT EXISTS system_logs (
    id SERIAL PRIMARY KEY,
    company_id UUID REFERENCES companies(id) ON DELETE SET NULL,
    log_level VARCHAR(20),
    message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =========================================================
-- [3] FİNANSAL TANIMLAR
-- =========================================================
CREATE TABLE IF NOT EXISTS taxes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100),
    rate INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS currency_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50),
    symbol VARCHAR(10),
    code VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS price_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

-- =========================================================
-- [4] ÜRÜN VE STOK YÖNETİMİ
-- =========================================================
CREATE TABLE IF NOT EXISTS inventories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    sku_id VARCHAR(100),
    width DECIMAL(10,2),
    height DECIMAL(10,2),
    length DECIMAL(10,2),
    weight DECIMAL(10,2),
    volume_in_decimeter DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS stock_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS inventory_stocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inventoriesid UUID REFERENCES inventories(id) ON DELETE CASCADE,
    stock_typesid UUID REFERENCES stock_types(id),
    quantity INTEGER DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS inventory_trees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inventoriesid UUID REFERENCES inventories(id) ON DELETE CASCADE,
    inventoriesid2 UUID REFERENCES inventories(id) ON DELETE CASCADE,
    child_quantity INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(inventoriesid, inventoriesid2) 
);

CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    inventoriesid UUID REFERENCES inventories(id),
    billing_name VARCHAR(255),
    gtin VARCHAR(100),
    mpn_id VARCHAR(100),
    list_price DECIMAL(10, 2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

-- =========================================================
-- [5] ENTEGRASYON & LOJİSTİK
-- =========================================================

CREATE TABLE IF NOT EXISTS marketplace_stores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(100),
    marketplace VARCHAR(50),
    -- Yeni şifreli alanlar ALTER ile aşağıda kontrol edilecek
    created_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS marketplace_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    marketplace_name VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS product_platforms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    productsid UUID REFERENCES products(id) ON DELETE CASCADE,
    marketplace_storesid UUID REFERENCES marketplace_stores(id) ON DELETE CASCADE,
    platform_sku_id VARCHAR(100),
    price DECIMAL(10, 2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    price_definitionsid UUID REFERENCES price_definitions(id),
    UNIQUE(productsid, marketplace_storesid)
);

CREATE TABLE IF NOT EXISTS invoice_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(100),
    provider VARCHAR(100),
    api_credentials JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS carrier_integrators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100),
    api_credentials JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS carrier (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100),
    target VARCHAR(100),
    carrier_integratorsid UUID REFERENCES carrier_integrators(id),
    created_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

-- =========================================================
-- [6] SİPARİŞ YÖNETİMİ
-- =========================================================
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    
    order_number VARCHAR(100) NOT NULL, -- UNIQUE Constraint aşağıda ALTER ile kontrol edilecek
    
    customer_full_name VARCHAR(255),
    customer_email VARCHAR(255),
    customer_phone VARCHAR(50),
    customer_identity_number VARCHAR(20),
    total_price_amount DECIMAL(10, 2),
    status INTEGER,
    order_date TIMESTAMP DEFAULT NOW(),
    
    cargo_provider_name VARCHAR(100),
    cargo_tracking_number VARCHAR(100),
    
    shipment_address_city VARCHAR(100),
    shipment_address_district VARCHAR(100),
    shipment_address_full TEXT,
    shipment_package_desi INTEGER DEFAULT 1,
    
    billing_address_city VARCHAR(100),
    billing_address_district VARCHAR(100),
    billing_address_full TEXT,
    
    invoice_id UUID,
    invoice_providersid UUID REFERENCES invoice_providers(id),
    carrier_id UUID REFERENCES carrier(id),
    
    created_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS order_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ordersid UUID REFERENCES orders(id) ON DELETE CASCADE,
    productsid UUID REFERENCES products(id),
    product_name VARCHAR(255),
    quantity INTEGER,
    unit_price_amount DECIMAL(10, 2),
    sku_id VARCHAR(100),
    vat_rate INTEGER DEFAULT 18
);

CREATE TABLE IF NOT EXISTS order_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ordersid UUID REFERENCES orders(id) ON DELETE CASCADE,
    status INTEGER,
    changed_at TIMESTAMP DEFAULT NOW()
);

-- =========================================================
-- [7] MIGRATIONS (MEVCUT TABLOLARI GÜNCELLEME)
-- Tablolar önceden oluşturulduysa yeni sütunların eklendiğinden emin oluyoruz
-- =========================================================

DO $$
BEGIN
    -- Users tablosuna güvenlik sütunları ekle
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='last_login') THEN
        ALTER TABLE users ADD COLUMN last_login TIMESTAMP;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='last_ip') THEN
        ALTER TABLE users ADD COLUMN last_ip VARCHAR(50);
    END IF;

    -- Marketplace Stores tablosuna şifreli alanlar ekle
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='marketplace_stores' AND column_name='api_key_enc') THEN
        ALTER TABLE marketplace_stores ADD COLUMN api_key_enc TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='marketplace_stores' AND column_name='api_secret_enc') THEN
        ALTER TABLE marketplace_stores ADD COLUMN api_secret_enc TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='marketplace_stores' AND column_name='merchant_id') THEN
        ALTER TABLE marketplace_stores ADD COLUMN merchant_id VARCHAR(100);
    END IF;

    -- Products tablosuna liste fiyatı ekle
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='products' AND column_name='list_price') THEN
        ALTER TABLE products ADD COLUMN list_price DECIMAL(10, 2) DEFAULT 0.00;
    END IF;

    -- Orders tablosuna UNIQUE constraint eklemeye çalış (Hata vermemesi için basit kontrol)
    -- Not: Eğer tabloda mükerrer order_number varsa bu işlem başarısız olur.
    BEGIN
        ALTER TABLE orders ADD CONSTRAINT orders_order_number_key UNIQUE (order_number);
    EXCEPTION WHEN duplicate_table OR others THEN
        -- Zaten varsa veya veri hatası varsa pass geç
        NULL;
    END;
END $$;


-- =========================================================
-- [8] VIEW, PROCEDURE, TRIGGER (REPLACE ile Güvenli)
-- =========================================================

CREATE OR REPLACE VIEW view_detailed_sales_report AS
SELECT 
    o.order_number, o.order_date, o.company_id, o.customer_full_name, 
    o.shipment_address_city, o.shipment_address_district,
    p.billing_name as product_name, p.gtin as product_sku,
    ol.quantity, ol.unit_price_amount, 
    (ol.quantity * ol.unit_price_amount) as total_line_amount, 
    o.status, o.is_deleted
FROM orders o
JOIN order_lines ol ON o.id = ol.ordersid
JOIN products p ON ol.productsid = p.id
WHERE o.is_deleted IS FALSE
ORDER BY o.order_date DESC;

CREATE OR REPLACE PROCEDURE sp_create_company(
    IN p_name VARCHAR, IN p_tax_no VARCHAR, IN p_email VARCHAR, IN p_pass_hash VARCHAR, IN p_first_name VARCHAR, IN p_last_name VARCHAR
)
LANGUAGE plpgsql AS $$
DECLARE
    v_comp_id UUID; v_user_id UUID; v_uc_id UUID; v_role_id UUID;
BEGIN
    INSERT INTO companies (name, tax_number) VALUES (p_name, p_tax_no) RETURNING id INTO v_comp_id;
    INSERT INTO users (email_address, first_name, last_name, password_hash) VALUES (p_email, p_first_name, p_last_name, p_pass_hash) RETURNING id INTO v_user_id;
    INSERT INTO user_company (usersid, companyid) VALUES (v_user_id, v_comp_id) RETURNING id INTO v_uc_id;
    SELECT id INTO v_role_id FROM roles WHERE name = 'Sirket_Admin';
    INSERT INTO user_company_roles (user_companyid, rolesid) VALUES (v_uc_id, v_role_id);
    
    -- Stok Tipleri (Hata vermemesi için WHERE NOT EXISTS kontrolü)
    INSERT INTO stock_types (name, company_id) SELECT 'Sağlam', v_comp_id WHERE NOT EXISTS (SELECT 1 FROM stock_types WHERE name='Sağlam' AND company_id=v_comp_id);
    INSERT INTO stock_types (name, company_id) SELECT 'Hasarlı', v_comp_id WHERE NOT EXISTS (SELECT 1 FROM stock_types WHERE name='Hasarlı' AND company_id=v_comp_id);
    INSERT INTO stock_types (name, company_id) SELECT 'İade', v_comp_id WHERE NOT EXISTS (SELECT 1 FROM stock_types WHERE name='İade' AND company_id=v_comp_id);
    INSERT INTO stock_types (name, company_id) SELECT 'Rezerve', v_comp_id WHERE NOT EXISTS (SELECT 1 FROM stock_types WHERE name='Rezerve' AND company_id=v_comp_id);

    INSERT INTO marketplace_stores (company_id, name, marketplace) VALUES (v_comp_id, 'Trendyol Mağazam', 'Trendyol');
    INSERT INTO marketplace_stores (company_id, name, marketplace) VALUES (v_comp_id, 'Hepsiburada Mağazam', 'Hepsiburada');
    
    INSERT INTO system_logs (company_id, log_level, message) VALUES (v_comp_id, 'SUCCESS', 'Şirket kurulumu tamamlandı.');
END;
$$;

CREATE OR REPLACE FUNCTION update_stock_after_order()
RETURNS TRIGGER AS $$
DECLARE
    rec RECORD; is_bundle BOOLEAN := FALSE; parent_inv_id UUID;
BEGIN
    SELECT inventoriesid INTO parent_inv_id FROM products WHERE id = NEW.productsid;
    IF EXISTS (SELECT 1 FROM inventory_trees WHERE inventoriesid = parent_inv_id) THEN is_bundle := TRUE; END IF;
    IF is_bundle THEN
        FOR rec IN SELECT inventoriesid2, child_quantity FROM inventory_trees WHERE inventoriesid = parent_inv_id LOOP
            UPDATE inventory_stocks SET quantity = quantity - (rec.child_quantity * NEW.quantity) 
            WHERE inventoriesid = rec.inventoriesid2 
            AND stock_typesid IN (SELECT id FROM stock_types WHERE name='Sağlam' AND company_id = (SELECT company_id FROM inventories WHERE id=rec.inventoriesid2));
        END LOOP;
    ELSE
        UPDATE inventory_stocks SET quantity = quantity - NEW.quantity 
        WHERE inventoriesid = parent_inv_id
        AND stock_typesid IN (SELECT id FROM stock_types WHERE name='Sağlam' AND company_id = (SELECT company_id FROM inventories WHERE id=parent_inv_id));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger'ları güvenli oluşturma
DROP TRIGGER IF EXISTS trg_reduce_stock ON order_lines;
CREATE TRIGGER trg_reduce_stock AFTER INSERT ON order_lines FOR EACH ROW EXECUTE FUNCTION update_stock_after_order();

CREATE OR REPLACE FUNCTION log_order_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.status IS DISTINCT FROM NEW.status) THEN
        INSERT INTO order_status_history (id, ordersid, status, changed_at) VALUES (gen_random_uuid(), NEW.id, NEW.status, NOW());
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_log_status ON orders;
CREATE TRIGGER trg_log_status AFTER UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION log_order_status_change();



------------------

-- [1] SİPARİŞ İPTALİNDE STOK İADESİ YAPAN TRIGGER
-- [1] SİPARİŞ İPTALİNDE STOK İADESİ YAPAN TRIGGER
CREATE OR REPLACE FUNCTION restore_stock_on_cancel()
RETURNS TRIGGER AS $$
DECLARE
    rec RECORD;
    parent_inv_id UUID;
    is_bundle BOOLEAN := FALSE;
    child_rec RECORD;
BEGIN
    -- Eğer sipariş durumu 'İPTAL' (400) yapıldıysa VE eski durumu 'İPTAL' değilse
    IF (NEW.status = 400 AND OLD.status != 400) THEN
        
        -- Siparişteki her bir satırı (ürünü) dön
        FOR rec IN SELECT productsid, quantity FROM order_lines WHERE ordersid = NEW.id LOOP
            
            -- Ürünün envanter ID'sini bul
            SELECT inventoriesid INTO parent_inv_id FROM products WHERE id = rec.productsid;
            
            -- Bu ürün bir SET mi kontrol et?
            IF EXISTS (SELECT 1 FROM inventory_trees WHERE inventoriesid = parent_inv_id) THEN
                -- Set ise alt parçaların stoğunu artır
                FOR child_rec IN SELECT inventoriesid2, child_quantity FROM inventory_trees WHERE inventoriesid = parent_inv_id LOOP
                    UPDATE inventory_stocks 
                    SET quantity = quantity + (child_rec.child_quantity * rec.quantity)
                    WHERE inventoriesid = child_rec.inventoriesid2 
                    AND stock_typesid IN (SELECT id FROM stock_types WHERE name='Sağlam' AND company_id = NEW.company_id);
                END LOOP;
            ELSE
                -- Tekil ürünse direkt stoğunu artır
                UPDATE inventory_stocks 
                SET quantity = quantity + rec.quantity
                WHERE inventoriesid = parent_inv_id
                AND stock_typesid IN (SELECT id FROM stock_types WHERE name='Sağlam' AND company_id = NEW.company_id);
            END IF;
            
        END LOOP;
        
        -- Log tablosuna bilgi düş
        INSERT INTO system_logs (company_id, log_level, message) 
        VALUES (NEW.company_id, 'WARNING', 'Sipariş iptal edildi (' || NEW.order_number || '), stoklar iade edildi.');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_restore_stock ON orders;
CREATE TRIGGER trg_restore_stock AFTER UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION restore_stock_on_cancel();


-- [2] KRİTİK STOK UYARISI YAPAN TRIGGER
CREATE OR REPLACE FUNCTION check_critical_stock()
RETURNS TRIGGER AS $$
DECLARE
    prod_name VARCHAR;
    comp_id UUID;
BEGIN
    -- Eğer stok 10 veya altına düştüyse VE eskiden 10'dan fazlaysa (Sürekli uyarı vermesin diye)
    IF (NEW.quantity <= 10 AND OLD.quantity > 10) THEN
        -- Ürün adını bul
        SELECT name, company_id INTO prod_name, comp_id FROM inventories WHERE id = NEW.inventoriesid;
        
        -- Log tablosuna KRİTİK uyarısı bas
        INSERT INTO system_logs (company_id, log_level, message) 
        VALUES (comp_id, 'WARNING', 'KRİTİK STOK UYARISI: ' || prod_name || ' (' || NEW.quantity || ' adet kaldı!)');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_critical_stock ON inventory_stocks;
CREATE TRIGGER trg_critical_stock AFTER UPDATE ON inventory_stocks FOR EACH ROW EXECUTE FUNCTION check_critical_stock();


-------------

-- =========================================================
-- [1] VERİ BÜTÜNLÜĞÜ (CHECK CONSTRAINTS)
-- Mantıksız veri girişini engellemek için kurallar
-- =========================================================

-- Ürün fiyatı negatif olamaz
ALTER TABLE products 
ADD CONSTRAINT chk_product_price_positive CHECK (list_price >= 0);

-- Envanter stoğu negatif olamaz (Trigger hatalı çalışırsa burası yakalar)
ALTER TABLE inventory_stocks 
ADD CONSTRAINT chk_stock_quantity_positive CHECK (quantity >= 0);

-- Negatif stokları sıfıra eşitle
UPDATE inventory_stocks 
SET quantity = 0 
WHERE quantity < 0;

--------------------------
-- Sipariş tutarı negatif olamaz
ALTER TABLE orders 
ADD CONSTRAINT chk_order_total_positive CHECK (total_price_amount >= 0);

-- Kargo desisi 0 veya daha küçük olamaz
ALTER TABLE orders
ADD CONSTRAINT chk_order_desi_positive CHECK (shipment_package_desi > 0);


-- =========================================================
-- [2] PERFORMANS İYİLEŞTİRMESİ (INDEXES)
-- Raporlama sayfalarında kullanılan sütunları hızlandırır
-- =========================================================

-- Siparişleri şirkete, duruma ve tarihe göre filtrelerken hız kazandırır
-- (Dashboard ve Raporlar sayfası için kritik)
CREATE INDEX idx_orders_company_status_date 
ON orders (company_id, status, order_date DESC);

-- Müşteri adına göre arama yaparken hız kazandırır
CREATE INDEX idx_orders_customer_name 
ON orders (company_id, customer_full_name);

-- Sipariş numarasına göre (UI'da detay sayfasına giderken) çok hızlı erişim
CREATE INDEX idx_orders_order_number 
ON orders (order_number);

-- Ürünleri adına veya barkoduna göre ararken hız kazandırır
CREATE INDEX idx_products_search 
ON products (company_id, billing_name, gtin);

-- Log tablosu şiştiğinde son logları hızlı getirmek için
CREATE INDEX idx_logs_company_date 
ON system_logs (company_id, created_at DESC);


-- =========================================================
-- [3] GELİŞMİŞ VIEW (DASHBOARD ANALİZİ)
-- Python içindeki "SELECT SUM..." sorgularını buraya taşıyoruz
-- =========================================================

CREATE OR REPLACE VIEW view_dashboard_daily_sales AS
SELECT 
    company_id,
    TO_CHAR(order_date, 'DD.MM') as day_label,
    DATE(order_date) as exact_date,
    COALESCE(SUM(total_price_amount), 0) as total_revenue,
    COUNT(*) as order_count
FROM orders 
WHERE status = 300 -- Sadece teslim edilenler ciroya dahil
AND is_deleted IS FALSE
GROUP BY company_id, day_label, exact_date;

CREATE OR REPLACE VIEW view_dashboard_platform_stats AS
SELECT 
    company_id,
    cargo_provider_name, -- Kargo firması veya Pazaryeri kaynağı olarak kullanılabilir
    COUNT(*) as usage_count
FROM orders 
WHERE is_deleted IS FALSE
GROUP BY company_id, cargo_provider_name;

UPDATE users 
SET email_address = 'suxfian@gmail.com' 
WHERE email_address = 'admin@highbrains.com';

--------------------------------

-- 1. Siparişler tablosuna 'Kaynak/Platform' sütunu ekleyelim
ALTER TABLE orders 
ADD COLUMN IF NOT EXISTS order_source VARCHAR(50) DEFAULT 'Web';

-- Mevcut verileri düzeltelim (Geçici çözüm: Kargo sütununda Trendyol yazanları Kaynak sütununa taşı)
UPDATE orders SET order_source = cargo_provider_name 
WHERE cargo_provider_name IN ('Trendyol', 'Hepsiburada', 'N11', 'Amazon', 'Web');

UPDATE orders SET cargo_provider_name = 'Aras Kargo' 
WHERE cargo_provider_name IN ('Trendyol', 'Hepsiburada', 'N11', 'Amazon', 'Web');

-- 2. Dashboard Grafiği için View'i güncelleyelim (Artık Kargo değil Kaynak sayacak)
DROP VIEW IF EXISTS view_dashboard_platform_stats;

CREATE OR REPLACE VIEW view_dashboard_platform_stats AS
SELECT 
    order_source as platform_name,
    COUNT(*) as usage_count,
    company_id
FROM orders 
WHERE is_deleted IS FALSE
GROUP BY order_source, company_id;