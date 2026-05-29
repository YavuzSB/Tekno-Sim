import os
from launch import LaunchDescription
from launch.actions import LogInfo, DeclareLaunchArgument
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    pkg_share = get_package_share_directory('sancak_hss_template')
    
    # TEKNOSIM_MODE Environment variable check & log
    teknosim_mode = os.environ.get('TEKNOSIM_MODE', 'SITL')
    
    # Declare launch arguments
    mode_arg = DeclareLaunchArgument(
        'mode',
        default_value=teknosim_mode,
        description='Simulation mode (SITL, HITL, PRODUCTION)'
    )

    # Controller configuration file path
    controller_config = os.path.join(pkg_share, 'config', 'generic_controller.yaml')

    robot_description = """<?xml version="1.0"?>
<robot name="sancak_hss">
  <link name="base_link"/>
  <joint name="rotor1_joint" type="continuous">
    <parent link="base_link"/>
    <child link="rotor1_link"/>
  </joint>
  <link name="rotor1_link"/>
  <joint name="rotor2_joint" type="continuous">
    <parent link="base_link"/>
    <child link="rotor2_link"/>
  </joint>
  <link name="rotor2_link"/>
  <joint name="rotor3_joint" type="continuous">
    <parent link="base_link"/>
    <child link="rotor3_link"/>
  </joint>
  <link name="rotor3_link"/>
  <joint name="rotor4_joint" type="continuous">
    <parent link="base_link"/>
    <child link="rotor4_link"/>
  </joint>
  <link name="rotor4_link"/>
  <ros2_control name="SITLSystem" type="system">
    <hardware>
      <plugin>teknosim_hardware_sitl_plugin/SitlHardwareInterface</plugin>
    </hardware>
    <joint name="rotor1_joint">
      <command_interface name="velocity"/>
      <state_interface name="position"/>
      <state_interface name="velocity"/>
    </joint>
    <joint name="rotor2_joint">
      <command_interface name="velocity"/>
      <state_interface name="position"/>
      <state_interface name="velocity"/>
    </joint>
    <joint name="rotor3_joint">
      <command_interface name="velocity"/>
      <state_interface name="position"/>
      <state_interface name="velocity"/>
    </joint>
    <joint name="rotor4_joint">
      <command_interface name="velocity"/>
      <state_interface name="position"/>
      <state_interface name="velocity"/>
    </joint>
  </ros2_control>
</robot>"""

    # ros2_control controller manager node
    controller_manager = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=[controller_config, {'robot_description': robot_description}],
        remappings=[('~/robot_description', '/robot_description')],
        output='screen'
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description}]
    )

    # Spawner nodes for controllers
    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster', '--controller-manager', '/controller_manager'],
        output='screen'
    )

    velocity_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['sancak_velocity_controller', '--controller-manager', '/controller_manager'],
        output='screen'
    )

    return LaunchDescription([
        mode_arg,
        LogInfo(msg=f"[TeknoSim Sancak HSS] Selected Operation Mode: {teknosim_mode}"),
        robot_state_publisher,
        controller_manager,
        joint_state_broadcaster_spawner,
        velocity_controller_spawner
    ])
