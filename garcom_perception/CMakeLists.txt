cmake_minimum_required(VERSION 3.0.2)
project(garcom_perception)

find_package(catkin REQUIRED COMPONENTS rospy std_msgs)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/aruco_node.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
