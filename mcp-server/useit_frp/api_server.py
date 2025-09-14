from flask import Flask, request, jsonify
from frp_tunnel import FrpTunnel, TunnelManager, CURRENT_DIR

app = Flask(__name__)
manager = TunnelManager(CURRENT_DIR / "tunnels.json")

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({"status": "ok"}), 200

@app.route('/tunnels', methods=['POST'])
def create_tunnel_api():
    """
    创建一个新的隧道
    请求体 JSON: {"port": <int>, "host": <str, optional>}
    """
    if not request.json or 'port' not in request.json:
        return jsonify({"error": "请求体必须是包含 'port' 的JSON"}), 400

    port = request.json['port']
    host = request.json.get('host', '127.0.0.1')

    try:
        tunnel = FrpTunnel(port, host, manager=manager)
        public_url = tunnel.start_tunnel()
        
        if public_url:
            tunnel_info = manager.get_tunnel(tunnel.share_token)
            return jsonify(tunnel_info), 201
        else:
            return jsonify({"error": "创建隧道失败，请查看服务器日志"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/tunnels', methods=['GET'])
def list_tunnels_api():
    """列出所有正在运行的隧道"""
    tunnels = manager.get_all_tunnels()
    return jsonify(tunnels)

@app.route('/tunnels/<path:identifier>', methods=['DELETE'])
def stop_tunnel_api(identifier):
    """
    停止一个隧道
    可以通过隧道ID或公网URL来指定要停止的隧道
    """
    # 优先尝试通过ID查找
    tunnel_info = manager.get_tunnel(identifier)
    
    # 如果ID找不到，再尝试通过URL查找
    if not tunnel_info:
        tunnel_info = manager.find_tunnel_by_url(identifier)

    if not tunnel_info:
        return jsonify({"error": f"未找到ID或URL为 '{identifier}' 的隧道"}), 404
    
    tunnel_id = tunnel_info["share_token"]
    manager.stop_tunnel(tunnel_id)
    return jsonify({"message": f"隧道 '{tunnel_id}' 已成功停止"}), 200

if __name__ == '__main__':
    print("🚀 启动隧道 API 服务器...")
    print("🔗 服务地址: http://127.0.0.1:5888")
    print("📖 API 文档:")
    print("   - POST /tunnels   (创建隧道, body: {'port': 8000, 'host': '127.0.0.1'})")
    print("   - GET /tunnels    (列出所有隧道)")
    print("   - DELETE /tunnels/<id> (停止隧道)")
    print("   - DELETE /tunnels/<url> (通过URL停止隧道)")
    app.run(host='0.0.0.0', port=5888)
