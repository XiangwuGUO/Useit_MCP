# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a distributed MCP (Model Context Protocol) system that provides a unified gateway for managing multiple MCP servers. The system supports both local development and distributed deployment using FRP (Fast Reverse Proxy) tunnels.

**Core Architecture:**
- `mcp-client/`: Unified API gateway that manages connections to multiple MCP servers
- `mcp-server/`: Collection of MCP server implementations (filesystem, audio processing, web search)
- FRP integration for remote deployment across networks

## Development Commands

### Server Management
```bash
# Start all MCP servers locally
./start_simple_servers.sh start

# Start MCP servers with FRP tunnels for remote access
./start_simple_servers.sh start-frp

# Start the unified API gateway (run in separate terminal)
cd mcp-client && python server.py

# Check server status
./start_simple_servers.sh status

# Stop all servers
./start_simple_servers.sh stop

# View logs
./start_simple_servers.sh logs

# List available servers
./start_simple_servers.sh list
```

### Single Server Testing
```bash
# Start individual servers for testing
./start_simple_servers.sh single filesystem
./start_simple_servers.sh single audio_slicer
./start_simple_servers.sh single web_search

# Start single server with FRP tunnel
./start_simple_servers.sh single-frp filesystem
```

### Testing
```bash
# Run system integration tests
python test_system.py

# Quick functionality test
python quick_test.py

# Basic connectivity test
python basic_test.py

# Audio server specific test
cd mcp-server/official_server/audio_slicer && python test_audio_server.py
```

### Dependencies
```bash
# Install MCP client dependencies
cd mcp-client && pip install -r requirements.txt

# Install MCP server dependencies  
cd mcp-server && pip install -r requirements.txt

# Install audio processing dependencies
cd mcp-server/official_server/audio_slicer && pip install -r requirements.txt
```

## Architecture Details

### Core Components

**1. MCP Gateway Client (`mcp-client/`)**
- `server.py`: FastAPI-based unified API gateway
- `core/client_manager.py`: Manages connections to MCP servers
- `core/task_executor.py`: Intelligent task execution using Claude API
- `core/api_models.py`: Pydantic models for API requests/responses
- Port: 8080

**2. MCP Server Collection (`mcp-server/`)**
- `simple_launcher.py`: Main server launcher with optional FRP support
- `simple_frp_registry.py`: FRP tunnel creation and registration
- `official_server/`: Standard MCP server implementations
  - `filesystem/`: File operations (port 8003)
  - `audio_slicer/`: Audio processing (port 8002) 
  - `web_search/`: Web search functionality (port 8004)

### Deployment Modes

**Local Development Mode:**
- All components run on same machine
- Communication via localhost
- Use: `./start_simple_servers.sh start`

**Distributed FRP Mode:**
- Client machines run MCP servers
- Server machine runs MCP gateway
- FRP tunnels enable cross-network communication
- Use: `./start_simple_servers.sh start-frp`

### Key API Endpoints

```
GET  /health              # System health check
GET  /stats               # System statistics  
GET  /clients             # List registered MCP servers
POST /clients             # Add new MCP server
POST /servers/register    # Register server (used by FRP)
GET  /tools               # List all available tools
POST /tools/call          # Call specific tool
POST /tools/find          # Find and call tool
POST /tasks/execute       # Execute intelligent task
```

## Configuration

### Environment Variables
```bash
# Gateway configuration
export MCP_GATEWAY_PORT=8080
export LOG_LEVEL=INFO

# FRP mode configuration
export MCP_CLIENT_URL="http://your-server:8080"

# Intelligent task execution (optional)
export ANTHROPIC_API_KEY="your-api-key"
export CLAUDE_MODEL="claude-3-sonnet-20240229"
```

### Configuration Files
- `mcp-client/config/settings.py`: Gateway server settings
- `mcp-server/servers_config.yaml`: Custom server definitions

## Testing Strategy

The system includes multiple test files:
- `test_system.py`: End-to-end system testing
- `quick_test.py`: Quick functionality verification  
- `basic_test.py`: Basic connectivity tests
- Individual server tests in respective directories

## Important Notes

- This is a defensive security and MCP development workspace
- The Python SDK is located in `../../python-sdk` and referenced as an editable dependency
- FRP functionality uses `useit.run` as the tunnel service
- All servers support both stdio and streamable-http transports
- The system automatically handles port allocation starting from 8002
- Logs are centralized in the `logs/` directory