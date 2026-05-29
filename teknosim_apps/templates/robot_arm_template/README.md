# Robotik Kol (Robot Arm) Şablon Paketi

Bu paket, **TeknoSim** simülasyon altyapısında sıfır kod değişikliğiyle derlenip çalıştırılabilecek standart bir **Robotik Kol (Robot Arm)** kontrolör şablonudur.

## 🚀 Genel Bakış

Robot Arm şablonu, 6 Serbestlik Derecesine (6 DOF) sahip endüstriyel tip bir robot kolunu kontrol eder. Eklemler jenerik olarak `joint1` ile `joint6` arasında adlandırılmıştır ve `position_controllers/JointGroupPositionController` ile pozisyon bazlı sürülür.

### 📌 Topoloji ve Haberleşme
*   **Giriş Komutları:** `/arm_position_controller/commands` [std_msgs/msg/Float64MultiArray] - 6 eklemin hedef pozisyonları (radyan).
*   **Eklem Durumları:** `/joint_states` [sensor_msgs/msg/JointState] - Eklemlerin güncel açısal konum ve hız bilgileri.

---

## 🛠️ Kurulum ve Derleme

Bu paketi TeknoSim çalışma alanında (workspace) derlemek için aşağıdaki adımları takip edin:

```bash
# Workspace kök dizinine gidin
cd /home/yavuz/projects/tekno-sim

# Bağımlılıkları kontrol edin ve derleyin
colcon build --packages-select robot_arm_template

# Workspace kaynaklarını yükleyin
source install/setup.bash
```

---

## ⚙️ TEKNOSIM_MODE ve Çalıştırma

Simülasyon başlatılırken ortam değişkeni (`TEKNOSIM_MODE`) aracılığıyla çalışma modu belirlenir. Desteklenen modlar:
*   `SITL`: Yazılımsal test ve simülasyon ortamı (Varsayılan).
*   `HITL`: Gerçek donanım (Hardware-in-the-Loop) entegrasyonu (micro-XRCE-DDS Wi-Fi UDP bağlantısı üzerinden).
*   `PRODUCTION`: Gerçek robotik kol donanımı.

### 1. SITL Modunda Çalıştırma (Simülasyon)
```bash
export TEKNOSIM_MODE=SITL
ros2 launch robot_arm_template competition.launch.py
```

### 2. HITL Modunda Çalıştırma (Donanım Entegrasyonu)
```bash
export TEKNOSIM_MODE=HITL
ros2 launch robot_arm_template competition.launch.py
```

Launch dosyası başladığında seçilen çalışma modunu otomatik olarak konsola yazdıracak ve `controller_manager` ile ilgili kontrolörleri ayağa kaldıracaktır.
