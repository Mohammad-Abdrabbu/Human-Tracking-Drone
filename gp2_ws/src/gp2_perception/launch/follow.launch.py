from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument

def generate_launch_description():
    params_file = LaunchConfiguration('params_file')

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file',
            default_value='',
            description='Path to default.yaml (optional if you use CLI params)'
        ),

        Node(
            package='gp2_perception',
            executable='follow_node',
            name='follow_node',
            output='screen',
            parameters=[{
                'udp_url':               LaunchConfiguration('f_udp_url'),
                'det_topic':             LaunchConfiguration('f_det_topic'),
                'tracks_topic':          LaunchConfiguration('f_tracks_topic'),
                'tracks_qos':            LaunchConfiguration('f_tracks_qos'),
                'require_target_selection': LaunchConfiguration('f_require_target_selection'),

                'img_w':     LaunchConfiguration('f_img_w'),
                'img_h':     LaunchConfiguration('f_img_h'),
                'hfov_deg':  LaunchConfiguration('f_hfov_deg'),
                'invert_ex': LaunchConfiguration('f_invert_ex'),

                'k_yaw':           LaunchConfiguration('f_k_yaw'),
                'kd_yaw':          LaunchConfiguration('f_kd_yaw'),
                'lpf_alpha':       LaunchConfiguration('f_lpf_alpha'),
                'deadzone':        LaunchConfiguration('f_deadzone'),
                'center_hold_deg': LaunchConfiguration('f_center_hold_deg'),
                'yawrate_max':     LaunchConfiguration('f_yawrate_max'),
                'rate_limit_yaw':  LaunchConfiguration('f_rate_limit_yaw'),

                'stand_off_px':    LaunchConfiguration('f_stand_off_px'),
                'max_close_px':    LaunchConfiguration('f_max_close_px'),
                'h_deadband_px':   LaunchConfiguration('f_h_deadband_px'),
                'kx':              LaunchConfiguration('f_kx'),
                'vx_max':          LaunchConfiguration('f_vx_max'),
                'rate_limit_vx':   LaunchConfiguration('f_rate_limit_vx'),
                'gate_ex':         LaunchConfiguration('f_gate_ex'),
                'h_lpf_alpha':     LaunchConfiguration('f_h_lpf_alpha'),
                'allow_reverse':   LaunchConfiguration('f_allow_reverse'),

                'stale_s':         LaunchConfiguration('f_stale_s'),
                'lock_k':          LaunchConfiguration('f_lock_k'),
                'publish_rate_hz': LaunchConfiguration('f_publish_rate_hz'),
                'scan_when_no_target': LaunchConfiguration('f_scan_when_no_target'),

                'do_auto_takeoff':     LaunchConfiguration('f_do_auto_takeoff'),
                'auto_takeoff_alt_m':  LaunchConfiguration('f_auto_takeoff_alt_m'),
                'takeoff_mode':        LaunchConfiguration('f_takeoff_mode'),

                'alt_guard_enable': LaunchConfiguration('f_alt_guard_enable'),
                'alt_max_m':        LaunchConfiguration('f_alt_max_m'),
                'alt_deadband_m':   LaunchConfiguration('f_alt_deadband_m'),
                'k_z_down':         LaunchConfiguration('f_k_z_down'),
                'vz_down_max':      LaunchConfiguration('f_vz_down_max'),
            }],
        ),
    ])
