cmake_minimum_required(VERSION 3.0.2)
project(garcom_simulation)

find_package(catkin REQUIRED)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/gerar_mundo.py
  scripts/simulador_2d.py
  scripts/obstaculo.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
install(DIRECTORY config launch rviz urdf worlds
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
