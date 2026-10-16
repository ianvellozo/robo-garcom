cmake_minimum_required(VERSION 3.0.2)
project(garcom_interface)

find_package(catkin REQUIRED COMPONENTS rospy garcom_msgs)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/interface_node.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
