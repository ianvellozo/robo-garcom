cmake_minimum_required(VERSION 3.0.2)
project(garcom_navigation)

find_package(catkin REQUIRED COMPONENTS rospy std_msgs garcom_msgs)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/navigation_node.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
install(FILES scripts/planejador.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
install(DIRECTORY config maps
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
