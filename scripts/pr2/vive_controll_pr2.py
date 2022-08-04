#!/usr/bin/env python3
import argparse
import os
import signal
import subprocess
import threading
import time
from abc import abstractmethod
from dataclasses import dataclass
from typing import Callable, ClassVar, List, Optional

import numpy as np
import rospy
from mohou.file import get_project_path
from skrobot.model import Link
from skrobot.models import PR2
from sound_play.libsoundplay import SoundClient

from mohou_ros_utils.config import Config
from mohou_ros_utils.pr2.params import larm_joint_names, rarm_joint_names
from mohou_ros_utils.script_utils import (
    count_rosbag_file,
    create_rosbag_command,
    get_latest_rosbag_filename,
    get_rosbag_filepath,
)
from mohou_ros_utils.utils import CoordinateTransform
from mohou_ros_utils.vive_controller.robot_interface import (
    SkrobotPR2Controller,
    SkrobotPR2LarmController,
    SkrobotPR2RarmController,
)
from mohou_ros_utils.vive_controller.vive_base import JoyDataManager, ViveController


class PR2ViveController(ViveController):
    robot_con: SkrobotPR2Controller
    config: Config
    gripper_close: bool
    tf_handref2camera: Optional[CoordinateTransform] = None
    tf_gripperref2base: Optional[CoordinateTransform] = None

    def __init__(
        self,
        joy_topic_name: str,
        pose_topic_name: str,
        robot_con: SkrobotPR2Controller,
        config: Config,
        scale: float,
    ):

        super().__init__(joy_topic_name, pose_topic_name, scale)
        self.robot_con = robot_con
        self.config = config
        self.gripper_close = False
        self.config = config

        self.joy_manager.register_processor(JoyDataManager.Button.BOTTOM, self.switch_grasp_state)
        self.joy_manager.register_processor(JoyDataManager.Button.SIDE, self.reset_to_home_position)
        self.loginfo("controller is initialized")

    @property
    @abstractmethod
    def arm_joint_names(self) -> List[str]:
        pass

    @property
    @abstractmethod
    def arm_end_effector_name(self) -> str:
        pass

    @property
    @abstractmethod
    def gripper_joint_name(self) -> str:
        pass

    def send_tracking_command(self, tf_gripper2base_target: CoordinateTransform) -> None:
        joints = [self.robot_con.robot_model.__dict__[jname] for jname in self.arm_joint_names]
        link_list = [joint.child_link for joint in joints]
        end_effector = self.robot_con.robot_model.__dict__[self.arm_end_effector_name]
        av_next = self.robot_con.robot_model.inverse_kinematics(
            tf_gripper2base_target.to_skrobot_coords(), end_effector, link_list, stop=5
        )

        if isinstance(av_next, np.ndarray):
            self.robot_con.update_real_robot(av_next, time=0.8)
        else:
            self.logwarn("solving inverse kinematics failed")

    def get_robot_end_coords(self) -> CoordinateTransform:
        self.robot_con.robot_model.angle_vector(self.robot_con.get_real_robot_joint_angles())
        end_effector: Link = self.robot_con.robot_model.__dict__[self.arm_end_effector_name]
        coords = end_effector.copy_worldcoords()
        tf_gripperref2base = CoordinateTransform.from_skrobot_coords(coords, "gripper-ref", "base")
        return tf_gripperref2base

    def switch_grasp_state(self) -> None:
        if self.gripper_close:
            self.robot_con.move_gripper(0.06)
            self.gripper_close = False
        else:
            self.robot_con.move_gripper(0.0)
            self.gripper_close = True

    def reset_to_home_position(self, reset_grasp: bool = True) -> None:
        self.is_tracking = False
        self.loginfo("turn off tracker")
        self.loginfo("resetting to home position")
        assert self.config.home_position is not None

        for joint_name in self.config.home_position.keys():
            angle = self.config.home_position[joint_name]
            self.robot_con.robot_model.__dict__[joint_name].joint_angle(angle)
        self.robot_con.robot_interface.angle_vector(
            self.robot_con.robot_model.angle_vector(), time=3.0, time_scale=1.0
        )
        self.config.home_position[self.gripper_joint_name]
        if reset_grasp:
            self.robot_con.move_gripper(self.config.home_position[self.gripper_joint_name])
        self.robot_con.robot_interface.wait_interpolation()


