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
