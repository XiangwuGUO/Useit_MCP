# 🚀 FRP隧道工具

一个简化的FRP隧道工具，现在提供命令行管理和API服务两种方式，可以快速将本地服务发布到公网。

## 🏛️ 项目核心功能

1.  **命令行管理 (`frp_tunnel.py`)**:
    *   `python frp_tunnel.py start <port>`: 启动一个新隧道。
    *   `python frp_tunnel.py list`: 列出所有正在运行的隧道。
    *   `python frp_tunnel.py stop <id>`: 停止一个隧道。

2.  **API 服务 (`api_server.py`)**:
    *   提供 RESTful API 来动态管理隧道。
    *   `python api_server.py`: 启动 API 服务器 (默认监听 `http://127.0.0.1:5000`)。

3.  **Web 服务器集成 (`web_server.py`)**:
    *   一个简单的 Web 服务器，可以一键启动并将 `index.html` 通过隧道发布出去。

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. (可选) 启动 API 服务

如果您想通过 API 来管理隧道，请运行：
```bash
python api_server.py
```

### 3. (可选) 运行 API 测试

要验证 API 服务是否正常工作，请运行：
```bash
python test_api.py
```

---

## 📖 API 接口文档

API 服务器基地址: `http://127.0.0.1:5000`

### 1. 创建新隧道

-   **Endpoint**: `POST /tunnels`
-   **功能**: 为本地服务创建一个新的公网隧道。

-   **输入 (Request Body)**:
    ```json
    {
        "port": 8080,
        "host": "127.0.0.1"
    }
    ```
    -   `port` (必填): 本地服务的端口号。
    -   `host` (可选): 本地服务的地址，默认为 `127.0.0.1`。

-   **输出 (Response Body)**:
    -   **成功 (201 Created)**:
        ```json
        {
            "share_token": "gradio_1678886400123_a1b2",
            "local_port": 8080,
            "local_host": "127.0.0.1",
            "public_url": "https://random-name.useit.run",
            "pid": 12345,
            "log_file": "E:\\Workspace\\tunnel\\logs\\gradio_1678886400123_a1b2.log"
        }
        ```

### 2. 列出所有隧道

-   **Endpoint**: `GET /tunnels`
-   **功能**: 获取当前所有正在运行的隧道的列表。

-   **输入**: 无

-   **输出 (Response Body)**:
    -   **成功 (200 OK)**:
        ```json
        [
            {
                "share_token": "gradio_1678886400123_a1b2",
                "local_port": 8080,
                "local_host": "127.0.0.1",
                "public_url": "https://random-name.useit.run",
                "pid": 12345,
                "log_file": "..."
            },
            {
                "share_token": "gradio_1678886400456_c3d4",
                "local_port": 9000,
                "local_host": "127.0.0.1",
                "public_url": "https://another-name.useit.run",
                "pid": 54321,
                "log_file": "..."
            }
        ]
        ```

### 3. 停止一个隧道

-   **Endpoint**: `DELETE /tunnels/<identifier>`
-   **功能**: 停止一个正在运行的隧道。

-   **输入 (URL Path)**:
    -   `identifier` (必填): 您要停止的隧道。**既可以是隧道的 `share_token` (ID)，也可以是它的 `public_url` (公网地址)**。
    -   示例 1 (通过ID): `DELETE /tunnels/gradio_1678886400123_a1b2`
    -   示例 2 (通过URL): `DELETE /tunnels/https://random-name.useit.run`

-   **输出 (Response Body)**:
    -   **成功 (200 OK)**:
        ```json
        {
            "message": "隧道 'gradio_1678886400123_a1b2' 已成功停止"
        }
        ```
    -   **失败 (404 Not Found)**:
        ```json
        {
            "error": "未找到ID或URL为 '...' 的隧道"
        }
        ```