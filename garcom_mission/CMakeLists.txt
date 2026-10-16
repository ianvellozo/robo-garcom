cmake_minimum_required(VERSION 3.0.2)
project(garcom_mission)

find_package(catkin REQUIRED COMPONENTS rospy std_msgs garcom_msgs)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/order_queue.py
  scripts/mission_manager.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
