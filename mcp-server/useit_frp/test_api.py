import unittest
import requests
import time
import threading
import sys
from api_server import app

class ApiTestCase(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """在所有测试开始前，启动Flask服务器"""
        cls.port = 5015  # 使用一个不同的端口以避免冲突
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        def run_app():
            try:
                # 在测试环境中禁用重载器
                app.run(host='127.0.0.1', port=cls.port, use_reloader=False)
            except Exception as e:
                print(f"Flask 服务器启动失败: {e}", file=sys.stderr)

        cls.server_thread = threading.Thread(target=run_app)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        
        # 通过轮询健康检查接口来等待服务器就绪
        start_time = time.time()
        while time.time() - start_time < 15:  # 15秒超时
            try:
                response = requests.get(f"{cls.base_url}/health")
                if response.status_code == 200:
                    print(f"✅ API 服务器已在后台启动 (端口: {cls.port})，用于测试。")
                    return
            except requests.ConnectionError:
                time.sleep(0.5)
        
        raise RuntimeError("API 服务器在15秒内未能启动。")

    @classmethod
    def tearDownClass(cls):
        """在所有测试结束后，可以考虑如何优雅地停止服务器"""
        # 在实际应用中，需要一种机制来关闭服务器线程。
        # 对于测试，由于线程是守护线程，当主线程结束时它会自动退出。
        print("\n✅ 测试完成。")

    def test_01_comprehensive_lifecycle(self):
        """测试创建两个隧道，并分别用ID和URL来停止"""
        print("\n--- 测试 1: 综合生命周期 (ID与URL删除) ---")
        
        # 1. 创建隧道 A
        print("步骤 1: 创建隧道 A (端口 8888)...")
        create_res_a = requests.post(f"{self.base_url}/tunnels", json={"port": 8888})
        self.assertEqual(create_res_a.status_code, 201)
        tunnel_a_data = create_res_a.json()
        tunnel_a_id = tunnel_a_data["share_token"]
        print(f"✅ 隧道 A 创建成功，ID: {tunnel_a_id}")

        # 2. 创建隧道 B
        print("\n步骤 2: 创建隧道 B (端口 8889)...")
        create_res_b = requests.post(f"{self.base_url}/tunnels", json={"port": 8889})
        self.assertEqual(create_res_b.status_code, 201)
        tunnel_b_data = create_res_b.json()
        tunnel_b_id = tunnel_b_data["share_token"]
        tunnel_b_url = tunnel_b_data["public_url"]
        print(f"✅ 隧道 B 创建成功，ID: {tunnel_b_id}, URL: {tunnel_b_url}")

        # 3. 列出并验证隧道
        print("\n步骤 3: 列出隧道并验证...")
        list_response = requests.get(f"{self.base_url}/tunnels")
        self.assertEqual(list_response.status_code, 200)
        tunnels = list_response.json()
        self.assertTrue(any(t['share_token'] == tunnel_a_id for t in tunnels), "隧道 A 不在列表中")
        self.assertTrue(any(t['share_token'] == tunnel_b_id for t in tunnels), "隧道 B 不在列表中")
        print("✅ 两个隧道都已在列表中。")

        # 4. 通过 ID 停止隧道 A
        stop_identifier_a = tunnel_a_id
        print(f"\n步骤 4: 准备通过 ID 停止隧道 A, 输入条件: '{stop_identifier_a}'")
        stop_response_a = requests.delete(f"{self.base_url}/tunnels/{stop_identifier_a}")
        self.assertEqual(stop_response_a.status_code, 200)
        print("✅ 隧道 A 已成功停止。")

        # 5. 通过 URL 停止隧道 B
        stop_identifier_b = tunnel_b_url
        print(f"\n步骤 5: 准备通过 URL 停止隧道 B, 输入条件: '{stop_identifier_b}'")
        stop_response_b = requests.delete(f"{self.base_url}/tunnels/{stop_identifier_b}")
        self.assertEqual(stop_response_b.status_code, 200)
        print("✅ 隧道 B 已成功停止。")
        
        # 6. 最终验证
        print("\n步骤 6: 最终验证隧道列表...")
        final_list_response = requests.get(f"{self.base_url}/tunnels")
        self.assertEqual(final_list_response.status_code, 200)
        final_tunnels = final_list_response.json()
        self.assertFalse(any(t['share_token'] == tunnel_a_id for t in final_tunnels), "隧道 A 未被移除")
        self.assertFalse(any(t['share_token'] == tunnel_b_id for t in final_tunnels), "隧道 B 未被移除")
        print("✅ 两个隧道都已成功从列表中移除。")

    def test_02_error_handling(self):
        """测试API的错误处理能力"""
        print("\n--- 测试 2: 错误处理 ---")
        
        # 1. 无效的创建请求 (缺少 port)
        print("步骤 1: 测试无效的创建请求...")
        bad_create_response = requests.post(f"{self.base_url}/tunnels", json={"host": "localhost"})
        self.assertEqual(bad_create_response.status_code, 400)
        print("✅ '400 Bad Request' 验证成功。")
        
        # 2. 删除一个不存在的隧道
        print("\n步骤 2: 测试删除不存在的隧道...")
        non_existent_id = "non_existent_tunnel_123"
        bad_delete_response = requests.delete(f"{self.base_url}/tunnels/{non_existent_id}")
        self.assertEqual(bad_delete_response.status_code, 404)
        print("✅ '404 Not Found' 验证成功。")

if __name__ == '__main__':
    unittest.main()
