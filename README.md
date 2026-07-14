# DeepSeek MCP Server

> A small, clean [Model Context Protocol](https://modelcontextprotocol.io) server that connects any MCP client — Claude Desktop, Cursor, Cline, Cowork — to the **DeepSeek API**, including **DeepSeek-R1** reasoning with a visible chain-of-thought.

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![MCP](https://img.shields.io/badge/MCP-compatible-6E56CF.svg)

One Python file, four tools, no framework lock-in. Bring your own DeepSeek key and you get fast V3 generation, multi-turn chat, and R1 deep reasoning that shows its work — straight from your assistant.

## ✨ Tools

| Tool | What it does |
|------|--------------|
| `deepseek_generate` | Single-turn text with DeepSeek-V3 (system instruction, temperature, JSON mode) |
| `deepseek_chat` | Multi-turn conversation; switch to `deepseek-reasoner` for step-by-step thinking |
| `deepseek_reason` | Hard problems with DeepSeek-R1 — returns the reasoning trace **and** the answer |
| `deepseek_list_models` | List models available to your key |

## 🚀 Quick start

### Option A — one-click (Windows, Claude Desktop)

```powershell
# in the repo folder, right-click install.ps1 -> "Run with PowerShell"
./install.ps1
```

It asks for your API key, installs dependencies, and wires up Claude Desktop. Restart Claude and you're done.

### Option B — manual (any OS / any MCP client)

```bash
git clone https://github.com/shenzhun/deepseek-mcp-server.git
cd deepseek-mcp-server
pip install -r requirements.txt
export DEEPSEEK_API_KEY="your-api-key"     # Windows: setx DEEPSEEK_API_KEY "your-api-key"
python deepseek_mcp.py
```

Get an API key at <https://platform.deepseek.com/api_keys>. DeepSeek's endpoint is OpenAI-compatible.

## 🔌 Add to your MCP client

Copy `config.example.json` and drop the server block into your client config,
replacing the placeholder key:

```json
{
  "mcpServers": {
    "deepseek": {
      "command": "python",
      "args": ["/absolute/path/to/deepseek_mcp.py"],
      "env": { "DEEPSEEK_API_KEY": "YOUR_DEEPSEEK_API_KEY_HERE" }
    }
  }
}
```

## 💬 Usage examples

- "Use deepseek to draft a product update in Chinese."
- "Ask deepseek_reason to solve this logic puzzle and show its reasoning."
- "Use deepseek_chat to continue our debugging conversation."

## 🔐 Security

- The key is read from the `DEEPSEEK_API_KEY` environment variable — **never hard-code it**.
- `config.json` and `.env` are git-ignored so a real key can't be committed by accident.
- Rotate your key in the [DeepSeek console](https://platform.deepseek.com/api_keys) if it is ever exposed.

## 🛠️ Development

```bash
pip install -r requirements.txt
python -c "import deepseek_mcp; print(deepseek_mcp.mcp.name)"   # smoke test
```

Single-file server (`deepseek_mcp.py`): typed Pydantic inputs, consistent error
handling, MCP tool annotations. A sibling of [gemini-mcp-server](https://github.com/shenzhun/gemini-mcp-server) — same clean shape, different provider.

## 📄 License

MIT © shenzhun (深准). Contributions welcome — open an issue or PR.
