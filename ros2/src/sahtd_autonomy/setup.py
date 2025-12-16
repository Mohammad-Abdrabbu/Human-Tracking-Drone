from setuptools import find_packages, setup

package_name = 'sahtd_autonomy'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'mavsdk'],
    zip_safe=True,
    maintainer='ramadan',
    maintainer_email='mohammed.abdrabbu46@gmail.com',
    description='SAHTD Autonomy - Perception and Control for Security-Aware Human Tracking Drone',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={ 
        'console_scripts': [
            'yolo_node = sahtd_autonomy.perception.yolo_node:main',
            'bytetrack_node = sahtd_autonomy.perception.bytetrack_node:main',
            'target_viz_node = sahtd_autonomy.perception.target_viz_node:main',
            'follow_node = sahtd_autonomy.control.follow_node:main',
            'geo_guard_node = sahtd_autonomy.control.geo_guard_node:main',
            'actor_pose_selector_node = sahtd_autonomy.helpers.actor_pose_selector_node:main',
            'target_guard_node = sahtd_autonomy.helpers.target_guard_node:main',
            'target_select_helper_node = sahtd_autonomy.helpers.target_select_helper_node:main',
            'event_logger_node = sahtd_autonomy.monitoring.sahtd_event_logger_node:main',
        ],},


)
