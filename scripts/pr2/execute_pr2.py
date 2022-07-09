#!/usr/bin/env python3
import argparse
import rospy

from mohou_ros_utils import _default_project_name
from mohou_ros_utils.pr2.executor import SkrobotPR2Executor


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-pn', type=str, default=_default_project_name, help='project name')
    parser.add_argument('--force', action='store_true', help='disable dry option')
    parser.add_argument('-hz', type=float, default=1.0, help='run Hz')
    parser.add_argument('-avt', type=float, default=1.0, help='angle_vector time')

    args = parser.parse_args()
    project_name = args.pn
    force = args.force
    hz = args.hz
    avt = args.avt

    rospy.init_node('executor', disable_signals=True)
    executor = SkrobotPR2Executor(project_name, dryrun=(not force), hz=hz, angle_vector_time=avt)
    executor.run()

    try:
        while(True):
            rospy.rostime.wallsleep(0.5)
    except KeyboardInterrupt:
        rospy.loginfo('finish')
        executor.terminate()
