from setuptools import find_packages, setup

package_name = 'sahtd_web_bridge'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ramadan',
    maintainer_email='mohammed.abdrabbu46@gmail.com',
    description='SAHTD Web Bridge - Telemetry logger for web dashboard',
    license='Apache-2.0',
    extras_require={
        'test': ['pytest'],
    },
    entry_points={
        'console_scripts': [
            'telemetry_bridge_node = sahtd_web_bridge.telemetry_bridge_node:main',
            'video_bridge_node = sahtd_web_bridge.video_bridge_node:main',
        ],
    },
)
