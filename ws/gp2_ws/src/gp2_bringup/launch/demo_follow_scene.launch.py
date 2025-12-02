from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import os

from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # Launch configurations
    use_sim_time = LaunchConfiguration('use_sim_time')
    follow_params_file = LaunchConfiguration('follow_params_file')
    perception_params_file = LaunchConfiguration('perception_params_file')
    geo_guard_params_file = LaunchConfiguration('geo_guard_params_file')

    # Package share dir for gp2_bringup
    bringup_share = get_package_share_directory('gp2_bringup')

    # === Launch arguments ===
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation (Gazebo) clock if true'
    )

    follow_params_arg = DeclareLaunchArgument(
        'follow_params_file',
        default_value=os.path.join(
            bringup_share,
            'config',
            'follow_params.yaml'
        ),
        description='Full path to the follow_node parameter file'
    )

    perception_params_arg = DeclareLaunchArgument(
        'perception_params_file',
        default_value=os.path.join(
            bringup_share,
            'config',
            'perception_params.yaml'
        ),
        description='Full path to the perception (YOLO + MOT) parameter file'
    )

    geo_guard_params_arg = DeclareLaunchArgument(
        'geo_guard_params_file',
        default_value=os.path.join(
            bringup_share,
            'config',
            'geo_guard_params.yaml'
        ),
        description='Full path to the geo_guard_node parameter file'
    )

    # === Camera bridge (Gazebo → ROS Image) ===
    # NOTE: Adjust the Gazebo topic if your world/model name changed.
    camera_bridge_node = Node(
        package='ros_gz_image',
        executable='image_bridge',
        name='camera_bridge',
        output='screen',
        emulate_tty=True,
        arguments=[
            '/world/default/model/x500_mono_cam_0/link/camera_link/sensor/imager/image'
        ],
        remappings=[
            ('/world/default/model/x500_mono_cam_0/link/camera_link/sensor/imager/image', '/camera/image_raw')
        ]
    )

    # === YOLO detection node ===
    yolo_node = Node(
        package='gp2_perception',
        executable='yolo_node',
        name='yolo_node',
        output='screen',
        emulate_tty=True,
        parameters=[
            perception_params_file,
            {'use_sim_time': use_sim_time}
        ],
    )

    # === ByteTrack MOT node ===
    bytetrack_node = Node(
        package='gp2_perception',
        executable='bytetrack_node',
        name='bytetrack_node',
        output='screen',
        emulate_tty=True,
        parameters=[
            perception_params_file,
            {'use_sim_time': use_sim_time}
        ],
    )

    # === Geo-guard node ===
    geo_guard_node = Node(
        package='gp2_perception',
        executable='geo_guard_node',
        name='geo_guard_node',
        output='screen',
        emulate_tty=True,
        parameters=[
            geo_guard_params_file,
            {'use_sim_time': use_sim_time}
        ],
        # If your node uses different topic names, add remappings here, e.g.:
        # remappings=[
        #     ('/vehicle_pose_in', '/gp2/vehicle/pose_local'),
        #     ('/cmd_in', '/gp2/follow/cmd_body'),
        #     ('/cmd_out', '/gp2/guard/cmd_body'),
        #     ('/guard/status', '/gp2/guard/status'),
        #     ('/guard/reason', '/gp2/guard/reason'),
        # ],
    )

    # === Follow node (already working from S1) ===
    follow_node = Node(
        package='gp2_perception',
        executable='follow_node',
        name='follow_node',
        output='screen',
        emulate_tty=True,
        parameters=[
            follow_params_file,
            {'use_sim_time': use_sim_time}
        ],
    )

    return LaunchDescription([
        use_sim_time_arg,
        follow_params_arg,
        perception_params_arg,
        geo_guard_params_arg,
        camera_bridge_node,
        yolo_node,
        bytetrack_node,
        geo_guard_node,
        follow_node,
    ])
