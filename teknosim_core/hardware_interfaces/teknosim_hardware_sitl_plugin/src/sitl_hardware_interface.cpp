#include "teknosim_hardware_sitl_plugin/sitl_hardware_interface.hpp"

#include <limits>
#include <vector>
#include <cstdlib>
#include <cerrno>

#include "hardware_interface/types/hardware_interface_type_values.hpp"
#include "rclcpp/rclcpp.hpp"
#include "pluginlib/class_list_macros.hpp"

namespace teknosim_hardware_sitl_plugin
{

hardware_interface::CallbackReturn SitlHardwareInterface::on_init(const hardware_interface::HardwareInfo & info)
{
  if (hardware_interface::SystemInterface::on_init(info) != hardware_interface::CallbackReturn::SUCCESS) {
    return hardware_interface::CallbackReturn::ERROR;
  }

  // 1. Read TEKNOSIM_MODE environment variable
  const char* mode_env = std::getenv("TEKNOSIM_MODE");
  if (mode_env != nullptr && std::string(mode_env) == "HITL") {
    is_hitl_mode_ = true;
    RCLCPP_INFO(rclcpp::get_logger("SitlHardwareInterface"), "TeknoSim Mode is set to HITL.");
  } else {
    is_hitl_mode_ = false;
    RCLCPP_INFO(rclcpp::get_logger("SitlHardwareInterface"), "TeknoSim Mode is set to SITL (pure simulation).");
  }

  // Check joint count limits
  if (info_.joints.size() > MAX_JOINTS) {
    RCLCPP_FATAL(
      rclcpp::get_logger("SitlHardwareInterface"),
      "Number of joints (%zu) exceeds maximum allowed joints (%zu)!",
      info_.joints.size(), MAX_JOINTS);
    return hardware_interface::CallbackReturn::ERROR;
  }

  hw_positions_.resize(info_.joints.size(), std::numeric_limits<double>::quiet_NaN());
  hw_velocities_.resize(info_.joints.size(), std::numeric_limits<double>::quiet_NaN());
  hw_commands_.resize(info_.joints.size(), std::numeric_limits<double>::quiet_NaN());

  return hardware_interface::CallbackReturn::SUCCESS;
}

std::vector<hardware_interface::StateInterface> SitlHardwareInterface::export_state_interfaces()
{
  std::vector<hardware_interface::StateInterface> state_interfaces;
  for (std::size_t i = 0; i < info_.joints.size(); ++i) {
    state_interfaces.emplace_back(hardware_interface::StateInterface(
      info_.joints[i].name, hardware_interface::HW_IF_POSITION, &hw_positions_[i]));
    state_interfaces.emplace_back(hardware_interface::StateInterface(
      info_.joints[i].name, hardware_interface::HW_IF_VELOCITY, &hw_velocities_[i]));
  }
  return state_interfaces;
}

std::vector<hardware_interface::CommandInterface> SitlHardwareInterface::export_command_interfaces()
{
  std::vector<hardware_interface::CommandInterface> command_interfaces;
  for (std::size_t i = 0; i < info_.joints.size(); ++i) {
    command_interfaces.emplace_back(hardware_interface::CommandInterface(
      info_.joints[i].name, hardware_interface::HW_IF_VELOCITY, &hw_commands_[i]));
  }
  return command_interfaces;
}

hardware_interface::CallbackReturn SitlHardwareInterface::on_activate(const rclcpp_lifecycle::State & /*previous_state*/)
{
  for (auto & pos : hw_positions_) {
    pos = 0.0;
  }
  for (auto & vel : hw_velocities_) {
    vel = 0.0;
  }
  for (auto & command : hw_commands_) {
    command = 0.0;
  }

  if (is_hitl_mode_) {
    sock_ = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock_ < 0) {
      RCLCPP_ERROR(rclcpp::get_logger("SitlHardwareInterface"), "Failed to create UDP socket!");
      return hardware_interface::CallbackReturn::ERROR;
    }

    // Set non-blocking socket
    int flags = fcntl(sock_, F_GETFL, 0);
    if (flags < 0 || fcntl(sock_, F_SETFL, flags | O_NONBLOCK) < 0) {
      RCLCPP_ERROR(rclcpp::get_logger("SitlHardwareInterface"), "Failed to set socket to non-blocking!");
      close(sock_);
      sock_ = -1;
      return hardware_interface::CallbackReturn::ERROR;
    }

    std::memset(&server_addr_, 0, sizeof(server_addr_));
    server_addr_.sin_family = AF_INET;
    server_addr_.sin_port = htons(34567);
    if (inet_pton(AF_INET, "127.0.0.1", &server_addr_.sin_addr) <= 0) {
      RCLCPP_ERROR(rclcpp::get_logger("SitlHardwareInterface"), "Invalid address structure!");
      close(sock_);
      sock_ = -1;
      return hardware_interface::CallbackReturn::ERROR;
    }

    // UDP Connect to establish default target for send/recv
    if (connect(sock_, (struct sockaddr *)&server_addr_, sizeof(server_addr_)) < 0) {
      RCLCPP_ERROR(rclcpp::get_logger("SitlHardwareInterface"), "Failed to connect to emulator address!");
      close(sock_);
      sock_ = -1;
      return hardware_interface::CallbackReturn::ERROR;
    }

    RCLCPP_INFO(rclcpp::get_logger("SitlHardwareInterface"), "UDP HITL client configured to connect to 127.0.0.1:34567");
  }

