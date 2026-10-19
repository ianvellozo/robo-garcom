cmake_minimum_required(VERSION 3.0.2)
project(garcom_interface)

find_package(catkin REQUIRED COMPONENTS rospy garcom_msgs)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/interface_node.py
  scripts/station_panel.py
  scripts/web_server.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
install(DIRECTORY web
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
