import os
from setuptools import find_packages, setup

install_requires = [
    "numpy",
    "scipy",
    "scikit-robot",
    "mohou>=0.2.7",
    "tunable-filter>=0.0.4",
]

if "ROS_DISTRO" in os.environ:
    if os.environ["ROS_DISTRO"] != "noetic":
        install_requires.append("bagpy")  # to avoid building rosbag from source
else:
    if not os.path.isdir("/opt/ros/noetic"):
        install_requires.append("bagpy")  # to avoid building rosbag from source


setup(
    name='mohou_ros_utils',
    version='0.0.1',
    description='utility for imitation learning data processing',
    author='Hirokazu Ishida',
    author_email='h-ishida@jsk.imi.i.u-tokyo.ac.jp',
    license='MIT',
    install_requires=install_requires,
    packages=find_packages(exclude=('tests', 'docs'))
)
