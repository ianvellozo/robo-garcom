cmake_minimum_required(VERSION 3.0.2)
project(garcom_msgs)

find_package(catkin REQUIRED COMPONENTS
  message_generation
  std_msgs
  actionlib_msgs
)

add_message_files(FILES
  Order.msg
  OrderStatus.msg
  PickupRequest.msg
  PickupDone.msg
  StockLevels.msg
)

add_service_files(FILES
  CheckStock.srv
  NextOrder.srv
  Restock.srv
  SetStock.srv
)

add_action_files(FILES
  GoToPoint.action
)

generate_messages(DEPENDENCIES
  std_msgs
  actionlib_msgs
)

catkin_package(CATKIN_DEPENDS
  message_runtime
  std_msgs
  actionlib_msgs
)
