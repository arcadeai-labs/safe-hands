"""Drive server.py through a real MCP client over stdio, the way an agent would, and assert the
governance decisions. This is the end-to-end check; server.py --smoke calls the functions directly.

    python mcp_client_check.py
"""
import asyncio, json, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import sensor


async def main():
    sensor.write(False)
    async with stdio_client(StdioServerParameters(command=sys.executable, args=["server.py"])) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = [t.name for t in (await s.list_tools()).tools]
            assert "human_presence" not in tools and not any("sensor" in t for t in tools), tools
            async def call(name, **kw):
                res = await s.call_tool(name, kw)
                d = json.loads(res.content[0].text)
                print(f"  {name:<15} {json.dumps(kw):<50} -> {d.get('status', 'OK'):<7} {d.get('law', d.get('message', ''))}")
                return d
            print("tools:", ", ".join(tools))
            assert (await call("move_joint", joint="j1", target_degrees=30))["status"] == "DENIED"          # no principal
            await call("authenticate", token="tok-bob")
            assert (await call("move_joint", joint="j1", target_degrees=30))["status"] == "OK"
            d = await call("move_joint", joint="j1", target_degrees=175);  assert d["status"] == "DENIED" and "Third" in d["law"]
            d = await call("move_joint", joint="j1", target_degrees=-175); assert d["status"] == "DENIED" and "Third" in d["law"]
            d = await call("move_joint", joint="safety_engaged", target_degrees=0); assert d["status"] == "DENIED"
            d = await call("disable_safety");  assert d["status"] == "DENIED" and "Second" in d["law"]     # no grant
            await call("authenticate", token="tok-alice")
            d = await call("disable_safety");  assert d["status"] == "DENIED" and "First" in d["law"]      # grant overridden
            sensor.write(True); print("  [sensor] human enters the cell")
            d = await call("move_joint", joint="j2", target_degrees=20, speed_cm_s=90); assert d["status"] == "DENIED" and "First" in d["law"]
            d = await call("move_joint", joint="j2", target_degrees=20, speed_cm_s=10); assert d["status"] == "OK"
            sensor.clear(); print("  [sensor] offline: fail closed")
            d = await call("move_joint", joint="j2", target_degrees=20, speed_cm_s=90); assert d["status"] == "DENIED" and "First" in d["law"]
            audit = json.loads((await s.call_tool("audit", {})).content[0].text)
            assert len(audit) >= 9 and all("law" in a for a in audit)
    sensor.write(False)
    print("MCP CLIENT CHECK: PASS")


if __name__ == "__main__":
    asyncio.run(main())
