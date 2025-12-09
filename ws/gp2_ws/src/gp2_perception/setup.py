from setuptools import find_packages, setup

package_name = 'gp2_perception'

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
    description='YOLOv8 -> vision_msgs/Detection2DArray',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={ 
        'console_scripts': [
            'yolo_node = gp2_perception.yolo_node:main',
            'bytetrack_node  = gp2_perception.bytetrack_node:main',
            'follow_node = gp2_perception.follow_node:main',
            'detect_rotate = gp2_detect_rotate.detect_rotate_node:main', 
            'geo_guard_node = gp2_perception.geo_guard_node:main',
            'actor_pose_selector_node = gp2_perception.actor_pose_selector_node:main',
            'target_guard_node = gp2_perception.target_guard_node:main',
            'target_viz_node = gp2_perception.target_viz_node:main',
            'target_select_helper_node = gp2_perception.target_select_helper_node:main',
        ],},


)
