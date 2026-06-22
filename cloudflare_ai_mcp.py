#!/usr/bin/env python3
"""MCP Server for Cloudflare Workers AI"""
import os, json, sys
from mcp.server.fastmcp import FastMCP
import httpx

import json, os
CF_CONFIG = os.path.join(os.path.dirname(__file__), '.cloudflare_config.json')
if os.path.exists(CF_CONFIG):
    with open(CF_CONFIG) as f:
        cfg = json.load(f)
    CF_ACCOUNT_ID = cfg.get('account_id', '')
    CF_API_TOKEN = cfg.get('api_token', '')
else:
    CF_ACCOUNT_ID = os.environ.get('CF_ACCOUNT_ID', '')
    CF_API_TOKEN = os.environ.get('CF_API_TOKEN', '')
if not CF_ACCOUNT_ID or not CF_API_TOKEN:
    print("ERROR: Cloudflare credentials not found. Create .cloudflare_config.json or set CF_ACCOUNT_ID/CF_API_TOKEN env vars.", file=__import__('sys').stderr)
    __import__('sys').exit(1)
BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run"

mcp = FastMCP("Cloudflare Workers AI")

@mcp.tool()
async def run_model(model: str = "@cf/meta/llama-3.2-3b-instruct", messages: list = [], max_tokens: int = 1024, temperature: float = 0.7) -> str:
    """Run a Cloudflare Workers AI model. Args: model (default: llama-3.2-3b), messages list like [{'role':'user','content':'hi'}], max_tokens, temperature"""
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{BASE_URL}/{model}",
            headers={"Authorization": f"Bearer {CF_API_TOKEN}", "Content-Type": "application/json"},
            json={"messages": messages, "max_tokens": max_tokens, "temperature": temperature, "stream": False}
        )
        data = resp.json()
        if not data.get("success"):
            return f"Error: {data.get('errors', data)}"
        return data["result"]["response"]

@mcp.tool()
async def list_models() -> str:
    """List available Cloudflare Workers AI models"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/models/search?per_page=50",
            headers={"Authorization": f"Bearer {CF_API_TOKEN}"}
        )
        data = resp.json()
        if not data.get("success"):
            return f"Error: {data.get('errors', data)}"
        models = [m["name"] for m in data["result"]]
        return json.dumps(models, indent=2)

@mcp.tool()
async def text_to_image(prompt: str, model: str = "@cf/black-forest-labs/flux-1-schnell") -> str:
    """Generate an image using Cloudflare Workers AI text-to-image models"""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{BASE_URL}/{model}",
            headers={"Authorization": f"Bearer {CF_API_TOKEN}", "Content-Type": "application/json"},
            json={"prompt": prompt}
        )
        data = resp.json()
        if not data.get("success"):
            return f"Error: {data.get('errors', data)}"
        result = data["result"]
        if "image" in result:
            return f"Base64 image generated ({len(result['image'])} chars). Use data:image/png;base64,{result['image']}"
        return json.dumps(result, indent=2)

if __name__ == "__main__":
    mcp.run(transport="stdio")
