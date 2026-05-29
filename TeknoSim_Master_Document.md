# TEKNOSIM MASTER MANİFESTO VE SİSTEM SPESİFİKASYONU (v4.4)
**Tarih:** Mayıs 2026
**Amaç:** İnsansız Hava Sistemleri (Sancak HSS), Otonom Araçlar veya Robot Kollar gibi her türlü teknoloji projesini test edebilecek; Windows/Linux bağımsız, tek tuşla kurulabilir (DevContainers) modüler, gecikmesiz ve deterministik bir SITL/HITL simülasyon (Kum Havuzu) çekirdeği inşa etmektir.

---

## BÖLÜM 1: GÖREV, KİMLİK VE MASTER PROMPT
Sen "TeknoSim" projesinin Ana Mimarı ve Yönetici Ajanısın (Orchestrator). Görevin, projenin "Çekirdek" (Core) altyapısını kurmak ve kullanıcının projelerine (Apps) müdahale etmeden onlara gerçekçi fizik, sensör verisi ve haberleşme otobanı sağlamaktır.

### ⚠️ KRİTİK ÇALIŞMA KURALLARI
1. **Çapraz Platform ve Modülerlik:** Altyapı OS-agnostic olmalı (VSCode DevContainers ile) ve çekirdek yapı (`teknosim_core`) ile kullanıcı projeleri (`teknosim_apps`) ayrılmalıdır. Disk şişmesini önlemek için tek bir Base Image kullanılmalı, modüller Volume olarak bağlanmalıdır.
2. **Beklenti Yönetimi:** Windows/WSL2 sadece "Geliştirme Ortamı"dır. Gerçek Zero-Copy performansı SADECE Linux Native (CachyOS vb.) üzerinde garanti edilir.
3. **Tartışmadan Koda Geçme:** Başlamadan önce kullanıcı (Yavuz) ile implementation plan üzerinden onay al.
4. **Güvenli Silme (Recycle Bin):** Hiçbir dosyayı kalıcı silme. Kök dizinde `_recyclebin` oluştur.

---

## BÖLÜM 2: GEREKLİ UZMAN ALT AJANLAR (SUB-AGENTS)
1. **`docker-architect`:** VSCode DevContainer, Docker Compose (Tek Base Image, Çoklu Volume), cgroups kısıtlamaları.
2. **`ros2-bridge-expert`:** Iceoryx (Zero-Copy), Host Fallback (UDP DDS) ve Foxglove ağ yapılandırması.
3. **`isaac-sim-pilot`:** Isaac Sim deterministik fizik (PhysX 5), OS-Agnostic köprü düğümleri ve RTX Interactive render sahnesi.
4. **`hitl-specialist`:** micro-XRCE-DDS üzerinden Wi-Fi (UDP) asenkron donanım haberleşmesi ve jenerik `ros2_control` entegrasyonu.

---

## BÖLÜM 3: ÇEKİRDEK (CORE) VE EKLENTİ (PLUGIN) MİMARİSİ
Sistem klasör ve mantık seviyesinde ikiye ayrılır:

### 3.1. `teknosim_core` (Dokunulmaz Jenerik Katman)
Tüm teknoloji projelerinin ortak kullanacağı simülasyon araçlarıdır.
*   **Zaman Yönetimi:** `/clock` senkronizasyonu ve `use_sim_time=true` zorlayıcı düğümler.
*   **Güvenlik:** Iceoryx "Zombie Memory" Watchdog'u ve kaynak limitleri (cgroups).
*   **Soyutlama:** SITL/HITL geçişini sağlayan jenerik `ros2_control` donanım arayüzü yöneticisi.
*   **Telemetri:** Foxglove için `image_transport` ile sıkıştırılmış veri (Observer Effect önleyici) düğümleri.

### 3.2. `teknosim_apps` (Proje Katmanı)
Kullanıcının geliştirdiği projelere ev sahipliği yapar (Örn: `sancak_hss`).
*   Vision, GNC vb. algoritmalar bu klasörde yaşar. Ayrı bir Docker imajı gerektirmez, çekirdek Base Image üzerine Volume olarak mount edilir.

---

## BÖLÜM 4: OS-AGNOSTIC KURULUM VE KAYNAK YÖNETİMİ

### 4.1. Tek Tıkla DevContainer ve Tek İmaj Stratejisi
*   **Kurulum:** Sistem `devcontainer.json` ile VSCode'da "Reopen in Container" dendiği an çalışır.
*   **İmaj Optimizasyonu (Konteyner Enflasyonu Koruması):** Core ve Apps için ayrı imajlar derlenmez. `docker-compose.yml` içinde tek bir ağır imaj (ROS 2 + CUDA + Iceoryx) bulunur, projeler klasör eşleştirmesi (Volume) ile çalışır.

### 4.2. Donanım Paylaşımı ve Determinizm
*   **GPU Limitleri:** Isaac Sim "RTX Interactive" modda çalışırken, Docker içindeki kullanıcı algoritmalarına cgroups ile VRAM limiti atanarak "frame drop" engellenir.
*   **Fiziksel Determinizm:** Isaac Sim'de `fixed_time_step` zorunludur.

