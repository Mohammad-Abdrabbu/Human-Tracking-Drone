from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument

def generate_launch_description():
    # YAML-backed params (we map YAML -> node parameters)
    params_file = LaunchConfiguration('params_file')

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file',
            default_value='',
            description='Path to default.yaml (optional if you use CLI params)'
        ),

        # YOLO detector (E)
        Node(
            package='gp2_perception',
            executable='yolo_node',
            name='yolo_node',
            output='screen',
            parameters=[{
                'model_path':         LaunchConfiguration('yolo_model_path'),
                'conf':               LaunchConfiguration('yolo_conf'),
                'imgsz':              LaunchConfiguration('yolo_imgsz'),
                'publish_debug_image':LaunchConfiguration('yolo_publish_debug_image'),
            }],
            remappings=[
                ('/camera/image_raw', LaunchConfiguration('yolo_image_topic')),
            ]
        ),

        # ByteTrack (M)
        Node(
            package='gp2_perception',
            executable='bytetrack_node',
            name='bytetrack_node',
            output='screen',
            parameters=[{
                'detections_topic':   LaunchConfiguration('bt_detections_topic'),
                'tracks_topic':       LaunchConfiguration('bt_tracks_topic'),
                'seen_ids_topic':     LaunchConfiguration('bt_seen_ids_topic'),
                'diagnostics_topic':  LaunchConfiguration('bt_diagnostics_topic'),
                'mot_classes':        LaunchConfiguration('bt_mot_classes'),
                'conf_thres':         LaunchConfiguration('bt_conf_thres'),
                'track_thresh':       LaunchConfiguration('bt_track_thresh'),
                'match_thresh':       LaunchConfiguration('bt_match_thresh'),
                'track_buffer':       LaunchConfiguration('bt_track_buffer'),
                'max_age_without_det':LaunchConfiguration('bt_max_age_without_det'),
                'min_box_area_px':    LaunchConfiguration('bt_min_box_area_px'),
                'fps_min':            LaunchConfiguration('bt_fps_min'),
                'debug_image_enable': LaunchConfiguration('bt_debug_image_enable'),
            }],
        ),
    ])
