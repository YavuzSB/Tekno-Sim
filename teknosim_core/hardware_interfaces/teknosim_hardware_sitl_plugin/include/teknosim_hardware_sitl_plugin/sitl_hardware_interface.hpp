#ifndef TEKNOSIM_HARDWARE_SITL_PLUGIN__SITL_HARDWARE_INTERFACE_HPP_
#define TEKNOSIM_HARDWARE_SITL_PLUGIN__SITL_HARDWARE_INTERFACE_HPP_

#include <vector>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstring>
#include <string>

#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/handle.hpp"
#include "hardware_interface/hardware_info.hpp"
#include "hardware_interface/types/hardware_interface_return_values.hpp"
#include "rclcpp/macros.hpp"
#include "rclcpp_lifecycle/node_interfaces/lifecycle_node_interface.hpp"
#include "rclcpp_lifecycle/state.hpp"

namespace teknosim_hardware_sitl_plugin
{

constexpr size_t MAX_JOINTS = 32;

struct ActuatorCommands
{
  double joint_commands[MAX_JOINTS];
};

struct SensorStates
{
  double joint_positions[MAX_JOINTS];
  double joint_velocities[MAX_JOINTS];
};

class SitlHardwareInterface : public hardware_interface::SystemInterface
{
public:
  RCLCPP_SHARED_PTR_DEFINITIONS(SitlHardwareInterface)

  hardware_interface::CallbackReturn on_init(const hardware_interface::HardwareInfo & info) override;
  std::vector<hardware_interface::StateInterface> export_state_interfaces() override;
  std::vector<hardware_interface::CommandInterface> export_command_interfaces() override;
  hardware_interface::CallbackReturn on_activate(const rclcpp_lifecycle::State & previous_state) override;
  hardware_interface::CallbackReturn on_deactivate(const rclcpp_lifecycle::State & previous_state) override;
  hardware_interface::return_type read(const rclcpp::Time & time, const rclcpp::Duration & period) override;
  hardware_interface::return_type write(const rclcpp::Time & time, const rclcpp::Duration & period) override;

private:
  // Hardware command and state vectors
  std::vector<double> hw_commands_;
  std::vector<double> hw_positions_;
  std::vector<double> hw_velocities_;

  // HITL / SITL mode control
  bool is_hitl_mode_{false};

  // Socket communication members
  int sock_{-1};
  struct sockaddr_in server_addr_{};
};

}  // namespace teknosim_hardware_sitl_plugin

#endif  // TEKNOSIM_HARDWARE_SITL_PLUGIN__SITL_HARDWARE_INTERFACE_HPP_
