import os
import pickle
import numpy as np
from mohou_ros_utils.conversion import imgmsg_to_numpy, numpy_to_imgmsg
from mohou_ros_utils.conversion import RGBImageConverter
from mohou_ros_utils.conversion import DepthImageConverter
from mohou_ros_utils.conversion import AngleVectorConverter
from mohou_ros_utils.conversion import VersatileConverter

from test_config import example_config  # noqa


def test_imgmsg_cv2_conversion():
    mat = np.random.randint(0, high=255, size=(224, 224, 3)).astype(np.uint8)
    msg = numpy_to_imgmsg(mat, 'rgb8')
    mat_again = imgmsg_to_numpy(msg)
    np.testing.assert_almost_equal(mat, mat_again)

    msg_again = numpy_to_imgmsg(mat_again, 'rgb8')
    assert msg.height == msg_again.height
    assert msg.width == msg_again.width
    assert msg.step == msg_again.step
    assert msg.encoding == msg_again.encoding
    assert msg.is_bigendian == msg_again.is_bigendian
    assert msg.data == msg_again.data


def get_test_data_path():
    here_full_filepath = os.path.join(os.getcwd(), __file__)
    here_full_dirpath = os.path.dirname(here_full_filepath)
    return os.path.join(here_full_dirpath, 'data')


def get_pickle_data_path(pickle_name):
    path = os.path.join(get_test_data_path(), pickle_name)
    if not os.path.exists(path):
        cmd = 'bash ' + os.path.join(get_test_data_path(), 'download_data.sh')
        os.system(cmd)

    with open(path, 'rb') as f:
        obj = pickle.load(f)
    return obj


def test_rgb_image_converter(example_config):  # type: ignore # noqa
    config = example_config
    rgb_image_msg = get_pickle_data_path('rgb_image.pkl')
    rgb_converter = RGBImageConverter.from_config(config)
    image = rgb_converter(rgb_image_msg)
    assert image.shape == (112, 112, 3)


def test_depth_image_converter(example_config):  # type: ignore # noqa
    config = example_config
    depth_image_msg = get_pickle_data_path('depth_image.pkl')
    depth_converter = DepthImageConverter.from_config(config)
    image = depth_converter(depth_image_msg)
    assert image.shape == (112, 112, 1)


def test_angle_vector_converter():
    # joint state of pr2
    joint_state = get_pickle_data_path('joint_states.pkl')

    control_joints = ['r_wrist_flex_joint', 'r_wrist_roll_joint']
    converter = AngleVectorConverter(control_joints)

    av = converter(joint_state)
    assert av.shape == (2,)


def test_versatile_converter(example_config):  # type: ignore # noqa
    config = example_config
    converter = VersatileConverter.from_config(config)

    rgb_image_msg = get_pickle_data_path('rgb_image.pkl')
    joint_state = get_pickle_data_path('joint_states.pkl')
    converter(rgb_image_msg)
    converter(joint_state)
