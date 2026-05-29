# 🦆 ŞÜPHECİ ÖRDEK - KONTROL İSTASYONU (GUI) MİMARİ UYARILAR REHBERİ
**Tarih:** Mayıs 2026  
**Amaç:** Foxglove Custom Panel ve FastAPI Sidecar geliştirilirken uyarılması gereken tüm sınır değerleri ve kritik zombi/kilitlenme engellerini belgelemek.

---

## 1. DEVCONTAINER ENTEGRASYON KURALLARI (FastAPI in Container)

FastAPI servisi, DevContainer içinde `postStartCommand` ile otomatik başlatılan entegre bir arka plan süreci olarak çalıştırılacaktır.

### ⚠️ Dikkat Edilecek Riskler ve Çözümler:
*   **PID 1 & Çökme Koruması (FastAPI Restarter):** FastAPI arka planda `&` ile başlatıldığında çökmesi durumunda konteyner bunu fark etmez.
    *   *Kural:* FastAPI'nin basit bir süpervizör döngüsüyle veya `--reload` geliştirme moduyla uvicorn üzerinden ayağa kaldırılması zorunludur:
        ```bash
        while true; do python3 -m uvicorn sidecar_server:app --host 0.0.0.0 --port 8000 --reload; sleep 1; done
        ```
*   **Log Yönlendirmesi (Log Isolation):** FastAPI stdout loglarının ROS 2 düğüm loglarıyla karışıp terminalleri kirletmemesi gerekir.
    *   *Kural:* Tüm FastAPI çıktıları bağımsız bir log dosyasına yönlendirilmelidir:
        ```bash
        >> /var/log/fastapi.log 2>&1
        ```
*   **İşlemci ve Kaynak Paylaşımı (Nice Priority & cgroups):** `colcon build` ve derleme işlemleri esnasında CPU/RAM tüketiminin artıp ROS 2 real-time döngülerini bozmasını engellemek zorunludur.
    *   *Kural:* FastAPI ve derleme alt süreçleri düşük öncelikle (`nice` değeri artırılarak) çalıştırılmalıdır:
        ```bash
        nice -n 10 colcon build --packages-select <project_name>
        ```

---

## 2. KİLİTLENME VE ZOMBİ SÜREÇ KORUMASI (Orchestration)

### ⚠️ Uç Durum (Edge Case) Kuralları:

#### A. Çoklu Proje / Çoklu Derleme Çakışması (Process Lock):
Aynı anda birden fazla build veya launch işlemi çalıştırılamaz. Çalıştırılması durumunda `.so` dosya kilitleri nedeniyle derleme çöker.
*   *Kural 1:* FastAPI kodunda global bir `process_lock = asyncio.Lock()` ve `current_process = None` tutulacaktır.
*   *Kural 2:* `/project/build` veya `/project/launch` çağrıldığında, eğer aktif bir süreç yürütülüyorsa `409 Conflict` dönülecektir.
*   *Kural 3:* Yeni derleme başlamadan önce, çalışmakta olan tüm kullanıcı düğümleri zorunlu olarak (`SIGINT` veya `SIGTERM`) sonlandırılacaktır.

#### B. Bağlantı Kopması ve Yetim Süreçlerin Temizlenmesi (Heartbeat):
Kullanıcı Foxglove Studio arayüzünü aniden kapattığında veya bağlantısı koptuğunda, arkada çalışan derlemeler (colcon build) yarıda kesilmemeli; ancak arka planda gereksiz CPU yiyen simülasyon launch süreçleri (`ros2 launch`) derhal durdurulmalıdır.
*   *Kural 1:* FastAPI, başlattığı tüm `ros2 launch` alt süreçlerini dinamik bir süreç havuzunda (Process Pool) PID değerleriyle takip eder.
*   *Kural 2:* Arayüz ile FastAPI arasında her 5 saniyede bir tetiklenen hafif bir `/ping` (Heartbeat) mekanizması kurulmalıdır.
*   *Kural 3:* Eğer FastAPI son 30 saniye boyunca hiçbir ping alamazsa, süreç havuzundaki tüm `ros2 launch` PID'lerini `os.kill(pid, signal.SIGINT)` ile sonlandıracaktır.

---

## 3. DOSYA PAYLAŞIM VE PORT KURALLARI (CORS & Volume)

*   **"Hot Folder" Klasör Listeleme:**
    *   *Kural:* Dosyalar Foxglove arayüzünden HTTP üzerinden upload edilmeyecektir. Kullanıcı host üzerinde projeyi `teknosim_apps/` dizinine kopyalar (veya orada geliştirir). Arayüzdeki "Yenile/Listele" butonu FastAPI `/projects` endpoint'ini tetikleyerek bu dizini tarar.
*   **CORS Ayarları:**
    *   *Kural:* Arayüz ile FastAPI arasındaki origin kısıtlamalarını aşmak için FastAPI tarafında mutlaka `CORSMiddleware` tanımlanmalıdır:
        ```python
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        ```
