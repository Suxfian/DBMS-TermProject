# Online Marketplace Entegrasyon Yönetim Sistemi

Bu proje, e-ticaret sektöründe faaliyet gösteren işletmelerin çoklu platform (Trendyol, Hepsiburada, Amazon vb.) ve fiziksel mağaza süreçlerini tek bir merkezden yönetmelerini sağlayan **Multi-Tenant (Çoklu Kiracı)** mimarisine sahip kapsamlı bir yönetim sistemidir. 

Sistem; veri tutarsızlığı, stok yönetimi hataları ve operasyonel verimsizlik problemlerine çözüm getirmek amacıyla veritabanı seviyesinde otomasyonlar (Triggers & Stored Procedures) barındıracak şekilde tasarlanmıştır.

## 🚀 Öne Çıkan Özellikler

* **Overselling (Aşırı Satış) Koruması:** Veritabanı seviyesinde çalışan tetikleyiciler (Triggers) ile stoklar anlık düşülür ve olmayan stoğun satılması engellenir.
* **Çoklu Kiracı (Multi-Tenant) Yapısı:** PostgreSQL üzerinde tek bir veritabanında, farklı şirketlerin verileri birbirinden tamamen izole ve güvenli bir şekilde barındırılır.
* **Gelişmiş Veri Güvenliği:** Kullanıcı şifreleri `bcrypt` ile hashlenirken, pazaryeri API anahtarları `AES-256` standartlarında (Fernet) şifrelenerek saklanır.
* **Rol Bazlı Erişim Kontrolü (RBAC):** Süper Admin, Şirket Yöneticisi, Depo Görevlisi ve Muhasebe rolleriyle yetkilendirme hiyerarşisi.
* **Canlı Sistem Logları:** Arka plan işlemlerinin, hataların ve sipariş simülasyonlarının yönetim panelinden canlı (WebSocket/Polling) olarak izlenebilmesi.
* **Toplu Entegrasyon & Excel:** XLSX formatında toplu ürün ekleme ve dışa aktarma (Export/Import).

## 🛠 Teknoloji Yığını

* **Backend:** Python 3, Flask, psycopg2
* **Veritabanı:** PostgreSQL (Stored Procedures, Triggers, Views, Check Constraints)
* **Frontend:** HTML5, Tailwind CSS, JavaScript, Chart.js
* **Güvenlik & Kimlik Doğrulama:** Authlib (Google OAuth), werkzeug.security, cryptography

---

## ⚙️ Kurulum Rehberi

Projeyi yerel ortamınızda (localhost) çalıştırmak için aşağıdaki adımları sırasıyla uygulayın.

### 1. Sistem Gereksinimleri
* Python 3.8 veya üzeri
* PostgreSQL 12 veya üzeri
* Git

### 2. Projeyi Klonlama ve Bağımlılıkların Yüklenmesi
Terminal veya komut satırını açarak projeyi bilgisayarınıza indirin ve sanal ortam (virtual environment) oluşturun:

```bash
# Projeyi klonlayın
git clone [https://github.com/KULLANICI_ADIN/online-marketplace-integration.git](https://github.com/KULLANICI_ADIN/online-marketplace-integration.git)
cd online-marketplace-integration

# Sanal ortam oluşturun
python -m venv venv

# Sanal ortamı aktifleştirin
# Windows için:
venv\Scripts\activate
# macOS/Linux için:
source venv/bin/activate

# Gerekli kütüphaneleri yükleyin
pip install -r requirements.txt

3. Veritabanı (PostgreSQL) Kurulumu
Projenin şifreleme modüllerinin ve tablolarının çalışabilmesi için veritabanının doğru yapılandırılması gerekmektedir.

PostgreSQL komut satırına (psql) veya pgAdmin'e giriş yapın.

Proje için yeni bir veritabanı oluşturun:

SQL
CREATE DATABASE project_db;
Oluşturduğunuz veritabanına bağlanın ve veri şifreleme işlemlerinde kullanılan pgcrypto eklentisini aktif edin:

SQL
\c project_db
CREATE EXTENSION IF NOT EXISTS pgcrypto;
Veritabanı tablolarını, tetikleyicileri (Triggers) ve saklı yordamları (Stored Procedures) oluşturmak için proje dizininde yer alan SQL dosyasını çalıştırın (Not: Eğer SQL dosyanızın adı db_setup.sql ise):

Bash
psql -U postgres -d project_db -f db_setup.sql

4. Çevre Değişkenlerinin (Environment Variables) Ayarlanması
Projenin kök dizininde bir .env dosyası oluşturun ve güvenlik/veritabanı bilgilerinizi buraya girin. app.py dosyasının bu bilgileri .env üzerinden okuduğundan emin olun.

Kod snippet'i
# Veritabanı Ayarları
DB_HOST=localhost
DB_NAME=project_db
DB_USER=postgres
DB_PASS=kendi_veritabani_sifren
DB_PORT=5432

# Flask ve Güvenlik Ayarları
FLASK_SECRET_KEY=cok_gizli_flask_anahtari
ENCRYPTION_KEY=b"AES_256_ICIN_GECERLI_BASE64_ANAHTARI_BURAYA="

# Google OAuth (Opsiyonel - Google Girişi İçin)
GOOGLE_CLIENT_ID=kendi_client_id_bilgin
GOOGLE_CLIENT_SECRET=kendi_client_secret_bilgin
5. Süper Admin Hesabının Oluşturulması
Tablolar oluştuktan sonra, sisteme ilk girişi yapabilmek için gerekli ana firmayı ve Süper Admin kullanıcısını oluşturmalısınız.

Bash
python create_super_admin.py
Bu komut başarıyla çalıştığında konsolda admin@firmaniz.com ve şifresi görüntülenecektir.

6. Uygulamayı Başlatma
Tüm kurulumlar tamamlandı. Flask sunucusunu başlatarak projeyi çalıştırabilirsiniz:

Bash
python app.py
Tarayıcınızı açın ve http://127.0.0.1:5000 adresine giderek oluşturduğunuz admin bilgileri ile sisteme giriş yapın.

📂 Proje Yapısı
Plaintext
online-marketplace-integration/
│
├── app.py                   # Flask ana uygulama dosyası
├── create_super_admin.py    # İlk kurulum ve yetkilendirme betiği
├── requirements.txt         # Python bağımlılık listesi
├── db_setup.sql             # Tablolar, View'lar, Trigger ve SP'ler (Varsa)
│
├── templates/               # HTML şablonları (Tailwind CSS)
│   ├── index.html           # Genel Bakış (Dashboard)
│   ├── login.html           # Kullanıcı Giriş Ekranı
│   ├── orders.html          # Sipariş Yönetimi
│   ├── products.html        # Envanter ve Stok Yönetimi
│   ├── integrations.html    # Pazaryeri Eşleştirme Sayfası
│   └── settings.html        # Ayarlar ve Personel Yönetimi
│
└── README.md                # Proje dokümantasyonu
