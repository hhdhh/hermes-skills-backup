#!/usr/bin/env python3
"""rear_to_front_scan.py — AutoLife 案B：后雷达(360°)直接转发到 front_lidar。
前雷达硬件缺失/未接（日志 `mod_lidar_front not found`）但后雷达完整 360° 时，
把后雷达 LaserScan 复制发布到 front_lidar，让合并器正常合成 /merged。
用法: python3 rear_to_front_scan.py --ros-args -p robot_id:=320
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


class RearToFrontBridge(Node):
    def __init__(self):
        super().__init__('rear_to_front_scan')
        self.robot_id = self.declare_parameter('robot_id', '320').value
        self.rear_topic = self.declare_parameter(
            'rear_topic', f'/topic_gv_rear_lidar_0_{self.robot_id}').value
        self.front_topic = self.declare_parameter(
            'front_topic', f'/topic_gv_front_lidar_0_{self.robot_id}').value
        self.pub = self.create_publisher(LaserScan, self.front_topic, 10)
        self.sub = self.create_subscription(
            LaserScan, self.rear_topic, self.on_scan, 10)
        self.get_logger().info(
            f'rear_to_front: {self.rear_topic} -> {self.front_topic}')

    def on_scan(self, msg):
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = RearToFrontBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