@dataclass
class RosbagManager:
    config: Config
    sound_client: SoundClient
    closure_stop: Optional[Callable] = None

    @property
    def is_running(self) -> bool:
        return self.closure_stop is not None

    def start(self) -> None:
        assert not self.is_running
        path = get_rosbag_filepath(self.config.project_path, time.strftime("%Y%m%d%H%M%S"))
        cmd = create_rosbag_command(path, config)
        p = subprocess.Popen(cmd)
        rospy.loginfo(p)
        share = {"is_running": True}

        def closure_stop():
            share["is_running"] = False

        self.closure_stop = closure_stop

        class Observer(threading.Thread):
            def run(self):
                while True:
                    time.sleep(0.5)
                    if not share["is_running"]:
                        rospy.loginfo("kill rosbag process")
                        os.kill(p.pid, signal.SIGTERM)
                        break

        self.sound_client.say("Start saving rosbag")
        thread = Observer()
        thread.start()

    def stop(self) -> None:
        assert self.is_running
        assert self.closure_stop is not None
        n_count = count_rosbag_file(self.config.project_path) + 1  # because we are gonna add one
        self.sound_client.say("Finish saving rosbag. Total number is {}".format(n_count))

        self.closure_stop()
        self.closure_stop = None

    def switch_state(self) -> None:
        rospy.loginfo("switch rosbag state")
        if self.is_running:
            self.stop()
        else:
            self.start()


class PR2RightArmViveController(PR2ViveController):
    rosbag_manager: RosbagManager
    arm_joint_names: ClassVar[List[str]] = rarm_joint_names
    arm_end_effector_name: ClassVar[str] = "r_gripper_tool_frame"
    gripper_joint_name: ClassVar[str] = "r_gripper_joint"
    log_prefix: ClassVar[str] = "Right"

    def __init__(self, config: Config, scale: float):
        controller_id = "LHR_F7AFBF47"
        joy_topic = "/controller_{}/joy".format(controller_id)
        pose_topic = "/controller_{}_as_posestamped".format(controller_id)

        robot_con = SkrobotPR2RarmController(PR2())
        super().__init__(joy_topic, pose_topic, robot_con, config, scale)

        rosbag_manager = RosbagManager(config, self.sound_client)
        self.rosbag_manager = rosbag_manager
        self.joy_manager.register_processor(
            JoyDataManager.Button.FRONT, rosbag_manager.switch_state
        )


class PR2LeftArmViveController(PR2ViveController):
    arm_joint_names: ClassVar[List[str]] = larm_joint_names
    arm_end_effector_name: ClassVar[str] = "l_gripper_tool_frame"
    gripper_joint_name: ClassVar[str] = "l_gripper_joint"
    log_prefix: ClassVar[str] = "Left"

    def __init__(self, config: Config, scale: float):
        controller_id = "LHR_FD35BD42"
        joy_topic = "/controller_{}/joy".format(controller_id)
        pose_topic = "/controller_{}_as_posestamped".format(controller_id)
        robot_con = SkrobotPR2LarmController(PR2())
        super().__init__(joy_topic, pose_topic, robot_con, config, scale)

        self.joy_manager.register_processor(JoyDataManager.Button.FRONT, self.delete_latest_rosbag)

    def delete_latest_rosbag(self) -> None:
        latest_rosbag = get_latest_rosbag_filename(self.config.project_path)
        if latest_rosbag is None:
            message = "deleting rosbag failed because there is no rosbag"
            rospy.logwarn(message)
            self.sound_client.say(message)
        else:
            rospy.logwarn("delete rosbag file named {}".format(latest_rosbag))
            self.sound_client.say("delete latest rosbag")
            os.remove(latest_rosbag)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-pn", type=str, help="project name")
    parser.add_argument("-scale", type=float, default=1.5, help="controller to real scaling")
    args, unknown = parser.parse_known_args()

    scale: float = args.scale
    project_name: Optional[str] = args.pn

    project_path = get_project_path(project_name)
    config = Config.from_project_path(project_path)

    rospy.init_node("pr2_vive_mohou")
    rarm_con = PR2RightArmViveController(config, scale)
    larm_con = PR2LeftArmViveController(config, scale)
    rarm_con.start()
    larm_con.start()
    rospy.spin()
