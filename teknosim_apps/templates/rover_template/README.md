# Otonom Kara Aracı (Rover) Şablon Paketi

Bu paket, **TeknoSim** simülasyon altyapısında sıfır kod değişikliğiyle derlenip çalıştırılabilecek standart bir **Otonom Kara Aracı (Ground Rover)** kontrolör şablonudur.

## 🚀 Genel Bakış

Rover şablonu, diferansiyel sürüş (`diff_drive_controller/DiffDriveController`) prensibini kullanan, sol (`left_wheel_joint`) ve sağ (`right_wheel_joint`) tekerleklere sahip standart bir mobil robot tabanını kontrol eder.

### 📌 Topoloji ve Haberleşme
*   **Giriş Komutları:** `/rover_base_controller/cmd_vel` [geometry_msgs/msg/Twist] - Rover'ın doğrusal (linear.x) ve açısal (angular.z) hız komutları.
*   **Eklem Durumları:** `/joint_states` [sensor_msgs/msg/JointState] - Tekerleklerin güncel konum ve hız bilgileri.
*   **Odometri Verisi:** `/rover_base_controller/odom` [nav_msgs/msg/Odometry] - Robotun tekerlek hareketlerine dayalı tahmini konumu.

---

## 🛠️ Kurulum ve Derleme

Bu paketi TeknoSim çalışma alanında (workspace) derlemek için aşağıdaki adımları takip edin:

```bash
# Workspace kök dizinine gidin
cd /home/yavuz/projects/tekno-sim

# Bağımlılıkları kontrol edin ve derleyin
colcon build --packages-select rover_template

# Workspace kaynaklarını yükleyin
source install/setup.bash
```

---

## ⚙️ TEKNOSIM_MODE ve Çalıştırma

Simülasyon başlatılırken ortam değişkeni (`TEKNOSIM_MODE`) aracılığıyla çalışma modu belirlenir. Desteklenen modlar:
*   `SITL`: Yazılımsal test ve simülasyon ortamı (Varsayılan).
*   `HITL`: Gerçek donanım (Hardware-in-the-Loop) entegrasyonu (micro-XRCE-DDS Wi-Fi UDP bağlantısı üzerinden).
*   `PRODUCTION`: Gerçek sürüş ve görev kontrol donanımı.

### 1. SITL Modunda Çalıştırma (Simülasyon)
```bash
export TEKNOSIM_MODE=SITL
ros2 launch rover_template competition.launch.py
```

### 2. HITL Modunda Çalıştırma (Donanım Entegrasyonu)
```bash
export TEKNOSIM_MODE=HITL
ros2 launch rover_template competition.launch.py
```

Launch dosyası başladığında seçilen çalışma modunu otomatik olarak konsola yazdıracak ve `controller_manager` ile ilgili kontrolörleri ayağa kaldıracaktır.
