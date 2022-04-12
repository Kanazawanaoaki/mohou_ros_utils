import os
import yaml
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class TopicConfig:
    rgb_topic: str
    depth_topic: str
    av_topic: str

    @classmethod
    def from_yaml_dict(cls, yaml_dict: Dict) -> 'TopicConfig':
        return cls(
            yaml_dict['RGBImage'],
            yaml_dict['DepthImage'],
            yaml_dict['AngleVector'])


@dataclass
class ImageConfig:
    x_min: int
    x_max: int
    y_min: int
    y_max: int
    resol: int

    @classmethod
    def from_yaml_dict(cls, yaml_dict: Dict) -> 'ImageConfig':
        return cls(
            yaml_dict['x_min'],
            yaml_dict['x_max'],
            yaml_dict['y_min'],
            yaml_dict['y_max'],
            yaml_dict['resol'])


@dataclass
class Config:
    control_joints: List[str]
    hz: float
    topics: TopicConfig
    image_config: ImageConfig

    @classmethod
    def from_yaml_dict(cls, yaml_dict: Dict) -> 'Config':
        control_joints = yaml_dict['control_joints']
        hz = yaml_dict['sampling_hz']
        topics = TopicConfig.from_yaml_dict(yaml_dict['topic'])
        image_config = ImageConfig.from_yaml_dict(yaml_dict['image'])
        return cls(
            control_joints,
            hz,
            topics,
            image_config)

    @classmethod
    def from_yaml_file(cls, file_path: str) -> 'Config':
        with open(file_path, 'r') as f:
            dic = yaml.safe_load(f)
        return cls.from_yaml_dict(dic)

    @classmethod
    def from_rospkg_path(cls, package_name: str, relative_path: str) -> 'Config':
        try:
            import rospkg
        except ImportError as e:
            e
            assert False, 'You need to intall ros. Or, maybe forget sourcing?'

        base_dir = rospkg.RosPack().get_path(package_name)
        yaml_file_path = os.path.join(base_dir, relative_path)
        return cls.from_yaml_file(yaml_file_path)
