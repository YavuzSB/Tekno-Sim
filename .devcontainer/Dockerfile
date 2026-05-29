FROM nvidia/cuda:12.4.1-devel-ubuntu24.04

# V4.3 Tek Base Image Stratejisi: Altyapı katmanı tek imajda tutularak konteyner enflasyonu önlenmiştir.
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8
ENV ROS_DISTRO=jazzy
ENV RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# Gerekli sistem paketleri ve lokal ayarları
RUN apt-get update && apt-get install -y --no-install-recommends \
    locales \
    curl \
    gnupg2 \
    lsb-release \
    build-essential \
    python3-pip \
    && locale-gen en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

# ROS 2 deposunu ekleme
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/ros2.list > /dev/null

# ROS 2 Jazzy, CycloneDDS ve Iceoryx kurulumu
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-jazzy-ros-base \
    ros-jazzy-rmw-cyclonedds-cpp \
    ros-jazzy-iceoryx-posh \
    ros-jazzy-iceoryx-hoofs \
    python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# Bash konfigürasyonu - ROS 2 workspace ortamını varsayılan yap
RUN echo "source /opt/ros/jazzy/setup.bash" >> /root/.bashrc

WORKDIR /workspace
