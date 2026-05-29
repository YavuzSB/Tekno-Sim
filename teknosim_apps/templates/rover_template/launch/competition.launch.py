import os
from launch import LaunchDescription
from launch.actions import LogInfo, DeclareLaunchArgument
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    pkg_share = get_package_share_directory('rover_template')
    
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

    # ros2_control controller manager node
    controller_manager = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=[controller_config],
        output='screen'
    )

    # Spawner nodes for controllers
    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster', '--controller-manager', '/controller_manager'],
        output='screen'
    )

    rover_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['rover_base_controller', '--controller-manager', '/controller_manager'],
        output='screen'
    )

    return LaunchDescription([
        mode_arg,
        LogInfo(msg=f"[TeknoSim Rover] Selected Operation Mode: {teknosim_mode}"),
        controller_manager,
        joint_state_broadcaster_spawner,
        rover_controller_spawner
    ])
