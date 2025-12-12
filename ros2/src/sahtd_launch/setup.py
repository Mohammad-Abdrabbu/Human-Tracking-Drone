from setuptools import setup
import os
from glob import glob

package_name = 'sahtd_launch'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        # Ament index so ROS 2 can find the package
        (os.path.join('share', 'ament_index', 'resource_index', 'packages'),
         [os.path.join('resource', package_name)]),

        # Package manifest
        (os.path.join('share', package_name), ['package.xml']),

        # Install launch files
        (os.path.join('share', package_name, 'launch'),
         glob('launch/*.launch.py')),

        # Install config files
        (os.path.join('share', package_name, 'config'),
         glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Mohammad',
    maintainer_email='you@example.com',
    description='Launch files and configurations for Security-Aware Human Tracking Drone.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        # No nodes yet, only launch files/config
        'console_scripts': [
        ],
    },
)