---

## BÖLÜM 5: ÇAPRAZ PLATFORM İLETİŞİM STRATEJİSİ VE GERÇEKLİKLER

### 5.1. Linux Native: "Sıfır Gecikme" (Zero-Copy) Garantisi
Host olarak Linux (CachyOS) kullanıldığında sistem tam kapasite çalışır. Konteynerler arası ve Host (Isaac Sim) ile Konteyner arası iletişim tamamen Iceoryx (Shared Memory) üzerinden gecikmesiz gerçekleşir.

### 5.2. Windows (WSL2): "Geliştirme ve Yarı-Performanslı Test" Ortamı
Windows Host üzerindeki Isaac Sim ile WSL2 içindeki Docker'ın haberleşmesinde IPC kısıtlamaları vardır. Bu nedenle:
*   Windows'ta Isaac Sim bağlantısı "Fallback" olarak standart UDP DDS (CycloneDDS vb.) kullanır. Ağ gecikmesi (latency) kabul edilir. Zero-copy vaadi Windows için geçerli değildir.

### 5.3. HITL (Donanım) İletişimi: Wi-Fi (UDP) Standardı
Gerçek donanıma (ESP32 vb.) geçildiğinde, Windows/WSL2 ortamında sıkça yaşanan USB/COM port (Serial) passthrough sorunlarını tamamen aşmak için **micro-XRCE-DDS Wi-Fi (UDP)** bağlantısı varsayılan standart olarak kabul edilir.

---

## BÖLÜM 6: CI/CD VE HİBRİT CODE REVIEW STRATEJİSİ
Projenin kalite güvencesi 3 aşamalı (Hybrid) bir filtreleme sistemine dayanır:
1. **Yerel Denetim (İç Savunma):** Kod GitHub'a gitmeden önce yerel **`skeptic-duck`** ajanı tarafından TeknoSim mimari kuralları (Zero-Copy, Fixed Time Step) açısından incelenir.
2. **GitHub Actions (Otomatik Test):** Kod push edildiğinde, **`qa-tester`** ajanının yazdığı birim ve entegrasyon testleri bulutta otomatik koşturulur.
3. **Octopus AI (Dış Savunma):** Testleri geçen kod Pull Request (PR) olarak açıldığında, genel yazılım mühendisliği (Syntax, Memory Leak, Linting) Hataları için **Octopus AI** tarafından incelenir. Bu üçlü yapı kodu kurşun geçirmez kılar.

---

## BÖLÜM 7: KONTROL İSTASYONU VE ENTEGRE GUI MİMARİSİ (v4.4)
Projenin kullanıcı arayüzü, kontrol katmanı ve süreç otomasyonu entegre ve kurşun geçirmez bir yapıyla koordine edilir.

### 7.1. Ön Uç: Foxglove Studio Custom Panel (React/TypeScript)
*   **Platform:** Foxglove Studio masaüstü veya web sürümü içinde çalışan custom eklenti paneli.
*   **Ağ Haberleşmesi:** `/teknosim/` ROS 2 servisleri ve uvicorn/FastAPI REST/SSE kanalları.
*   **Özellikler:**
    *   **Proje Yönetimi:** `teknosim_apps/` altındaki aktif projelerin (şablon ve kullanıcı kodu) taranıp listelenmesi.
    *   **Süreç Denetimi:** SITL/HITL mod seçimi, "Build" ve "Start/Stop" butonları ile uzaktan süreç kontrolü.
    *   **Canlı Konsol:** FastAPI'den gelen Server-Sent Events (SSE) akışıyla `colcon build` loglarının arayüze gerçek zamanlı yazdırılması.

### 7.2. Arka Uç: DevContainer İçi FastAPI Sidecar
*   **Çalışma Ortamı:** Ayrı bir Docker servisi yerine, DevContainer içinde `postStartCommand` ile otomatik başlatılan entegre hafif uvicorn/FastAPI sunucusu.
*   **Proje Bağlama (Hot Folder):** Büyük dosya yüklemelerinin tarayıcıyı çökertmesini önlemek için doğrudan host ile konteyner arasında bind-mount olan `/workspace/teknosim_apps/` klasörü "Hot Folder" olarak kullanılır. Kullanıcı projesini host'ta buraya kopyalar; FastAPI bunu anlık algılar.
*   **Güvenli Süreç ve Kilitleme Mantığı:**
    *   **Aynı Anda Tek İşlem:** Çakışmaları ve `.so` kütüphane kilitlerini önlemek için `asyncio.Lock` kullanılır. Derleme (`colcon build`) başlamadan önce aktif çalışan tüm kullanıcı düğümleri sonlandırılır.
    *   **Zombi Temizliği:** Arka planda `ros2 launch` komutları PID havuzuyla takip edilir. Foxglove bağlantısı koptuğunda veya durdurulduğunda bu yetim süreçler (`SIGINT/SIGTERM`) ile temizlenir.

