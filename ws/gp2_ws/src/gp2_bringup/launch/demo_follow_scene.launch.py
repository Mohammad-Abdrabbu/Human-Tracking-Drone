from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
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
    # Delayed start to ensure PX4 SITL is fully initialized before MAVSDK connection
    follow_node = TimerAction(
        period=5.0,  # 5-second delay
        actions=[
            Node(
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
        ]
    )

    # === Lane B2: Gazebo Pose Bridge (Pose_V → TFMessage) ===
    # Bridges /world/default/pose/info to ROS as TF messages
    pose_bridge_node = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='pose_bridge',
        output='screen',
        emulate_tty=True,
        arguments=[
            '/world/default/pose/info@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V'
        ],
        remappings=[
            ('/world/default/pose/info', '/gp2/world_poses')
        ]
    )

    # === Lane B2: Actor Pose Selector Node ===
    # Extracts specific actor pose from world_poses and publishes /gp2/target_pose_gt
    actor_pose_selector_node = Node(
        package='gp2_perception',
        executable='actor_pose_selector_node',
        name='actor_pose_selector_node',
        output='screen',
        emulate_tty=True,
        parameters=[
            {'target_actor_name': 'human_violate'},  # Default target
            {'output_frame_id': 'map'},
            {'publish_rate_hz': 10.0},
            {'use_sim_time': use_sim_time}
        ],
    )

    # === Lane B2: Target Guard Node (Human-aware geo-guard) ===
    # Monitors target position relative to fence
    target_guard_node = Node(
        package='gp2_perception',
        executable='target_guard_node',
        name='target_guard_node',
        output='screen',
        emulate_tty=True,
        parameters=[
            geo_guard_params_file,  # Reuse same fence config
            {'use_sim_time': use_sim_time}
        ],
    )

    # === Lane B3: Target Visualization Node ===
    # Overlays bounding boxes and track IDs on camera image
    target_viz_node = Node(
        package='gp2_perception',
        executable='target_viz_node',
        name='target_viz_node',
        output='screen',
        emulate_tty=True,
        parameters=[
            {'image_topic': '/camera/image_raw'},
            {'tracks_topic': '/perception/tracks'},
            {'target_select_topic': '/perception/target_select'},
            {'output_image_topic': '/perception/debug_image_tracks'},
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
        pose_bridge_node,
        actor_pose_selector_node,
        # target_guard_node,  # TEMPORARILY DISABLED for testing
        target_viz_node,
    ])


