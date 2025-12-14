from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from launch_ros.actions import Node
import os

from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # Launch configurations
    use_sim_time = LaunchConfiguration('use_sim_time')
    follow_params_file = LaunchConfiguration('follow_params_file')
    perception_params_file = LaunchConfiguration('perception_params_file')
    geo_guard_params_file = LaunchConfiguration('geo_guard_params_file')
    world_name = LaunchConfiguration('world_name')
    enable_geofence = LaunchConfiguration('enable_geofence')

    # Package share dir for sahtd_launch
    launch_share = get_package_share_directory('sahtd_launch')

    # === Launch arguments ===
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation (Gazebo) clock if true'
    )

    follow_params_arg = DeclareLaunchArgument(
        'follow_params_file',
        default_value=os.path.join(
            launch_share,
            'config',
            'follow.yaml'
        ),
        description='Full path to the follow_node parameter file'
    )

    perception_params_arg = DeclareLaunchArgument(
        'perception_params_file',
        default_value=os.path.join(
            launch_share,
            'config',
            'perception.yaml'
        ),
        description='Full path to the perception (YOLO + MOT) parameter file'
    )

    geo_guard_params_arg = DeclareLaunchArgument(
        'geo_guard_params_file',
        default_value=os.path.join(
            launch_share,
            'config',
            'geo_guard.yaml'
        ),
        description='Full path to the geo_guard_node parameter file'
    )

    world_name_arg = DeclareLaunchArgument(
        'world_name',
        default_value='default',
        description='Gazebo world name for topic path derivation'
    )

    enable_geofence_arg = DeclareLaunchArgument(
        'enable_geofence',
        default_value='true',
        description='Enable geofence nodes (set false for tracking demo scenes)'
    )

    target_actor_name_arg = DeclareLaunchArgument(
        'target_actor_name',
        default_value='person_violator',
        description='Name of the actor entity to monitor for geofence violations'
    )
    target_actor_name = LaunchConfiguration('target_actor_name')

    # === Camera bridge (Gazebo → ROS Image) ===
    # Topic path derived from world_name argument
    camera_bridge_node = Node(
        package='ros_gz_image',
        executable='image_bridge',
        name='camera_bridge',
        output='screen',
        emulate_tty=True,
        arguments=[
            ['/world/', world_name, '/model/x500_mono_cam_0/link/camera_link/sensor/imager/image']
        ],
        remappings=[
            (['/world/', world_name, '/model/x500_mono_cam_0/link/camera_link/sensor/imager/image'], '/camera/image_raw')
        ]
    )

    # === YOLO detection node ===
    yolo_node = Node(
        package='sahtd_autonomy',
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
        package='sahtd_autonomy',
        executable='bytetrack_node',
        name='bytetrack_node',
        output='screen',
        emulate_tty=True,
        parameters=[
            perception_params_file,
            {'use_sim_time': use_sim_time}
        ],
    )

    # === Geo-guard node (conditional on enable_geofence) ===
    geo_guard_node = Node(
        package='sahtd_autonomy',
        executable='geo_guard_node',
        name='geo_guard_node',
        output='screen',
        emulate_tty=True,
        condition=IfCondition(enable_geofence),
        parameters=[
            geo_guard_params_file,
            {'use_sim_time': use_sim_time}
        ],
    )

    # === Follow node (already working from S1) ===
    # Delayed start to ensure PX4 SITL is fully initialized before MAVSDK connection
    follow_node = TimerAction(
        period=5.0,  # 5-second delay
        actions=[
            Node(
                package='sahtd_autonomy',
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
    # Topic path derived from world_name argument
    pose_bridge_node = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='pose_bridge',
        output='screen',
        emulate_tty=True,
        arguments=[
            ['/world/', world_name, '/pose/info@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V']
        ],
        remappings=[
            (['/world/', world_name, '/pose/info'], '/gp2/world_poses')
        ]
    )

    # === Lane B2: Actor Pose Selector Node ===
    # Extracts specific actor pose from world_poses and publishes /gp2/target_pose_gt
    # Only runs when geofence is enabled
    actor_pose_selector_node = Node(
        package='sahtd_autonomy',
        executable='actor_pose_selector_node',
        name='actor_pose_selector_node',
        output='screen',
        emulate_tty=True,
        condition=IfCondition(enable_geofence),
        parameters=[
            {'target_actor_name': target_actor_name},
            {'output_frame_id': 'map'},
            {'publish_rate_hz': 10.0},
            {'gz_topic': ['/world/', world_name, '/pose/info']},
            {'use_sim_time': use_sim_time}
        ],
    )

    # === Lane B2: Target Guard Node (Human-aware geo-guard) ===
    # Monitors target position relative to fence
    # Only runs when geofence is enabled
    target_guard_node = Node(
        package='sahtd_autonomy',
        executable='target_guard_node',
        name='target_guard_node',
        output='screen',
        emulate_tty=True,
        condition=IfCondition(enable_geofence),
        parameters=[
            geo_guard_params_file,  # Reuse same fence config
            {'use_sim_time': use_sim_time}
        ],
    )

    # === Lane B3: Target Visualization Node ===
    # Overlays bounding boxes and track IDs on camera image
    target_viz_node = Node(
        package='sahtd_autonomy',
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

    # === rqt_image_view to display target_viz_node output ===
    # Delayed start to ensure target_viz_node is publishing
    image_viewer_node = TimerAction(
        period=6.0,  # 6-second delay
        actions=[
            Node(
                package='rqt_image_view',
                executable='rqt_image_view',
                name='target_image_viewer',
                output='screen',
                arguments=['/perception/debug_image_tracks'],
            )
        ]
    )

    return LaunchDescription([
        use_sim_time_arg,
        follow_params_arg,
        perception_params_arg,
        geo_guard_params_arg,
        world_name_arg,
        enable_geofence_arg,
        target_actor_name_arg,
        camera_bridge_node,
        yolo_node,
        bytetrack_node,
        geo_guard_node,
        follow_node,
        pose_bridge_node,
        actor_pose_selector_node,
        target_guard_node,
        target_viz_node,
        image_viewer_node,
    ])


