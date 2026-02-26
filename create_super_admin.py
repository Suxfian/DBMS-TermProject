import psycopg2
from werkzeug.security import generate_password_hash

# --- VERİTABANI AYARLARI ---
DB_HOST = "localhost"
DB_NAME = "project_db"
DB_USER = "postgres"
DB_PASS = "admin"

def create_super_admin():
    print("⏳ Süper Admin oluşturma işlemi başlıyor...")
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port="5432")
    cur = conn.cursor()
    
    try:
        # 1. "HighBrains Yönetim" adında ana şirketi oluştur (Eğer yoksa)
        print("🏢 Ana şirket oluşturuluyor...")
        cur.execute("INSERT INTO companies (name, tax_number) VALUES ('HighBrains Yönetim', '1111111111') RETURNING id")
        comp_id = cur.fetchone()[0]
        
        # 2. Süper Admin kullanıcısını ekle
        print("👤 Kullanıcı kaydediliyor...")
        # İstenen şifre: admin123
        pass_hash = generate_password_hash("admin123") 
        
        cur.execute("""
            INSERT INTO users (email_address, password_hash, first_name, last_name) 
            VALUES ('admin@highbrains.com', %s, 'Süper', 'Yönetici') 
            RETURNING id
        """, (pass_hash,))
        user_id = cur.fetchone()[0]
        
        # 3. Kullanıcıyı Şirkete Bağla
        cur.execute("INSERT INTO user_company (usersid, companyid) VALUES (%s, %s) RETURNING id", (user_id, comp_id))
        uc_id = cur.fetchone()[0]
        
        # 4. "Super_Admin" Rolünü Ata
        # Not: Rollerin db_setup.sql ile oluşturulduğundan emin olmalıyız.
        cur.execute("SELECT id FROM roles WHERE name = 'Super_Admin'")
        role_row = cur.fetchone()
        
        if role_row:
            role_id = role_row[0]
            cur.execute("INSERT INTO user_company_roles (user_companyid, rolesid) VALUES (%s, %s)", (uc_id, role_id))
            
            # --- EKSTRA: İzinler (Opsiyonel ama tam yetki için iyi olur) ---
            # user_company_permissions tablosuna 'all' yetkisi verelim
            cur.execute("INSERT INTO user_company_permissions (user_companyid, permission) VALUES (%s, 'all')", (uc_id,))
            
            conn.commit()
            print("\n✅ SÜPER ADMIN OLUŞTURULDU!")
            print("------------------------------------------------")
            print("📧 Email: admin@highbrains.com")
            print("🔑 Şifre: admin123")
            print("------------------------------------------------")
        else:
            print("❌ HATA: 'Super_Admin' rolü veritabanında bulunamadı. Lütfen önce db_setup.sql'i çalıştırın.")
            conn.rollback()
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Bir hata oluştu: {e}")
        # Hata detayını görelim (Unique violation vb.)
        if "duplicate key" in str(e):
            print("💡 İPUCU: Bu kullanıcı veya şirket zaten var olabilir.")
            
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    create_super_admin()