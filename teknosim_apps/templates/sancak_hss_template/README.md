# Sancak HSS (UAV) Şablon Paketi

Bu paket, **TeknoSim** simülasyon altyapısında sıfır kod değişikliğiyle derlenip çalıştırılabilecek standart bir **İnsansız Hava Sistemi (UAV)** kontrolör şablonudur.

## 🚀 Genel Bakış

Sancak HSS jenerik olarak 4 adet rotor eklemine (`rotor1_joint`, `rotor2_joint`, `rotor3_joint`, `rotor4_joint`) sahip bir quadrotor modelidir. Motor hızları `velocity_controllers/JointGroupVelocityController` ile kontrol edilmektedir.

### 📌 Topoloji ve Haberleşme
*   **Giriş Komutları:** `/sancak_velocity_controller/commands` [std_msgs/msg/Float64MultiArray] - 4 adet motorun hedef açısal hızları (rad/s).
*   **Eklem Durumları:** `/joint_states` [sensor_msgs/msg/JointState] - Rotorların güncel konum ve hız bilgileri.

---

## 🛠️ Kurulum ve Derleme

Bu paketi TeknoSim çalışma alanında (workspace) derlemek için aşağıdaki adımları takip edin:

```bash
# Workspace kök dizinine gidin
cd /home/yavuz/projects/tekno-sim

# Bağımlılıkları kontrol edin ve derleyin
colcon build --packages-select sancak_hss_template

# Workspace kaynaklarını yükleyin
source install/setup.bash
```

---

## ⚙️ TEKNOSIM_MODE ve Çalıştırma

Simülasyon başlatılırken ortam değişkeni (`TEKNOSIM_MODE`) aracılığıyla çalışma modu belirlenir. Desteklenen modlar:
*   `SITL`: Yazılımsal test ve simülasyon ortamı (Varsayılan).
*   `HITL`: Gerçek donanım (Hardware-in-the-Loop) entegrasyonu (micro-XRCE-DDS Wi-Fi UDP bağlantısı üzerinden).
*   `PRODUCTION`: Gerçek uçuş ve görev kontrol donanımı.

### 1. SITL Modunda Çalıştırma (Simülasyon)
```bash
export TEKNOSIM_MODE=SITL
ros2 launch sancak_hss_template competition.launch.py
```

### 2. HITL Modunda Çalıştırma (Donanım Entegrasyonu)
```bash
export TEKNOSIM_MODE=HITL
ros2 launch sancak_hss_template competition.launch.py
```

Launch dosyası başladığında seçilen çalışma modunu otomatik olarak konsola yazdıracak ve `controller_manager` ile ilgili kontrolörleri ayağa kaldıracaktır.