  RCLCPP_INFO(rclcpp::get_logger("SitlHardwareInterface"), "SITL/HITL Hardware Interface successfully activated!");
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn SitlHardwareInterface::on_deactivate(const rclcpp_lifecycle::State & /*previous_state*/)
{
  if (sock_ >= 0) {
    close(sock_);
    sock_ = -1;
    RCLCPP_INFO(rclcpp::get_logger("SitlHardwareInterface"), "UDP HITL socket closed successfully.");
  }
  RCLCPP_INFO(rclcpp::get_logger("SitlHardwareInterface"), "SITL Hardware Interface successfully deactivated!");
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::return_type SitlHardwareInterface::read(const rclcpp::Time & /*time*/, const rclcpp::Duration & period)
{
  if (is_hitl_mode_) {
    if (sock_ < 0) {
      RCLCPP_ERROR(rclcpp::get_logger("SitlHardwareInterface"), "Socket is not initialized!");
      return hardware_interface::return_type::ERROR;
    }

    SensorStates states_packet;
    ssize_t bytes_received = recv(sock_, &states_packet, sizeof(states_packet), 0);

    if (bytes_received == sizeof(states_packet)) {
      // Decode sensor data from binary packet
      for (std::size_t i = 0; i < info_.joints.size(); ++i) {
        hw_positions_[i] = states_packet.joint_positions[i];
        hw_velocities_[i] = states_packet.joint_velocities[i];
      }
    } else if (bytes_received < 0) {
      if (errno == EAGAIN || errno == EWOULDBLOCK) {
        // No packet available yet, keep previous state to prevent blocking the control loop
      } else {
        RCLCPP_ERROR(rclcpp::get_logger("SitlHardwareInterface"), "Error reading UDP data: %s", std::strerror(errno));
        return hardware_interface::return_type::ERROR;
      }
    } else {
      RCLCPP_WARN(
        rclcpp::get_logger("SitlHardwareInterface"),
        "Incomplete binary packet size received: %zd bytes, expected: %zu",
        bytes_received, sizeof(states_packet));
    }
  } else {
    // SITL Loopback Mode
    for (std::size_t i = 0; i < info_.joints.size(); ++i) {
      hw_velocities_[i] = hw_commands_[i];
      hw_positions_[i] += hw_velocities_[i] * period.seconds();
    }
  }

  return hardware_interface::return_type::OK;
}

hardware_interface::return_type SitlHardwareInterface::write(const rclcpp::Time & /*time*/, const rclcpp::Duration & /*period*/)
{
  if (is_hitl_mode_) {
    if (sock_ < 0) {
      RCLCPP_ERROR(rclcpp::get_logger("SitlHardwareInterface"), "Socket is not initialized!");
      return hardware_interface::return_type::ERROR;
    }

    ActuatorCommands commands_packet;
    std::memset(&commands_packet, 0, sizeof(commands_packet));

    for (std::size_t i = 0; i < info_.joints.size(); ++i) {
      commands_packet.joint_commands[i] = hw_commands_[i];
    }

    ssize_t bytes_sent = send(sock_, &commands_packet, sizeof(commands_packet), 0);
    if (bytes_sent != sizeof(commands_packet)) {
      if (bytes_sent < 0) {
        RCLCPP_ERROR(rclcpp::get_logger("SitlHardwareInterface"), "Error writing UDP data: %s", std::strerror(errno));
      } else {
        RCLCPP_WARN(
          rclcpp::get_logger("SitlHardwareInterface"),
          "Incomplete binary packet size sent: %zd bytes, expected: %zu",
          bytes_sent, sizeof(commands_packet));
      }
      return hardware_interface::return_type::ERROR;
    }
  } else {
    // SITL Loopback Mode - no additional write action required
  }

  return hardware_interface::return_type::OK;
}

}  // namespace teknosim_hardware_sitl_plugin

PLUGINLIB_EXPORT_CLASS(
  teknosim_hardware_sitl_plugin::SitlHardwareInterface, hardware_interface::SystemInterface)
